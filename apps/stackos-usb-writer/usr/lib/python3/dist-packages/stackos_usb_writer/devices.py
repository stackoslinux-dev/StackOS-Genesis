"""Read-only block-device discovery and safety classification."""

from __future__ import annotations

from dataclasses import dataclass
import json
import hashlib
import subprocess
from typing import Any, Iterable


PROTECTED_MOUNTPOINTS = {"/", "/boot", "/boot/efi", "/home", "/usr", "/var", "/etc", "/opt", "[SWAP]"}


@dataclass(frozen=True, slots=True)
class UsbDevice:
    path: str
    model: str
    vendor: str
    size: int
    transport: str
    removable: bool
    protected: bool
    protection_reason: str = ""
    serial: str = ""
    wwn: str = ""
    major_minor: str = ""

    @property
    def identity(self) -> str:
        return hashlib.sha256(json.dumps([self.path,self.model,self.vendor,self.size,self.serial,self.wwn,self.major_minor]).encode()).hexdigest()

    @property
    def display_name(self) -> str:
        identity = " ".join(part for part in (self.vendor, self.model) if part)
        return identity or self.path


def _mountpoints(node: dict[str, Any]) -> Iterable[str]:
    value = node.get("mountpoints")
    if isinstance(value, list):
        yield from (str(item) for item in value if item)
    elif node.get("mountpoint"):
        yield str(node["mountpoint"])

    for child in node.get("children") or []:
        yield from _mountpoints(child)


def _has_protected_mount(node: dict[str, Any]) -> bool:
    return any(p in PROTECTED_MOUNTPOINTS or any(p.startswith(root+"/") for root in ("/boot","/home","/usr","/var","/etc","/opt")) for p in _mountpoints(node))


def parse_lsblk(payload: str) -> list[UsbDevice]:
    """Convert lsblk JSON into a conservative list of USB candidates."""
    data = json.loads(payload)
    devices: list[UsbDevice] = []

    all_nodes=[]
    def visit(node):
        all_nodes.append(node)
        for child in node.get('children') or []:visit(child)
    for node in data.get('blockdevices',[]):visit(node)
    def descendants(node):
        seen=set();pending=[node]
        while pending:
            current=pending.pop();path=current.get('path','')
            if path in seen:continue
            seen.add(path);yield current
            pending.extend(current.get('children') or [])
            pending.extend(n for n in all_nodes if n.get('pkname') in (path,path.rsplit('/',1)[-1]))
    for node in all_nodes:
        if node.get("type") != "disk":
            continue

        transport = str(node.get("tran") or "").lower()
        removable = str(node.get("rm")).lower() in ("true","1")
        if transport != "usb" and not removable:
            continue

        protected = any(_has_protected_mount(n) for n in descendants(node)) or str(node.get("ro")).lower() in ("true","1")
        reason = "partição crítica em uso ou dispositivo somente leitura" if protected else ""
        path = str(node.get("path") or "")
        if not path.startswith("/dev/"):
            protected = True
            reason = "caminho de dispositivo inválido"

        if int(node.get("size") or 0)<=0:
            protected=True;reason="capacidade inválida ou mídia ausente"

        devices.append(
            UsbDevice(
                path=path,
                model=str(node.get("model") or "").strip(),
                vendor=str(node.get("vendor") or "").strip(),
                size=int(node.get("size") or 0),
                transport=transport,
                removable=removable,
                protected=protected,
                protection_reason=reason,
                serial=str(node.get("serial") or ""),wwn=str(node.get("wwn") or ""),major_minor=str(node.get("maj:min") or ""),
            )
        )

    return list({d.path:d for d in devices}.values())


def discover_usb_devices() -> list[UsbDevice]:
    command = [
        "lsblk",
        "--bytes",
        "--json",
        "--output",
        "PATH,TYPE,SIZE,MODEL,VENDOR,TRAN,RM,RO,PKNAME,MAJ:MIN,SERIAL,WWN,MOUNTPOINTS",
    ]
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return parse_lsblk(result.stdout)


def find_device(path: str) -> UsbDevice | None:
    return next((item for item in discover_usb_devices() if item.path == path), None)


def format_size(size: int) -> str:
    value = float(size)
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if value < 1000 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1000
    return f"{size} B"

"""Read-only block-device discovery and safety classification."""

from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
from typing import Any, Iterable


PROTECTED_MOUNTPOINTS = {"/", "/boot", "/boot/efi"}


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
    return bool(PROTECTED_MOUNTPOINTS.intersection(_mountpoints(node)))


def parse_lsblk(payload: str) -> list[UsbDevice]:
    """Convert lsblk JSON into a conservative list of USB candidates."""
    data = json.loads(payload)
    devices: list[UsbDevice] = []

    for node in data.get("blockdevices", []):
        if node.get("type") != "disk":
            continue

        transport = str(node.get("tran") or "").lower()
        removable = bool(node.get("rm"))
        if transport != "usb" and not removable:
            continue

        protected = _has_protected_mount(node)
        reason = "contém uma partição do sistema em uso" if protected else ""
        path = str(node.get("path") or "")
        if not path.startswith("/dev/"):
            protected = True
            reason = "caminho de dispositivo inválido"

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
            )
        )

    return devices


def discover_usb_devices() -> list[UsbDevice]:
    command = [
        "lsblk",
        "--bytes",
        "--json",
        "--output",
        "PATH,TYPE,SIZE,MODEL,VENDOR,TRAN,RM,MOUNTPOINTS",
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

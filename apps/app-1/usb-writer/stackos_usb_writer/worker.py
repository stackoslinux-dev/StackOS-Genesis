"""Privileged command-line worker invoked through pkexec."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from .devices import discover_usb_devices
from .operations import CHUNK_SIZE, compare_stream_prefix, validate_image


def emit(event: str, **values: object) -> None:
    print(json.dumps({"event": event, **values}), flush=True)


def allowed_device(path: str) -> bool:
    real = str(Path(path).resolve())
    return any(
        device.path == real and not device.protected
        for device in discover_usb_devices()
    )


def require_safe_device(path: str) -> str:
    real = str(Path(path).resolve())
    if not real.startswith("/dev/") or not allowed_device(real):
        raise PermissionError("Dispositivo recusado pela verificação de segurança.")
    return real


def unmount_children(device: str) -> None:
    result = subprocess.run(
        ["lsblk", "--json", "--output", "PATH,MOUNTPOINTS", device],
        check=True,
        capture_output=True,
        text=True,
    )
    nodes = json.loads(result.stdout).get("blockdevices", [])
    for child in nodes[0].get("children", []) if nodes else []:
        if any(child.get("mountpoints") or []):
            subprocess.run(
                ["udisksctl", "unmount", "--block-device", child["path"]],
                check=True,
                capture_output=True,
                text=True,
            )


def write_image(image_path: str, device_path: str, verify: bool) -> None:
    image = validate_image(image_path)
    device = require_safe_device(device_path)
    capacity = int(
        subprocess.run(
            ["blockdev", "--getsize64", device],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    if image.stat().st_size > capacity:
        raise ValueError("A imagem é maior que o dispositivo.")

    unmount_children(device)
    total = image.stat().st_size
    processed = 0
    started = time.monotonic()
    emit("stage", name="writing", total=total)
    with image.open("rb", buffering=0) as source, open(
        device, "wb", buffering=0
    ) as target:
        while chunk := source.read(CHUNK_SIZE):
            target.write(chunk)
            processed += len(chunk)
            elapsed = max(time.monotonic() - started, 0.001)
            emit(
                "progress",
                current=processed,
                total=total,
                speed=int(processed / elapsed),
            )
        target.flush()
        os.fsync(target.fileno())

    subprocess.run(["blockdev", "--rereadpt", device], check=False)
    if verify:
        emit("stage", name="verifying", total=total)

        def report(current: int, maximum: int) -> None:
            emit("progress", current=current, total=maximum, speed=0)

        if not compare_stream_prefix(str(image), device, report):
            raise IOError("A verificação encontrou diferenças na gravação.")
    emit("complete", device=device)


def erase_device(device_path: str, filesystem: str, label: str) -> None:
    device = require_safe_device(device_path)
    if filesystem not in {"fat32", "exfat", "ntfs"}:
        raise ValueError("Sistema de arquivos não permitido.")
    if len(label) > 11:
        raise ValueError("O rótulo deve ter no máximo 11 caracteres.")

    unmount_children(device)
    emit("stage", name="formatting", total=1)
    subprocess.run(["wipefs", "--all", device], check=True)
    subprocess.run(
        ["parted", "--script", device, "mklabel", "gpt", "mkpart", "primary", "1MiB", "100%"],
        check=True,
    )
    subprocess.run(["udevadm", "settle"], check=True)
    partition = f"{device}p1" if device[-1].isdigit() else f"{device}1"
    command = {
        "fat32": ["mkfs.vfat", "-F", "32", "-n", label, partition],
        "exfat": ["mkfs.exfat", "-n", label, partition],
        "ntfs": ["mkfs.ntfs", "-F", "-L", label, partition],
    }[filesystem]
    subprocess.run(command, check=True)
    emit("progress", current=1, total=1, speed=0)
    emit("complete", device=device)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="stackos-usb-writer-worker")
    sub = result.add_subparsers(dest="operation", required=True)
    write = sub.add_parser("write")
    write.add_argument("--image", required=True)
    write.add_argument("--device", required=True)
    write.add_argument("--verify", action="store_true")
    erase = sub.add_parser("format")
    erase.add_argument("--device", required=True)
    erase.add_argument("--filesystem", choices=("fat32", "exfat", "ntfs"), required=True)
    erase.add_argument("--label", default="STACKOS")
    return result


def main() -> int:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        args = parser().parse_args()
        if args.operation == "write":
            write_image(args.image, args.device, args.verify)
        else:
            erase_device(args.device, args.filesystem, args.label)
        return 0
    except Exception as error:
        emit("error", message=str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

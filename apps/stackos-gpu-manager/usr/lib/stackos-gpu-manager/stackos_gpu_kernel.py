#!/usr/bin/env python3

from pathlib import Path
import platform


DEFAULT_DRM_PATH = "/sys/class/drm"
DEFAULT_PCI_PATH = "/sys/bus/pci/devices"


def read_text(path):
    try:
        return Path(path).read_text(
            encoding="utf-8"
        ).strip()
    except (OSError, UnicodeError):
        return None


def resolve_name(path):
    try:
        return Path(path).resolve(
            strict=True
        ).name
    except OSError:
        return None


def is_display_controller(device):
    class_code = read_text(
        Path(device) / "class"
    )

    if not class_code:
        return False

    return class_code.lower().startswith(
        "0x03"
    )


def find_drm_cards(
    device,
    drm_root,
):
    result = []

    try:
        target = Path(device).resolve(
            strict=True
        )
    except OSError:
        return result

    for card in sorted(
        Path(drm_root).glob("card[0-9]*")
    ):
        suffix = card.name[4:]

        if not suffix.isdigit():
            continue

        try:
            card_device = (
                card / "device"
            ).resolve(strict=True)
        except OSError:
            continue

        if card_device == target:
            result.append(card.name)

    return result


def find_render_nodes(
    device,
    drm_root,
):
    result = []

    try:
        target = Path(device).resolve(
            strict=True
        )
    except OSError:
        return result

    for node in sorted(
        Path(drm_root).glob("renderD*")
    ):
        try:
            node_device = (
                node / "device"
            ).resolve(strict=True)
        except OSError:
            continue

        if node_device == target:
            result.append(
                f"/dev/dri/{node.name}"
            )

    return result


def kernel_gpu_state(
    drm_path=DEFAULT_DRM_PATH,
    pci_path=DEFAULT_PCI_PATH,
):
    drm_root = Path(drm_path)
    pci_root = Path(pci_path)

    result = []

    try:
        pci_devices = sorted(
            pci_root.iterdir()
        )
    except OSError:
        return result

    for device in pci_devices:
        if not is_display_controller(
            device
        ):
            continue

        pci_address = device.name

        cards = find_drm_cards(
            device,
            drm_root,
        )

        render_nodes = find_render_nodes(
            device,
            drm_root,
        )

        gpu = {
            "card": (
                cards[0]
                if cards
                else None
            ),
            "cards": cards,
            "pci_address": pci_address,
            "vendor_id": read_text(
                device / "vendor"
            ),
            "device_id": read_text(
                device / "device"
            ),
            "subsystem_vendor_id": read_text(
                device / "subsystem_vendor"
            ),
            "subsystem_device_id": read_text(
                device / "subsystem_device"
            ),
            "revision": read_text(
                device / "revision"
            ),
            "class": read_text(
                device / "class"
            ),
            "driver": resolve_name(
                device / "driver"
            ),
            "power_state": read_text(
                device / "power_state"
            ),
            "render_nodes": render_nodes,
        }

        result.append(gpu)

    return result


def kernel_state(
    drm_path=DEFAULT_DRM_PATH,
    pci_path=DEFAULT_PCI_PATH,
):
    return {
        "kernel_release": platform.release(),
        "machine": platform.machine(),
        "gpus": kernel_gpu_state(
            drm_path=drm_path,
            pci_path=pci_path,
        ),
    }


if __name__ == "__main__":
    import json

    print(
        json.dumps(
            kernel_state(),
            indent=2,
            ensure_ascii=False,
        )
    )

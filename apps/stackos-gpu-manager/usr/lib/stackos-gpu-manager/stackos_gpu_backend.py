#!/usr/bin/env python3

from pathlib import Path
import subprocess
import configparser
import json
import re


VENDORS = {
    "0x1002": "AMD",
    "0x10de": "NVIDIA",
    "0x8086": "Intel",
}


def run(cmd):
    try:
        return subprocess.check_output(
            cmd,
            text=True,
            stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def read_file(path):
    try:
        return Path(path).read_text().strip()
    except Exception:
        return None


def pci_name(address):
    if not address:
        return None

    out = run(["lspci", "-s", address])

    if not out:
        return None

    out = re.sub(
        r"^[0-9a-fA-F:.]+\s+",
        "",
        out
    )

    out = re.sub(
        r"^(VGA compatible controller|3D controller|Display controller):\s*",
        "",
        out
    )

    return out


def detect_gpus():
    gpus = []

    for card in sorted(
        Path("/sys/class/drm").glob("card[0-9]*")
    ):
        # Ignora conectores:
        # card1-DP-1, card1-HDMI-A-1, etc.
        if not card.name[4:].isdigit():
            continue

        device = card / "device"

        if not device.exists():
            continue

        vendor_id = read_file(device / "vendor")
        device_id = read_file(device / "device")

        try:
            driver = (device / "driver").resolve().name
        except Exception:
            driver = None

        try:
            pci_address = device.resolve().name
        except Exception:
            pci_address = None

        render_nodes = []

        drm_dir = device / "drm"

        if drm_dir.exists():
            for node in drm_dir.iterdir():
                if node.name.startswith("renderD"):
                    render_nodes.append(
                        f"/dev/dri/{node.name}"
                    )

        gpus.append({
            "card": f"/dev/dri/{card.name}",
            "render_nodes": sorted(render_nodes),
            "pci_address": pci_address,
            "vendor_id": vendor_id,
            "vendor": VENDORS.get(
                vendor_id,
                "Unknown"
            ),
            "device_id": device_id,
            "driver": driver,
            "name": pci_name(pci_address),
        })

    return gpus


def detect_switcheroo():
    result = {
        "available": False,
        "num_gpus": None,
        "has_dual_gpu": None,
    }

    num = run([
        "busctl",
        "--system",
        "get-property",
        "net.hadess.SwitcherooControl",
        "/net/hadess/SwitcherooControl",
        "net.hadess.SwitcherooControl",
        "NumGPUs"
    ])

    dual = run([
        "busctl",
        "--system",
        "get-property",
        "net.hadess.SwitcherooControl",
        "/net/hadess/SwitcherooControl",
        "net.hadess.SwitcherooControl",
        "HasDualGpu"
    ])

    if num:
        result["available"] = True

        match = re.search(
            r"\b(\d+)$",
            num
        )

        if match:
            result["num_gpus"] = int(
                match.group(1)
            )

    if dual:
        result["available"] = True

        if dual.endswith("true"):
            result["has_dual_gpu"] = True

        elif dual.endswith("false"):
            result["has_dual_gpu"] = False

    return result


def discover_applications():
    system_dir = Path(
        "/usr/share/applications"
    )

    user_dir = (
        Path.home()
        / ".local/share/applications"
    )

    system_files = {
        p.name: p
        for p in system_dir.glob("*.desktop")
    } if system_dir.exists() else {}

    user_files = {
        p.name: p
        for p in user_dir.glob("*.desktop")
    } if user_dir.exists() else {}

    desktop_files = dict(system_files)

    # XDG: arquivo do usuário substitui
    # o arquivo de sistema com mesmo Desktop ID.
    desktop_files.update(user_files)

    apps = []

    for desktop_id, desktop in sorted(
        desktop_files.items()
    ):
        parser = configparser.ConfigParser(
            interpolation=None,
            strict=False
        )

        try:
            parser.read(
                desktop,
                encoding="utf-8"
            )
        except Exception:
            continue

        if "Desktop Entry" not in parser:
            continue

        entry = parser["Desktop Entry"]

        if entry.get(
            "Type",
            ""
        ) != "Application":
            continue

        if entry.get(
            "Hidden",
            "false"
        ).lower() == "true":
            continue

        if entry.get(
            "NoDisplay",
            "false"
        ).lower() == "true":
            continue

        name = entry.get("Name")
        command = entry.get("Exec")

        if not name or not command:
            continue

        is_user_file = (
            desktop_id in user_files
        )

        is_override = (
            desktop_id in user_files
            and desktop_id in system_files
        )

        apps.append({
            "desktop_id": desktop_id,
            "name": name,
            "exec": command,
            "icon": entry.get("Icon"),
            "prefers_non_default_gpu":
                entry.get(
                    "PrefersNonDefaultGPU",
                    "false"
                ).lower() == "true",
            "source":
                "user"
                if is_user_file
                else "system",
            "is_override": is_override,
            "path": str(desktop),
        })

    return apps


def system_state():
    gpus = detect_gpus()
    switcheroo = detect_switcheroo()
    apps = discover_applications()

    return {
        "gpu_count": len(gpus),
        "dual_gpu": len(gpus) > 1,
        "switcheroo": switcheroo,
        "gpus": gpus,
        "applications": apps,
    }


if __name__ == "__main__":
    print(
        json.dumps(
            system_state(),
            indent=2,
            ensure_ascii=False
        )
    )

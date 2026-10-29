#!/usr/bin/env python3

import re
import subprocess


class ResolverError(Exception):
    pass


def switcheroo_devices():
    try:
        out = subprocess.check_output(
            ["switcherooctl", "list"],
            text=True,
            stderr=subprocess.DEVNULL
        )
    except Exception as exc:
        raise ResolverError(
            f"Falha ao executar switcherooctl: {exc}"
        ) from exc

    devices = []
    current = None

    for raw in out.splitlines():
        line = raw.strip()

        if line.startswith("Device:"):
            if current is not None:
                devices.append(current)

            current = {
                "id": int(
                    line.split(":", 1)[1].strip()
                ),
                "name": None,
                "default": False,
                "discrete": False,
                "environment": {},
            }

            continue

        if current is None:
            continue

        if line.startswith("Name:"):
            current["name"] = (
                line.split(":", 1)[1].strip()
            )

        elif line.startswith("Default:"):
            current["default"] = (
                line.split(":", 1)[1].strip()
                == "yes"
            )

        elif line.startswith("Discrete:"):
            current["discrete"] = (
                line.split(":", 1)[1].strip()
                == "yes"
            )

        elif line.startswith("Environment:"):
            env_text = (
                line.split(":", 1)[1].strip()
            )

            for item in env_text.split():
                if "=" not in item:
                    continue

                key, value = item.split("=", 1)
                current["environment"][key] = value

    if current is not None:
        devices.append(current)

    return devices


def normalize_pci_from_dri_prime(value):
    if not value:
        return None

    # Exemplo:
    # pci-0000_03_00_0
    m = re.fullmatch(
        r"pci-([0-9a-fA-F]{4})_"
        r"([0-9a-fA-F]{2})_"
        r"([0-9a-fA-F]{2})_"
        r"([0-7])",
        value
    )

    if not m:
        return None

    return (
        f"{m.group(1)}:"
        f"{m.group(2)}:"
        f"{m.group(3)}."
        f"{m.group(4)}"
    ).lower()


def stable_gpu_id(device):
    dri_prime = (
        device
        .get("environment", {})
        .get("DRI_PRIME")
    )

    pci = normalize_pci_from_dri_prime(
        dri_prime
    )

    if pci:
        return f"pci:{pci}"

    return None


def resolve_selection(selection):
    devices = switcheroo_devices()

    if selection == "role:default":
        matches = [
            device
            for device in devices
            if device.get("default") is True
        ]

        if len(matches) == 1:
            return matches[0]["id"]

        return None

    if selection == "role:discrete":
        matches = [
            device
            for device in devices
            if device.get("discrete") is True
            and device.get("default") is not True
        ]

        if len(matches) == 1:
            return matches[0]["id"]

        return None

    for device in devices:
        stable = stable_gpu_id(device)

        if stable == selection:
            return device["id"]

    return None


if __name__ == "__main__":
    for device in switcheroo_devices():
        print(
            "GPU",
            device["id"],
            "->",
            stable_gpu_id(device),
            "->",
            device["name"]
        )

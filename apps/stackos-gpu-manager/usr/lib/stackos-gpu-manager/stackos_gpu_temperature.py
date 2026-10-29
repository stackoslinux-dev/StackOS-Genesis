#!/usr/bin/env python3

from pathlib import Path
import re
import subprocess


class TemperatureError(Exception):
    pass


def read_text(path):
    try:
        return Path(path).read_text(
            encoding="utf-8"
        ).strip()
    except (OSError, UnicodeError):
        return None


def read_temperature(path):
    raw = read_text(path)

    if raw is None:
        return None

    try:
        value = int(raw)
    except ValueError:
        return None

    return value / 1000.0


def card_pci_address(card):
    try:
        device = (
            card / "device"
        ).resolve(strict=True)
    except OSError:
        return None

    name = device.name

    if ":" not in name or "." not in name:
        return None

    return name


def cpu_package_temperature():
    hwmon_root = Path("/sys/class/hwmon")

    for hwmon in sorted(
        hwmon_root.glob("hwmon*")
    ):
        driver = read_text(
            hwmon / "name"
        )

        if driver != "coretemp":
            continue

        for temp_input in sorted(
            hwmon.glob("temp*_input")
        ):
            stem = temp_input.name[
                :-len("_input")
            ]

            label = read_text(
                hwmon / f"{stem}_label"
            )

            if label != "Package id 0":
                continue

            value = read_temperature(
                temp_input
            )

            if value is None:
                continue

            return {
                "temperature_c": value,
                "driver": driver,
                "label": label,
                "path": str(temp_input),
            }

    return None




def normalize_nvidia_pci_address(value):
    if not value:
        return None

    match = re.fullmatch(
        r"([0-9a-fA-F]{4,8}):"
        r"([0-9a-fA-F]{2}):"
        r"([0-9a-fA-F]{2})\."
        r"([0-9a-fA-F])",
        value.strip(),
    )

    if not match:
        return None

    domain, bus, device, function = (
        match.groups()
    )

    try:
        domain_value = int(domain, 16)
    except ValueError:
        return None

    if domain_value > 0xFFFF:
        return None

    return (
        f"{domain_value:04x}:"
        f"{bus.lower()}:"
        f"{device.lower()}."
        f"{function.lower()}"
    )


def nvidia_smi_temperatures():
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=pci.bus_id,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (
        OSError,
        subprocess.TimeoutExpired,
    ):
        return {}

    if completed.returncode != 0:
        return {}

    result = {}

    for raw_line in completed.stdout.splitlines():
        parts = [
            part.strip()
            for part in raw_line.split(",", 1)
        ]

        if len(parts) != 2:
            continue

        raw_pci, raw_temperature = parts

        pci = normalize_nvidia_pci_address(
            raw_pci
        )

        if pci is None:
            continue

        try:
            temperature = float(
                raw_temperature
            )
        except ValueError:
            continue

        result[pci] = temperature

    return result



def gpu_temperatures():
    result = []

    drm = Path("/sys/class/drm")

    # PRIMEIRA ETAPA:
    # descobrir tudo pelo kernel/sysfs/DRM.
    for card in sorted(
        drm.glob("card[0-9]*")
    ):
        suffix = card.name[4:]

        if not suffix.isdigit():
            continue

        device = card / "device"

        if not device.exists():
            continue

        pci = card_pci_address(card)

        vendor_id = read_text(
            device / "vendor"
        )

        driver_name = None
        driver_link = device / "driver"

        if driver_link.exists():
            try:
                driver_name = (
                    driver_link.resolve().name
                )
            except OSError:
                driver_name = None

        sensors = []

        # Temperatura fornecida pelo kernel.
        for hwmon in sorted(
            device.glob("hwmon/hwmon*")
        ):
            hwmon_driver = read_text(
                hwmon / "name"
            )

            for temp_input in sorted(
                hwmon.glob("temp*_input")
            ):
                stem = temp_input.name[
                    :-len("_input")
                ]

                label = read_text(
                    hwmon / f"{stem}_label"
                )

                value = read_temperature(
                    temp_input
                )

                if value is None:
                    continue

                sensors.append({
                    "sensor": stem,
                    "label": label,
                    "temperature_c": value,
                    "driver": hwmon_driver,
                    "path": str(temp_input),
                    "source": "kernel-hwmon",
                })

        result.append({
            "card": card.name,
            "pci_address": pci,
            "vendor_id": vendor_id,
            "kernel_driver": driver_name,
            "sensors": sensors,
        })

    # SEGUNDA ETAPA:
    # somente GPUs NVIDIA que ficaram sem
    # temperatura do kernel podem precisar
    # do fallback do driver proprietário.
    nvidia_missing = [
        gpu
        for gpu in result
        if (
            not gpu["sensors"]
            and gpu.get("vendor_id") == "0x10de"
            and gpu.get("kernel_driver") == "nvidia"
            and gpu.get("pci_address")
        )
    ]

    if nvidia_missing:
        nvidia_by_pci = (
            nvidia_smi_temperatures()
        )

        for gpu in nvidia_missing:
            pci = gpu["pci_address"]

            if pci not in nvidia_by_pci:
                continue

            gpu["sensors"].append({
                "sensor": "gpu",
                "label": "GPU",
                "temperature_c": (
                    nvidia_by_pci[pci]
                ),
                "driver": "nvidia",
                "path": "nvidia-smi",
                "source": (
                    "nvidia-smi-fallback"
                ),
            })

    return result



if __name__ == "__main__":
    import json

    print(
        json.dumps(
            gpu_temperatures(),
            indent=2,
            ensure_ascii=False,
        )
    )

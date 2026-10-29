#!/usr/bin/env python3

import re
import subprocess

from stackos_gpu_kernel import kernel_gpu_state
from stackos_gpu_temperature import gpu_temperatures


def index_by_pci(items):
    result = {}

    for item in items:
        pci = item.get("pci_address")

        if pci:
            result[pci] = item

    return result


def pci_from_environment(environment):
    if not environment:
        return None

    match = re.search(
        r"DRI_PRIME=pci-"
        r"([0-9a-fA-F]{4})_"
        r"([0-9a-fA-F]{2})_"
        r"([0-9a-fA-F]{2})_"
        r"([0-9a-fA-F])",
        environment,
    )

    if not match:
        return None

    domain, bus, device, function = (
        match.groups()
    )

    return (
        f"{domain.lower()}:"
        f"{bus.lower()}:"
        f"{device.lower()}."
        f"{function.lower()}"
    )


def parse_switcheroo_list(text):
    devices = []
    current = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        if line.startswith("Device:"):
            if current is not None:
                current["pci_address"] = (
                    pci_from_environment(
                        current.get(
                            "environment"
                        )
                    )
                )
                devices.append(current)

            raw_id = line.split(
                ":",
                1,
            )[1].strip()

            try:
                gpu_id = int(raw_id)
            except ValueError:
                gpu_id = raw_id

            current = {
                "gpu_id": gpu_id,
                "name": None,
                "default": False,
                "discrete": False,
                "environment": None,
                "pci_address": None,
            }

            continue

        if current is None:
            continue

        stripped = line.strip()

        if stripped.startswith("Name:"):
            current["name"] = stripped.split(
                ":",
                1,
            )[1].strip()

        elif stripped.startswith("Default:"):
            value = stripped.split(
                ":",
                1,
            )[1].strip().lower()

            current["default"] = (
                value == "yes"
            )

        elif stripped.startswith("Discrete:"):
            value = stripped.split(
                ":",
                1,
            )[1].strip().lower()

            current["discrete"] = (
                value == "yes"
            )

        elif stripped.startswith("Environment:"):
            current["environment"] = (
                stripped.split(
                    ":",
                    1,
                )[1].strip()
            )

    if current is not None:
        current["pci_address"] = (
            pci_from_environment(
                current.get(
                    "environment"
                )
            )
        )
        devices.append(current)

    return devices


def switcheroo_devices():
    try:
        completed = subprocess.run(
            [
                "switcherooctl",
                "list",
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
        return []

    if completed.returncode != 0:
        return []

    return parse_switcheroo_list(
        completed.stdout
    )


def merged_gpu_state():
    kernel_gpus = kernel_gpu_state()
    temperature_gpus = gpu_temperatures()
    switcheroo_gpus = switcheroo_devices()

    temperatures = index_by_pci(
        temperature_gpus
    )

    switcheroo_by_pci = index_by_pci(
        switcheroo_gpus
    )

    # Fallback seguro:
    # se existe exatamente 1 GPU no kernel e
    # exatamente 1 no switcheroo, elas são
    # necessariamente o mesmo dispositivo.
    if (
        len(kernel_gpus) == 1
        and len(switcheroo_gpus) == 1
    ):
        only_kernel_pci = kernel_gpus[
            0
        ].get("pci_address")

        only_switcheroo = (
            switcheroo_gpus[0]
        )

        if (
            only_kernel_pci
            and not only_switcheroo.get(
                "pci_address"
            )
        ):
            switcheroo_by_pci[
                only_kernel_pci
            ] = only_switcheroo

    # Fallback híbrido seguro:
    # depois das associações exatas por PCI, se
    # sobrar exatamente 1 GPU do kernel e exatamente
    # 1 dispositivo switcheroo sem PCI, eles são o
    # único par possível. Não adivinhar se houver
    # qualquer ambiguidade.
    matched_switcheroo_ids = {
        device.get("gpu_id")
        for device in switcheroo_by_pci.values()
    }

    unmatched_kernel_gpus = [
        gpu
        for gpu in kernel_gpus
        if gpu.get("pci_address")
        and gpu.get("pci_address")
        not in switcheroo_by_pci
    ]

    unmatched_switcheroo_gpus = [
        device
        for device in switcheroo_gpus
        if device.get("gpu_id")
        not in matched_switcheroo_ids
    ]

    if (
        len(unmatched_kernel_gpus) == 1
        and len(unmatched_switcheroo_gpus) == 1
        and not unmatched_switcheroo_gpus[
            0
        ].get("pci_address")
    ):
        unmatched_pci = (
            unmatched_kernel_gpus[
                0
            ].get("pci_address")
        )

        if unmatched_pci:
            switcheroo_by_pci[
                unmatched_pci
            ] = unmatched_switcheroo_gpus[0]

    result = []

    for kernel_gpu in kernel_gpus:
        pci = kernel_gpu.get(
            "pci_address"
        )

        temperature = temperatures.get(
            pci
        )

        switcheroo = switcheroo_by_pci.get(
            pci
        )

        merged = dict(kernel_gpu)

        if temperature is None:
            merged[
                "temperature_sensors"
            ] = []

            merged[
                "temperature_source"
            ] = None

        else:
            sensors = temperature.get(
                "sensors",
                [],
            )

            merged[
                "temperature_sensors"
            ] = sensors

            drivers = {
                sensor.get("driver")
                for sensor in sensors
                if sensor.get("driver")
            }

            if len(drivers) == 1:
                merged[
                    "temperature_source"
                ] = next(iter(drivers))
            else:
                merged[
                    "temperature_source"
                ] = None

        if switcheroo is None:
            merged["switcheroo"] = None
        else:
            merged["switcheroo"] = {
                "gpu_id": switcheroo.get(
                    "gpu_id"
                ),
                "name": switcheroo.get(
                    "name"
                ),
                "default": switcheroo.get(
                    "default"
                ),
                "discrete": switcheroo.get(
                    "discrete"
                ),
                "environment": (
                    switcheroo.get(
                        "environment"
                    )
                ),
            }

        result.append(merged)

    return result


if __name__ == "__main__":
    import json

    print(
        json.dumps(
            merged_gpu_state(),
            indent=2,
            ensure_ascii=False,
        )
    )

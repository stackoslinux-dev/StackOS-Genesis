#!/usr/bin/env python3

import subprocess


class LauncherError(Exception):
    pass


def switcheroo_gpu_ids():
    try:
        out = subprocess.check_output(
            ["switcherooctl", "list"],
            text=True,
            stderr=subprocess.DEVNULL
        )
    except Exception as exc:
        raise LauncherError(
            f"switcherooctl indisponível: {exc}"
        ) from exc

    ids = []

    for line in out.splitlines():
        line = line.strip()

        if line.startswith("Device:"):
            value = line.split(":", 1)[1].strip()

            try:
                ids.append(int(value))
            except ValueError:
                continue

    return ids


def build_launch_command(gpu_id, command):
    if not isinstance(gpu_id, int):
        raise LauncherError(
            "GPU ID deve ser inteiro."
        )

    if not isinstance(command, list):
        raise LauncherError(
            "Comando deve ser uma lista."
        )

    if not command:
        raise LauncherError(
            "Comando vazio."
        )

    if not all(
        isinstance(item, str)
        for item in command
    ):
        raise LauncherError(
            "Todos os argumentos devem ser texto."
        )

    return [
        "switcherooctl",
        "launch",
        "-g",
        str(gpu_id),
        *command
    ]


def launch(gpu_id, command, check=False):
    ids = switcheroo_gpu_ids()

    if gpu_id not in ids:
        raise LauncherError(
            f"GPU {gpu_id} não encontrada. "
            f"Disponíveis: {ids}"
        )

    full_command = build_launch_command(
        gpu_id,
        command
    )

    return subprocess.run(
        full_command,
        check=check
    )


if __name__ == "__main__":
    print(
        "GPUs disponíveis:",
        switcheroo_gpu_ids()
    )

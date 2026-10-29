#!/usr/bin/env python3

from pathlib import Path
import shutil
import subprocess

import gi

gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3
except (ValueError, ImportError):
    AyatanaAppIndicator3 = None

from gi.repository import (
    Gtk,
    GLib,
)


POLL_INTERVAL_MS = 2000

PROJECT_ICON_DIR = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "indicator"
)

INSTALLED_ICON_DIR = Path(
    "/usr/share/stackos-gpu-manager/icons"
)


def read_text(path):
    try:
        return Path(path).read_text(
            encoding="utf-8",
            errors="replace",
        ).strip()
    except (
        OSError,
        PermissionError,
    ):
        return None


def normalize_pci_address(value):
    if not value:
        return None

    value = value.strip().lower()

    parts = value.split(":")

    if len(parts) == 3:
        domain, bus, slot_func = parts

        try:
            domain = f"{int(domain, 16):04x}"
            bus = f"{int(bus, 16):02x}"
        except ValueError:
            return value

        return f"{domain}:{bus}:{slot_func}"

    return value


def is_gpu_pci_device(device):
    pci_class = read_text(
        Path(device) / "class"
    )

    return bool(
        pci_class
        and pci_class.lower().startswith("0x03")
    )


def kernel_gpu_usage(
    pci_root="/sys/bus/pci/devices",
):
    """Obtém utilização diretamente do kernel/sysfs.

    Retorna uma lista com GPUs para as quais o kernel
    expõe gpu_busy_percent.

    Existência física continua baseada no PCI classe 0x03.
    """

    root = Path(pci_root)

    if not root.exists():
        return []

    result = []

    try:
        devices = sorted(root.iterdir())
    except OSError:
        return []

    for device in devices:
        if not is_gpu_pci_device(device):
            continue

        pci = normalize_pci_address(
            device.name
        )

        vendor = read_text(
            device / "vendor"
        )

        driver = None

        try:
            driver_link = (
                device / "driver"
            )

            if driver_link.exists():
                driver = (
                    driver_link.resolve().name
                )
        except OSError:
            pass

        busy_file = (
            device / "gpu_busy_percent"
        )

        usage = None

        if busy_file.is_file():
            value = read_text(busy_file)

            try:
                usage = int(value)
            except (
                TypeError,
                ValueError,
            ):
                usage = None

            if usage is not None:
                usage = max(
                    0,
                    min(100, usage),
                )

        runtime_status = read_text(
            device / "power" / "runtime_status"
        )

        result.append({
            "pci_address": pci,
            "vendor_id": vendor,
            "driver": driver,
            "usage_percent": usage,
            "runtime_status": runtime_status,
            "source": (
                "kernel-sysfs"
                if usage is not None
                else None
            ),
        })

    return result


def nvidia_smi_usage():
    """Fallback NVIDIA.

    Nunca é usado para provar existência da GPU.
    Apenas fornece utilização quando o kernel não
    disponibiliza esse dado.
    """

    if shutil.which("nvidia-smi") is None:
        return {}

    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=pci.bus_id,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (
        OSError,
        subprocess.TimeoutExpired,
    ):
        return {}

    if completed.returncode != 0:
        return {}

    result = {}

    for line in completed.stdout.splitlines():
        parts = [
            part.strip()
            for part in line.split(",")
        ]

        if len(parts) != 2:
            continue

        pci = normalize_pci_address(
            parts[0]
        )

        try:
            usage = int(parts[1])
        except ValueError:
            continue

        result[pci] = max(
            0,
            min(100, usage),
        )

    return result


def gpu_usage_state(
    pci_root="/sys/bus/pci/devices",
):
    gpus = kernel_gpu_usage(
        pci_root=pci_root
    )

    need_nvidia_fallback = []

    for gpu in gpus:
        if (
            gpu["usage_percent"] is None
            and gpu["vendor_id"] == "0x10de"
            and gpu["driver"] == "nvidia"
        ):
            # Não acordar uma NVIDIA que o kernel
            # informa estar suspensa.
            if gpu["runtime_status"] == "suspended":
                gpu["usage_percent"] = 0
                gpu["source"] = (
                    "kernel-runtime-suspended"
                )
            else:
                need_nvidia_fallback.append(
                    gpu
                )

    if need_nvidia_fallback:
        fallback = nvidia_smi_usage()

        for gpu in need_nvidia_fallback:
            usage = fallback.get(
                gpu["pci_address"]
            )

            if usage is not None:
                gpu["usage_percent"] = usage
                gpu["source"] = (
                    "nvidia-smi-fallback"
                )

    return gpus


def indicator_level(usage_percent):
    if usage_percent is None:
        return "unavailable"

    if usage_percent <= 45:
        return "green"

    if usage_percent <= 70:
        return "orange"

    return "red"


def highest_usage(gpus):
    available = [
        gpu
        for gpu in gpus
        if gpu.get("usage_percent")
        is not None
    ]

    if not available:
        return None

    return max(
        available,
        key=lambda gpu: gpu["usage_percent"],
    )


def icon_directory():
    if INSTALLED_ICON_DIR.exists():
        return INSTALLED_ICON_DIR

    return PROJECT_ICON_DIR


def icon_path(level):
    return (
        icon_directory()
        / f"stackos-gpu-{level}.svg"
    )


def launch_manager():
    installed = shutil.which(
        "stackos-gpu-manager"
    )

    if installed:
        command = [installed]
    else:
        ui = (
            Path(__file__).resolve().parent
            / "stackos_gpu_ui.py"
        )

        command = [
            "python3",
            str(ui),
        ]

    try:
        subprocess.Popen(
            command,
            start_new_session=True,
        )
    except OSError:
        pass


class GPUIndicator:
    def __init__(self):
        self.indicator = (
            AyatanaAppIndicator3.Indicator.new(
                "stackos-gpu-monitor",
                str(
                    icon_path(
                        "unavailable"
                    )
                ),
                AyatanaAppIndicator3
                .IndicatorCategory
                .HARDWARE,
            )
        )

        self.indicator.set_status(
            AyatanaAppIndicator3
            .IndicatorStatus
            .ACTIVE
        )

        self.menu = Gtk.Menu()

        self.usage_item = Gtk.MenuItem(
            label="Uso da GPU: verificando..."
        )
        self.usage_item.set_sensitive(
            False
        )
        self.menu.append(
            self.usage_item
        )

        self.menu.append(
            Gtk.SeparatorMenuItem()
        )

        open_item = Gtk.MenuItem(
            label="Abrir StackOS GPU Manager"
        )
        open_item.connect(
            "activate",
            self._open_manager,
        )
        self.menu.append(
            open_item
        )

        quit_item = Gtk.MenuItem(
            label="Sair do indicador"
        )
        quit_item.connect(
            "activate",
            self._quit,
        )
        self.menu.append(
            quit_item
        )

        self.menu.show_all()

        self.indicator.set_menu(
            self.menu
        )

        self.refresh()

        GLib.timeout_add(
            POLL_INTERVAL_MS,
            self.refresh,
        )

    def _open_manager(
        self,
        *_args,
    ):
        launch_manager()

    def _quit(
        self,
        *_args,
    ):
        Gtk.main_quit()

    def refresh(self):
        gpus = gpu_usage_state()
        gpu = highest_usage(gpus)

        if gpu is None:
            usage = None
            level = "unavailable"
            label = (
                "Uso da GPU: indisponível"
            )
        else:
            usage = gpu["usage_percent"]
            level = indicator_level(
                usage
            )

            label = (
                f"Uso da GPU: {usage}%"
            )

            if len(gpus) > 1:
                label += (
                    f" • {gpu['pci_address']}"
                )

        self.indicator.set_icon_full(
            str(icon_path(level)),
            label,
        )

        self.indicator.set_title(
            label
        )

        self.usage_item.set_label(
            label
        )

        return True


def main():
    GPUIndicator()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

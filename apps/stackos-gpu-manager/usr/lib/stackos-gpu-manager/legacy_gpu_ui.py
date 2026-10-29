#!/usr/bin/env python3

import math
import gi
from pathlib import Path

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gdk

from stackos_gpu_sources import merged_gpu_state
from stackos_gpu_manager_core import build_state
from stackos_gpu_preferences import (
    PreferencesStore,
    default_config_path,
)
from stackos_gpu_executor import (
    build_execution_plan,
    launch_plan,
    ExecutorError,
)


APPS_PER_PAGE = 9
GRID_COLUMNS = 3


from stackos_gpu_runplan import RunPlanError
from stackos_desktop_exec import DesktopExecError
from stackos_gpu_launcher import LauncherError

def detect_visual_layout(gpus):
    """Escolhe a identidade visual pela GPU presente.

    Prioridade:
        NVIDIA > AMD > Intel

    Intel só assume o layout quando nenhuma GPU
    NVIDIA ou AMD estiver presente.
    """
    vendors = {
        gpu.get("vendor_id")
        for gpu in gpus
        if isinstance(gpu, dict)
    }

    if "0x10de" in vendors:
        return "nvidia"

    if "0x1002" in vendors:
        return "amd"

    return "intel"


def install_visual_theme(layout):
    themes = {
        "nvidia": {
            "accent": "#76b900",
            "accent_soft": "#9ddc43",
            "panel": "#0b1409",
            "panel_alt": "#111b0f",
            "border": "#345b18",
        },
        "amd": {
            "accent": "#e3343a",
            "accent_soft": "#ff6267",
            "panel": "#17090d",
            "panel_alt": "#1f0d15",
            "border": "#71303b",
        },
        "intel": {
            "accent": "#3d78d8",
            "accent_soft": "#67b8ff",
            "panel": "#07111d",
            "panel_alt": "#0a1726",
            "border": "#244e7b",
        },
    }

    theme = themes.get(
        layout,
        themes["intel"],
    )

    css = f"""
    .stackos-gpu-window {{
        background: #05081c;
        color: #ffffff;
    }}

    .stackos-gpu-header {{
        background: {theme["panel"]};
        border-bottom: 1px solid {theme["border"]};
    }}

    .stackos-gpu-brand {{
        color: {theme["accent_soft"]};
        font-weight: 800;
    }}

    .stackos-gpu-accent {{
        color: {theme["accent"]};
    }}

    .stackos-gpu-panel {{
        background: {theme["panel_alt"]};
        border: 1px solid {theme["border"]};
        border-radius: 12px;
    }}

    .stackos-hero {{
        background: {theme["panel"]};
        border-bottom: 1px solid {theme["border"]};
        padding: 16px 22px;
    }}

    .stackos-hero-brand {{
        font-size: 26px;
        font-weight: 900;
        color: #ffffff;
    }}

    .stackos-hero-subtitle {{
        font-size: 13px;
        font-weight: 800;
        color: {theme["accent_soft"]};
    }}

    .stackos-hero-gpu-name {{
        font-size: 21px;
        font-weight: 900;
        color: #ffffff;
    }}

    .stackos-hero-vendor {{
        font-size: 13px;
        font-weight: 900;
        color: {theme["accent"]};
    }}

    .stackos-metric {{
        background: {theme["panel_alt"]};
        border: 1px solid {theme["border"]};
        border-radius: 12px;
        padding: 9px 14px;
    }}

    .stackos-metric-title {{
        font-size: 10px;
        font-weight: 800;
        color: {theme["accent_soft"]};
    }}

    .stackos-metric-value {{
        font-size: 17px;
        font-weight: 900;
        color: #ffffff;
    }}

    .stackos-app-card {{
        background: {theme["panel_alt"]};
        border: 1px solid {theme["border"]};
        border-radius: 14px;
    }}

    .stackos-app-card:hover {{
        background: rgba(255, 255, 255, 0.055);
        border-color: {theme["accent"]};
    }}

    .stackos-app-open {{
        background: rgba(255, 255, 255, 0.08);
        color: #ffffff;
        font-weight: 800;
        border: 1px solid {theme["border"]};
        border-radius: 9px;
    }}

    .stackos-app-open:hover {{
        background: {theme["accent"]};
        border-color: {theme["accent"]};
        color: #ffffff;
    }}

    .stackos-app-open:focus {{
        border-color: {theme["accent_soft"]};
    }}
    """

    provider = Gtk.CssProvider()
    provider.load_from_string(css)

    display = Gdk.Display.get_default()

    if display is None:
        return provider

    Gtk.StyleContext.add_provider_for_display(
        display,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )

    return provider


def build_gpu_hero(gpus, layout, window):
    hero = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        spacing=22,
    )
    hero.add_css_class("stackos-hero")

    brand_box = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=0,
    )

    brand = Gtk.Label(
        label="STACKOS"
    )
    brand.set_xalign(0)
    brand.add_css_class(
        "stackos-hero-brand"
    )

    subtitle = Gtk.Label(
        label="GPU MANAGER"
    )
    subtitle.set_xalign(0)
    subtitle.add_css_class(
        "stackos-hero-subtitle"
    )

    brand_box.append(brand)
    brand_box.append(subtitle)

    hero.append(brand_box)

    preferred_vendor = {
        "nvidia": "0x10de",
        "amd": "0x1002",
        "intel": "0x8086",
    }.get(layout)

    gpu = None

    for candidate in gpus:
        if (
            candidate.get("vendor_id")
            == preferred_vendor
        ):
            gpu = candidate
            break

    if gpu is None and gpus:
        gpu = gpus[0]

    if gpu is None:
        gpu_name = "GPU não detectada"
        driver = "Indisponível"
        temperature = None
        discrete = False
    else:
        gpu_name = short_gpu_name(gpu)

        driver = (
            gpu.get("driver")
            or "Indisponível"
        )

        temperature = main_temperature(
            gpu
        )

        sw = gpu.get("switcheroo") or {}

        discrete = bool(
            sw.get("discrete")
        )

    identity = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=2,
    )
    identity.set_hexpand(True)
    identity.set_valign(
        Gtk.Align.CENTER
    )

    gpu_label = Gtk.Label(
        label=gpu_name
    )
    gpu_label.set_xalign(0)
    gpu_label.set_ellipsize(3)
    gpu_label.add_css_class(
        "stackos-hero-gpu-name"
    )

    vendor_names = {
        "nvidia": "NVIDIA",
        "amd": "AMD",
        "intel": "INTEL",
    }

    vendor_label = Gtk.Label(
        label=vendor_names.get(
            layout,
            "GPU",
        )
    )
    vendor_label.set_xalign(0)
    vendor_label.add_css_class(
        "stackos-hero-vendor"
    )

    identity.append(gpu_label)
    identity.append(vendor_label)

    hero.append(identity)

    def metric(title, value):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2,
        )
        box.set_valign(
            Gtk.Align.CENTER
        )
        box.add_css_class(
            "stackos-metric"
        )

        title_label = Gtk.Label(
            label=title
        )
        title_label.add_css_class(
            "stackos-metric-title"
        )

        value_label = Gtk.Label(
            label=value
        )
        value_label.add_css_class(
            "stackos-metric-value"
        )

        box.append(title_label)
        box.append(value_label)

        return box

    temp_text = (
        f"{temperature:.0f} °C"
        if temperature is not None
        else "—"
    )

    hero.append(
        metric(
            "TEMPERATURA",
            temp_text,
        )
    )

    hero.append(
        metric(
            "DRIVER",
            driver,
        )
    )

    hero.append(
        metric(
            "MODO",
            (
                "DEDICADA"
                if discrete
                else "INTEGRADA"
            ),
        )
    )

    window_controls = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        spacing=6,
    )
    window_controls.set_valign(
        Gtk.Align.CENTER
    )

    minimize_button = Gtk.Button.new_from_icon_name(
        "window-minimize-symbolic"
    )
    minimize_button.set_tooltip_text(
        "Minimizar"
    )
    minimize_button.add_css_class(
        "flat"
    )
    minimize_button.connect(
        "clicked",
        lambda _button: window.minimize(),
    )

    close_button = Gtk.Button.new_from_icon_name(
        "window-close-symbolic"
    )
    close_button.set_tooltip_text(
        "Fechar"
    )
    close_button.add_css_class(
        "flat"
    )
    close_button.connect(
        "clicked",
        lambda _button: window.close(),
    )

    window_controls.append(
        minimize_button
    )
    window_controls.append(
        close_button
    )

    hero.append(
        window_controls
    )

    return hero


def short_gpu_name(gpu):
    sw = gpu.get("switcheroo") or {}
    name = sw.get("name") or ""
    vendor = gpu.get("vendor_id")

    if vendor == "0x1002":
        if "RX 7600" in name:
            return "AMD Radeon RX 7600"
        return "AMD Radeon"

    if vendor == "0x10de":
        return name or "NVIDIA GPU"

    if vendor == "0x8086":
        return name or "Intel Graphics"

    return name or gpu.get("card") or "GPU"


def main_temperature(gpu):
    sensors = gpu.get(
        "temperature_sensors",
        [],
    )

    priorities = (
        "edge",
        "gpu",
        "package",
        "junction",
    )

    for wanted in priorities:
        for sensor in sensors:
            label = (
                sensor.get("label")
                or sensor.get("sensor")
                or ""
            ).lower()

            if wanted in label:
                value = sensor.get(
                    "temperature_c"
                )

                if value is not None:
                    return value

    for sensor in sensors:
        value = sensor.get(
            "temperature_c"
        )

        if value is not None:
            return value

    return None


def environment_row(value):
    full_value = (
        str(value)
        if value
        else "Indisponível"
    )

    if value:
        parts = full_value.split()

        short_value = (
            parts[0]
            if parts
            else full_value
        )

        if len(parts) > 1:
            short_value += "  …"
    else:
        short_value = full_value

    row = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        spacing=8,
    )

    left = Gtk.Label(
        label="Environment"
    )
    left.set_xalign(0)
    left.set_hexpand(True)

    right = Gtk.Label(
        label=short_value
    )
    right.set_xalign(1)
    right.set_ellipsize(3)
    right.set_selectable(True)
    right.set_tooltip_text(full_value)

    row.append(left)
    row.append(right)

    return row


def info_row(name, value):
    row = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        spacing=8,
    )

    left = Gtk.Label(
        label=name
    )
    left.set_xalign(0)
    left.set_hexpand(True)

    right = Gtk.Label(
        label=(
            str(value)
            if value is not None
            else "Indisponível"
        )
    )
    right.set_xalign(1)
    right.set_selectable(True)
    right.set_wrap(True)

    row.append(left)
    row.append(right)

    return row


class AppCard(Gtk.Frame):
    def __init__(
        self,
        app_data,
        store,
        high_performance_available,
        status_callback,
        launch_status_callback=None,
    ):
        super().__init__()

        self.add_css_class(
            "stackos-app-card"
        )

        self.app_data = app_data
        self.store = store
        self.status_callback = status_callback
        self.launch_status_callback = (
            launch_status_callback
            if launch_status_callback is not None
            else status_callback
        )
        self.loading = True

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )

        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(12)
        box.set_margin_end(12)

        app_header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
        )
        app_header.set_valign(
            Gtk.Align.CENTER
        )

        icon_value = app_data.get("icon")
        app_icon = None

        if icon_value:
            icon_path = Path(icon_value)

            if (
                icon_path.is_absolute()
                and icon_path.is_file()
            ):
                try:
                    texture = Gdk.Texture.new_from_filename(
                        str(icon_path)
                    )

                    app_icon = Gtk.Image.new_from_paintable(
                        texture
                    )

                    app_icon.set_size_request(
                        48,
                        48,
                    )

                except Exception:
                    app_icon = None

            else:
                app_icon = Gtk.Image.new_from_icon_name(
                    icon_value
                )

        if app_icon is None:
            app_icon = Gtk.Image.new_from_icon_name(
                "application-x-executable-symbolic"
            )

        app_icon.set_pixel_size(48)
        app_icon.set_valign(Gtk.Align.CENTER)

        name = Gtk.Label(
            label=app_data.get(
                "name",
                app_data["desktop_id"],
            )
        )
        name.set_xalign(0)
        name.set_yalign(0.5)
        name.set_wrap(True)
        name.set_lines(2)
        name.set_ellipsize(3)
        name.set_hexpand(True)
        name.add_css_class("heading")

        app_header.append(app_icon)
        app_header.append(name)

        box.append(app_header)

        options = [
            "Automático",
            "GPU padrão",
        ]

        if high_performance_available:
            options.append(
                "Alto desempenho"
            )

        self.options = options

        model = Gtk.StringList.new(
            options
        )

        self.dropdown = Gtk.DropDown(
            model=model
        )
        self.dropdown.set_hexpand(True)

        self.open_button = Gtk.Button(
            label="Abrir"
        )
        self.open_button.add_css_class(
            "stackos-app-open"
        )
        self.open_button.set_tooltip_text(
            "Abrir aplicativo com a GPU selecionada"
        )
        self.open_button.connect(
            "clicked",
            self.on_open,
        )

        preference = (
            store.get_preference(
                app_data["desktop_id"]
            )
        )

        selected = 0

        if preference:
            selection = preference.get(
                "selection"
            )
            source = preference.get(
                "source"
            )

            if (
                source == "manual"
                and selection
                == "role:default"
            ):
                selected = 1

            elif (
                source == "manual"
                and selection
                == "role:discrete"
                and high_performance_available
            ):
                selected = 2

        self.dropdown.set_selected(
            selected
        )

        controls = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        controls.set_valign(
            Gtk.Align.END
        )

        controls.append(
            self.dropdown
        )
        controls.append(
            self.open_button
        )

        box.append(controls)
        self.set_child(box)

        self.loading = False

        self.dropdown.connect(
            "notify::selected",
            self.on_changed,
        )

    def on_open(
        self,
        _button,
    ):
        desktop_id = self.app_data[
            "desktop_id"
        ]

        name = self.app_data.get(
            "name",
            desktop_id,
        )

        try:
            plan = build_execution_plan(
                desktop_id,
                self.store.path,
            )

            process = launch_plan(
                plan
            )

        except (
            ExecutorError,
            RunPlanError,
            DesktopExecError,
            LauncherError,
        ) as exc:
            self.launch_status_callback(
                f"Erro ao abrir {name}: {exc}"
            )
            return

        self.launch_status_callback(
            f"Aberto: {name} "
            f"(PID {process.pid})"
        )

    def on_changed(
        self,
        dropdown,
        _param,
    ):
        if self.loading:
            return

        index = dropdown.get_selected()

        if index >= len(self.options):
            return

        choice = self.options[index]

        desktop_id = self.app_data[
            "desktop_id"
        ]


        if choice == "Automático":
            self.store.remove_selection(
                desktop_id
            )

        elif choice == "GPU padrão":
            self.store.set_selection(
                desktop_id,
                "role:default",
                source="manual",
            )

        elif choice == "Alto desempenho":
            self.store.set_selection(
                desktop_id,
                "role:discrete",
                source="manual",
            )

        self.store.save()

        self.status_callback(
            f"{self.app_data.get('name', desktop_id)}: "
            f"{choice}"
        )


class GPUColumn(Gtk.Box):
    def __init__(
        self,
        gpus,
        high_performance_available,
    ):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
        )

        self.set_margin_top(14)
        self.set_margin_bottom(14)
        self.set_margin_start(14)
        self.set_margin_end(14)

        heading = Gtk.Label(
            label="GPU"
        )
        heading.set_xalign(0)
        heading.add_css_class("title-2")
        self.append(heading)

        if not gpus:
            empty = Gtk.Label(
                label="Nenhuma GPU detectada."
            )
            empty.set_xalign(0)
            self.append(empty)
            return

        gpu = gpus[0]
        sw = gpu.get("switcheroo") or {}

        card = Gtk.Frame()

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=9,
        )

        box.set_margin_top(14)
        box.set_margin_bottom(14)
        box.set_margin_start(14)
        box.set_margin_end(14)

        # ----------------------------------------------------
        # ESTADO
        # ----------------------------------------------------

        state_heading = Gtk.Label(
            label="Estado"
        )
        state_heading.set_xalign(0)
        state_heading.add_css_class(
            "heading"
        )

        box.append(state_heading)

        box.append(
            info_row(
                "GPU padrão",
                (
                    "Indisponível"
                    if not sw
                    else (
                        "Sim"
                        if sw.get("default")
                        else "Não"
                    )
                ),
            )
        )

        box.append(
            info_row(
                "GPU dedicada",
                (
                    "Indisponível"
                    if not sw
                    else (
                        "Sim"
                        if sw.get("discrete")
                        else "Não"
                    )
                ),
            )
        )

        box.append(
            info_row(
                "Energia",
                gpu.get("power_state")
                or "Indisponível",
            )
        )

        # ----------------------------------------------------
        # SENSORES
        # ----------------------------------------------------

        sensors = gpu.get(
            "temperature_sensors",
            [],
        )

        if sensors:
            box.append(
                Gtk.Separator(
                    orientation=Gtk.Orientation.HORIZONTAL
                )
            )

            temp_heading = Gtk.Label(
                label="Sensores"
            )
            temp_heading.set_xalign(0)
            temp_heading.add_css_class(
                "heading"
            )

            box.append(temp_heading)

            for sensor in sensors:
                label = (
                    sensor.get("label")
                    or sensor.get("sensor")
                    or "Sensor"
                )

                value = sensor.get(
                    "temperature_c"
                )

                value_text = (
                    f"{value:.1f} °C"
                    if value is not None
                    else "Indisponível"
                )

                box.append(
                    info_row(
                        label,
                        value_text,
                    )
                )

        # ----------------------------------------------------
        # HARDWARE
        # ----------------------------------------------------

        box.append(
            Gtk.Separator(
                orientation=Gtk.Orientation.HORIZONTAL
            )
        )

        hardware_heading = Gtk.Label(
            label="Hardware"
        )
        hardware_heading.set_xalign(0)
        hardware_heading.add_css_class(
            "heading"
        )

        box.append(hardware_heading)

        box.append(
            info_row(
                "PCI",
                gpu.get("pci_address")
                or "Indisponível",
            )
        )

        render_nodes = gpu.get(
            "render_nodes",
            [],
        )

        render_node = (
            render_nodes[0]
            if render_nodes
            else "Indisponível"
        )

        box.append(
            info_row(
                "Render",
                render_node,
            )
        )

        card.set_child(box)
        self.append(card)

        # ----------------------------------------------------
        # DISPONIBILIDADE DE GPU ALTERNATIVA
        # ----------------------------------------------------

        if not high_performance_available:
            note = Gtk.Frame()

            note_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=4,
            )

            note_box.set_margin_top(10)
            note_box.set_margin_bottom(10)
            note_box.set_margin_start(10)
            note_box.set_margin_end(10)

            line1 = Gtk.Label(
                label="Somente uma GPU detectada."
            )
            line1.set_xalign(0)

            line2 = Gtk.Label(
                label=(
                    "Alto desempenho não está disponível."
                )
            )
            line2.set_xalign(0)
            line2.add_css_class(
                "dim-label"
            )

            note_box.append(line1)
            note_box.append(line2)

            note.set_child(note_box)
            self.append(note)


class AppsColumn(Gtk.Box):
    def __init__(
        self,
        applications,
        store,
        high_performance_available,
    ):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
        )

        self.set_margin_top(14)
        self.set_margin_bottom(14)
        self.set_margin_start(14)
        self.set_margin_end(14)

        self.store = store
        self.high_performance_available = (
            high_performance_available
        )

        self.all_apps = sorted(
            applications,
            key=lambda item: item.get(
                "name",
                "",
            ).casefold(),
        )

        self.filtered_apps = list(
            self.all_apps
        )

        self.current_page = 0

        heading = Gtk.Label(
            label="Aplicativos"
        )
        heading.set_xalign(0)
        heading.add_css_class(
            "title-2"
        )

        self.append(heading)

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text(
            "Pesquisar aplicativos..."
        )
        self.search.connect(
            "search-changed",
            self.on_search,
        )

        self.append(self.search)

        self.status = Gtk.Label(
            label="Nenhuma alteração realizada."
        )
        self.status.set_xalign(0)
        self.status.set_ellipsize(3)
        self.status.add_css_class(
            "dim-label"
        )

        self.append(self.status)

        self.grid = Gtk.Grid()

        self.grid.set_column_spacing(8)
        self.grid.set_row_spacing(8)
        self.grid.set_column_homogeneous(
            True
        )
        self.grid.set_row_homogeneous(
            True
        )

        self.grid.set_hexpand(True)
        self.grid.set_vexpand(True)

        self.append(self.grid)

        footer = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
        )

        footer.set_halign(
            Gtk.Align.CENTER
        )

        self.prev = Gtk.Button(
            label="◀"
        )
        self.next = Gtk.Button(
            label="▶"
        )

        self.page_label = Gtk.Label()

        self.prev.connect(
            "clicked",
            self.previous_page,
        )

        self.next.connect(
            "clicked",
            self.next_page,
        )

        footer.append(self.prev)
        footer.append(self.page_label)
        footer.append(self.next)

        self.append(footer)

        self.refresh_grid()

    def set_status(self, text):
        self.status.set_text(
            "Salvo: " + text
        )

    def set_launch_status(
        self,
        text,
    ):
        self.status.set_text(
            text
        )

    def on_search(self, entry):
        query = (
            entry.get_text()
            .strip()
            .casefold()
        )

        if query:
            self.filtered_apps = [
                app
                for app in self.all_apps
                if query in app.get(
                    "name",
                    "",
                ).casefold()
            ]
        else:
            self.filtered_apps = list(
                self.all_apps
            )

        self.current_page = 0
        self.refresh_grid()

    def clear_grid(self):
        child = (
            self.grid.get_first_child()
        )

        while child is not None:
            next_child = (
                child.get_next_sibling()
            )
            self.grid.remove(child)
            child = next_child

    def refresh_grid(self):
        self.clear_grid()

        total = len(
            self.filtered_apps
        )

        pages = max(
            1,
            math.ceil(
                total / APPS_PER_PAGE
            ),
        )

        if self.current_page >= pages:
            self.current_page = (
                pages - 1
            )

        start = (
            self.current_page
            * APPS_PER_PAGE
        )

        visible = (
            self.filtered_apps[
                start:
                start + APPS_PER_PAGE
            ]
        )

        for index, app_data in enumerate(
            visible
        ):
            column = (
                index % GRID_COLUMNS
            )

            row = (
                index // GRID_COLUMNS
            )

            card = AppCard(
                app_data,
                self.store,
                self.high_performance_available,
                self.set_status,
                self.set_launch_status,
            )

            card.set_hexpand(True)
            card.set_vexpand(True)

            self.grid.attach(
                card,
                column,
                row,
                1,
                1,
            )

        self.page_label.set_text(
            f"Página {self.current_page + 1} / {pages}"
        )

        self.prev.set_sensitive(
            self.current_page > 0
        )

        self.next.set_sensitive(
            self.current_page < pages - 1
        )

    def previous_page(
        self,
        _button,
    ):
        if self.current_page > 0:
            self.current_page -= 1
            self.refresh_grid()

    def next_page(
        self,
        _button,
    ):
        pages = max(
            1,
            math.ceil(
                len(self.filtered_apps)
                / APPS_PER_PAGE
            ),
        )

        if self.current_page < pages - 1:
            self.current_page += 1
            self.refresh_grid()


class DetailsColumn(Gtk.Box):
    def __init__(self, gpus):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
        )

        self.set_margin_top(14)
        self.set_margin_bottom(14)
        self.set_margin_start(14)
        self.set_margin_end(14)

        heading = Gtk.Label(
            label="Detalhes"
        )
        heading.set_xalign(0)
        heading.add_css_class(
            "title-2"
        )

        self.append(heading)

        if not gpus:
            self.append(
                Gtk.Label(
                    label="Sem informações."
                )
            )
            return

        gpu = gpus[0]
        sw = gpu.get(
            "switcheroo"
        ) or {}

        self.append(
            self.section(
                "Hardware",
                [
                    (
                        "Nome",
                        short_gpu_name(gpu),
                    ),
                    (
                        "PCI",
                        gpu.get(
                            "pci_address"
                        ),
                    ),
                    (
                        "Vendor",
                        gpu.get(
                            "vendor_id"
                        ),
                    ),
                    (
                        "Device",
                        gpu.get(
                            "device_id"
                        ),
                    ),
                    (
                        "Driver",
                        gpu.get(
                            "driver"
                        ),
                    ),
                    (
                        "Render",
                        ", ".join(
                            gpu.get(
                                "render_nodes",
                                [],
                            )
                        ),
                    ),
                    (
                        "Energia",
                        gpu.get(
                            "power_state"
                        ),
                    ),
                    (
                        "DRM",
                        (
                            "Disponível"
                            if gpu.get("cards")
                            else "Indisponível"
                        ),
                    ),
                    (
                        "Render disponível",
                        (
                            "Sim"
                            if gpu.get("render_nodes")
                            else "Não"
                        ),
                    ),
                    (
                        "Temperatura",
                        (
                            "Disponível"
                            if gpu.get(
                                "temperature_sensors"
                            )
                            else "Indisponível"
                        ),
                    ),
                    (
                        "Switcheroo",
                        (
                            "Disponível"
                            if gpu.get("switcheroo")
                            else "Indisponível"
                        ),
                    ),
                ],
            )
        )

        switcheroo_section = self.section(
            "Switcheroo",
            [
                (
                    "GPU ID",
                    sw.get("gpu_id"),
                ),
                (
                    "Padrão",
                    "Sim"
                    if sw.get(
                        "default"
                    )
                    else "Não",
                ),
                (
                    "Dedicada",
                    "Sim"
                    if sw.get(
                        "discrete"
                    )
                    else "Não",
                ),
            ],
        )

        switcheroo_box = (
            switcheroo_section.get_child()
        )

        switcheroo_box.append(
            environment_row(
                sw.get("environment")
            )
        )

        self.append(
            switcheroo_section
        )

        temp_rows = []

        for sensor in gpu.get(
            "temperature_sensors",
            [],
        ):
            label = (
                sensor.get("label")
                or sensor.get("sensor")
                or "Sensor"
            )

            value = sensor.get(
                "temperature_c"
            )

            temp_rows.append(
                (
                    label,
                    (
                        f"{value:.1f} °C"
                        if value is not None
                        else "Indisponível"
                    ),
                )
            )

        if not temp_rows:
            temp_rows.append(
                (
                    "Sensores",
                    "Indisponíveis",
                )
            )

        self.append(
            self.section(
                "Temperaturas",
                temp_rows,
            )
        )

    def section(
        self,
        title,
        rows,
    ):
        frame = Gtk.Frame()

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
        )

        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)

        heading = Gtk.Label(
            label=title
        )
        heading.set_xalign(0)
        heading.add_css_class(
            "heading"
        )
        box.append(heading)

        for key, value in rows:
            box.append(
                info_row(
                    key,
                    value,
                )
            )

        frame.set_child(box)
        return frame


class GPUManagerWindow(
    Adw.ApplicationWindow
):
    def __init__(self, app):
        super().__init__(
            application=app
        )

        self.set_title(
            "StackOS GPU Manager"
        )

        self.set_default_size(
            1180,
            680,
        )

        self.set_resizable(True)

        preferences_path = (
            default_config_path()
        )

        store = PreferencesStore(
            preferences_path
        )
        store.load()

        core = build_state(
            preferences_path
        )

        try:
            gpus = merged_gpu_state()
        except Exception:
            gpus = []

        self.visual_layout = detect_visual_layout(
            gpus
        )

        self.visual_css = install_visual_theme(
            self.visual_layout
        )

        self.add_css_class(
            "stackos-gpu-window"
        )

        self.add_css_class(
            f"stackos-{self.visual_layout}"
        )

        switcheroo = core.get(
            "switcheroo",
            {},
        )

        high_performance_available = (
            bool(
                core.get("dual_gpu")
            )
            and switcheroo.get(
                "available",
                False,
            )
            and switcheroo.get(
                "num_gpus",
                0,
            ) > 1
        )

        toolbar = Adw.ToolbarView()

        columns = Gtk.Grid()

        columns.set_column_spacing(1)
        columns.set_column_homogeneous(
            False
        )

        columns.set_hexpand(True)
        columns.set_vexpand(True)

        left = GPUColumn(
            gpus,
            high_performance_available,
        )

        center = AppsColumn(
            core.get(
                "applications",
                [],
            ),
            store,
            high_performance_available,
        )

        right = DetailsColumn(
            gpus
        )

        left.set_size_request(
            300,
            -1,
        )

        center.set_size_request(
            500,
            -1,
        )

        right.set_size_request(
            340,
            -1,
        )

        columns.attach(
            left,
            0,
            0,
            1,
            1,
        )

        columns.attach(
            Gtk.Separator(
                orientation=Gtk.Orientation.VERTICAL
            ),
            1,
            0,
            1,
            1,
        )

        columns.attach(
            center,
            2,
            0,
            1,
            1,
        )

        columns.attach(
            Gtk.Separator(
                orientation=Gtk.Orientation.VERTICAL
            ),
            3,
            0,
            1,
            1,
        )

        columns.attach(
            right,
            4,
            0,
            1,
            1,
        )

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )

        hero = build_gpu_hero(
            gpus,
            self.visual_layout,
            self,
        )

        content.append(hero)
        content.append(columns)

        toolbar.set_content(
            content
        )

        self.set_content(
            toolbar
        )


class GPUManagerApp(
    Adw.Application
):
    def __init__(self):
        super().__init__(
            application_id=(
                "org.stackos.GPUManager"
            )
        )

    def do_activate(self):
        window = (
            self.props.active_window
        )

        if window is None:
            window = GPUManagerWindow(
                self
            )

        window.present()


def main():
    return GPUManagerApp().run(
        None
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

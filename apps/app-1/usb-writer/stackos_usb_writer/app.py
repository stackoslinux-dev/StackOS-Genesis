"""GTK4 desktop application."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading

from .devices import UsbDevice, discover_usb_devices, format_size
from .operations import sha256_file, validate_image


APP_ID = "org.stackos.UsbWriter"


def main() -> int:
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gio, GLib, Gtk
    except (ImportError, ValueError) as error:
        print("Instale: sudo apt install python3-gi gir1.2-gtk-4.0", file=sys.stderr)
        print(error, file=sys.stderr)
        return 1

    class MainWindow(Gtk.ApplicationWindow):
        def __init__(self, application: Gtk.Application) -> None:
            super().__init__(application=application)
            self.set_title("StackOS USB Writer")
            self.set_default_size(760, 600)
            self.devices: list[UsbDevice] = []
            self.image_path = ""
            self.process: subprocess.Popen[str] | None = None

            # ── Tema visual StackOS ─────────────────────────────────────
            css = Gtk.CssProvider()
            css.load_from_data(b"""
            window {
                background: #070b14;
                color: #ffffff;
            }

            .stackos-sidebar {
                background: #0b111e;
                border-right: 1px solid rgba(61, 120, 216, 0.22);
                padding: 18px;
            }

            .stackos-brand {
                font-size: 24px;
                font-weight: 800;
                color: #ffffff;
            }

            .stackos-brand-accent {
                color: #3d78d8;
            }

            .stackos-muted {
                color: #9aa7bd;
            }

            .stackos-nav-active {
                background: #1559c7;
                color: #ffffff;
                border-radius: 10px;
                padding: 10px 14px;
                font-weight: 700;
            }

            .stackos-card {
                background: #0d1422;
                border: 1px solid rgba(61, 120, 216, 0.28);
                border-radius: 14px;
                padding: 14px;
            }

            .stackos-title {
                font-size: 26px;
                font-weight: 800;
                color: #ffffff;
            }

            .stackos-subtitle {
                color: #a9b8d0;
            }

            .stackos-section-title {
                font-weight: 700;
                color: #ffffff;
            }

            .stackos-security {
                background: rgba(20, 81, 165, 0.20);
                border: 1px solid rgba(61, 120, 216, 0.45);
                border-radius: 12px;
                padding: 12px;
                color: #bcd5ff;
            }

            button {
                border-radius: 10px;
                min-height: 36px;
            }

            button.suggested-action {
                background: #155fd1;
                color: #ffffff;
            }

            progressbar trough {
                min-height: 8px;
                border-radius: 8px;
                background: #151c29;
            }

            progressbar progress {
                border-radius: 8px;
                background: #3d78d8;
            }

            entry, dropdown {
                border-radius: 9px;
            }
            """)

            Gtk.StyleContext.add_provider_for_display(
                self.get_display(),
                css,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

            # ── Header ─────────────────────────────────────────────────
            header = Gtk.HeaderBar()
            header.set_show_title_buttons(True)

            header_title = Gtk.Label(label="StackOS USB Writer")
            header_title.add_css_class("stackos-section-title")
            header.set_title_widget(header_title)

            refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
            refresh.set_tooltip_text("Atualizar dispositivos")
            refresh.connect(
                "clicked",
                lambda _button: self.refresh_devices()
            )
            header.pack_end(refresh)

            self.set_titlebar(header)
            self.set_default_size(920, 620)
            self.set_resizable(False)

            # ── Layout principal ───────────────────────────────────────
            shell = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=0,
            )
            self.set_child(shell)

            # ── Sidebar ────────────────────────────────────────────────
            sidebar = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=14,
            )
            sidebar.set_size_request(210, -1)
            sidebar.add_css_class("stackos-sidebar")

            brand_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=10,
            )

            brand_icon = Gtk.Image.new_from_icon_name(
                "stackos-usb-writer"
            )
            brand_icon.set_pixel_size(42)
            brand_row.append(brand_icon)

            brand_text = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=0,
            )

            brand = Gtk.Label(label="StackOS", xalign=0)
            brand.add_css_class("stackos-brand")

            brand_linux = Gtk.Label(label="USB Writer", xalign=0)
            brand_linux.add_css_class("stackos-muted")

            brand_text.append(brand)
            brand_text.append(brand_linux)
            brand_row.append(brand_text)
            sidebar.append(brand_row)

            sidebar.append(Gtk.Separator())

            nav = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=10,
            )
            nav.add_css_class("stackos-nav-active")

            nav_icon = Gtk.Image.new_from_icon_name(
                "media-removable-symbolic"
            )
            nav.append(nav_icon)
            nav.append(Gtk.Label(label="Gravar USB", xalign=0))
            sidebar.append(nav)

            info = Gtk.Label(
                label="Imagem ISO / IMG",
                xalign=0,
            )
            info.add_css_class("stackos-muted")
            sidebar.append(info)

            verify_info = Gtk.Label(
                label="Verificação SHA-256",
                xalign=0,
            )
            verify_info.add_css_class("stackos-muted")
            sidebar.append(verify_info)

            format_info = Gtk.Label(
                label="Formatação USB",
                xalign=0,
            )
            format_info.add_css_class("stackos-muted")
            sidebar.append(format_info)

            filler = Gtk.Box(vexpand=True)
            sidebar.append(filler)

            security_title = Gtk.Label(
                label="🛡  Segurança",
                xalign=0,
            )
            security_title.add_css_class("stackos-section-title")
            sidebar.append(security_title)

            security_text = Gtk.Label(
                label=(
                    "Somente dispositivos USB\n"
                    "seguros são exibidos."
                ),
                xalign=0,
            )
            security_text.set_wrap(True)
            security_text.add_css_class("stackos-muted")
            sidebar.append(security_text)

            shell.append(sidebar)

            # ── Conteúdo ───────────────────────────────────────────────
            root = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=14,
                margin_top=24,
                margin_bottom=24,
                margin_start=26,
                margin_end=26,
                hexpand=True,
                vexpand=True,
            )
            shell.append(root)

            hero = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=16,
            )

            hero_icon = Gtk.Image.new_from_icon_name(
                "stackos-usb-writer"
            )
            hero_icon.set_pixel_size(58)
            hero.append(hero_icon)

            hero_text = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=3,
                valign=Gtk.Align.CENTER,
            )

            title = Gtk.Label(
                label="StackOS USB Writer",
                xalign=0,
            )
            title.add_css_class("stackos-title")

            subtitle = Gtk.Label(
                label=(
                    "Crie mídias USB inicializáveis "
                    "com segurança e verificação."
                ),
                xalign=0,
            )
            subtitle.add_css_class("stackos-subtitle")

            hero_text.append(title)
            hero_text.append(subtitle)
            hero.append(hero_text)
            root.append(hero)

            # ── Card: imagem ───────────────────────────────────────────
            image_card = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=10,
            )
            image_card.add_css_class("stackos-card")

            image_title = Gtk.Label(
                label="Imagem ISO ou IMG",
                xalign=0,
            )
            image_title.add_css_class("stackos-section-title")
            image_card.append(image_title)

            image_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=10,
            )

            self.image_label = Gtk.Label(
                label="Nenhuma imagem selecionada",
                xalign=0,
                hexpand=True,
            )
            self.image_label.set_ellipsize(3)
            self.image_label.add_css_class("stackos-muted")
            image_row.append(self.image_label)

            choose = Gtk.Button(label="Selecionar…")
            choose.set_icon_name("folder-open-symbolic")
            choose.connect("clicked", self.choose_image)
            image_row.append(choose)

            checksum = Gtk.Button(label="SHA-256")
            checksum.set_icon_name("emblem-ok-symbolic")
            checksum.connect("clicked", self.calculate_checksum)
            image_row.append(checksum)

            image_card.append(image_row)
            root.append(image_card)

            # ── Card: dispositivo ──────────────────────────────────────
            device_card = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=10,
            )
            device_card.add_css_class("stackos-card")

            device_title = Gtk.Label(
                label="Dispositivo USB",
                xalign=0,
            )
            device_title.add_css_class("stackos-section-title")
            device_card.append(device_title)

            self.device_combo = Gtk.DropDown()
            self.device_combo.connect(
                "notify::selected",
                lambda *_args: self.update_buttons(),
            )
            device_card.append(self.device_combo)

            self.device_details = Gtk.Label(
                xalign=0,
                wrap=True,
            )
            self.device_details.add_css_class("stackos-muted")
            device_card.append(self.device_details)

            root.append(device_card)

            # ── Opções ─────────────────────────────────────────────────
            option_card = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=12,
            )
            option_card.add_css_class("stackos-card")

            self.verify = Gtk.CheckButton(
                label="Verificar integridade após gravar"
            )
            self.verify.set_active(True)
            option_card.append(self.verify)

            format_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=10,
            )

            format_box.append(
                Gtk.Label(label="Formatação:")
            )

            self.filesystem = Gtk.DropDown.new_from_strings(
                ["FAT32", "exFAT", "NTFS"]
            )
            format_box.append(self.filesystem)

            self.label_entry = Gtk.Entry(
                placeholder_text="Rótulo",
                text="STACKOS",
                hexpand=True,
            )
            self.label_entry.set_max_length(11)
            format_box.append(self.label_entry)

            self.format_button = Gtk.Button(
                label="Formatar USB"
            )
            self.format_button.set_icon_name(
                "edit-clear-all-symbolic"
            )
            self.format_button.add_css_class(
                "destructive-action"
            )
            self.format_button.connect(
                "clicked",
                self.confirm_format,
            )
            format_box.append(self.format_button)

            option_card.append(format_box)
            root.append(option_card)

            # ── Segurança ──────────────────────────────────────────────
            security = Gtk.Label(
                label=(
                    "ⓘ A gravação altera o dispositivo selecionado. "
                    "Confirme o USB correto antes de continuar."
                ),
                xalign=0,
                wrap=True,
            )
            security.add_css_class("stackos-security")
            root.append(security)

            # ── Progresso / status ─────────────────────────────────────
            self.progress = Gtk.ProgressBar(show_text=True)
            root.append(self.progress)

            self.status = Gtk.Label(
                xalign=0,
                wrap=True,
            )
            self.status.add_css_class("stackos-muted")
            root.append(self.status)

            # ── Ações ──────────────────────────────────────────────────
            actions = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=10,
                halign=Gtk.Align.END,
            )
            root.append(actions)

            self.cancel_button = Gtk.Button(
                label="Cancelar",
                sensitive=False,
            )
            self.cancel_button.set_icon_name(
                "process-stop-symbolic"
            )
            self.cancel_button.connect(
                "clicked",
                self.cancel_operation,
            )
            actions.append(self.cancel_button)

            self.write_button = Gtk.Button(
                label="Gravar USB"
            )
            self.write_button.set_icon_name(
                "media-removable-symbolic"
            )
            self.write_button.add_css_class(
                "suggested-action"
            )
            self.write_button.connect(
                "clicked",
                self.confirm_write,
            )
            actions.append(self.write_button)

            self.refresh_devices()

        def alert(self, title: str, body: str) -> None:
            dialog = Gtk.AlertDialog(message=title, detail=body)
            dialog.show(self)

        def ask(self, title: str, body: str, callback) -> None:
            dialog = Gtk.AlertDialog(
                message=title,
                detail=body,
                buttons=["Cancelar", "Continuar"],
                cancel_button=0,
                default_button=0,
            )
            dialog.choose(self, None, self._answer, callback)

        def _answer(self, dialog, result, callback) -> None:
            try:
                if dialog.choose_finish(result) == 1:
                    callback()
            except Exception:
                pass

        def selected_device(self) -> UsbDevice | None:
            index = self.device_combo.get_selected()
            return self.devices[index] if index < len(self.devices) else None

        def refresh_devices(self) -> None:
            try:
                self.devices = [item for item in discover_usb_devices() if not item.protected]
            except Exception as error:
                self.devices = []
                self.status.set_text(f"Falha ao detectar dispositivos: {error}")
            names = [
                f"{item.display_name} — {format_size(item.size)} ({item.path})"
                for item in self.devices
            ] or ["Nenhum dispositivo USB seguro encontrado"]
            self.device_combo.set_model(Gtk.StringList.new(names))
            self.device_combo.set_selected(0)
            self.update_buttons()

        def update_buttons(self) -> None:
            device = self.selected_device()
            idle = self.process is None
            self.write_button.set_sensitive(bool(device and self.image_path and idle))
            self.format_button.set_sensitive(bool(device and idle))
            self.device_details.set_text(
                f"Destino: {device.path}. Todo o conteúdo será apagado."
                if device
                else "Conecte um pendrive e clique em atualizar."
            )

        def choose_image(self, _button) -> None:
            dialog = Gtk.FileDialog(title="Selecionar imagem")
            image_filter = Gtk.FileFilter()
            image_filter.set_name("Imagens ISO e IMG")
            image_filter.add_pattern("*.iso")
            image_filter.add_pattern("*.img")
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(image_filter)
            dialog.set_filters(filters)
            dialog.open(self, None, self._image_selected)

        def _image_selected(self, dialog, result) -> None:
            try:
                path = dialog.open_finish(result).get_path()
                self.image_path = str(validate_image(path))
                self.image_label.set_text(self.image_path)
                self.status.set_text(
                    f"Imagem pronta: {format_size(os.path.getsize(self.image_path))}"
                )
            except Exception as error:
                self.alert("Imagem inválida", str(error))
            self.update_buttons()

        def calculate_checksum(self, _button) -> None:
            if not self.image_path:
                self.alert("Selecione uma imagem", "Escolha um arquivo ISO ou IMG primeiro.")
                return
            self.status.set_text("Calculando SHA-256…")
            self.progress.pulse()

            def run() -> None:
                try:
                    digest = sha256_file(
                        self.image_path,
                        lambda current, total: GLib.idle_add(
                            self.set_progress, current, total, 0
                        ),
                    )
                    GLib.idle_add(self.status.set_text, f"SHA-256: {digest}")
                except Exception as error:
                    GLib.idle_add(self.alert, "Falha no checksum", str(error))

            threading.Thread(target=run, daemon=True).start()

        def confirm_write(self, _button) -> None:
            device = self.selected_device()
            if not device:
                return
            self.ask(
                "Apagar e gravar o dispositivo?",
                f"Todos os dados de {device.path} serão destruídos. Esta ação não pode ser desfeita.",
                self.start_write,
            )

        def start_write(self) -> None:
            device = self.selected_device()
            if not device:
                return
            args = [
                "pkexec",
                "/usr/lib/stackos-usb-writer/stackos-usb-writer-worker",
                "write",
                "--image",
                self.image_path,
                "--device",
                device.path,
            ]
            if self.verify.get_active():
                args.append("--verify")
            self.start_worker(args)

        def confirm_format(self, _button) -> None:
            device = self.selected_device()
            if not device:
                return
            self.ask(
                "Formatar o dispositivo?",
                f"Todos os dados de {device.path} serão destruídos. Esta ação não pode ser desfeita.",
                self.start_format,
            )

        def start_format(self) -> None:
            device = self.selected_device()
            if not device:
                return
            filesystem = ("fat32", "exfat", "ntfs")[self.filesystem.get_selected()]
            args = [
                "pkexec",
                "/usr/lib/stackos-usb-writer/stackos-usb-writer-worker",
                "format",
                "--device",
                device.path,
                "--filesystem",
                filesystem,
                "--label",
                self.label_entry.get_text() or "STACKOS",
            ]
            self.start_worker(args)

        def start_worker(self, args: list[str]) -> None:
            try:
                self.process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
            except Exception as error:
                self.process = None
                self.alert("Não foi possível iniciar", str(error))
                return
            self.cancel_button.set_sensitive(True)
            self.update_buttons()
            self.status.set_text("Operação iniciada…")
            threading.Thread(target=self.read_worker, daemon=True).start()

        def read_worker(self) -> None:
            assert self.process and self.process.stdout
            process = self.process
            for line in process.stdout:
                try:
                    event = json.loads(line)
                    GLib.idle_add(self.handle_event, event)
                except json.JSONDecodeError:
                    GLib.idle_add(self.status.set_text, line.strip())
            code = process.wait()
            GLib.idle_add(self.worker_finished, code)

        def handle_event(self, event: dict) -> None:
            kind = event.get("event")
            if kind == "stage":
                label = {
                    "writing": "Gravando imagem…",
                    "verifying": "Verificando gravação…",
                    "formatting": "Formatando dispositivo…",
                }.get(event.get("name"), "Processando…")
                self.status.set_text(label)
            elif kind == "progress":
                self.set_progress(event["current"], event["total"], event.get("speed", 0))
            elif kind == "error":
                self.alert("A operação falhou", event.get("message", "Erro desconhecido"))
            elif kind == "complete":
                self.status.set_text("Operação concluída com sucesso.")

        def set_progress(self, current: int, total: int, speed: int) -> None:
            fraction = current / total if total else 0
            self.progress.set_fraction(max(0, min(1, fraction)))
            text = f"{fraction * 100:.1f}%"
            if speed:
                text += f" — {format_size(speed)}/s"
            self.progress.set_text(text)

        def cancel_operation(self, _button) -> None:
            if self.process and self.process.poll() is None:
                self.process.send_signal(signal.SIGINT)
                self.status.set_text("Cancelando com segurança…")

        def worker_finished(self, code: int) -> None:
            self.process = None
            self.cancel_button.set_sensitive(False)
            if code != 0:
                self.status.set_text("Operação cancelada ou encerrada com erro.")
            self.update_buttons()
            self.refresh_devices()

    class Application(Gtk.Application):
        def __init__(self) -> None:
            super().__init__(application_id=APP_ID)

        def do_activate(self) -> None:
            window = self.props.active_window or MainWindow(self)
            window.present()

    return Application().run(sys.argv)

import {indicatorState} from './status.js';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import Clutter from 'gi://Clutter';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';


export default class StackOSUpdaterExtension extends Extension {
    enable() {
        this._indicator = new PanelMenu.Button(
            0.0,
            'StackOS Updater'
        );

        this._icon = new St.Icon({
            gicon: this._iconForStatus('yellow'),
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'stackos-updater-shield',
        });

        this._indicator.add_child(this._icon);

        this._statusItem = new PopupMenu.PopupMenuItem(
            'Carregando estado...',
            {
                reactive: false,
                can_focus: false,
            }
        );

        this._indicator.menu.addMenuItem(
            this._statusItem
        );

        const openItem = new PopupMenu.PopupMenuItem(
            'Abrir Atualizações do StackOS'
        );

        openItem.connect('activate', () => {
            Gio.Subprocess.new(
                ['/usr/local/bin/stackos-updater'],
                Gio.SubprocessFlags.NONE
            );
        });

        this._indicator.menu.addMenuItem(openItem);

        this._checking = false;
        const checkItem = new PopupMenu.PopupMenuItem(
            'Buscar atualizações'
        );

        checkItem.connect('activate', () => {
            if (this._checking) return;
            this._checking = true;
            checkItem.setSensitive(false);
            const process = Gio.Subprocess.new(
                [
                    '/usr/lib/stackos/stackos-updater-helper',
                    'check',
                ],
                Gio.SubprocessFlags.STDOUT_PIPE |
                Gio.SubprocessFlags.STDERR_PIPE
            );

            process.communicate_utf8_async(
                null,
                null,
                (proc, result) => {
                    try {
                        if (!this._indicator) return;
                        const [ok, stdout, stderr] =
                            proc.communicate_utf8_finish(result);

                        if (!ok || !proc.get_successful())
                            throw new Error(stderr || 'Falha na busca');

                        const data = JSON.parse(stdout);
                        if (!data || !Array.isArray(data.packages)) throw new Error('Resposta inválida do verificador');
                        data.service_error = '';

                        const path = GLib.build_filenamev([
                            GLib.get_home_dir(),
                            '.cache',
                            'stackos-updater',
                            'status.json',
                        ]);

                        GLib.mkdir_with_parents(GLib.path_get_dirname(path), 0o700);
                        Gio.File.new_for_path(path).replace_contents(
                            new TextEncoder().encode(JSON.stringify(data, null, 2) + '\n'),
                            null, false, Gio.FileCreateFlags.PRIVATE, null
                        );

                        this._refresh();
                    } catch (error) {
                        logError(error);
                        this._setStatus('red', 'Erro na verificação');
                    } finally {
                        this._checking = false;
                        if (this._indicator) checkItem.setSensitive(true);
                    }
                }
            );
        });

        this._indicator.menu.addMenuItem(checkItem);

        Main.panel.addToStatusArea(
            'stackos-updater',
            this._indicator
        );

        this._refresh();
        const cacheDir = GLib.build_filenamev([GLib.get_home_dir(), '.cache', 'stackos-updater']);
        GLib.mkdir_with_parents(cacheDir, 0o700);
        this._monitor = Gio.File.new_for_path(cacheDir).monitor_directory(Gio.FileMonitorFlags.NONE, null);
        this._monitor.connect('changed', () => this._refresh());

        this._timer = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT,
            30,
            () => {
                this._refresh();
                return GLib.SOURCE_CONTINUE;
            }
        );
    }

    _iconForStatus(status) {
        const path = GLib.build_filenamev([this.path, `stackos-updater-${status}.svg`]);

        return new Gio.FileIcon({
            file: Gio.File.new_for_path(path),
        });
    }

    _refresh() {
        const path = GLib.build_filenamev([
            GLib.get_home_dir(),
            '.cache',
            'stackos-updater',
            'status.json',
        ]);

        let data;

        try {
            const [ok, contents] =
                GLib.file_get_contents(path);

            if (!ok)
                throw new Error('Arquivo ausente');

            data = JSON.parse(
                new TextDecoder().decode(contents)
            );
            if (!data || typeof data !== 'object' || !Array.isArray(data.packages))
                throw new Error('Estado inválido');
        } catch (_error) {
            this._setStatus(
                'yellow',
                'Ainda não verificado'
            );
            return;
        }

        this._setStatus(...indicatorState(data));
    }

    _setStatus(status, text) {
        if (!this._icon || !this._statusItem) return;
        this._icon.gicon =
            this._iconForStatus(status);

        this._statusItem.label.text = text;
    }

    disable() {
        if (this._monitor) { this._monitor.cancel(); this._monitor = null; }
        if (this._timer) {
            GLib.source_remove(this._timer);
            this._timer = null;
        }

        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }

        this._icon = null;
        this._statusItem = null;
    }
}

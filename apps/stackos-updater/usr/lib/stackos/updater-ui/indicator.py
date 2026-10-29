#!/usr/bin/python3
"""Indicador do atualizador; evita duplicação com a extensão nativa GNOME."""
import json
import subprocess
from pathlib import Path
import gi
gi.require_version('Gtk','3.0')
gi.require_version('AyatanaAppIndicator3','0.1')
from gi.repository import Gtk, GLib, Gio, AyatanaAppIndicator3 as AI
CACHE=Path.home()/'.cache/stackos-updater/status.json'
ICONS=Path('/usr/lib/stackos/updater-ui/assets')

def state(data):
    if not isinstance(data,dict) or not isinstance(data.get('packages'),list):return 'yellow','Ainda não verificado'
    if data.get('service_error'):return 'red','Erro na verificação'
    if data.get('reboot_required'):return 'red','Reinicialização necessária'
    packages=data['packages'];critical=max(int(data.get('critical_count') or 0),sum(bool(p.get('critical')) for p in packages))
    if critical or data.get('status')=='red':return 'red',f'{critical} atualização(ões) de segurança/crítica(s)'
    if not data.get('checked_at'):return 'yellow','Ainda não verificado'
    if packages:return 'yellow',f'{len(packages)} atualização(ões) disponível(is)'
    if data.get('blocked'):return 'yellow',f"{len(data['blocked'])} pacote(s) bloqueado(s)"
    if data.get('status') not in (None,'green'):return 'yellow','Verificação pendente'
    return 'green','Sistema atualizado'

class Indicator:
    def __init__(self):
        self.indicator=AI.Indicator.new('stackos_updater',str(ICONS/'stackos-updater-yellow.svg'),AI.IndicatorCategory.SYSTEM_SERVICES)
        menu=Gtk.Menu();self.label=Gtk.MenuItem(label='Carregando estado…');self.label.set_sensitive(False);menu.append(self.label)
        item=Gtk.MenuItem(label='Abrir Atualizações do StackOS');item.connect('activate',lambda *_:subprocess.Popen(['/usr/local/bin/stackos-updater']));menu.append(item)
        self.check=Gtk.MenuItem(label='Buscar atualizações');self.check.connect('activate',self.search);menu.append(self.check)
        menu.show_all();self.indicator.set_menu(menu)
        self.bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
        self.refresh();GLib.timeout_add_seconds(5,self.refresh)
    def refresh(self):
        try:data=json.loads(CACHE.read_text())
        except (OSError,ValueError):data=None
        try:color,label=state(data)
        except (TypeError,ValueError):color,label='yellow','Estado inválido; verificar novamente'
        self.label.set_label(label);self.indicator.set_icon_full(str(ICONS/f'stackos-updater-{color}.svg'),label)
        native=False
        try:
            reply=self.bus.call_sync('org.gnome.Shell.Extensions','/org/gnome/Shell/Extensions','org.gnome.Shell.Extensions','GetExtensionInfo',GLib.Variant('(s)',('stackos-updater@stackoslinux',)),None,Gio.DBusCallFlags.NONE,1000,None).unpack()[0]
            native=reply.get('state')==1
        except GLib.Error:pass
        self.indicator.set_status(AI.IndicatorStatus.PASSIVE if native else AI.IndicatorStatus.ACTIVE)
        return True
    def search(self,*_):
        self.check.set_sensitive(False)
        try:
            proc=Gio.Subprocess.new(['/usr/lib/stackos/stackos-updater-helper','check'],Gio.SubprocessFlags.STDOUT_PIPE|Gio.SubprocessFlags.STDERR_PIPE)
            proc.communicate_utf8_async(None,None,self.completed)
        except GLib.Error as error:
            self.label.set_label('Falha na busca: '+str(error));self.check.set_sensitive(True)
    def completed(self,proc,result):
        try:
            ok,out,err=proc.communicate_utf8_finish(result)
            if not ok or not proc.get_successful():raise ValueError(err or 'Falha na consulta')
            data=json.loads(out)
            if not isinstance(data.get('packages'),list):raise ValueError('Resposta inválida')
            data['service_error']='';CACHE.parent.mkdir(parents=True,exist_ok=True)
            temporary=CACHE.with_suffix('.indicator.tmp');temporary.write_text(json.dumps(data,ensure_ascii=False)+'\n');temporary.replace(CACHE)
            self.refresh()
        except (GLib.Error,OSError,ValueError) as error:self.label.set_label('Falha na busca: '+str(error))
        finally:self.check.set_sensitive(True)

if __name__=='__main__':
    indicator=Indicator();Gtk.main()

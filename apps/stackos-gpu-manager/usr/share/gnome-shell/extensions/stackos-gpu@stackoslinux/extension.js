import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
export default class StackOSGpu extends Extension {
 enable() {
  this._button=new PanelMenu.Button(0.0,'StackOS GPU');
  this._icon=new St.Icon({icon_size:20});this._button.add_child(this._icon);
  this._status=new PopupMenu.PopupMenuItem('Uso da GPU: verificando…',{reactive:false});this._button.menu.addMenuItem(this._status);
  this._button.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
  const open=new PopupMenu.PopupMenuItem('Abrir StackOS GPU Manager');open.connect('activate',()=>Gio.Subprocess.new(['/usr/bin/stackos-gpu-manager'],Gio.SubprocessFlags.NONE));this._button.menu.addMenuItem(open);
  const quit=new PopupMenu.PopupMenuItem('Sair do indicador');quit.connect('activate',()=>{Gio.Subprocess.new(['/usr/bin/systemctl','--user','stop','stackos-gpu-indicator.service'],Gio.SubprocessFlags.NONE);this.disable();});this._button.menu.addMenuItem(quit);
  Main.panel.addToStatusArea('stackos-gpu',this._button);
  this._update();this._timer=GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT,2,()=>{this._update();return GLib.SOURCE_CONTINUE;});
 }
 _update() {
  let state={usage_percent:null,level:'unavailable'};
  try {const [ok,bytes]=GLib.file_get_contents(GLib.build_filenamev([GLib.get_home_dir(),'.cache','stackos-gpu-manager','indicator.json']));if(ok) {const value=JSON.parse(new TextDecoder().decode(bytes));if(Date.now()/1000-value.updated_at<15)state=value;}}catch(e){}
  const level=['green','orange','red'].includes(state.level)?state.level:'unavailable';
  this._icon.gicon=Gio.icon_new_for_string(`/usr/share/stackos-gpu-manager/icons/stackos-gpu-${level}.svg`);
  this._status.label.text=state.usage_percent===null?'Uso da GPU: indisponível':`Uso da GPU: ${state.usage_percent}%`;
 }
 disable(){if(this._timer){GLib.source_remove(this._timer);this._timer=0;}this._button?.destroy();this._button=null;this._icon=null;this._status=null;}
}

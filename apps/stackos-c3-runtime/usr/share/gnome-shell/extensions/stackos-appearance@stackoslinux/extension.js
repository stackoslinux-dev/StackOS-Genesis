import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
export default class StackOSAppearance extends Extension {
 enable(){
  this._settings=new Gio.Settings({schema_id:'org.gnome.desktop.interface'});
  this._id=this._settings.connect('changed::color-scheme',()=>this._apply());this._apply();
  this._startupId=Main.layoutManager.connect('startup-complete',()=>this._showDesktop());
  this._desktopTimer=GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT,3,()=>{this._desktopTimer=0;this._showDesktop();return GLib.SOURCE_REMOVE;});
 }
 _showDesktop(){if(this._startupId){Main.layoutManager.disconnect(this._startupId);this._startupId=0;}Main.overview.hide();}
 _apply(){const light=this._settings.get_string('color-scheme')!=='prefer-dark';for(const actor of [Main.panel,Main.uiGroup]){if(light)actor.add_style_class_name('stackos-light');else actor.remove_style_class_name('stackos-light');}}
 disable(){if(this._id)this._settings.disconnect(this._id);if(this._startupId)Main.layoutManager.disconnect(this._startupId);if(this._desktopTimer)GLib.source_remove(this._desktopTimer);this._id=0;this._startupId=0;this._desktopTimer=0;this._settings=null;for(const actor of [Main.panel,Main.uiGroup])actor.remove_style_class_name('stackos-light');}
}

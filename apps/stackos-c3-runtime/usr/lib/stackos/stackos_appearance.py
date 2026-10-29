from pathlib import Path
import sys
import gi
gi.require_version('Gtk','4.0')
gi.require_version('Adw','1')
from gi.repository import Gtk,Gdk,Gio,GLib,Adw
_provider=None
_settings=None
LIGHT="""
window, window.background, .root, .main, .content-area { background-image: none; background-color:#f6f8fc; color:#17223b; }
window label { color:#17223b; }
.header,.chrome,.sidebar,.promo,.hero-banner { background-image:linear-gradient(120deg,#edf2fc,#f9faff); color:#17223b; border-color:#d4deee; }
.card,.panel,.app-card,.package-card,.section-card,.stat-card,.hint,.description,.drop-zone,.drop-area,.status-panel { background-image:none; background-color:#ffffff; color:#17223b; border-color:#cbd8ee; }
window entry,window textview,window textview text,window searchentry { background-color:#ffffff; color:#17223b; border-color:#9eb9e8; }
window button { color:#243a62; }
window button label { color:inherit; }
window button.primary,window .primary,window .suggested-action,window .nav.selected,window .nav.active { color:#ffffff; }
window .primary label,window .suggested-action label,window .nav.selected label,window .nav.active label { color:#ffffff; }
window .muted,window .subtitle,window .brand-sub,window .window-title,window .stackos-signature { color:#526b91; }
window .accent-title { color:#3954e8; }
window .success,window .installed,window .status-good { color:#007f5c; }
"""
def _apply(*args):
 global _provider
 display=Gdk.Display.get_default()
 if display is None:return GLib.SOURCE_CONTINUE
 if _provider is None:
  _provider=Gtk.CssProvider();Gtk.StyleContext.add_provider_for_display(display,_provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+30)
 dark=_settings.get_string('color-scheme')=='prefer-dark'
 Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK if dark else Adw.ColorScheme.FORCE_LIGHT)
 css=Path(sys.argv[0]).resolve().parent/'theme-light.css'
 if not css.exists() and 'usb' in sys.argv[0]:css=Path('/usr/lib/python3/dist-packages/stackos_usb_writer/theme-light.css')
 data=css.read_text() if css.exists() else LIGHT
 data=data.replace('__ASSETS__',(css.parent/'assets').as_uri()).replace('__ACCENT__',getattr(sys.modules.get('__main__'),'CURRENT_ACCENT','#1675d1')).replace('__BORDER__','#c0d2ea')
 _provider.load_from_string('' if dark else data)
 return GLib.SOURCE_REMOVE
def install():
 global _settings
 if _settings is not None:return
 _settings=Gio.Settings.new('org.gnome.desktop.interface');_settings.connect('changed::color-scheme',_apply)
 GLib.idle_add(_apply)

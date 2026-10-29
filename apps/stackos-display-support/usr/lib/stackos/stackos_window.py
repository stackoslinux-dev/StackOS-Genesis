import gi
gi.require_version("Gtk","4.0")
from gi.repository import Gtk,Gdk

def fit_window(window, preferred_width=1000, preferred_height=680):
 from stackos_widget_i18n import translate_window
 translate_window(window)
 window.set_resizable(True)
 window.set_deletable(True)
 display=Gdk.Display.get_default()
 monitors=display.get_monitors() if display else None
 geometry=monitors.get_item(0).get_geometry() if monitors and monitors.get_n_items() else None
 width=min(preferred_width, max(320, geometry.width-64)) if geometry else preferred_width
 height=min(preferred_height, max(240, geometry.height-120)) if geometry else preferred_height
 window.set_size_request(0,0)
 window.set_default_size(width,height)
 content_api=hasattr(window,'get_content') and hasattr(window,'set_content')
 prop='content' if content_api else 'child'
 def viewport(*_):
  bar=window.get_titlebar()
  if isinstance(bar,Gtk.HeaderBar):
   bar.set_show_title_buttons(True)
   bar.set_decoration_layout(":minimize,maximize,close")
  if getattr(window,'_stackos_fitting',False):return
  child=window.get_content() if content_api else window.get_child()
  if child is None or child is getattr(window,'_stackos_viewport',None):return
  window._stackos_fitting=True
  try:
   if content_api:window.set_content(None)
   else:window.set_child(None)
   scroll=Gtk.ScrolledWindow()
   scroll.set_policy(Gtk.PolicyType.AUTOMATIC,Gtk.PolicyType.AUTOMATIC)
   scroll.set_propagate_natural_width(False)
   scroll.set_propagate_natural_height(False)
   scroll.set_child(child)
   window._stackos_viewport=scroll
   if content_api:window.set_content(scroll)
   else:window.set_child(scroll)
  finally:window._stackos_fitting=False
 window.connect('notify::'+prop,viewport)
 viewport()
 return width,height

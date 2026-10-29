import weakref
from gi.repository import Gtk
from stackos_i18n import get_translator

def translate_window(window):
 translate=get_translator('stackos')
 def attach(widget):
  if getattr(widget,'_stackos_i18n_attached',False):return
  widget._stackos_i18n_attached=True
  def change_label(obj,*args):
   source=obj.get_label()
   if not source:return
   target=translate(source)
   if source!=target:obj.set_label(target)
  if isinstance(widget,Gtk.Label):
   change_label(widget);widget.connect('notify::label',change_label)
  if isinstance(widget,Gtk.Entry):
   def placeholder(obj,*args):
    source=obj.get_placeholder_text() or ''
    if not source:return
    target=translate(source)
    if source!=target:obj.set_placeholder_text(target)
   placeholder(widget);widget.connect('notify::placeholder-text',placeholder)
  if isinstance(widget,Gtk.Window):
   source=widget.get_title() or '';target=translate(source) if source else source
   if source!=target:widget.set_title(target)
  # Listen for newly added widgets; no continuous polling or render loop.
  model=widget.observe_children()
  widget._stackos_i18n_children=model
  def added(children,position,removed,count):
   for index in range(position,position+count):attach(children.get_item(index))
  model.connect('items-changed',added)
  for index in range(model.get_n_items()):attach(model.get_item(index))
 attach(window)

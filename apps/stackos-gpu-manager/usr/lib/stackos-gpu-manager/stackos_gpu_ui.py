#!/usr/bin/env python3
"""StackOS GPU Manager: interface moderna, usando os serviços e preferências existentes."""
import os,sys,math,json,re,threading,configparser,unicodedata
from pathlib import Path
import weakref
os.environ.setdefault('GSK_RENDERER','cairo')
import gi
gi.require_version('Gtk','4.0');gi.require_version('Adw','1');gi.require_version('GdkPixbuf','2.0')
from gi.repository import Gtk,Adw,Gdk,Gio,GLib,Pango,GdkPixbuf

import sys as _appearance_sys
_appearance_sys.path.insert(0, '/usr/lib/stackos')
import stackos_appearance
import stackos_window
stackos_appearance.install()
from legacy_gpu_ui import AppCard as LegacyAppCard,detect_visual_layout,short_gpu_name,main_temperature
from stackos_gpu_sources import merged_gpu_state
from stackos_gpu_manager_core import build_state
from stackos_gpu_preferences import PreferencesStore,default_config_path
from stackos_gpu_metrics import metrics
BASE=Path(__file__).resolve().parent;ASSETS=BASE/'assets'
PALETTES={'amd':{'accent':'#ef454f','border':'#683443','vendor':'AMD'},'nvidia':{'accent':'#83cc28','border':'#365b2c','vendor':'NVIDIA'},'intel':{'accent':'#149cff','border':'#244e79','vendor':'Intel'}}
CURRENT_ACCENT='#149cff'
VECTOR_WIDGETS=weakref.WeakKeyDictionary()
VECTOR_PATHS={
 'temperature-symbolic':'<path d="M14 5a3 3 0 0 1 6 0v13a6 6 0 1 1-6 0z"/><path d="M17 10v13"/><circle cx="17" cy="24" r="2" fill="currentColor"/>',
 'view-filter-symbolic':'<path d="M6 9h22M10 16h14M14 23h6"/>',
 'view-grid-symbolic':'<rect x="4" y="4" width="10" height="10" rx="3" fill="currentColor"/><rect x="20" y="4" width="10" height="10" rx="3" fill="currentColor"/><rect x="4" y="20" width="10" height="10" rx="3" fill="currentColor"/><rect x="20" y="20" width="10" height="10" rx="3" fill="currentColor"/>',
 'computer-symbolic':'<rect x="9" y="9" width="16" height="16" rx="3"/><rect x="13" y="13" width="8" height="8" rx="1"/><path d="M13 4v5m8-5v5m-8 16v5m8-5v5M4 13h5m-5 8h5m16-8h5m-5 8h5"/>',
 'stackos-layers':'<path d="m4 10 13-7 13 7-13 7z" fill="currentColor"/><path d="m4 18 13 7 13-7M4 25l13 7 13-7"/>'}
CATEGORIES=['Todos','Jogos','Internet','Multimídia','Escritório','Sistema','Outros']
def clean(s):return ''.join(c for c in unicodedata.normalize('NFKD',s.casefold()) if not unicodedata.combining(c))
def lab(text,css=None,wrap=False):
 x=Gtk.Label(label=str(text));x.set_xalign(0)
 if css:x.add_css_class(css)
 if wrap:x.set_wrap(True);x.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
 return x

def vector_paintable(name,color):
 svg=('<svg xmlns="http://www.w3.org/2000/svg" width="34" height="34" viewBox="0 0 34 34"><g fill="none" stroke="'+color+'" color="'+color+'" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'+VECTOR_PATHS[name]+'</g></svg>')
 stream=Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(svg.encode()));pix=GdkPixbuf.Pixbuf.new_from_stream(stream,None);return Gdk.Texture.new_for_pixbuf(pix)
def icon(name,size=24):
 if name=='utilities-system-monitor-symbolic':name='computer-symbolic'
 if name in VECTOR_PATHS:
  w=Gtk.Image.new_from_paintable(vector_paintable(name,CURRENT_ACCENT));VECTOR_WIDGETS[w]=name
 else:w=Gtk.Image.new_from_icon_name(name)
 w.set_pixel_size(size);return w

def image(name,size):
 w=Gtk.Image.new_from_file(str(ASSETS/name));w.set_pixel_size(size);return w

def box(vertical=True,spacing=8,css=None):
 w=Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL,spacing=spacing)
 if css:w.add_css_class(css)
 return w

def category(app):
 cats=''
 try:
  p=configparser.ConfigParser(interpolation=None,strict=False);p.read(app.get('path',''),encoding='utf8');cats=p.get('Desktop Entry','Categories',fallback='')
 except (OSError,configparser.Error):pass
 words=set(cats.split(';'))
 for ids,name in [({'Game'},'Jogos'),({'Network','WebBrowser'},'Internet'),({'AudioVideo','Audio','Video'},'Multimídia'),({'Office'},'Escritório'),({'System','Settings','Utility'},'Sistema')]:
  if words&ids:return name
 return 'Outros'

def category_caption(app):
 n=clean(app.get('name',''))
 for match,label in [('blender','Criação 3D'),('obs','Gravação'),('resolve','Edição de vídeo'),('code','Desenvolvimento'),('gimp','Edição de imagem'),('chatgpt','Produtividade')]:
  if match in n:return label
 return app.get('_category','Outros')

def sort_apps(apps):
 preferred=['firefox','steam','discord','blender','obs','davinci','calculator','calculador','calendar','visual studio code','chatgpt','gimp','libreoffice']
 def key(a):
  n=clean(a.get('name',''));rank=next((i for i,s in enumerate(preferred) if s in n),len(preferred));return rank,n
 for a in apps:a['_category']=category(a)
 return sorted(apps,key=key)

class Gauge(Gtk.Picture):
 def __init__(self,title,color):
  super().__init__();self.title=title;self.color=color;self.set_size_request(100,108);self.set_can_shrink(True);self.set_content_fit(Gtk.ContentFit.CONTAIN);self.update(None)
 def update(self,value,suffix='',maximum=100):
  ratio=0 if value is None else max(0,min(1,float(value)/maximum));txt='—' if value is None else f'{value:.0f}{suffix}'
  arc=2*math.pi*60*.75;circ=2*math.pi*60
  foreground=f'<circle cx="80" cy="78" r="60" fill="none" stroke="url(#g)" stroke-width="12" stroke-linecap="round" stroke-dasharray="{arc*ratio} {circ}" transform="rotate(135 80 78)"/>' if value is not None and ratio>0 else ''
  svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="160" height="150" viewBox="0 0 160 150"><defs><linearGradient id="g"><stop stop-color="{self.color}"/><stop offset="1" stop-color="#8f45ff"/></linearGradient></defs><circle cx="80" cy="78" r="60" fill="none" stroke="#1b2b48" stroke-width="12" stroke-linecap="round" stroke-dasharray="{arc} {circ}" transform="rotate(135 80 78)"/>{foreground}<text x="80" y="88" font-family="DejaVu Sans" font-size="27" font-weight="bold" text-anchor="middle" fill="#f7faff">{txt}</text><text x="80" y="116" font-family="DejaVu Sans" font-size="9" text-anchor="middle" fill="#bacce8">{self.title}</text></svg>'''
  if stackos_appearance._settings.get_string('color-scheme')!='prefer-dark':svg=svg.replace('#f7faff','#17223b').replace('#bacce8','#526b91').replace('#1b2b48','#c5d2e8')
  stream=Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(svg.encode()));pix=GdkPixbuf.Pixbuf.new_from_stream(stream,None);self.set_paintable(Gdk.Texture.new_for_pixbuf(pix))

class Card(LegacyAppCard):
 def __init__(self,app_data,store,available,status,launch_status):
  Gtk.Frame.__init__(self);self.add_css_class('app-card');self.app_data=app_data;self.store=store;self.status_callback=status;self.launch_status_callback=launch_status;self.loading=True
  self.options=['Automático','GPU padrão']+(['Alto desempenho'] if available else [])
  content=box(spacing=14);head=box(False,10)
  iv=app_data.get('icon') or 'application-x-executable-symbolic'
  app_icon=Gtk.Image.new_from_file(iv) if Path(iv).is_absolute() and Path(iv).is_file() else icon(iv,43)
  app_icon.set_pixel_size(43);app_icon.set_size_request(43,43);head.append(app_icon)
  text=box(spacing=4);text.set_hexpand(True);name=lab(app_data.get('name',app_data['desktop_id']),'heading');name.set_ellipsize(Pango.EllipsizeMode.END);name.set_max_width_chars(24);name.set_tooltip_text(app_data.get('name'));text.append(name);text.append(lab(category_caption(app_data),'category'));head.append(text)
  menu=Gtk.MenuButton();menu.set_icon_name('view-more-symbolic');menu.add_css_class('more-button');menu.set_valign(Gtk.Align.START)
  pop=Gtk.Popover();pb=box();pb.set_margin_top(10);pb.set_margin_bottom(10);pb.set_margin_start(12);pb.set_margin_end(12)
  ident=lab(app_data['desktop_id'],'muted',True);ident.set_max_width_chars(28);pb.append(ident)
  reset=Gtk.Button(label='Usar seleção automática');reset.connect('clicked',lambda *_:self.reset_auto());pb.append(reset);pop.set_child(pb);menu.set_popover(pop);head.append(menu);content.append(head)
  controls=box(False,9);self.dropdown=Gtk.DropDown(model=Gtk.StringList.new(['Automático','GPU Padrão']+(['GPU Dedicada'] if available else [])));self.dropdown.set_hexpand(True)
  pref=store.get_preference(app_data['desktop_id']) or {};sel=1 if pref.get('source')=='manual' and pref.get('selection')=='role:default' else 2 if pref.get('source')=='manual' and pref.get('selection')=='role:discrete' and available else 0
  self.dropdown.set_selected(sel);controls.append(self.dropdown)
  self.open_button=Gtk.Button();self.open_button.set_child(icon('media-playback-start-symbolic',18));self.open_button.add_css_class('app-launch');self.open_button.set_tooltip_text('Abrir aplicativo com a GPU selecionada');self.open_button.connect('clicked',self.on_open);controls.append(self.open_button);content.append(controls);self.set_child(content)
  self.loading=False;self.mark_selection();self.dropdown.connect('notify::selected',self.changed)
 def reset_auto(self):
  old=self.dropdown.get_selected();self.dropdown.set_selected(0)
  if old==0:self.changed(self.dropdown,None)
 def changed(self,d,p):
  LegacyAppCard.on_changed(self,d,p);self.mark_selection()
 def mark_selection(self):
  if self.dropdown.get_selected()==2:self.add_css_class('dedicated')
  else:self.remove_css_class('dedicated')

class AppsView(Gtk.Box):
 def __init__(self,apps,store,available):
  super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=17);self.add_css_class('main-area');self.store=store;self.available=available;self.apps=sort_apps(apps);self.page=0;self.per_page=9;self.columns=3;self.category='Todos';self.manual_only=False;self.query='';self.cards=[]
  top=box(False,12);glyph=icon('view-grid-symbolic',38);glyph.add_css_class('brand-sub');top.append(glyph)
  title=box(spacing=4);title.set_hexpand(True);title.append(lab('Aplicativos','page-title'));title.append(lab('Gerencie qual GPU cada aplicativo deve usar','muted'));top.append(title)
  self.search=Gtk.SearchEntry();self.search.set_placeholder_text('Pesquisar aplicativos…');self.search.set_size_request(210,-1);self.search.add_css_class('search');self.search.connect('search-changed',self.on_search);top.append(self.search)
  filterbtn=Gtk.MenuButton();filterbtn.set_child(icon('view-filter-symbolic',20));filterbtn.add_css_class('icon-button');filterbtn.set_tooltip_text('Filtrar aplicativos');pop=Gtk.Popover();pb=box();pb.set_margin_top(12);pb.set_margin_bottom(12);pb.set_margin_start(12);pb.set_margin_end(12)
  cb=Gtk.CheckButton(label='Somente preferências manuais');cb.connect('toggled',self.on_manual);pb.append(cb);pop.set_child(pb);filterbtn.set_popover(pop);top.append(filterbtn);self.append(top)
  tabs=box(False,5);self.tabs={}
  for name in CATEGORIES:
   b=Gtk.Button(label=name);b.add_css_class('tab');b.connect('clicked',lambda _,n=name:self.set_category(n));tabs.append(b);self.tabs[name]=b
  self.tabs['Todos'].add_css_class('active');self.append(tabs)
  self.status=lab('As preferências atuais foram preservadas.','status-line');self.append(self.status)
  self.scroller=Gtk.ScrolledWindow();self.scroller.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);self.scroller.set_vexpand(True)
  self.grid=Gtk.Grid(column_spacing=18,row_spacing=16);self.grid.set_column_homogeneous(True);self.grid.set_row_homogeneous(True);self.grid.set_hexpand(True);self.scroller.set_child(self.grid);self.append(self.scroller)
  footer=box(False,26);footer.set_halign(Gtk.Align.CENTER);self.prev=Gtk.Button();self.prev.set_child(icon('go-previous-symbolic',18));self.prev.add_css_class('pager');self.prev.connect('clicked',lambda *_:self.turn(-1));footer.append(self.prev)
  self.page_label=lab('','heading');footer.append(self.page_label);self.next=Gtk.Button();self.next.set_child(icon('go-next-symbolic',18));self.next.add_css_class('pager');self.next.add_css_class('next');self.next.connect('clicked',lambda *_:self.turn(1));footer.append(self.next);self.append(footer);self.refresh()
 def on_search(self,e):self.query=clean(e.get_text().strip());self.page=0;self.refresh()
 def on_manual(self,b):self.manual_only=b.get_active();self.page=0;self.refresh()
 def set_category(self,c):
  self.category=c;self.page=0
  for n,b in self.tabs.items():b.add_css_class('active') if n==c else b.remove_css_class('active')
  self.refresh()
 def matches(self,a):return (not self.query or self.query in clean(a.get('name','')) or self.query in clean(a['desktop_id'])) and (self.category=='Todos' or a['_category']==self.category) and (not self.manual_only or self.store.get_source(a['desktop_id'])=='manual')
 def refresh(self):
  while self.grid.get_first_child():self.grid.remove(self.grid.get_first_child())
  filtered=[a for a in self.apps if self.matches(a)];self.filtered=filtered;pages=max(1,math.ceil(len(filtered)/self.per_page));self.page=max(0,min(self.page,pages-1));self.cards=[]
  for i,a in enumerate(filtered[self.page*self.per_page:(self.page+1)*self.per_page]):
   c=Card(a,self.store,self.available,self.saved,self.launched);c.set_hexpand(True);c.set_vexpand(True);c.set_size_request(195,125);self.grid.attach(c,i%self.columns,i//self.columns,1,1);self.cards.append(c)
  if not filtered:self.grid.attach(lab('Nenhum aplicativo encontrado.','muted'),0,0,1,1)
  self.page_label.set_text(f'Página {self.page+1} de {pages}');self.prev.set_sensitive(self.page>0);self.next.set_sensitive(self.page+1<pages)
 def turn(self,n):self.page+=n;self.refresh()
 def saved(self,text):self.status.set_text('Preferência salva: '+text)
 def launched(self,text):self.status.set_text(text)

class Telemetry(Gtk.Box):
 def __init__(self,color):
  super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=12);self.add_css_class('right-area');self.set_size_request(268,-1)
  self.state=self.panel('Estado da GPU','utilities-system-monitor-symbolic');rings=box(False,8);rings.set_homogeneous(True);self.temp=Gauge('TEMPERATURA',color);self.usage=Gauge('USO DA GPU','#8151f9');rings.append(self.temp);rings.append(self.usage);self.state.append(rings)
  self.bars={};self.values={}
  for k,title in [('vram','VRAM'),('clock','Clock'),('power','Energia')]:
   row=box(False,8);key=lab(title,'field-key');key.set_size_request(54,-1);row.append(key);bar=Gtk.ProgressBar();bar.set_hexpand(True);bar.set_valign(Gtk.Align.CENTER);bar.add_css_class('metric-bar');
   if k=='clock':bar.add_css_class('purple')
   row.append(bar);value=lab('—','field-value');value.set_xalign(1);value.set_size_request(80,-1);row.append(value);self.state.append(row);self.bars[k]=bar;self.values[k]=value
  self.hardware=self.panel('Hardware','computer-symbolic');self.fields={}
  for k,title in [('name','Nome'),('pci','PCI'),('vendor','Vendor'),('device','Device'),('driver','Driver'),('render','Render'),('drm','DRM'),('switcheroo','Switcheroo')]:
   row=box(False,12);row.append(lab(title,'field-key'));v=lab('—','field-value');v.set_hexpand(True);v.set_xalign(1);v.set_ellipsize(Pango.EllipsizeMode.MIDDLE);v.set_max_width_chars(28);row.append(v);self.hardware.append(row);self.fields[k]=v
  self.sensors=self.panel('Sensores','temperature-symbolic');self.sensor_rows={}
  self.note=lab('','warning',True);self.append(self.note)
 def panel(self,title,ico):
  p=box(spacing=10,css='panel');heading=box(False,10);i=icon(ico,22);i.add_css_class('brand-sub');heading.append(i);text=lab(title,'panel-title');text.set_hexpand(True);heading.append(text);heading.append(icon('pan-down-symbolic',12));p.append(heading);self.append(p);return p
 def update(self,gpu,m,available):
  if getattr(self,'last_pci',None)!=gpu.get('pci_address'):
   child=self.sensors.get_first_child().get_next_sibling()
   while child:
    nxt=child.get_next_sibling();self.sensors.remove(child);child=nxt
   self.sensor_rows={};self.last_pci=gpu.get('pci_address')
  t=main_temperature(gpu);self.temp.update(t,' °C',110);self.usage.update(m.get('usage'),' %')
  used=m.get('vram_used');total=m.get('vram_total');clock=m.get('clock_mhz');power=m.get('power_w')
  self.values['vram'].set_text(f'{used/1024**3:.1f} / {total/1024**3:.1f} GB' if used is not None and total else 'N/D');self.bars['vram'].set_fraction(min(1,used/total) if used is not None and total else 0)
  self.values['clock'].set_text(f'{clock/1000:.2f} GHz' if clock is not None else 'N/D');self.bars['clock'].set_fraction(min(1,clock/3000) if clock is not None else 0)
  self.values['power'].set_text(f'{power:.0f} W' if power is not None else 'N/D');self.bars['power'].set_fraction(min(1,power/300) if power is not None else 0)
  vals={'name':short_gpu_name(gpu),'pci':gpu.get('pci_address'),'vendor':gpu.get('vendor_id'),'device':gpu.get('device_id'),'driver':gpu.get('driver'),'render':', '.join(gpu.get('render_nodes') or []),'drm':'Disponível' if gpu.get('card') else 'Indisponível','switcheroo':'Disponível' if gpu.get('switcheroo') else 'Indisponível'}
  for k,v in vals.items():self.fields[k].set_text(v or 'N/D');self.fields[k].set_tooltip_text(v or 'Não informado')
  for sensor in gpu.get('temperature_sensors',[]):
   name=sensor.get('label') or sensor.get('sensor') or 'GPU'
   if name not in self.sensor_rows:
    r=box(False,8);r.append(lab(name,'field-key'));v=lab('','field-value');v.set_size_request(58,-1);r.append(v);bar=Gtk.ProgressBar();bar.set_hexpand(True);bar.set_valign(Gtk.Align.CENTER);bar.add_css_class('metric-bar');r.append(bar);self.sensors.append(r);self.sensor_rows[name]=(v,bar)
   v,b=self.sensor_rows[name];value=sensor.get('temperature_c');v.set_text(f'{value:.1f} °C' if value is not None else 'N/D');b.set_fraction(max(0,min(1,value/110)) if value is not None else 0)
  self.note.set_text('A seleção de alto desempenho depende de uma GPU alternativa e do serviço Switcheroo.' if not available else 'Preferências por aplicativo disponíveis. A seleção automática segue a política existente.')

def signature_link():
    link=Gtk.LinkButton.new_with_label('https://github.com/stackoslinux-dev','StackOS Linux · GitHub')
    link.set_tooltip_text('Autoria: StackOS Linux <stackoslinux@gmail.com>')
    link.add_css_class('stackos-signature')
    link.set_halign(Gtk.Align.START)
    return link

class GPUManagerWindow(Adw.ApplicationWindow):
 def __init__(self,app,qa=False):
  super().__init__(application=app,title='StackOS GPU Manager');stackos_window.fit_window(self);self.add_css_class('gpu-modern');self.qa=qa;self.closed=False;self.busy=False;self.provider=None;self.navbuttons={};self.visual_layout=None
  self.connect('close-request',self.on_close);Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
  config=BASE.parent/'qa/preferences.json' if qa else default_config_path();self.store=PreferencesStore(config);self.store.load();core=build_state(config);self.gpus=merged_gpu_state();self.gpu=self.pick(self.gpus);self.high_available=self.performance(core);self.apply_theme(detect_visual_layout(self.gpus))
  outer=box(spacing=0);self.set_content(outer);self.chrome=box(False,20,css='chrome');outer.append(self.chrome);self.build_header()
  body=box(False,0);body.set_vexpand(True);outer.append(body);self.sidebar=self.build_sidebar();body.append(self.sidebar)
  self.stack=Gtk.Stack();self.stack.set_hexpand(True);self.stack.set_vexpand(True);self.apps=AppsView(core.get('applications',[]),self.store,self.high_available);self.stack.add_named(self.apps,'apps');self.stack.add_named(self.info_page('Estado da GPU',True),'state');self.stack.add_named(self.info_page('Detalhes do hardware',False),'details');self.stack.add_named(self.settings_page(),'settings');self.stack.add_named(self.about_page(),'about');body.append(self.stack)
  rs=Gtk.ScrolledWindow();rs.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);rs.set_size_request(284,-1);self.telemetry=Telemetry(self.palette['accent']);rs.set_child(self.telemetry);body.append(rs);self.right_scroll=rs
  self.last_layout=None;self.add_tick_callback(self.responsive);self.update_metrics(self.gpus,metrics(self.gpu));self.timer=GLib.timeout_add_seconds(3,self.refresh_async)
  if qa:GLib.timeout_add(1200,self.capture)
 def responsive(self,*_):
  w,h=self.get_width(),self.get_height()
  if w<1:return True
  columns=3 if w>=1200 else 2;rows=4 if h>=920 else 3;layout=(columns,rows,w>=1200)
  if layout!=self.last_layout:
   first=self.apps.page*self.apps.per_page;self.apps.columns=columns;self.apps.per_page=columns*rows;self.apps.page=first//self.apps.per_page;self.apps.refresh();self.right_scroll.set_visible(w>=1200);self.last_layout=layout
  return True
 def pick(self,gpus):
  preferred={'amd':'0x1002','nvidia':'0x10de','intel':'0x8086'}.get(detect_visual_layout(gpus))
  return next((g for g in gpus if g.get('vendor_id')==preferred),gpus[0] if gpus else {})
 def performance(self,core):
  s=core.get('switcheroo',{});return bool(core.get('dual_gpu') and s.get('available') and (s.get('num_gpus') or 0)>1)
 def apply_theme(self,layout):
  global CURRENT_ACCENT
  CURRENT_ACCENT=PALETTES[layout]['accent']
  for w,name in list(VECTOR_WIDGETS.items()):w.set_from_paintable(vector_paintable(name,CURRENT_ACCENT))
  self.visual_layout=layout;self.palette=PALETTES[layout];css=(BASE/'theme.css').read_text().replace('__ASSETS__',ASSETS.as_uri()).replace('__ACCENT__',self.palette['accent']).replace('__BORDER__',self.palette['border']);p=Gtk.CssProvider();p.load_from_string(css)
  if self.provider:Gtk.StyleContext.remove_provider_for_display(self.get_display(),self.provider)
  Gtk.StyleContext.add_provider_for_display(self.get_display(),p,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);self.provider=p
 def build_header(self):
  self.chrome.append(image('stackos-symbol.png',54));brand=box(spacing=0);brand.set_size_request(145,-1);brand.append(lab('STACKOS','brand-title'));brand.append(lab('GPU MANAGER','brand-sub'));self.chrome.append(brand);sep=Gtk.Separator(orientation=Gtk.Orientation.VERTICAL);sep.set_margin_top(8);sep.set_margin_bottom(8);self.chrome.append(sep)
  gpu=box(spacing=3);gpu.set_hexpand(True);self.gpu_name=lab(short_gpu_name(self.gpu),'gpu-name');self.gpu_name.set_ellipsize(Pango.EllipsizeMode.END);self.gpu_name.set_tooltip_text(short_gpu_name(self.gpu));gpu.append(self.gpu_name);self.vendor=lab({'0x1002':'AMD','0x10de':'NVIDIA','0x8086':'Intel'}.get(self.gpu.get('vendor_id'),'GPU virtual / outro'),'vendor');gpu.append(self.vendor);self.chrome.append(gpu);self.metrics_header={}
  for key,caption,ico in [('temp','TEMPERATURA','temperature-symbolic'),('driver','DRIVER','preferences-system-symbolic'),('mode','MODO','stackos-layers')]:
   metric=box(False,10,css='metric');glyph=icon(ico,30);glyph.add_css_class('brand-sub');metric.append(glyph);txt=box(spacing=3);v=lab('—','metric-value');txt.append(v);txt.append(lab(caption,'metric-caption'));metric.append(txt);self.chrome.append(metric);self.metrics_header[key]=v
  controls=box(False,8);controls.set_margin_start(10)
  for action,text,tip in [('minimize','−','Minimizar'),('maximize','□','Maximizar/restaurar'),('close','×','Fechar janela; manter indicador ativo')]:
   b=Gtk.Button(label=text);b.add_css_class('control');b.set_tooltip_text(tip)
   if action=='close':b.add_css_class('close')
   b.connect('clicked',lambda _,a=action:self.control(a));controls.append(b)
  self.chrome.append(controls)
 def control(self,action):
  if action=='minimize':self.minimize()
  elif action=='maximize':self.unmaximize() if self.is_maximized() else self.maximize()
  else:self.close()
 def build_sidebar(self):
  side=box(spacing=18,css='sidebar');side.set_size_request(220,-1);nav=box(spacing=2,css='navigation');side.append(nav)
  for key,name,desc,ico in [('apps','Aplicativos','Gerencie a GPU por aplicativo','view-grid-symbolic'),('state','Estado da GPU','Sensores e desempenho','utilities-system-monitor-symbolic'),('details','Detalhes','Informações do hardware','computer-symbolic'),('settings','Configurações','Preferências e regras','preferences-system-symbolic'),('about','Sobre','StackOS GPU Manager','help-about-symbolic')]:
   b=Gtk.Button();b.add_css_class('nav-item');r=box(False,15);i=icon(ico,30);r.append(i);t=box(spacing=5);t.set_hexpand(True);t.append(lab(name,'nav-title'));sub=lab(desc,'nav-sub');sub.set_ellipsize(Pango.EllipsizeMode.END);sub.set_max_width_chars(21);t.append(sub);r.append(t);b.set_child(r);b.connect('clicked',lambda _,k=key:self.navigate(k));nav.append(b);self.navbuttons[key]=b
  self.navbuttons['apps'].add_css_class('selected');promo=box(spacing=6,css='promo');promo.set_vexpand(True);spacer=box();spacer.set_vexpand(True);spacer.set_size_request(-1,45);promo.append(spacer);logo=image('stackos-symbol.png',48);logo.set_halign(Gtk.Align.START);promo.append(logo);promo.append(lab('STACKOS','promo-name'));promo.append(lab('GPU MANAGER','promo-sub'));copy=lab('Controle total da sua GPU\nMais desempenho\nem suas mãos.','promo-copy');copy.set_margin_top(12);promo.append(copy);side.append(promo);side.append(signature_link());return side
 def navigate(self,key):
  self.stack.set_visible_child_name(key)
  for n,b in self.navbuttons.items():b.add_css_class('selected') if n==key else b.remove_css_class('selected')
 def info_page(self,title,state):
  p=box(spacing=20,css='main-area');p.append(lab(title,'page-title'));p.append(lab('Informações reais fornecidas pelo kernel e pelo serviço Switcheroo.','muted',True));self.info_labels=getattr(self,'info_labels',[]);detail=lab('','field-value',True);detail.set_selectable(True);p.append(detail);self.info_labels.append(detail);return p
 def settings_page(self):
  p=box(spacing=18,css='main-area');p.append(lab('Configurações','page-title'));p.append(lab('As regras de escolha de GPU e o formato das preferências são os mesmos da versão instalada.','muted',True));p.append(lab('Arquivo de preferências','heading'));config=lab(str(self.store.path),'field-value',True);config.set_selectable(True);p.append(config)
  p.append(lab('Identidade automática','heading'));p.append(lab('AMD → vermelho\nNVIDIA → verde\nIntel → azul\nPrioridade mantida: NVIDIA, AMD, Intel.','field-value',True));b=Gtk.Button(label='Atualizar lista de aplicativos');b.add_css_class('settings-button');b.set_halign(Gtk.Align.START);b.connect('clicked',self.reload_apps);p.append(b);return p
 def about_page(self):
  p=box(spacing=18,css='main-area');im=image('stackos-symbol.png',110);im.set_halign(Gtk.Align.START);p.append(im);p.append(lab('StackOS GPU Manager','page-title'));p.append(lab('Controle a GPU utilizada pelos aplicativos.','heading'));p.append(lab('Interface GTK4 modernizada. Detecção, preferências, resolução de GPU, execução e indicador do sistema preservados. Métricas indisponíveis são apresentadas como N/D.','muted',True));return p
 def reload_apps(self,*_):
  try:self.store.load();core=build_state(self.store.path);self.apps.apps=sort_apps(core.get('applications',[]));self.apps.available=self.performance(core);self.apps.refresh();self.apps.status.set_text('Lista e preferências atualizadas.')
  except Exception as e:self.apps.status.set_text('Não foi possível atualizar: '+str(e))
 def update_metrics(self,gpus,m):
  if self.closed:return False
  self.gpus=gpus;self.gpu=self.pick(gpus);layout=detect_visual_layout(gpus)
  if layout!=self.visual_layout:self.apply_theme(layout);self.telemetry.temp.color=self.palette['accent']
  self.gpu_name.set_text(short_gpu_name(self.gpu));self.vendor.set_text({'0x1002':'AMD','0x10de':'NVIDIA','0x8086':'Intel'}.get(self.gpu.get('vendor_id'),'GPU virtual / outro'));t=main_temperature(self.gpu);self.metrics_header['temp'].set_text(f'{t:.0f} °C' if t is not None else 'N/D');self.metrics_header['driver'].set_text(self.gpu.get('driver') or 'N/D');sw=self.gpu.get('switcheroo') or {};self.metrics_header['mode'].set_text('VIRTUAL' if (self.gpu.get('driver') or '').startswith('virtio') else 'DEDICADA' if sw.get('discrete') else 'INTEGRADA' if gpus else 'N/D');self.telemetry.update(self.gpu,m,self.high_available)
  text='\n\n'.join(short_gpu_name(g)+'\n'+'\n'.join(f'{k}: {v}' for k,v in g.items() if k not in ('temperature_sensors','switcheroo'))+'\nSwitcheroo: '+str(g.get('switcheroo'))+'\nSensores: '+'; '.join(f"{t.get('label')}: {t.get('temperature_c')} °C" for t in g.get('temperature_sensors',[])) for g in gpus)
  for l in self.info_labels:l.set_text(text)
  self.busy=False;return False
 def refresh_async(self):
  if self.closed:return False
  if self.busy:return True
  self.busy=True
  def worker():
   try:gpus=merged_gpu_state();m=metrics(self.pick(gpus));GLib.idle_add(self.update_metrics,gpus,m)
   except Exception:GLib.idle_add(self.reset_busy)
  threading.Thread(target=worker,daemon=True).start();return True
 def reset_busy(self):self.busy=False;return False
 def on_close(self,*_):
  self.closed=True
  if self.timer:GLib.source_remove(self.timer);self.timer=None
  return False
 def capture(self):
  try:
   paintable=Gtk.WidgetPaintable.new(self.get_content());snap=Gtk.Snapshot();paintable.snapshot(snap,self.get_content().get_width(),self.get_content().get_height());node=snap.to_node()
   if node is None:raise RuntimeError('Nenhum conteúdo renderizado.')
   texture=self.get_native().get_renderer().render_texture(node,None);qa=BASE.parent/'qa';qa.mkdir(exist_ok=True);texture.save_to_png(str(qa/'gpu-manager.png'))
   (qa/'state.json').write_text(json.dumps({'theme':self.visual_layout,'gpu':self.gpu,'available':self.high_available,'applications':len(self.apps.apps),'cards':len(self.apps.cards),'size':[self.get_width(),self.get_height()]},ensure_ascii=False,indent=2));print('RENDER_OK',flush=True)
  except Exception as e:print('RENDER_ERROR',repr(e),flush=True)
  self.close();return False

class GPUManagerApp(Adw.Application):
 def __init__(self,qa=False):super().__init__(application_id='org.stackos.GPUManager' if not qa else 'org.stackos.GPUManager.Preview',flags=Gio.ApplicationFlags.NON_UNIQUE if qa else Gio.ApplicationFlags.DEFAULT_FLAGS);self.qa=qa;marker=Gio.SimpleAction.new_stateful('ui-build',None,GLib.Variant('s','modern-photo2'));self.add_action(marker)
 def do_activate(self):
  w=self.get_active_window()
  if w is None:w=GPUManagerWindow(self,self.qa)
  w.present()
def ensure_indicator():
 try:
  bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
  bus.call_sync('org.freedesktop.systemd1','/org/freedesktop/systemd1','org.freedesktop.systemd1.Manager','StartUnit',GLib.Variant('(ss)',('stackos-gpu-indicator.service','replace')),None,Gio.DBusCallFlags.NONE,5000,None)
 except GLib.Error as exc:print('Indicador:',exc.message,file=sys.stderr)
def main():
 qa='--qa' in sys.argv
 if not qa:ensure_indicator()
 return GPUManagerApp(qa).run([sys.argv[0]])
if __name__=='__main__':raise SystemExit(main())

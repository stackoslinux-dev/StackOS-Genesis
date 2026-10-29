#!/usr/bin/python3
import os,sys,json,subprocess
from pathlib import Path
os.environ.setdefault('GSK_RENDERER','cairo')
import gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,Gdk,Gio,GLib,Pango

import sys as _appearance_sys
_appearance_sys.path.insert(0, '/usr/lib/stackos')
import stackos_appearance
import stackos_window
stackos_appearance.install()
import state
BASE=Path(__file__).resolve().parent

def box(vertical=True,spacing=10,css=''):
 w=Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL,spacing=spacing)
 for c in css.split():w.add_css_class(c)
 return w

def label(text,css='',wrap=False):
 w=Gtk.Label(label=str(text),xalign=0,wrap=wrap)
 if wrap:w.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
 for c in css.split():w.add_css_class(c)
 return w

def image(name,size=24):
 w=Gtk.Image.new_from_file(str(BASE/'assets'/name)) if (BASE/'assets'/name).exists() else Gtk.Image.new_from_icon_name(name)
 w.set_pixel_size(size);return w

def button(text,callback,css='',ico=None):
 b=Gtk.Button();r=box(False,10)
 if ico:r.append(image(ico,22))
 r.append(label(text));b.set_child(r);b.connect('clicked',callback)
 for c in css.split():b.add_css_class(c)
 return b

def signature_link():
    link=Gtk.LinkButton.new_with_label('https://github.com/stackoslinux-dev','StackOS Linux · GitHub')
    link.set_tooltip_text('Autoria: StackOS Linux <stackoslinux@gmail.com>')
    link.add_css_class('stackos-signature')
    link.set_halign(Gtk.Align.START)
    return link

class Welcome(Gtk.Application):
 def __init__(self,qa=False):
  super().__init__(application_id='com.stackos.welcome' if not qa else 'com.stackos.welcome.Preview',flags=Gio.ApplicationFlags.DEFAULT_FLAGS if not qa else Gio.ApplicationFlags.NON_UNIQUE)
  self.qa=qa;self.win=None;self.current=0;self.switching=False;self.config_root=BASE.parent/'qa/config' if qa else None;self.system=state.system_info();self.guide=json.loads((BASE/'guide.json').read_text())
 def do_activate(self):
  if self.win:self.win.present();return
  provider=Gtk.CssProvider();provider.load_from_data((BASE/'theme.css').read_text().replace('__ASSETS__',(BASE/'assets').as_uri()).encode());Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
  self.win=Gtk.ApplicationWindow(application=self,title='Bem-vindo ao StackOS');stackos_window.fit_window(self.win);self.win.set_icon_name('org.stackos.Welcome');self.win.add_css_class('welcome');self.win.connect('close-request',self.on_close)
  bar=Gtk.HeaderBar();bar.add_css_class('chrome');bar.set_title_widget(label('Bem-vindo ao StackOS','window-title'));self.win.set_titlebar(bar)
  root=box(spacing=0,css='root');self.win.set_child(root);body=box(False,0);body.set_vexpand(True);root.append(body)
  side=box(spacing=13,css='brand-panel');side.set_size_request(210,-1);body.append(side);side.append(image('stackos-symbol.png',94));side.append(label('StackOS\nGenesis','brand-title'));side.append(label('Modular.\nLeve.\nPoderoso.','brand-copy'));side.append(Gtk.Separator());self.home_button=button('Boas-vindas',lambda *_:self.home(),'nav selected','go-home-symbolic');side.append(self.home_button);self.guide_button=button('Guia do StackOS',lambda *_:self.open_guide(0),'nav','help-browser-symbolic');side.append(self.guide_button);sp=box();sp.set_vexpand(True);side.append(sp);side.append(label(self.system['display'],'system-version',True));side.append(label(self.system['arch'],'system-version'))
  self.stack=Gtk.Stack();self.stack.set_hhomogeneous(False);self.stack.set_vhomogeneous(False);self.stack.set_hexpand(True);self.stack.set_vexpand(True);body.append(self.stack)
  self.build_home();self.build_guide()
  footer=box(False,12,css='footer');self.startup=Gtk.CheckButton(label='Mostrar ao iniciar o computador');self.startup.set_active(state.startup_enabled(self.config_root));self.startup.connect('toggled',self.startup_changed);footer.append(self.startup);sp=box();sp.set_hexpand(True);footer.append(sp);self.startup_button=button('Desativar início automático' if self.startup.get_active() else 'Reativar início automático',lambda *_:self.startup.set_active(not self.startup.get_active()),'secondary');footer.append(signature_link());footer.append(self.startup_button);root.append(footer)
  self.status=label('Você pode reabrir este guia pelo menu de aplicativos.','status',True);root.append(self.status);self.win.present()
  if self.qa:
   if os.environ.get('STACKOS_WELCOME_QA_PAGE'):self.open_guide(int(os.environ['STACKOS_WELCOME_QA_PAGE']))
   GLib.timeout_add(1000,self.capture)
 def build_home(self):
  scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);self.stack.add_named(scroll,'home');page=box(spacing=16,css='content');scroll.set_child(page)
  badge=label('Seja bem-vindo','welcome-badge');badge.set_halign(Gtk.Align.CENTER);page.append(badge);title=label('StackOS Genesis','hero-title',True);title.set_halign(Gtk.Align.CENTER);page.append(title);sub=label('Modular. Leve. Poderoso.','hero-sub');sub.set_halign(Gtk.Align.CENTER);page.append(sub)
  intro=box(False,20,css='intro-card');intro.append(image('layers.svg',110));texts=box(spacing=10);texts.set_hexpand(True);texts.append(label('Bem-vindo ao '+self.system['display']+'!','intro-title',True));texts.append(label('Conheça seu sistema, instale seus aplicativos e configure o hardware com as ferramentas do StackOS. O guia abaixo acompanha seus primeiros passos.','muted',True));intro.append(texts);page.append(intro)
  grid=Gtk.Grid(column_spacing=12,row_spacing=12,column_homogeneous=True,row_homogeneous=True);page.append(grid)
  items=[('Loja de Apps','Instale e gerencie\nseus aplicativos','store.svg',lambda:self.launch_app('store'),'blue'),('Drivers','Gerencie seu\nhardware','drivers.svg',lambda:self.launch_app('drivers'),'purple'),('Site Oficial','Conheça o projeto\ne suas novidades','web.svg',lambda:self.open_link('site'),'blue'),('Documentação','Tutoriais, referências\ne guia integrado','docs.svg',lambda:self.open_guide(0),'purple'),('Fórum','Participe da\ncomunidade','forum.svg',lambda:self.open_link('forum'),'green'),('Contato','Fale com a equipe\ndo StackOS','contact.svg',lambda:self.open_link('contact'),'gold')]
  for i,(name,copy,ico,callback,color) in enumerate(items):
   b=Gtk.Button();b.add_css_class('tile');b.add_css_class(color);row=box(False,12);row.append(image(ico,50));t=box(spacing=6);t.set_hexpand(True);t.append(label(name,'tile-title'));t.append(label(copy,'tile-copy',True));row.append(t);row.append(image('go-next-symbolic',18));b.set_child(row);b.connect('clicked',lambda _,fn=callback:fn());grid.attach(b,i%2,i//2,1,1)
  begin=button('Começar a usar o StackOS',lambda *_:self.open_guide(0),'primary','media-playback-start-symbolic');begin.set_halign(Gtk.Align.CENTER);page.append(begin)
  facts=box(False,16,css='facts');facts.set_homogeneous(True)
  for ico,text in [('computer-symbolic',self.system['base']),('view-grid-symbolic','Sistema modular\ne personalizável'),('help-browser-symbolic','Guia e ferramentas\ndo StackOS')]:r=box(False,9);r.append(image(ico,26));r.append(label(text,'fact-copy',True));facts.append(r)
  page.append(facts)
 def build_guide(self):
  container=box(spacing=0);self.stack.add_named(container,'guide');sc=Gtk.ScrolledWindow();sc.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);sc.set_vexpand(True);container.append(sc);self.guide_content=box(spacing=18,css='content');sc.set_child(self.guide_content)
  self.guide_progress=Gtk.ProgressBar();container.append(self.guide_progress);controls=box(False,12,css='guide-controls');self.previous=button('Anterior',lambda *_:self.open_guide(self.current-1),'secondary','go-previous-symbolic');controls.append(self.previous);self.page_indicator=label('','muted');self.page_indicator.set_hexpand(True);self.page_indicator.set_xalign(.5);controls.append(self.page_indicator);self.next_button=button('Próximo',self.next_page,'primary','go-next-symbolic');controls.append(self.next_button);container.append(controls)
 def home(self):
  self.stack.set_visible_child_name('home');self.home_button.add_css_class('selected');self.guide_button.remove_css_class('selected')
 def open_guide(self,index):
  self.current=max(0,min(index,len(self.guide)-1));topic=self.guide[self.current];self.stack.set_visible_child_name('guide');self.home_button.remove_css_class('selected');self.guide_button.add_css_class('selected')
  while self.guide_content.get_first_child():self.guide_content.remove(self.guide_content.get_first_child())
  heading=box(False,16);heading.append(image(topic['icon'],55));heading.append(label(topic['title'],'guide-title',True));self.guide_content.append(heading);self.guide_content.append(label(topic['intro'],'muted',True))
  for n,text in enumerate(topic['steps'],1):r=box(False,14,css='step');r.append(label(str(n),'step-number'));r.append(label(text,'step-copy',True));self.guide_content.append(r)
  if topic.get('image'):
   frame=box(css='screenshot');tools=box(False,10);caption=label('Imagem real da interface · exemplo de uso','image-caption');caption.set_hexpand(True);tools.append(caption);tools.append(button('Ampliar imagem',lambda *_:self.enlarge_image(topic['image']),'secondary','view-fullscreen-symbolic'));frame.append(tools);pic=Gtk.Picture.new_for_filename(str(BASE/'assets'/topic['image']));pic.set_can_shrink(True);pic.set_content_fit(Gtk.ContentFit.CONTAIN);pic.set_size_request(-1,220);frame.append(pic);self.guide_content.append(frame)
  actions=box(False,12);actions.append(button(topic['action_label'],lambda *_:self.launch_app(topic['action']),'primary'));actions.append(button('Documentação on-line',lambda *_:self.open_link('docs'),'secondary'));self.guide_content.append(actions)
  self.previous.set_sensitive(self.current>0);self.page_indicator.set_text(f'{self.current+1} de {len(self.guide)} · Guia do StackOS');self.next_button.get_child().get_last_child().set_text('Concluir guia' if self.current==len(self.guide)-1 else 'Próximo');self.guide_progress.set_fraction((self.current+1)/len(self.guide))
 def enlarge_image(self,name):
  window=Gtk.Window(title='Interface do StackOS',transient_for=self.win,modal=True,default_width=1000,default_height=740);window.add_css_class('welcome');header=Gtk.HeaderBar();header.add_css_class('chrome');window.set_titlebar(header);pic=Gtk.Picture.new_for_filename(str(BASE/'assets'/name));pic.set_can_shrink(True);pic.set_content_fit(Gtk.ContentFit.CONTAIN);window.set_child(pic);window.present();return window
 def next_page(self,*_):
  if self.current==len(self.guide)-1:self.status.set_text('Guia concluído. Seu StackOS está à disposição — volte quando precisar.');self.home()
  else:self.open_guide(self.current+1)
 def startup_changed(self,check):
  if self.switching:return
  enabled=check.get_active()
  try:
   state.set_startup(enabled,self.config_root);self.startup_button.get_child().get_last_child().set_text('Desativar início automático' if enabled else 'Reativar início automático');self.status.set_text('Esta tela será mostrada nos próximos logins.' if enabled else 'Início automático desativado. Você ainda pode abrir pelo menu Bem-vindo ao StackOS.')
  except OSError as e:
   self.switching=True;check.set_active(not enabled);self.switching=False;self.status.set_text('Não foi possível salvar a preferência: '+str(e))
 def launch_app(self,key):
  try:subprocess.Popen(state.APPS[key],start_new_session=True);self.status.set_text('Aplicativo aberto. Você pode voltar ao guia quando quiser.')
  except (OSError,KeyError) as e:self.status.set_text('Não foi possível abrir o aplicativo: '+str(e))
 def open_link(self,key):
  try:Gtk.show_uri(self.win,state.LINKS[key],Gdk.CURRENT_TIME);self.status.set_text('Link aberto no aplicativo padrão.')
  except (GLib.Error,KeyError) as e:self.status.set_text('Não foi possível abrir o link: '+str(e))
 def on_close(self,*_):self.win=None;return False
 def capture(self):
  snap=Gtk.Snapshot();paint=Gtk.WidgetPaintable.new(self.win);paint.snapshot(snap,self.win.get_width(),self.win.get_height());texture=self.win.get_renderer().render_texture(snap.to_node(),None);out=BASE.parent/'qa';out.mkdir(exist_ok=True);texture.save_to_png(str(out/('guide-preview.png' if self.stack.get_visible_child_name()=='guide' else 'preview.png')));print('RENDER_OK',self.win.get_width(),self.win.get_height(),flush=True);self.win.close();return False

def main(argv=None):
 argv=sys.argv if argv is None else argv
 if '--autostart' in argv and not state.startup_enabled():return 0
 return Welcome('--qa' in argv).run([argv[0]])
if __name__=='__main__':raise SystemExit(main())

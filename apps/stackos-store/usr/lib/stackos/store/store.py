#!/usr/bin/python3
import os,sys,json,threading,subprocess,re,urllib.parse
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
import backend,online
BASE=Path(__file__).resolve().parent
CATS=['Início','Instalados','Internet','Desenvolvimento','Multimídia','Office','Sistema','Jogos','Jogos Nativos','Segurança','Atualizações','Backups']
ICONS=['go-home-symbolic','folder-download-symbolic','web-browser-symbolic','applications-engineering-symbolic','video-x-generic-symbolic','x-office-document-symbolic','emblem-system-symbolic','applications-games-symbolic','input-gaming-symbolic','security-high-symbolic','software-update-available-symbolic','drive-harddisk-symbolic']
def box(vertical=True,spacing=10,css=''):
 w=Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL,spacing=spacing)
 for c in css.split():w.add_css_class(c)
 return w
def label(text,css='',wrap=False):
 w=Gtk.Label(label=str(text),xalign=0,wrap=wrap)
 if wrap:w.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
 for c in css.split():w.add_css_class(c)
 return w
def icon(name,size=24):
 if Path(name).is_absolute() and Path(name).is_file():w=Gtk.Image.new_from_file(name)
 elif (BASE/'assets'/name).is_file():w=Gtk.Image.new_from_file(str(BASE/'assets'/name))
 elif (Path('/usr/share/stackos-store/icons')/(name+'.svg')).is_file():w=Gtk.Image.new_from_file(str(Path('/usr/share/stackos-store/icons')/(name+'.svg')))
 else:
  theme=Gtk.IconTheme.get_for_display(Gdk.Display.get_default());w=Gtk.Image.new_from_icon_name(name if name and theme.has_icon(name) else 'application-x-executable-symbolic')
 w.set_pixel_size(size);return w
def button(text,callback,css='',ico=None):
 b=Gtk.Button();r=box(False,9)
 if ico:r.append(icon(ico,19))
 r.append(label(text));b.set_child(r);b.connect('clicked',callback)
 for c in css.split():b.add_css_class(c)
 return b

def atomic_json(path,data):
 import tempfile
 path.parent.mkdir(parents=True,exist_ok=True);fd,name=tempfile.mkstemp(dir=path.parent,prefix='.'+path.name)
 try:
  with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
  os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)

def signature_link():
    link=Gtk.LinkButton.new_with_label('https://github.com/stackoslinux-dev','StackOS Linux · GitHub')
    link.set_tooltip_text('Autoria: StackOS Linux <stackoslinux@gmail.com>')
    link.add_css_class('stackos-signature')
    link.set_halign(Gtk.Align.START)
    return link

class Store(Gtk.Application):
 def __init__(self,qa=False):
  super().__init__(application_id='com.stackos.store' if not qa else 'com.stackos.store.Preview',flags=Gio.ApplicationFlags.DEFAULT_FLAGS if not qa else Gio.ApplicationFlags.NON_UNIQUE)
  self.qa=qa;self.updater_data=None;self.checking_updates=False
  if qa:os.environ['STACKOS_STORE_ICON_CACHE']=str(BASE.parent/'qa/icons')
  self.win=None;self.catalog=None;self.category='Início';self.query='';self.busy=False;self.loading=False;self.page=0;self.per_page=24;self.search_timer=None;self.generation=0;self.closed=False;self.detail_app=None;self.snapshot=None;self.pending_plan=None;self.pulse_timer=None
  self.votes_path=BASE.parent/'qa/votes.json' if qa else Path.home()/'.config/stackos-store/votes.json'
  self.votes={}
  try:
   saved=json.loads(self.votes_path.read_text())
   if isinstance(saved,dict):
    for pkg,value in saved.items():
     if not isinstance(value,dict):continue
     try:self.votes[pkg]={'up':max(0,int(value.get('up',0))),'down':max(0,int(value.get('down',0))),'mine':value.get('mine') if value.get('mine') in ('up','down') else None}
     except (ValueError,TypeError):continue
  except (OSError,ValueError):pass
 def do_activate(self):
  if self.win:self.win.present();return
  p=Gtk.CssProvider();css=(BASE/'theme.css').read_text().replace('__ASSETS__',(BASE/'assets').as_uri());p.load_from_data(css.encode());Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),p,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
  self.win=Gtk.ApplicationWindow(application=self,title='StackOS Store');stackos_window.fit_window(self.win);self.win.set_icon_name('org.stackos.Store');self.win.add_css_class('store');self.win.connect('close-request',self.on_close);self.win.connect('notify::is-active',self.focus_changed)
  bar=Gtk.HeaderBar();bar.add_css_class('chrome');bar.set_title_widget(label('StackOS Store','window-title'));self.win.set_titlebar(bar)
  root=box(spacing=0,css='root');self.win.set_child(root);header=box(False,18,'header');header.append(icon('store.svg',52));t=box(spacing=4);t.append(label('StackOS Store','brand-title'));t.append(label('POWERED BY MOSA','brand-sub'));header.append(t)
  self.search=Gtk.SearchEntry(placeholder_text='Buscar aplicativos, jogos, ferramentas…');self.search.set_hexpand(True);self.search.connect('search-changed',self.search_changed);header.append(self.search);self.online_button=button('Internet',lambda *_:self.online_search(),'secondary','web-browser-symbolic');header.append(self.online_button);header.append(button('.deb',lambda *_:self.url_dialog(),'secondary','package-x-generic-symbolic'));header.append(button('Atualizar catálogo',lambda *_:self.refresh_indices(),'secondary','view-refresh-symbolic'));root.append(header)
  body=box(False,0);body.set_vexpand(True);root.append(body);sidebar_scroll=Gtk.ScrolledWindow();sidebar_scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);sidebar_scroll.set_size_request(200,-1);sidebar=box(spacing=5,css='sidebar');sidebar_scroll.set_child(sidebar);body.append(sidebar_scroll);self.nav={}
  for cat,ico in zip(CATS,ICONS):b=button(cat,lambda _,c=cat:self.navigate(c),'nav',ico);sidebar.append(b);self.nav[cat]=b
  sp=box();sp.set_vexpand(True);sidebar.append(sp);promo=box(spacing=8,css='promo');promo.append(icon('store.svg',62));promo.append(label('StackOS Store','section-title'));promo.append(label('Aplicativos DEB nativos.\nModular. Leve. Poderoso.','muted',True));sidebar.append(promo);sidebar.append(signature_link())
  self.stack=Gtk.Stack();self.stack.set_hhomogeneous(False);self.stack.set_vhomogeneous(False);self.stack.set_hexpand(True);self.stack.set_vexpand(True);body.append(self.stack)
  self.scroll=Gtk.ScrolledWindow();self.scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);self.stack.add_named(self.scroll,'catalog');self.detail_scroll=Gtk.ScrolledWindow();self.detail_scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);self.stack.add_named(self.detail_scroll,'detail')
  footer=box(False,12,'footer');self.progress=Gtk.ProgressBar();self.progress.set_size_request(140,-1);self.progress.set_visible(False);footer.append(self.progress);self.status=label('Carregando aplicativos dos repositórios…','muted',True);self.status.set_hexpand(True);footer.append(self.status);root.append(footer)
  self.navigate('Início');self.win.present();self.load_catalog()
 def task(self,fn,done):
  def worker():
   try:value=fn();GLib.idle_add(done,value,None)
   except Exception as e:GLib.idle_add(done,None,str(e))
  threading.Thread(target=worker,daemon=True).start()
 def load_catalog(self):
  if self.loading:return
  self.loading=True
  self.task(backend.Catalog,self.loaded)
 def loaded(self,catalog,error):
  if self.closed:return False
  self.loading=False
  if error:self.status.set_text('Não foi possível carregar o catálogo: '+error);return False
  self.catalog=catalog
  try:self.dpkg_stamp=Path('/var/lib/dpkg/status').stat().st_mtime_ns
  except OSError:self.dpkg_stamp=None
  self.status.set_text(f'{len(catalog.apps)} aplicativos · {sum(a["installed"] for a in catalog.apps.values())} instalados · Snap bloqueado');self.show_backups() if self.category=='Backups' else self.show_updates() if self.category=='Atualizações' else self.render()
  self.check_updates()
  if self.qa:GLib.timeout_add(1000,self.capture)
  return False
 def focus_changed(self,*_):
  if self.win and self.win.is_active() and self.catalog and not self.busy and not self.loading:
   try:
    if Path('/var/lib/dpkg/status').stat().st_mtime_ns!=getattr(self,'dpkg_stamp',None):self.load_catalog()
   except OSError:pass
 def navigate(self,category):
  self.category=category;self.page=0;self.detail_app=None;self.stack.set_visible_child_name('catalog')
  for c,b in self.nav.items():b.add_css_class('selected') if c==category else b.remove_css_class('selected')
  if category=='Atualizações':self.show_updates();return
  if category=='Backups':self.show_backups();return
  self.render()
 def search_changed(self,entry):
  self.query=entry.get_text().strip();self.page=0
  if self.search_timer:GLib.source_remove(self.search_timer)
  self.search_timer=GLib.timeout_add(300,self.apply_search)
 def apply_search(self):self.search_timer=None;self.render();return False
 def render(self):
  if not self.catalog:
   p=box(css='content');p.append(label('Preparando seu catálogo DEB…','page-title'));p.append(label('Lendo APT e AppStream, sem instalar ou alterar pacotes.','muted'));self.scroll.set_child(p);return
  self.stack.set_visible_child_name('catalog');page=box(spacing=18,css='content');self.scroll.set_child(page)
  if self.category=='Início' and not self.query:
   hero=box(False,20,'hero');t=box(spacing=10);t.set_hexpand(True);t.append(label('D E S C U B R A','hero-kicker'));t.append(label('Aplicativos para um\nStackOS ainda melhor','hero-title'));t.append(label('Navegadores, ferramentas, jogos e produtividade.\nPacotes DEB dos seus repositórios, em um só lugar.','hero-copy',True));hero.append(t);hero.append(icon('laptop.svg',210));page.append(hero)
   cats=box(False,8)
   for cat in ['Todos','Internet','Desenvolvimento','Multimídia','Office']:cats.append(button(cat,lambda _,c=cat:self.navigate('Início' if c=='Todos' else c),'category'))
   page.append(cats)
  top=box(False,10);heading='Instalados' if self.category=='Instalados' else 'Aplicativos em destaque' if self.category=='Início' and not self.query else 'Resultados da pesquisa' if self.query else self.category;title=label(heading,'section-title');title.set_hexpand(True);top.append(title)
  self.packages_toggle=Gtk.CheckButton(label='Incluir pacotes e ferramentas');self.packages_toggle.set_active(getattr(self,'include_packages',False));self.packages_toggle.connect('toggled',self.package_filter);top.append(self.packages_toggle);page.append(top)
  cat='Todos' if self.category in ('Início','Instalados','Atualizações','Backups') else self.category;installed=self.category=='Instalados';query=self.query;cat='Todos' if query else cat;include=getattr(self,'include_packages',False);generation=self.generation=self.generation+1
  if include and query:
   self.task(lambda:self.catalog.search(query,cat,installed,True),lambda apps,error:self.search_results(page,apps,error,generation))
  else:self.search_results(page,self.catalog.search(query,cat,installed),None,generation)
 def package_filter(self,toggle):self.include_packages=toggle.get_active();self.page=0;self.render()
 def search_results(self,page,apps,error,generation):
  if self.closed or generation!=self.generation:return False
  if error:page.append(label(error,'muted',True));return False
  self.results=apps;total=len(apps);pages=max(1,(total+self.per_page-1)//self.per_page);self.page=min(self.page,pages-1)
  page.append(label(f'{total} resultado(s) · catálogo C3','muted'));grid=Gtk.FlowBox();grid.set_selection_mode(Gtk.SelectionMode.NONE);grid.set_min_children_per_line(1);grid.set_max_children_per_line(4);grid.set_column_spacing(12);grid.set_row_spacing(12);grid.set_homogeneous(True)
  for app in apps[self.page*self.per_page:(self.page+1)*self.per_page]:grid.append(self.card(app))
  page.append(grid)
  if not apps:page.append(label('Nenhum resultado no catálogo local. Use Internet para pesquisar em fontes oficiais.','muted',True))
  pager=box(False,15);pager.set_halign(Gtk.Align.CENTER);prev=button('Anterior',lambda *_:self.turn_page(-1));prev.set_sensitive(self.page>0);pager.append(prev);pager.append(label(f'Página {self.page+1} de {pages}','muted'));nxt=button('Próxima',lambda *_:self.turn_page(1));nxt.set_sensitive(self.page+1<pages);pager.append(nxt);page.append(pager)
  if self.query:page.append(button('Pesquisar também na internet',lambda *_:self.online_search(),'secondary','web-browser-symbolic'))
  return False
 def turn_page(self,delta):self.page+=delta;self.render();self.scroll.get_vadjustment().set_value(0)
 def card(self,app):
  card=box(spacing=10,css='app-card');card.set_size_request(180,-1);head=box(False,10);head.append(icon(app['icon'],48));sp=box();sp.set_hexpand(True);head.append(sp);head.append(button('⋮',lambda *_:self.open_detail(app),'more'));card.append(head)
  name=label(app['name'],'app-name');name.set_ellipsize(Pango.EllipsizeMode.END);name.set_max_width_chars(23);name.set_tooltip_text(app['name']);card.append(name)
  summary=label(app['summary'],'muted',True);summary.set_lines(2);summary.set_ellipsize(Pango.EllipsizeMode.END);summary.set_max_width_chars(27);summary.set_wrap_mode(Pango.WrapMode.WORD_CHAR);card.append(summary)
  card.append(label('↑ Atualização disponível' if app.get('upgradable') else ('✓ Instalado · C3' if app.get('system_native') else '✓ Instalado · DEB') if app['installed'] else 'DEB · Repositório','installed' if app['installed'] else 'package-label'))
  votes=self.votes.get(app['pkg'],{});card.append(label(f"👍 {votes.get('up',0)}   👎 {votes.get('down',0)} · votos locais",'vote-caption'))
  action='Remover' if app['installed'] else 'Instalar';b=button(action,lambda *_:self.prepare_action(app),'remove' if app['installed'] else 'install','user-trash-symbolic' if app['installed'] else 'folder-download-symbolic');b.set_sensitive(not self.busy and (not app['protected'] if app['installed'] else app['can_install']));card.append(b);return card
 def open_detail(self,app):
  self.detail_app=app;page=box(spacing=18,css='content');page.append(button('Voltar',lambda *_:self.stack.set_visible_child_name('catalog'),'secondary','go-previous-symbolic'));top=box(False,20);top.append(icon(app['icon'],88));t=box(spacing=8);t.append(label(app['name'],'page-title'));t.append(label(app['summary'],'muted',True));top.append(t);page.append(top)
  page.append(label(app['description'],'description-text',True));page.append(label(f"Pacote: {app['pkg']}\nOrigem: {app['source']}\nVersão instalada: {app['version'] or 'Não instalado'}\nVersão disponível: {app['candidate'] or 'Não disponível'}\nLicença no AppStream: {app['license']}\nFormato: DEB nativo\nDownload: {app['size']/1024**2:.1f} MB" if app['size'] is not None else f"Pacote: {app['pkg']}\nOrigem: {app['source']}",'muted',True))
  actions=box(False,10);b=button('Desinstalar' if app['installed'] else 'Instalar',lambda *_:self.prepare_action(app),'remove' if app['installed'] else 'install');b.set_sensitive(not self.busy and (not app['protected'] if app['installed'] else app['can_install']));actions.append(b)
  if app.get('upgradable'):actions.append(button('Ver atualizações',lambda *_:self.navigate('Atualizações'),'install'))
  if app['desktop'] and app['installed']:actions.append(button('Abrir',lambda *_:self.launch_app(app),'secondary'))
  if app['url'].startswith('https://'):actions.append(button('Site do projeto',lambda *_:Gtk.show_uri(self.win,app['url'],Gdk.CURRENT_TIME),'secondary'))
  page.append(actions)
  if app['protected']:page.append(label('A remoção deste componente essencial está bloqueada.','error',True))
  votes=box(False,10);votes.append(label('Sua avaliação neste PC','muted'));votes.append(button('👍 Gostei',lambda *_:self.do_vote(app,'up')));votes.append(button('👎 Não gostei',lambda *_:self.do_vote(app,'down')));page.append(votes);self.detail_scroll.set_child(page);self.stack.set_visible_child_name('detail')
 def do_vote(self,app,kind):
  self.votes[app['pkg']]=backend.vote(self.votes,app['pkg'],kind)
  try:atomic_json(self.votes_path,self.votes);self.status.set_text('Avaliação local salva.');self.open_detail(app)
  except OSError as e:self.status.set_text(str(e))
 def launch_app(self,app):
  path=Path('/usr/share/applications')/app['desktop']
  try:
   desktop=Gio.DesktopAppInfo.new_from_filename(str(path))
   if not desktop:raise RuntimeError('Atalho de abertura não encontrado.')
   desktop.launch([],None)
  except Exception as e:self.status.set_text(str(e))
 def set_busy(self,value,message=''):
  self.busy=value;self.progress.set_visible(value)
  if message:self.status.set_text(message)
  if value and self.pulse_timer is None:self.pulse_timer=GLib.timeout_add(150,self.pulse)
  elif not value and self.pulse_timer is not None:GLib.source_remove(self.pulse_timer);self.pulse_timer=None
 def pulse(self):
  if self.busy and not self.closed:self.progress.pulse();return True
  self.pulse_timer=None;return False
 def prepare_action(self,app):
  if self.busy:return
  action='remove' if app['installed'] else 'install';self.set_busy(True,'Conferindo dependências e plano do APT…');self.task(lambda:backend.simulate(action,app['pkg']),self.plan_ready)
 def plan_ready(self,plan,error):
  self.set_busy(False)
  if error:self.status.set_text(error);return False
  dialog=Gtk.Window(title='Revisar operação',transient_for=self.win,modal=True,default_width=700,default_height=460);page=box(spacing=16,css='content root');dialog.set_child(page);page.append(label(('Instalar ' if plan['action']=='install' else 'Desinstalar ')+plan['package'],'section-title'));page.append(label('Confira as alterações de dependências previstas pelo APT. O sistema pedirá autenticação.','muted',True));view=Gtk.TextView(editable=False,monospace=True,wrap_mode=Gtk.WrapMode.WORD_CHAR);view.get_buffer().set_text('\n'.join(plan['changes']) or 'Nenhuma alteração necessária.');scroll=Gtk.ScrolledWindow();scroll.set_vexpand(True);scroll.set_child(view);page.append(scroll);row=box(False,10);row.append(button('Cancelar',lambda *_:dialog.close()));row.append(button('Confirmar',lambda *_:(dialog.close(),self.execute(plan)),'remove' if plan['action']=='remove' else 'install'));page.append(row);dialog.present();return False
 def execute(self,plan):
  if self.busy:return
  self.set_busy(True,'Aguarde a autenticação e a operação do APT…')
  self.task(lambda:self.run_helper([plan['action'],plan['package'],plan['digest']]),self.executed)
 def run_helper(self,args):
  command=['pkexec','/usr/lib/stackos/store/helper.py',*args];p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace');lines=[]
  for raw in p.stdout:
   line=raw.strip();lines.append(line);lines=lines[-800:]
   if line.startswith('pmstatus:'):
    fields=line.split(':',3)
    try:GLib.idle_add(self.progress.set_fraction,max(0,min(1,float(fields[2])/100)))
    except (ValueError,IndexError):pass
  code=p.wait();return {'code':code,'output':'\n'.join(lines)[-60000:]}
 def executed(self,result,error):
  self.set_busy(False)
  if error or result['code']!=0:self.status.set_text('Operação não concluída: '+(error or result['output'][-600:]))
  else:self.status.set_text('Operação concluída. Atualizando os aplicativos instalados.');self.load_catalog()
  return False
 def refresh_indices(self):
  if self.busy:return
  dialog=Gtk.MessageDialog(transient_for=self.win,modal=True,buttons=Gtk.ButtonsType.YES_NO,text='Atualizar o catálogo APT?',secondary_text='Os índices dos repositórios configurados serão atualizados com autenticação. Nenhum aplicativo será instalado automaticamente.')
  def response(d,r):
   d.destroy()
   if r==Gtk.ResponseType.YES:self.set_busy(True,'Atualizando índices dos repositórios…');self.task(lambda:self.run_helper(['refresh']),self.executed)
  dialog.connect('response',response);dialog.present()
 def online_search(self):
  if not self.query:self.status.set_text('Digite o nome do aplicativo na busca para pesquisar na internet.');self.search.grab_focus();return
  self.status.set_text('Pesquisando em fontes oficiais na internet…');query=self.query;generation=self.online_generation=getattr(self,'online_generation',0)+1;self.task(lambda:online.search(query),lambda result,error:self.online_results(result,error) if generation==self.online_generation and not self.closed else False)
 def online_results(self,result,error):
  if self.closed:return False
  page=box(spacing=15,css='content');page.append(label('Pesquisa na internet','page-title'));self.scroll.set_child(page);self.stack.set_visible_child_name('catalog')
  if error:page.append(label('Não foi possível pesquisar: '+error,'error',True));return False
  page.append(label(result['note'],'muted',True));page.append(button('Ver pesquisa oficial no navegador',lambda *_:Gtk.show_uri(self.win,result['search_url'],Gdk.CURRENT_TIME),'secondary'))
  for item in result['items']:
   row=box(False,12,'online-row');t=box(spacing=6);t.set_hexpand(True);t.append(label(item.get('name',item['pkg']),'section-title'));t.append(label(item['source'],'muted'));row.append(t)
   local=self.catalog.lookup(item['pkg']) if self.catalog else None
   if local:row.append(button('Ver / instalar DEB',lambda _,a=local:self.open_detail(a),'install'))
   elif item.get('download'):row.append(button('Baixar .deb',lambda _,i=item:self.download(i),'install','folder-download-symbolic'))
   else:row.append(button('Baixar .deb',lambda _,i=item:self.download(i),'install','folder-download-symbolic'))
   page.append(row)
  if not result['items']:page.append(label('Nenhum resultado nesta fonte. Tente o nome usado pelo projeto.','muted',True))
  self.status.set_text(f"{len(result['items'])} resultado(s) em fontes oficiais.");return False
 def package_download(self,item):
  # Se não há índice local, o diretório oficial mostra a versão e os mirrors.
  Gtk.show_uri(self.win,item['url'],Gdk.CURRENT_TIME)
  self.status.set_text('Página oficial aberta. Você também pode colar um link HTTPS de .deb para baixar pela loja.')
  self.url_dialog(item['url'])
 def url_dialog(self,page_url=''):
  dialog=Gtk.Window(title='Baixar pacote DEB',transient_for=self.win,modal=True,default_width=650);p=box(spacing=15,css='content root');dialog.set_child(p);p.append(label('Link HTTPS direto para o .deb','section-title'));p.append(label('Use o endereço de download informado pelo projeto ou pelo diretório oficial. A origem será exibida antes da instalação.','muted',True));entry=Gtk.Entry(placeholder_text='https://…/aplicativo.deb');p.append(entry);p.append(button('Baixar e conferir',lambda *_:(dialog.close(),self.download({'download':entry.get_text(),'name':'Pacote DEB'})),'install'));dialog.present()
 def download(self,item):
  if self.busy:return
  self.set_busy(True,'Baixando '+item.get('name',item.get('pkg','pacote'))+'…');self.task(lambda:online.download_deb(online.resolve_deb(item),progress=lambda done,total:GLib.idle_add(self.status.set_text,f'Download: {done/1024**2:.1f} MB'+(f' de {total/1024**2:.1f} MB' if total else ''))),self.downloaded)
 def downloaded(self,data,error):
  self.set_busy(False)
  if error:self.status.set_text('Não foi possível baixar: '+error);return False
  dialog=Gtk.Window(title='Revisar DEB baixado',transient_for=self.win,modal=True,default_width=700);p=box(spacing=16,css='content root');dialog.set_child(p);p.append(label(data['pkg'],'page-title'));p.append(label(f"Versão: {data['version']}\nArquitetura: {data['arch']}\nOrigem: {data['source']}\nSHA-256: {data['sha256']}\nArquivo: {data['path']}\n\nO formato e a arquitetura foram conferidos; isso não certifica o conteúdo de scripts do pacote. O instalador do StackOS fará a revisão de dependências e pedirá autenticação.",'muted',True));install=button('Abrir instalador do StackOS',lambda *_:(dialog.close(),self.launch(['/usr/local/bin/stackos-package-installer',data['path']])),'install');install.set_sensitive(not data.get('dependency_error'));p.append(install)
  if data.get('dependency_error'):p.append(label('O arquivo foi salvo, mas as dependências não foram resolvidas: '+data['dependency_error'],'error',True))
  p.append(button('Guardar para depois',lambda *_:dialog.close()));dialog.present();self.status.set_text('DEB baixado e conferido. A instalação depende de sua confirmação.');return False
 def check_updates(self):
  if self.checking_updates:return
  self.checking_updates=True;self.task(backend.updater_status,self.updates_checked)
 def updates_checked(self,data,error):
  self.checking_updates=False
  if self.closed:return False
  if error:
   self.updater_error=error
   if self.category=='Atualizações':self.status.set_text('Falha ao consultar o Updater: '+error)
  else:
   self.updater_error=None;self.updater_data=data
   path=BASE.parent/'qa/updater-status.json' if self.qa else Path.home()/'.cache/stackos-updater/status.json'
   try:atomic_json(path,data)
   except OSError as e:self.status.set_text('Consulta concluída, mas não foi possível sincronizar o indicador: '+str(e))
  if self.category=='Atualizações':self.show_updates()
  return False
 def show_updates(self):
  page=box(spacing=16,css='content');self.scroll.set_child(page)
  page.append(label('Atualizações · StackOS Updater','page-title'))
  page.append(label('A loja usa o motor do StackOS Updater e o mesmo estado do indicador da barra. Aplicativos DEB com repositório configurado recebem atualizações por ele. DEBs locais sem repositório exigem uma versão nova do fabricante.','muted',True))
  row=box(False,10);update_button=button('Atualizar agora',lambda *_:self.confirm_updates(),'install');update_button.set_sensitive(bool(self.updater_data and self.updater_data.get('packages')) and not self.busy);row.append(update_button);row.append(button('Consultar Updater',lambda *_:self.check_updates(),'secondary'));row.append(button('Renovar índices APT',lambda *_:self.refresh_indices(),'secondary'));page.append(row)
  if self.updater_data is None:
   page.append(label('Consultando o Updater…' if self.checking_updates else getattr(self,'updater_error',None) or 'Clique em Consultar Updater para verificar.','muted',True));return
  data=self.updater_data
  page.append(label(f"{data.get('count',len(data['packages']))} atualização(ões), {data.get('critical_count',0)} de segurança/críticas. Última consulta: {data.get('checked_at','Não informada')}",'section-title',True))
  if not data['packages']:page.append(label('Nenhuma atualização nos índices atuais. Renove os índices APT para consultar os repositórios novamente.','muted',True))
  for update in data['packages']:
   row=box(spacing=6,css='online-row');row.append(label(update['name'],'section-title'));row.append(label(update.get('description',''),'muted',True));page.append(row)
 def confirm_updates(self):
  if self.busy or not self.updater_data or not self.updater_data.get('packages'):return
  dialog=Gtk.MessageDialog(transient_for=self.win,modal=True,buttons=Gtk.ButtonsType.YES_NO,text='Atualizar aplicativos e sistema?',secondary_text='A loja usará o motor existente do StackOS Updater, com autenticação, progresso e política sem Snap. Os índices serão renovados; todas as atualizações permitidas serão aplicadas. '+str(len(self.updater_data['packages']))+' pacote(s) constam na consulta atual.')
  def response(d,r):
   d.destroy()
   if r==Gtk.ResponseType.YES:self.update_now()
  dialog.connect('response',response);dialog.present()
 def update_now(self):
  if self.busy:return
  self.set_busy(True,'Atualizando com o motor do StackOS Updater…');self.task(self.run_updater,self.updater_finished)
 def run_updater(self):
  p=subprocess.Popen(['pkexec','/usr/lib/stackos/stackos-updater-helper','install'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace');lines=[];final=None
  for raw in p.stdout:
   line=raw.strip()
   if line.startswith('__STACKOS_PROGRESS__'):
    try:
     data=json.loads(line[len('__STACKOS_PROGRESS__'):]);GLib.idle_add(self.update_progress,data)
    except (ValueError,TypeError):pass
   elif line.startswith('__STACKOS_RESULT__'):
    try:final=json.loads(line[len('__STACKOS_RESULT__'):])
    except ValueError:pass
   else:lines.append(line);lines=lines[-300:]
  return {'code':p.wait(),'final':final,'output':'\n'.join(lines)[-1500:]}
 def update_progress(self,data):
  try:value=max(0,min(100,float(data.get('percent',0))))
  except (ValueError,TypeError):value=0
  if self.pulse_timer:GLib.source_remove(self.pulse_timer);self.pulse_timer=None
  self.progress.set_fraction(value/100);self.progress.set_show_text(True);self.progress.set_text(f'{value:.0f}%');self.status.set_text(' · '.join(str(data.get(k,'')) for k in ('stage','package','message') if data.get(k)));return False
 def updater_finished(self,result,error):
  self.set_busy(False);self.progress.set_show_text(False)
  if error or result['code']!=0 or not isinstance(result.get('final'),dict) or not isinstance(result['final'].get('packages'),list):self.status.set_text('Atualização não confirmada: '+(error or result.get('output') or 'O Updater não retornou um resultado final válido.'));return False
  self.updates_checked(result['final'],None);self.status.set_text('Atualização concluída pelo StackOS Updater.');self.load_catalog();return False
 def show_backups(self):
  page=box(spacing=16,css='content');self.scroll.set_child(page);page.append(label('Backups do sistema','page-title'));page.append(label('Backups existentes em /var/backups/stackos. A restauração altera o sistema inteiro e requer confirmação e autenticação.','muted',True));base=Path('/var/backups/stackos');page.append(button('Criar backup',lambda *_:self.backup_action('create',''),'secondary'))
  try:snapshots=[p for p in sorted(base.iterdir(),reverse=True) if p.is_dir() and not p.is_symlink() and re.fullmatch(r'\d{8}_\d{6}',p.name)]
  except OSError:snapshots=[]
  if not snapshots:page.append(label('Nenhum backup encontrado.','muted'))
  for path in snapshots:
   row=box(False,12,'online-row');row.append(label(path.name,'section-title'));row.append(button('Restaurar',lambda _,n=path.name:self.backup_action('restore',n),'remove'));row.append(button('Apagar',lambda _,n=path.name:self.backup_action('delete',n),'secondary'));page.append(row)
 def backup_action(self,action,name):
  if self.busy:return
  dialog=Gtk.Window(title='Confirmar backup',transient_for=self.win,modal=True,default_width=650);p=box(spacing=15,css='content root');dialog.set_child(p);p.append(label({'create':'Criar cópia do sistema','restore':'Restaurar o sistema inteiro','delete':'Apagar backup'}[action],'page-title'));p.append(label('A criação pode ocupar muito espaço. Restaurar sobrescreve o estado atual do sistema; salve seu trabalho. Para confirmar, digite CONFIRMAR.','muted',True));entry=Gtk.Entry();p.append(entry)
  def accept(*_):
   if entry.get_text()!='CONFIRMAR':return
   dialog.close();self.set_busy(True,'Executando operação de backup…');self.task(lambda:self.run_helper(['backup-'+action,name or '-']),self.executed)
  p.append(button('Confirmar',accept,'remove' if action!='create' else 'install'));dialog.present()
 def launch(self,args):
  try:subprocess.Popen(args,start_new_session=True)
  except OSError as e:self.status.set_text(str(e))
 def on_close(self,*_):
  if self.busy:self.status.set_text('Aguarde a operação terminar. Você pode minimizar a janela.');return True
  self.closed=True
  if self.search_timer:GLib.source_remove(self.search_timer);self.search_timer=None
  self.win=None;return False
 def capture(self):
  snap=Gtk.Snapshot();paint=Gtk.WidgetPaintable.new(self.win);paint.snapshot(snap,self.win.get_width(),self.win.get_height());texture=self.win.get_renderer().render_texture(snap.to_node(),None);out=BASE.parent/'qa';out.mkdir(exist_ok=True);texture.save_to_png(str(out/'preview.png'));print('RENDER_OK',self.win.get_width(),self.win.get_height(),flush=True);self.win.close();return False
if __name__=='__main__':raise SystemExit(Store('--qa' in sys.argv).run([sys.argv[0]]))

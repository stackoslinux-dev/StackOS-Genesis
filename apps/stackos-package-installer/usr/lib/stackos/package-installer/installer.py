#!/usr/bin/python3
import os,sys,json,subprocess,threading
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
import legacy
from inspect_file import inspect,fingerprint,execution_command,extract_archive,FORMATS
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

class Installer(legacy.PackageInstaller):
 def __init__(self,qa=False):
  super().__init__();self.qa=qa;self.data=None;self.busy=False;self.generation=0;self.log='';self.pulse_timer=None;self.nav={}
  if qa:self.set_application_id('org.stackos.PackageInstaller.Preview');self.set_flags(Gio.ApplicationFlags.NON_UNIQUE|Gio.ApplicationFlags.HANDLES_OPEN)
 def build_window(self):
  css=Gtk.CssProvider();css.load_from_data((BASE/'theme.css').read_text().replace('__ASSETS__',(BASE/'assets').as_uri()).encode());Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
  self.window=Gtk.ApplicationWindow(application=self,title='Instalador de Aplicativos StackOS');stackos_window.fit_window(self.window);self.window.set_icon_name('org.stackos.Installer');self.window.add_css_class('installer');self.window.connect('close-request',self.close_requested)
  bar=Gtk.HeaderBar();bar.add_css_class('chrome');bar.set_title_widget(label('Instalador de Aplicativos StackOS','window-title'));self.window.set_titlebar(bar)
  shell=box(False,0,css='root');self.window.set_child(shell);side=box(spacing=16,css='sidebar');side.set_size_request(205,-1);shell.append(side);side.append(image('stackos-symbol.png',75));side.append(label('StackOS','brand-title'));side.append(label('Linux','brand-sub'));side.append(label('Modular. Leve. Poderoso.','muted',True))
  for key,title,ico in [('install','Instalador','folder-download-symbolic'),('formats','Formatos','view-grid-symbolic'),('help','Ajuda','help-browser-symbolic'),('about','Sobre','help-about-symbolic')]:b=button(title,lambda _,k=key:self.navigate(k),'nav',ico);side.append(b);self.nav[key]=b
  sp=box();sp.set_vexpand(True);side.append(sp);side.append(Gtk.Separator());side.append(button('Segurança',lambda *_:self.navigate('security'),'nav','security-high-symbolic'));side.append(label('Snap bloqueado','muted'));side.append(signature_link())
  right=box(spacing=0);right.set_hexpand(True);shell.append(right);self.stack=Gtk.Stack();self.stack.set_hhomogeneous(False);self.stack.set_vhomogeneous(False);self.stack.set_vexpand(True);right.append(self.stack)
  scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);self.stack.add_named(scroll,'install');page=box(spacing=19,css='content');scroll.set_child(page)
  hero=box(False,20);hero.append(image('installer.svg',80));t=box(spacing=10);t.set_hexpand(True);t.append(label('Instalador Universal StackOS','hero-title',True));t.append(label('Instale aplicativos e pacotes Linux compatíveis com o StackOS.','subtitle',True));hero.append(t);page.append(hero)
  panel=box(spacing=18,css='panel');tabs=box(False,10);tabs.append(button('Instalar arquivo',lambda *_:self.select_file(None),'tab selected','folder-download-symbolic'));tabs.append(button('Pesquisar aplicativos',lambda *_:self.open_store(),'tab','system-search-symbolic'));panel.append(tabs)
  drop=box(False,15,css='dropzone');drop.append(image('upload.svg',48));info=box(spacing=8);info.set_hexpand(True);self.package_label=label('Arraste um arquivo aqui','drop-title',True);info.append(self.package_label);self.file_hint=label('ou clique para selecionar','muted',True);info.append(self.file_hint);drop.append(info);self.select_button=button('Selecionar arquivo',self.select_file,'primary','folder-open-symbolic');drop.append(self.select_button);panel.append(drop);panel.append(label('DEB, AppImage, RUN, SH, executáveis, Flatpak e arquivos portáteis ZIP/TAR.','muted',True));page.append(panel)
  target=Gtk.DropTarget.new(Gdk.FileList,Gdk.DragAction.COPY);target.connect('drop',self.on_drop);drop.add_controller(target)
  self.details=label('','muted',True);self.details.set_selectable(True);self.details.set_visible(False);page.append(self.details)
  title=box(False,10);l=label('Formatos suportados','section-title');l.set_hexpand(True);title.append(l);title.append(button('Saiba mais',lambda *_:self.navigate('formats'),'link'));page.append(title)
  grid=Gtk.Grid(column_spacing=10,row_spacing=10,column_homogeneous=True);page.append(grid)
  for n,(name,subtitle,ico) in enumerate([('DEB','Pacotes nativos','deb.svg'),('AppImage','Apps portáteis','appimage.svg'),('RUN','Instaladores Linux','run.svg'),('SH','Scripts de shell','script.svg'),('Executáveis','Binários Linux','binary.svg'),('Flatpak','Apps sandbox','flatpak.svg')]):
   b=Gtk.Button();b.add_css_class('format-card');c=box(spacing=9);c.append(image(ico,42));l=label(name,'format-title');l.set_halign(Gtk.Align.CENTER);c.append(l);l=label(subtitle,'caption',True);l.set_halign(Gtk.Align.CENTER);c.append(l);b.set_child(c);b.connect('clicked',lambda *_:self.navigate('formats'));grid.attach(b,n,0,1,1)
  self.info_label=label('ⓘ  O Snap é bloqueado pela política do StackOS.','security-card',True);page.append(self.info_label);self.status=label('Selecione um arquivo para analisar. Nada será executado automaticamente.','status',True);self.status.set_selectable(True);page.append(self.status)
  self.progress=Gtk.ProgressBar();self.progress.set_visible(False);page.append(self.progress);self.spinner=Gtk.Spinner();page.append(self.spinner);self.log_button=button('Ver detalhes da operação',lambda *_:self.show_log(),'link');page.append(self.log_button)
  self.build_info_pages()
  footer=box(False,14,css='footer');right.append(footer);self.clear_button=button('Limpar',lambda *_:self.clear(),'secondary','edit-clear-symbolic');footer.append(self.clear_button);sp=box();sp.set_hexpand(True);footer.append(sp);self.install_button=button('Instalar',self.install_selected,'primary','emblem-ok-symbolic');self.install_button.set_sensitive(False);footer.append(self.install_button);self.navigate('install')
  if self.qa:GLib.timeout_add(1100,self.capture)
 def build_info_pages(self):
  text={
   'formats':('Formatos suportados','DEB — Pacote nativo. A instalação usa APT e autenticação administrativa, com resolução de dependências.\n\nAppImage — Aplicativo portátil Linux, executado com os privilégios do seu usuário.\n\nRUN — Instalador Linux. O aplicativo é iniciado como seu usuário; ele pode pedir sua própria autenticação.\n\nSH — Script executado com Bash como seu usuário. Leia e confira a origem do arquivo.\n\nExecutáveis — Binários Linux ELF compatíveis. A execução depende da arquitetura e das bibliotecas do sistema.\n\nFlatpak/Flatpakref — Instalação por usuário, quando a ferramenta Flatpak está disponível.\n\nZIP/TAR — Arquivos portáteis, extraídos na pasta Applications sem execução automática.\n\nRPM — Reconhecido; procure a versão DEB compatível com o sistema.\n\nEXE/MSI — Execução por compatibilidade Wine quando ele está instalado. Isso não garante compatibilidade de todo aplicativo.'),
   'help':('Como instalar','1. Selecione ou arraste um arquivo local. Abrir um arquivo pelo gerenciador de arquivos também funciona.\n\n2. Aguarde a análise. Confira formato, origem, arquitetura e informações do pacote.\n\n3. Clique em Instalar ou Executar e confirme a ação. Nenhum arquivo é iniciado só por ser selecionado.\n\n4. Para DEB, a autenticação é feita pelo sistema. O helper verifica novamente o arquivo antes de usar o APT.\n\n5. Se houver falha, abra os detalhes da operação. Cancelar a autenticação não é tratado como sucesso.\n\nPara buscar aplicativos, use Pesquisar aplicativos e abra a StackOS Store.'),
   'about':('Instalador StackOS 1.2.0','Instalador integrado à StackOS Store e ao gerenciador de arquivos.\n\nInterface GTK4, análise em segundo plano, arrastar e soltar, preservação dos formatos existentes e helper autenticado para pacotes DEB.\n\nModular. Leve. Poderoso.'),
   'security':('Segurança e política do StackOS','Snap e pacotes DEB de transição para Snap são bloqueados. O helper também confere as dependências que o APT pretende instalar.\n\nO hash SHA-256 identifica o arquivo analisado; ele não certifica o publicador. Para DEB, o helper copia o arquivo para uma pasta protegida e confere o hash novamente antes de instalar.\n\nScripts, AppImage e executáveis são programas. Confira a origem e a compatibilidade antes de executar. O instalador não os eleva automaticamente para root.\n\nAplicativos Flatpak são instalados por usuário; as permissões e a origem continuam dependendo do pacote.'),
  }
  for key,(title,body) in text.items():sc=Gtk.ScrolledWindow();p=box(spacing=20,css='content');p.append(label(title,'hero-title',True));p.append(label(body,'info-copy',True));sc.set_child(p);self.stack.add_named(sc,key)
 def navigate(self,key):
  self.stack.set_visible_child_name(key)
  for name,b in self.nav.items():b.add_css_class('selected') if name==key else b.remove_css_class('selected')
 def on_drop(self,target,files,x,y):
  if self.busy:return False
  selected=files.get_files()
  if not selected:return False
  path=selected[0].get_path()
  if not path:self.status.set_text('Selecione um arquivo local.');return False
  self.load_file(Path(path));return True
 def select_file(self,button):
  if self.busy:return
  chooser=Gtk.FileChooserNative.new('Selecionar aplicativo ou pacote',self.window,Gtk.FileChooserAction.OPEN,'Selecionar','Cancelar');chooser.connect('response',self.file_selected);chooser.show()
 def file_selected(self,chooser,response):
  if response==Gtk.ResponseType.ACCEPT and chooser.get_file() and chooser.get_file().get_path():self.load_file(Path(chooser.get_file().get_path()))
  chooser.destroy()
 def load_file(self,source):
  if self.busy:return
  self.navigate('install');self.generation+=1;generation=self.generation;self.data=None;self.file_path=None;self.install_button.set_sensitive(False);self.status.set_text('Analisando o arquivo…')
  def worker():
   try:data=inspect(source);GLib.idle_add(self.analyzed,generation,data,None)
   except Exception as e:GLib.idle_add(self.analyzed,generation,None,str(e))
  threading.Thread(target=worker,daemon=True).start()
 def analyzed(self,generation,data,error):
  if generation!=self.generation or self.window is None:return False
  if error:self.status.set_text('Não foi possível analisar: '+error);self.file_hint.set_text('Selecione outro arquivo para continuar.');return False
  self.data=data;self.file_path=data['path'];self.file_type=data['kind'];self.package_label.set_text(data['name']);self.file_hint.set_text(str(data['path']));self.status.set_text(data['message']);metadata=data['metadata'];detail=f"Formato: {FORMATS.get(data['kind'],(data['kind'],''))[0]} · Tamanho: {data['size']/1024**2:.2f} MB"
  if metadata:detail+=f"\nVersão: {metadata.get('Version','Não informada')} · Arquitetura: {metadata.get('Architecture','Não informada')}"
  detail+='\nSHA-256: '+data['sha256'];self.details.set_text(detail);self.details.set_visible(True);self.install_button.set_sensitive(data['ready']);self.install_button.get_child().get_last_child().set_text('Executar aplicativo' if data['kind']=='appimage' else 'Executar' if data['kind'] in ('run','script','executable') else 'Extrair aplicativo' if data['kind']=='archive' else 'Executar com Wine' if data['kind']=='windows' else 'Instalar');return False
 def clear(self):
  if self.busy:return
  self.generation+=1;self.data=None;self.file_path=None;self.file_type=None;self.package_label.set_text('Arraste um arquivo aqui');self.file_hint.set_text('ou clique para selecionar');self.details.set_visible(False);self.install_button.set_sensitive(False);self.status.set_text('Selecione um arquivo para analisar. Nada será executado automaticamente.');self.navigate('install')
 def install_selected(self,*_):
  if self.busy or not self.data or not self.data['ready']:return
  dialog=Gtk.MessageDialog(transient_for=self.window,modal=True,buttons=Gtk.ButtonsType.YES_NO,text=('Extrair ' if self.file_type=='archive' else 'Instalar ' if self.file_type in ('deb','flatpak','flatpakref') else 'Executar ')+self.data['name']+'?',secondary_text='Confirme a origem e o arquivo selecionado. DEB usa autenticação do sistema; os demais formatos são iniciados como seu usuário.')
  def response(d,r):
   d.destroy()
   if r==Gtk.ResponseType.YES:self.begin_install()
  dialog.connect('response',response);dialog.present()
 def begin_install(self):
  if self.busy or not self.data:return
  self.start_busy('Conferindo o arquivo antes de continuar…');data=dict(self.data)
  def worker():
   try:
    if fingerprint(data['path'])!=data['sha256']:raise ValueError('O arquivo mudou depois da análise. Selecione-o novamente.')
    if data['kind']=='archive':
     folder=extract_archive(data['path']);GLib.idle_add(self.archive_ready,folder);return
    if data['kind']=='deb':self.deb_worker();return
    if data['kind'] in ('flatpak','flatpakref'):self.flatpak_worker();return
    if data['kind']!='windows':
     mode=data['path'].stat().st_mode;data['path'].chmod(mode|0o100)
    subprocess.Popen(execution_command(data),cwd=str(data['path'].parent),start_new_session=True);GLib.idle_add(self.user_started,None)
   except Exception as e:GLib.idle_add(self.user_started,str(e))
  threading.Thread(target=worker,daemon=True).start()
 def archive_ready(self,folder):
  self.stop_busy();self.status.set_text('Arquivos extraídos em '+str(folder)+'. Escolha o executável para iniciar; nada foi executado automaticamente.');self.log=str(folder);self.install_button.set_sensitive(False)
  try:Gtk.show_uri(self.window,Path(folder).as_uri(),Gdk.CURRENT_TIME)
  except GLib.Error:pass
  return False
 def user_started(self,error):self.stop_busy();self.status.set_text('Falha ao iniciar: '+error if error else 'Aplicativo/instalador iniciado. A conclusão depende do próprio programa.');self.install_button.set_sensitive(not error and bool(self.data));return False
 def deb_worker(self):
  cmd=['pkexec','/usr/lib/stackos/stackos-package-installer-helper','install',str(self.file_path),self.data['sha256']]
  try:
   proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace');lines=[];marker=False
   for raw in proc.stdout:
    line=raw.strip();marker=marker or line=='STACKOS_INSTALL_OK';lines.append(line);lines=lines[-800:]
    if line.startswith('pmstatus:'):
     values=line.split(':',3)
     try:GLib.idle_add(self.real_progress,float(values[2]),values[3] if len(values)>3 else '')
     except (ValueError,IndexError):pass
   code=proc.wait();GLib.idle_add(self.finish_deb,code==0 and marker,'\n'.join(lines))
  except Exception as e:GLib.idle_add(self.finish_deb,False,str(e))
 def finish_deb(self,success,output):self.log=output;self.stop_busy();self.status.set_text('Pacote instalado com sucesso.' if success else 'Instalação não concluída: '+(output[-1500:] or 'O resultado não foi confirmado.'));self.install_button.set_sensitive(not success);return False
 def finish_flatpak(self,success,output):self.log=output;self.stop_busy();self.status.set_text('Aplicativo Flatpak instalado por usuário.' if success else output[-1500:] or 'A instalação Flatpak não foi concluída.');self.install_button.set_sensitive(not success);return False
 def start_busy(self,text):
  self.busy=True;self.spinner.start();self.status.set_text(text);self.install_button.set_sensitive(False);self.clear_button.set_sensitive(False);self.select_button.set_sensitive(False);self.progress.set_visible(True);self.pulse_timer=GLib.timeout_add(140,self.pulse)
 def pulse(self):
  if self.busy:self.progress.pulse();return True
  self.pulse_timer=None;return False
 def real_progress(self,value,message):
  if self.pulse_timer:GLib.source_remove(self.pulse_timer);self.pulse_timer=None
  self.progress.set_fraction(max(0,min(1,value/100)));self.progress.set_show_text(True);self.progress.set_text(f'{value:.0f}%');self.status.set_text(message);return False
 def stop_busy(self):
  self.busy=False;self.spinner.stop();self.clear_button.set_sensitive(True);self.select_button.set_sensitive(True);self.progress.set_visible(False);self.progress.set_show_text(False)
  if self.pulse_timer:GLib.source_remove(self.pulse_timer);self.pulse_timer=None
 def show_log(self):
  window=Gtk.Window(title='Detalhes da operação',transient_for=self.window,modal=True,default_width=850,default_height=550);window.add_css_class('installer');scroll=Gtk.ScrolledWindow();view=Gtk.TextView(editable=False,monospace=True,wrap_mode=Gtk.WrapMode.WORD_CHAR);view.get_buffer().set_text(self.log or 'Nenhuma operação registrada nesta sessão.');scroll.set_child(view);window.set_child(scroll);window.present()
 def open_store(self):
  try:subprocess.Popen(['/usr/local/bin/stackos-store'],start_new_session=True)
  except OSError as e:self.status.set_text('Não foi possível abrir a loja: '+str(e))
 def close_requested(self,*_):
  if self.busy:self.status.set_text('Aguarde a operação terminar. Você pode minimizar esta janela.');return True
  self.generation+=1;self.window=None;return False
 def capture(self):
  snap=Gtk.Snapshot();paint=Gtk.WidgetPaintable.new(self.window);paint.snapshot(snap,self.window.get_width(),self.window.get_height());texture=self.window.get_renderer().render_texture(snap.to_node(),None);out=BASE.parent/'qa';out.mkdir(exist_ok=True);texture.save_to_png(str(out/'preview.png'));print('RENDER_OK',self.window.get_width(),self.window.get_height(),flush=True);self.window.close();return False
if __name__=='__main__':raise SystemExit(Installer('--qa' in sys.argv).run([sys.argv[0]] if '--qa' in sys.argv else sys.argv))

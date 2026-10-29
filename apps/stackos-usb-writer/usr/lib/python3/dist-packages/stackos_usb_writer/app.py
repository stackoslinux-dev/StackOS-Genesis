"""Interface GTK4; operações destrutivas são exclusivas do worker autenticado."""
import os,sys,json,threading,subprocess,re
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
from .devices import discover_usb_devices,format_size
from .operations import validate_image,signature,sha256_file,image_kind
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
 w=Gtk.Image.new_from_file(str(BASE/'assets'/name)) if (BASE/'assets'/name).is_file() else Gtk.Image.new_from_icon_name(name);w.set_pixel_size(size);return w

def button(text,callback,css='',ico=None):
 b=Gtk.Button();r=box(False,10)
 if ico:r.append(image(ico,21))
 r.append(label(text));b.set_child(r);b.connect('clicked',callback)
 for c in css.split():b.add_css_class(c)
 return b

def signature_link():
    link=Gtk.LinkButton.new_with_label('https://github.com/stackoslinux-dev','StackOS Linux · GitHub')
    link.set_tooltip_text('Autoria: StackOS Linux <stackoslinux@gmail.com>')
    link.add_css_class('stackos-signature')
    link.set_halign(Gtk.Align.START)
    return link

class UsbWriter(Gtk.Application):
 def __init__(self,qa=False):
  super().__init__(application_id='org.stackos.UsbWriter' if not qa else 'org.stackos.UsbWriter.Preview',flags=Gio.ApplicationFlags.DEFAULT_FLAGS if not qa else Gio.ApplicationFlags.NON_UNIQUE);self.qa=qa;self.window=None;self.devices=[];self.image_path='';self.image_sig='';self.digest='';self.process=None;self.computing=False;self.hash_cancel=threading.Event();self.complete=False;self.cancelled=False;self.error='';self.discovery=False;self.pulse_timer=None;self.log='';self.nav={};self.generation=0
 def do_activate(self):
  if self.window:self.window.present();return
  css=Gtk.CssProvider();css.load_from_data((BASE/'theme.css').read_text().replace('__ASSETS__',(BASE/'assets').as_uri()).encode());Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
  self.window=Gtk.ApplicationWindow(application=self,title='StackOS USB Writer');stackos_window.fit_window(self.window);self.window.set_icon_name('org.stackos.UsbWriter');self.window.add_css_class('usb');self.window.connect('close-request',self.close_requested)
  header=Gtk.HeaderBar();header.add_css_class('chrome');header.set_title_widget(label('StackOS USB Writer','window-title'));self.window.set_titlebar(header)
  shell=box(False,0,css='root');self.window.set_child(shell);side=box(spacing=16,css='sidebar');side.set_size_request(210,-1);shell.append(side);side.append(image('stackos-symbol.png',80));side.append(label('StackOS','brand'));side.append(label('USB Writer','muted'));copy=label('Imagens e mídias USB\ncom verificação.','muted',True);copy.set_max_width_chars(23);side.append(copy)
  for key,title,ico in [('write','Gravar USB','media-removable-symbolic'),('image','Imagem ISO / IMG','media-optical-symbolic'),('checksum','Verificação SHA-256','security-high-symbolic'),('format','Formatação USB','drive-harddisk-symbolic'),('help','Ajuda','help-browser-symbolic')]:b=button(title,lambda _,k=key:self.navigate(k),'nav',ico);side.append(b);self.nav[key]=b
  sp=box();sp.set_vexpand(True);side.append(sp);safe=box(spacing=10,css='side-card');safe.append(label('Segurança','section-title'));copy=label('Somente USBs/removíveis permitidos. Discos críticos e somente leitura são bloqueados.','muted',True);copy.set_max_width_chars(23);safe.append(copy);side.append(safe);side.append(signature_link())
  main=box(spacing=0);main.set_hexpand(True);shell.append(main);self.stack=Gtk.Stack();self.stack.set_hhomogeneous(False);self.stack.set_vhomogeneous(False);self.stack.set_vexpand(True);main.append(self.stack)
  sc=Gtk.ScrolledWindow();sc.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);page=box(spacing=14,css='content');sc.set_child(page);self.stack.add_named(sc,'write');hero=box(False,16);hero.append(image('usb.svg',64));t=box(spacing=8);t.set_hexpand(True);t.append(label('StackOS USB Writer','hero-title'));t.append(label('Crie mídias USB inicializáveis com segurança e verificação.','subtitle',True));hero.append(t);hero.append(image('usb-art.svg',110));page.append(hero)
  features=box(False,20)
  for ico,title,sub in [('security-high-symbolic','Seguro','Verificação após gravar'),('view-refresh-symbolic','Compatível','Imagens brutas e comprimidas'),('preferences-system-symbolic','Simples','Um fluxo em três etapas')]:r=box(False,9);r.append(image(ico,25));t=box(spacing=4);t.append(label(title,'feature-title'));t.append(label(sub,'caption'));r.append(t);features.append(r)
  page.append(features)
  first=self.panel(page,'1','Selecionar imagem ISO ou IMG');drop=box(False,16,css='dropzone');drop.append(image('image.svg',44));t=box(spacing=7);t.set_hexpand(True);self.image_label=label('Arraste uma imagem aqui','drop-title',True);t.append(self.image_label);self.image_details=label('ISO, IMG, GZ, XZ, BZ2 ou ZIP com uma única imagem.','muted',True);t.append(self.image_details);drop.append(t);self.choose_button=button('Selecionar arquivo',self.choose_image,'primary','folder-open-symbolic');drop.append(self.choose_button);first.append(drop);target=Gtk.DropTarget.new(Gdk.FileList,Gdk.DragAction.COPY);target.connect('drop',self.on_drop);drop.add_controller(target)
  second=self.panel(page,'2','Selecionar dispositivo USB');r=box(False,10);self.device_combo=Gtk.DropDown();self.device_combo.set_hexpand(True);self.device_combo.connect('notify::selected',lambda *_:self.update_buttons());r.append(self.device_combo);self.refresh_button=button('Atualizar',lambda *_:self.refresh_devices(),'secondary','view-refresh-symbolic');r.append(self.refresh_button);second.append(r);self.device_details=label('Conecte um pendrive e atualize a lista.','muted',True);second.append(self.device_details)
  third=self.panel(page,'3','Configurações e verificação');self.verify=Gtk.CheckButton(label='Verificar integridade após gravar (comparação byte a byte)');self.verify.set_active(True);third.append(self.verify);r=box(False,10);r.append(label('Formatação:','muted'));self.filesystem=Gtk.DropDown.new_from_strings(['FAT32','exFAT','NTFS']);r.append(self.filesystem);self.label_entry=Gtk.Entry(text='STACKOS',max_length=11,placeholder_text='Nome do volume');self.label_entry.set_hexpand(True);r.append(self.label_entry);self.format_button=button('Formatar',lambda *_:self.confirm('format'),'secondary','edit-clear-symbolic');r.append(self.format_button);third.append(r);third.append(label('Formato e nome do volume são usados somente ao formatar. Gravar uma imagem usa o layout contido nela.','caption',True))
  page.append(label('A gravação e a formatação apagam dados do destino escolhido. Confira modelo, capacidade e caminho antes de confirmar.','warning',True))
  self.build_pages()
  footer=box(spacing=10,css='footer');main.append(footer);self.progress=Gtk.ProgressBar(show_text=True);self.progress.set_fraction(0);self.progress.set_text('0%');footer.append(self.progress);self.status=label('Selecione uma imagem e um dispositivo para continuar.','muted',True);self.status.set_selectable(True);footer.append(self.status);r=box(False,12);self.log_button=button('Ver detalhes',lambda *_:self.show_log(),'link');r.append(self.log_button);sp=box();sp.set_hexpand(True);r.append(sp);self.cancel_button=button('Cancelar',self.cancel,'secondary','process-stop-symbolic');self.cancel_button.set_sensitive(False);r.append(self.cancel_button);self.write_button=button('Gravar USB',lambda *_:self.confirm('write'),'primary','media-removable-symbolic');r.append(self.write_button);footer.append(r)
  self.navigate('write');self.window.present();self.refresh_devices();self.timer=GLib.timeout_add_seconds(5,self.auto_refresh)
 def panel(self,page,number,title):
  p=box(spacing=13,css='panel');r=box(False,13);r.append(label(number,'step-number'));r.append(label(title,'section-title'));p.append(r);page.append(p);return p
 def build_pages(self):
  self.checksum_page=box(spacing=20,css='content');self.checksum_page.append(label('Verificação SHA-256','hero-title'));self.checksum_page.append(label('O hash identifica os bytes do arquivo selecionado, inclusive quando comprimido. Compare com o valor publicado pela origem da imagem. A verificação após gravar compara os bytes descomprimidos com o USB.','muted',True));self.checksum_label=label('Nenhum hash calculado.','mono',True);self.checksum_label.set_selectable(True);self.checksum_page.append(self.checksum_label);self.expected=Gtk.Entry(placeholder_text='SHA-256 esperado (opcional)',max_length=64);self.checksum_page.append(self.expected);self.hash_button=button('Calcular / comparar SHA-256',self.calculate_checksum,'primary','security-high-symbolic');self.checksum_page.append(self.hash_button);self.stack.add_named(self.checksum_page,'checksum')
  p=box(spacing=20,css='content');p.append(label('Formatar USB','hero-title'));p.append(label('Use os controles de formatação na tela principal para recriar o USB em FAT32, exFAT ou NTFS. Isso apaga o dispositivo inteiro e cria uma tabela GPT nova.','muted',True));p.append(label('FAT32: ampla compatibilidade, limite de 4 GB por arquivo.\n\nexFAT: arquivos grandes em sistemas compatíveis.\n\nNTFS: uso comum para dados em ambientes Windows/Linux.\n\nO formato não converte uma ISO em inicializável e não altera o modo de gravação bruta.','info-copy',True));p.append(button('Ir para os controles',lambda *_:self.navigate('write'),'primary'));self.stack.add_named(p,'format')
  p=box(spacing=20,css='content');p.append(label('Imagens e compatibilidade','hero-title'));p.append(label('ISO/IMG são gravadas em blocos, preservando o layout da imagem. São aceitos .iso, .img, .iso/.img comprimidos em GZ/XZ/BZ2 e ZIP que contenha exatamente uma ISO/IMG. Não há extração arbitrária do ZIP no disco.\n\nA imagem pode ser de outra distribuição ou arquitetura: quem precisa ser compatível é o computador que vai iniciar por esse USB. A inicialização depende da própria imagem, de UEFI/Legacy e das configurações do destino.\n\nISOs híbridas Linux e imagens brutas são adequadas a esse método. Algumas ISOs Windows precisam de preparação especializada; copiar os bytes não garante que inicializem. Multiboot, persistência e conversão Windows não são adicionados automaticamente.','info-copy',True));p.append(button('Selecionar imagem',self.choose_image,'primary'));self.stack.add_named(p,'image')
  p=box(spacing=20,css='content');p.append(label('Ajuda e segurança','hero-title'));p.append(label('1. Escolha a imagem e, se disponível, compare o SHA-256 oficial.\n\n2. Selecione explicitamente o USB. Confira modelo, tamanho e caminho.\n\n3. Deixe a verificação após gravar ativada e confirme o destino na janela seguinte. O sistema pedirá autenticação.\n\nO worker revalida o dispositivo, a imagem e a capacidade. Discos internos não removíveis, dispositivos somente leitura, partições críticas em uso e o USB que contém a imagem de origem são recusados.\n\nCancelar interrompe as próximas escritas; não restaura os dados anteriores. Depois de cancelar ou falhar, o USB pode estar parcialmente gravado ou formatado. Aguarde a conclusão da operação antes de retirar o dispositivo.','info-copy',True));self.stack.add_named(p,'help')
 def navigate(self,key):
  self.stack.set_visible_child_name(key)
  for name,b in self.nav.items():b.add_css_class('selected') if name==key else b.remove_css_class('selected')
 def busy(self):return self.process is not None or self.computing
 def selected_device(self):
  index=self.device_combo.get_selected();return self.devices[index-1] if 0<index<=len(self.devices) else None
 def update_buttons(self):
  d=self.selected_device();idle=not self.busy();self.write_button.set_sensitive(bool(d and self.image_path and idle));self.format_button.set_sensitive(bool(d and idle));self.choose_button.set_sensitive(idle);self.refresh_button.set_sensitive(idle);self.device_combo.set_sensitive(idle);self.filesystem.set_sensitive(idle);self.label_entry.set_sensitive(idle);self.verify.set_sensitive(idle);self.expected.set_sensitive(idle);self.hash_button.set_sensitive(bool(idle and self.image_path));self.cancel_button.set_sensitive(self.busy())
  self.device_details.set_text(f'Destino: {d.display_name} · {format_size(d.size)} · {d.path}. Todo o conteúdo será apagado.' if d else 'Selecione explicitamente um USB; nenhum destino é escolhido automaticamente.')
 def refresh_devices(self):
  if self.busy() or self.discovery:return
  self.discovery=True;selected=self.selected_device();old=selected.identity if selected else None
  def worker():
   try:data=discover_usb_devices();GLib.idle_add(self.devices_ready,data,old,None)
   except Exception as e:GLib.idle_add(self.devices_ready,[],old,str(e))
  threading.Thread(target=worker,daemon=True).start()
 def devices_ready(self,data,old,error):
  self.discovery=False
  if not self.window:return False
  self.devices=[d for d in data if not d.protected];names=['Selecione um dispositivo USB']+[f'{d.display_name} — {format_size(d.size)} ({d.path})' for d in self.devices];self.device_combo.set_model(Gtk.StringList.new(names));self.device_combo.set_selected(next((i+1 for i,d in enumerate(self.devices) if d.identity==old),0));self.update_buttons()
  if error:self.status.set_text('Falha ao detectar USBs: '+error)
  elif not self.devices:self.device_details.set_text('Nenhum dispositivo USB permitido encontrado. Conecte um pendrive e clique em Atualizar.')
  if self.qa:GLib.timeout_add(900,self.capture)
  return False
 def auto_refresh(self):
  if not self.window:return False
  self.refresh_devices();return True
 def choose_image(self,*_):
  if self.busy():return
  dialog=Gtk.FileChooserNative.new('Selecionar imagem',self.window,Gtk.FileChooserAction.OPEN,'Selecionar','Cancelar');f=Gtk.FileFilter();f.set_name('Imagens ISO/IMG e comprimidas')
  for suffix in ['*.iso','*.img','*.iso.gz','*.img.gz','*.iso.xz','*.img.xz','*.iso.bz2','*.img.bz2','*.zip']:f.add_pattern(suffix)
  dialog.add_filter(f)
  def selected(d,response):
   if response==Gtk.ResponseType.ACCEPT and d.get_file() and d.get_file().get_path():self.load_image(d.get_file().get_path())
   d.destroy()
  dialog.connect('response',selected);dialog.show()
 def on_drop(self,target,data,x,y):
  if self.busy():return False
  files=data.get_files()
  if files and files[0].get_path():self.load_image(files[0].get_path());return True
  return False
 def load_image(self,path):
  if self.busy():return
  try:
   selected=validate_image(path);self.image_path=str(selected);self.image_sig=signature(selected);self.digest='';self.image_label.set_text(selected.name);self.image_details.set_text(format_size(selected.stat().st_size)+' · '+image_kind(selected)+'\n'+str(selected));self.checksum_label.set_text('Nenhum hash calculado para esta imagem.');self.progress.set_fraction(0);self.progress.set_text('0%');self.status.set_text('Imagem selecionada. A preparação confere a capacidade antes de gravar.');self.navigate('write')
  except Exception as e:self.image_path='';self.status.set_text('Imagem inválida: '+str(e))
  self.update_buttons()
 def calculate_checksum(self,*_):
  if self.busy() or not self.image_path:return
  path=self.image_path;sig=self.image_sig;self.computing=True;self.hash_cancel.clear();self.update_buttons();self.status.set_text('Calculando SHA-256…')
  def progress(current,total):
   if self.hash_cancel.is_set():raise InterruptedError('Cálculo cancelado.')
   GLib.idle_add(self.set_progress,current,total,0)
  def worker():
   try:digest=sha256_file(path,progress);error=None if signature(path)==sig else 'O arquivo mudou durante o cálculo.'
   except Exception as e:digest='';error=str(e)
   GLib.idle_add(self.checksum_ready,digest,error)
  threading.Thread(target=worker,daemon=True).start()
 def checksum_ready(self,digest,error):
  self.computing=False
  if not self.window:return False
  self.digest=digest if not error else '';self.checksum_label.set_text(digest if not error else error);expected=self.expected.get_text().strip().lower();self.status.set_text(error or ('SHA-256 confere com o esperado.' if expected and expected==digest else 'SHA-256 diferente do esperado. Não grave antes de conferir a origem.' if expected else 'SHA-256 calculado. Compare com o valor publicado pela origem.'));self.update_buttons();return False
 def confirm(self,operation):
  d=self.selected_device()
  if self.busy() or not d or operation=='write' and not self.image_path:return
  expected=self.expected.get_text().strip().lower()
  if operation=='write' and expected and not re.fullmatch('[0-9a-f]{64}',expected):self.status.set_text('O SHA-256 esperado deve ter 64 caracteres hexadecimais.');self.navigate('checksum');return
  if operation=='write' and expected and self.digest and expected!=self.digest:self.status.set_text('O SHA-256 calculado não confere. Operação bloqueada.');return
  dialog=Gtk.Window(title='Confirmar destino USB',transient_for=self.window,modal=True,default_width=650);page=box(spacing=17,css='content root');dialog.set_child(page);page.append(label('Apagar e '+('gravar' if operation=='write' else 'formatar')+' o USB?','section-title'));page.append(label(f'{d.display_name}\n{d.path} · {format_size(d.size)}\n\nTodos os dados desse dispositivo serão apagados. Para confirmar, digite o nome do destino: {Path(d.path).name}','warning',True));entry=Gtk.Entry(placeholder_text=Path(d.path).name);page.append(entry)
  def confirm(*_):
   if entry.get_text()!=Path(d.path).name:return
   dialog.close();self.start_operation(operation,d)
  page.append(button('Confirmar destino',confirm,'primary'));dialog.present()
 def start_operation(self,operation,device):
  if self.busy():return
  args=['pkexec','/usr/lib/stackos-usb-writer/stackos-usb-writer-worker',operation,'--device',device.path,'--device-id',device.identity]
  if operation=='write':
   if not self.image_path:return
   args+=['--image',self.image_path,'--source-signature',self.image_sig]
   if self.verify.get_active():args.append('--verify')
   sha=self.expected.get_text().strip().lower() or self.digest
   if sha:args+=['--sha256',sha]
  else:
   labeltext=self.label_entry.get_text() or 'STACKOS'
   if not all(c.isascii() and (c.isalnum() or c in '_- ') for c in labeltext):self.status.set_text('Use letras/números ASCII, espaço, _ ou - no nome do volume.');return
   args+=['--filesystem',('fat32','exfat','ntfs')[self.filesystem.get_selected()],'--label',labeltext]
  try:self.process=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',bufsize=1)
  except Exception as e:self.process=None;self.status.set_text('Não foi possível iniciar: '+str(e));return
  self.complete=False;self.cancelled=False;self.error='';self.log='';self.progress.set_fraction(0);self.status.set_text('Aguarde a autenticação e a preparação…');self.update_buttons();self.navigate('write');threading.Thread(target=self.read_worker,args=(self.process,),daemon=True).start()
 def read_worker(self,process):
  lines=[]
  for raw in process.stdout:
   lines.append(raw.rstrip());lines=lines[-1000:]
   try:event=json.loads(raw)
   except ValueError:continue
   GLib.idle_add(self.handle_event,event)
  code=process.wait();GLib.idle_add(self.worker_finished,code,'\n'.join(lines))
 def handle_event(self,event):
  if not self.window or not isinstance(event,dict):return False
  kind=event.get('event')
  if kind=='stage':
   name=event.get('name');self.status.set_text({'preparing':'Preparando e conferindo a imagem…','writing':'Gravando imagem no USB…','verifying':'Verificando os bytes gravados…','formatting':'Formatando o USB…'}.get(name,'Processando…'))
   if name in ('preparing','formatting'):
    self.progress.set_text('Preparando…' if name=='preparing' else 'Formatando…')
    if not self.pulse_timer:self.pulse_timer=GLib.timeout_add(140,self.pulse)
  elif kind=='progress':self.set_progress(event.get('current',0),event.get('total',0),event.get('speed',0))
  elif kind=='error':self.error=str(event.get('message','Erro desconhecido'));self.status.set_text(self.error)
  elif kind=='cancelled':self.cancelled=True;self.status.set_text(str(event.get('message','Operação cancelada.')))
  elif kind=='complete':self.complete=True
  return False
 def pulse(self):
  if self.process:self.progress.pulse();return True
  self.pulse_timer=None;return False
 def set_progress(self,current,total,speed):
  if self.pulse_timer:GLib.source_remove(self.pulse_timer);self.pulse_timer=None
  try:fraction=max(0,min(1,float(current)/float(total))) if total else 0
  except (ValueError,TypeError):fraction=0
  self.progress.set_fraction(fraction);self.progress.set_text(f'{fraction*100:.1f}%'+(f' · {format_size(speed)}/s' if speed else ''));return False
 def worker_finished(self,code,log):
  if self.process and self.process.stdin:
   try:self.process.stdin.close()
   except OSError:pass
  self.process=None;self.log=log
  if self.pulse_timer:GLib.source_remove(self.pulse_timer);self.pulse_timer=None
  if code==0 and self.complete:self.status.set_text('Operação concluída. Aguarde a atividade do dispositivo terminar e use a ejeção segura.');self.progress.set_fraction(1);self.progress.set_text('100%')
  elif self.cancelled or code==130:self.status.set_text('Operação cancelada. O USB pode estar parcialmente alterado; os dados anteriores não foram restaurados.')
  else:self.status.set_text('Operação não concluída: '+(self.error or log[-500:] or 'Sem confirmação final do worker.'))
  self.update_buttons();self.refresh_devices();return False
 def cancel(self,*_):
  if self.computing:self.hash_cancel.set();self.status.set_text('Cancelando cálculo…');return
  if self.process and self.process.stdin:
   try:self.process.stdin.write('cancel\n');self.process.stdin.flush();self.status.set_text('Cancelamento solicitado. A etapa atual poderá precisar terminar; o USB pode ficar parcialmente alterado.');self.cancel_button.set_sensitive(False)
   except (BrokenPipeError,OSError) as e:self.status.set_text('Não foi possível solicitar o cancelamento: '+str(e))
 def show_log(self):
  window=Gtk.Window(title='Detalhes do USB Writer',transient_for=self.window,modal=True,default_width=820,default_height=550);view=Gtk.TextView(editable=False,monospace=True,wrap_mode=Gtk.WrapMode.WORD_CHAR);view.get_buffer().set_text(self.log or 'Nenhuma operação registrada nesta sessão.');scroll=Gtk.ScrolledWindow();scroll.set_child(view);window.set_child(scroll);window.present()
 def close_requested(self,*_):
  if self.busy():self.status.set_text('Aguarde ou solicite cancelamento antes de fechar.');return True
  if self.timer:GLib.source_remove(self.timer);self.timer=None
  self.window=None;return False
 def capture(self):
  snap=Gtk.Snapshot();paint=Gtk.WidgetPaintable.new(self.window);paint.snapshot(snap,self.window.get_width(),self.window.get_height());texture=self.window.get_renderer().render_texture(snap.to_node(),None);out=BASE.parent/'qa';out.mkdir(exist_ok=True);texture.save_to_png(str(out/'preview.png'));print('RENDER_OK',self.window.get_width(),self.window.get_height(),flush=True);self.window.close();return False

def main():return UsbWriter('--qa' in sys.argv).run([sys.argv[0]])
if __name__=='__main__':raise SystemExit(main())

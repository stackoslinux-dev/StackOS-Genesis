#!/usr/bin/python3
import os,sys,json,threading,subprocess
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
import core
BASE=Path(__file__).resolve().parent

def box(vertical=True,spacing=10,css=''):
 w=Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL,spacing=spacing)
 for c in css.split():w.add_css_class(c)
 return w

def label(text,css='',wrap=False):
 w=Gtk.Label(label=str(text),xalign=0,wrap=wrap)
 for c in css.split():w.add_css_class(c)
 return w

def icon(name,size=24):
 w=Gtk.Image.new_from_file(str(BASE/'assets'/name)) if name.endswith(('.png','.svg')) else Gtk.Image.new_from_icon_name(name);w.set_pixel_size(size);return w

def button(text,callback,css='',image=None):
 w=Gtk.Button();b=box(False,10)
 if image:b.append(icon(image,20))
 b.append(label(text));w.set_child(b);w.connect('clicked',callback)
 for c in css.split():w.add_css_class(c)
 return w

def signature_link():
    link=Gtk.LinkButton.new_with_label('https://github.com/stackoslinux-dev','StackOS Linux · GitHub')
    link.set_tooltip_text('Autoria: StackOS Linux <stackoslinux@gmail.com>')
    link.add_css_class('stackos-signature')
    link.set_halign(Gtk.Align.START)
    return link

class Drivers(Gtk.Application):
 def __init__(self,qa=False):
  super().__init__(application_id='com.stackos.drivers' if not qa else 'com.stackos.drivers.Preview',flags=Gio.ApplicationFlags.DEFAULT_FLAGS if not qa else Gio.ApplicationFlags.NON_UNIQUE)
  self.qa=qa;self.win=None;self.busy=False;self.state=None;self.devices=[];self.filter='Todos';self.only_installed=False;self.nav={};self.timer=None;self.closed=False;self.operation_message='';self.needs_reboot=False;self.telemetry_busy=False;self.pulse_timer=None
  self.config=BASE.parent/'qa/settings.json' if qa else Path.home()/'.config/stackos/drivers.json'
  try:self.only_installed=bool(json.loads(self.config.read_text()).get('only_installed',False))
  except (OSError,ValueError):pass
 def do_activate(self):
  if self.win:self.win.present();return
  self.closed=False;p=Gtk.CssProvider();p.load_from_data((BASE/'theme.css').read_bytes());Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),p,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
  self.win=Gtk.ApplicationWindow(application=self,title='StackOS Drivers');stackos_window.fit_window(self.win);self.win.set_icon_name('org.stackos.Drivers');self.win.add_css_class('drivers');self.win.connect('close-request',self.on_close)
  bar=Gtk.HeaderBar();bar.add_css_class('chrome');bar.set_title_widget(label('StackOS Drivers','window-title'));self.win.set_titlebar(bar)
  root=box(spacing=0,css='root');self.win.set_child(root);header=box(False,18,'header');header.append(icon('drivers.svg',54));brand=box(spacing=5);brand.append(label('StackOS Drivers','brand-title'));brand.append(label('GERENCIADOR DE DRIVERS','brand-sub'));header.append(brand);sp=box();sp.set_hexpand(True);header.append(sp)
  for key,title,ico in [('kernel','Kernel','computer-symbolic'),('active','Driver ativo','video-display-symbolic')]:
   b=box(False,10);b.append(icon(ico,28));t=box(spacing=5);t.append(label(title,'muted'));v=label('—','header-value');t.append(v);b.append(t);header.append(b);setattr(self,key+'_label',v)
  self.scan_button=button('Verificar Hardware',lambda *_:self.scan(),'primary','view-refresh-symbolic');header.append(self.scan_button);root.append(header)
  body=box(False,0);body.set_vexpand(True);root.append(body);side=box(spacing=10,css='sidebar');side.set_size_request(190,-1);body.append(side)
  for key,name,ico in [('Todos','Visão geral','computer-symbolic'),('GPU','Placa de vídeo','video-display-symbolic'),('Áudio','Áudio','audio-speakers-symbolic'),('Rede','Rede e outros','network-wired-symbolic'),('settings','Configurações','emblem-system-symbolic'),('about','Sobre','help-about-symbolic')]:
   b=button(name,lambda _,k=key:self.navigate(k),'nav',ico);side.append(b);self.nav[key]=b
  sp=box();sp.set_vexpand(True);side.append(sp);promo=box(spacing=10,css='promo');promo.append(icon('drivers.svg',62));promo.append(label('StackOS Drivers','section-title'));promo.append(label('Modular. Leve. Poderoso.','muted',True));promo.append(label('v1.6.0','muted'));side.append(promo);side.append(signature_link())
  self.stack=Gtk.Stack();self.stack.set_vhomogeneous(False);self.stack.set_hhomogeneous(False);self.stack.set_hexpand(True);self.stack.set_vexpand(True);body.append(self.stack)
  center=box(spacing=14,css='center');self.stack.add_named(center,'devices')
  banner=box(False,14,'banner');banner.append(icon('object-select-symbolic',42));t=box(spacing=6);t.set_hexpand(True);self.summary=label('Detectando hardware…','summary');self.summary2=label('Consultando o kernel e os pacotes instalados.','positive');t.append(self.summary);t.append(self.summary2);banner.append(t);banner.append(button('Detalhes',lambda *_:self.show_details(),'secondary','view-more-symbolic'));center.append(banner)
  self.progress=Gtk.ProgressBar();self.progress.set_visible(False);center.append(self.progress)
  self.tabs=box(False,6);self.tab_buttons={}
  for key,name in [('Todos','Todos'),('GPU','Placa de vídeo'),('Áudio','Áudio'),('Rede','Rede e outros'),('Proprietários','Proprietários')]:
   b=button(name,lambda _,k=key:self.navigate(k),'tab');self.tabs.append(b);self.tab_buttons[key]=b
  center.append(self.tabs);scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);scroll.set_vexpand(True);self.cards=box(spacing=12);scroll.set_child(self.cards);center.append(scroll)
  self.status=label('','muted',True);center.append(self.status)
  for key,title in [('settings','Configurações'),('about','Sobre o StackOS Drivers'),('logs','Logs de operações'),('details','Informações do sistema')]:
   p=box(spacing=18,css='center');p.append(label(title,'page-title'));self.stack.add_named(p,key);setattr(self,key+'_page',p)
  toggle=Gtk.CheckButton(label='Mostrar somente componentes disponíveis/instalados');toggle.set_active(self.only_installed);toggle.connect('toggled',self.setting_changed);self.settings_page.append(toggle);self.settings_page.append(label('Esse filtro altera apenas a visualização. Instalações e remoções continuam exigindo autenticação do sistema.','muted',True));self.settings_page.append(label('Preferência salva em '+str(self.config),'muted',True))
  self.about_page.append(icon('drivers.svg',90));self.about_page.append(label('StackOS Drivers 1.6.0','summary'));self.about_page.append(label('Detecção PCI/USB, catálogo original de componentes, instalação e remoção com pkexec e APT.\n\nOs dados de hardware e sensores são lidos do PC. Campos indisponíveis mostram N/D. As recomendações são as heurísticas do catálogo, e não garantias de compatibilidade.','muted',True))
  self.logs_text=Gtk.TextView(editable=False,monospace=True,wrap_mode=Gtk.WrapMode.WORD_CHAR);s=Gtk.ScrolledWindow();s.set_child(self.logs_text);s.set_vexpand(True);self.logs_page.append(s)
  self.detail_text=label('Aguardando detecção…','muted',True);self.detail_text.set_selectable(True);s=Gtk.ScrolledWindow();s.set_vexpand(True);s.set_child(self.detail_text);self.details_page.append(s)
  rightscroll=Gtk.ScrolledWindow();rightscroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);rightscroll.set_size_request(270,-1);body.append(rightscroll);self.right=box(spacing=12,css='right');rightscroll.set_child(self.right);self.right_scroll=rightscroll
  self.system_fields={};panel=self.panel('Informações do sistema','computer-symbolic')
  for key,title in [('kernel','Kernel'),('distro','Distro'),('arch','Arquitetura'),('driver','Driver da GPU')]:self.system_fields[key]=self.field(panel,title)
  self.gpu_panel=self.panel('GPU','video-display-symbolic');self.gpu_name=label('Aguardando detecção…','muted',True);self.gpu_name.set_max_width_chars(28);self.gpu_name.set_wrap_mode(Pango.WrapMode.WORD_CHAR);self.gpu_panel.append(self.gpu_name);self.gpu_fields={}
  for key,title in [('driver','Driver'),('vram','VRAM'),('usage','Uso'),('temperature','Temperatura'),('power','Energia')]:self.gpu_fields[key]=self.field(self.gpu_panel,title)
  self.usage_bar=Gtk.ProgressBar();self.gpu_panel.append(self.usage_bar);self.temp_bar=Gtk.ProgressBar();self.gpu_panel.append(self.temp_bar)
  panel=self.panel('Ações rápidas','system-run-symbolic')
  for name,callback,ico in [('Verificar hardware',lambda *_:self.scan(),'view-refresh-symbolic'),('Abrir atualizações',lambda *_:self.launch('/usr/local/bin/stackos-updater'),'folder-download-symbolic'),('Relatar problema',lambda *_:self.launch('/usr/local/bin/stackos-bugreport'),'dialog-warning-symbolic'),('Ver logs',lambda *_:self.navigate('logs'),'text-x-generic-symbolic')]:panel.append(button(name,callback,'quick',ico))
  self.win.add_tick_callback(self.resize);self.navigate('Todos');self.win.present();self.scan();self.timer=GLib.timeout_add_seconds(5,self.refresh_telemetry)
 def field(self,parent,title):
  r=box(False,8);r.append(label(title,'muted'));v=label('N/D','field-value');v.set_hexpand(True);v.set_xalign(1);v.set_ellipsize(Pango.EllipsizeMode.MIDDLE);v.set_max_width_chars(22);r.append(v);parent.append(r);return v
 def panel(self,title,ico):
  p=box(spacing=12,css='panel');r=box(False,10);r.append(icon(ico,23));r.append(label(title,'panel-title'));p.append(r);self.right.append(p);return p
 def resize(self,*_):self.right_scroll.set_visible(self.win.get_width()>=1180);return True
 def setting_changed(self,toggle):
  self.only_installed=toggle.get_active();self.render()
  try:self.config.parent.mkdir(parents=True,exist_ok=True);self.config.write_text(json.dumps({'only_installed':self.only_installed})+'\n')
  except OSError as e:self.status.set_text('Não foi possível salvar a preferência: '+str(e))
 def navigate(self,key):
  if key in ('Todos','GPU','Áudio','Rede','Proprietários'):self.filter=key;self.stack.set_visible_child_name('devices');self.render()
  else:self.stack.set_visible_child_name(key)
  for k,b in self.nav.items():b.add_css_class('selected') if k==key else b.remove_css_class('selected')
  for k,b in self.tab_buttons.items():b.add_css_class('selected') if k==self.filter else b.remove_css_class('selected')
  if key=='logs':self.logs_text.get_buffer().set_text(core.read_logs())
 def show_details(self):self.navigate('details')
 def set_busy(self,value):
  self.busy=value;self.scan_button.set_sensitive(not value);self.cards.set_sensitive(not value);self.progress.set_visible(value)
  if value and self.pulse_timer is None:self.pulse_timer=GLib.timeout_add(120,self.pulse)
  elif not value and self.pulse_timer is not None:GLib.source_remove(self.pulse_timer);self.pulse_timer=None
 def pulse(self):
  if self.busy and not self.closed:self.progress.pulse();return True
  self.pulse_timer=None;return False
 def scan(self):
  if self.busy:return
  self.set_busy(True);self.status.set_text('Verificando hardware…')
  def worker():
   try:state=core.scan();m=core.telemetry(next((d for d in state['devices'] if d['type']=='GPU'),{}));GLib.idle_add(self.scanned,state,m,None)
   except Exception as e:GLib.idle_add(self.scanned,None,None,str(e))
  threading.Thread(target=worker,daemon=True).start()
 def scanned(self,state,m,error):
  if self.closed:return False
  self.set_busy(False)
  if error:self.status.set_text('Falha na verificação: '+error);self.summary.set_text('Não foi possível verificar o hardware.')
  else:
   self.state=state;self.devices=state['devices'];self.needs_reboot=self.needs_reboot or state['reboot'];self.kernel_label.set_text(state['kernel']);g=next((d for d in self.devices if d['type']=='GPU'),{});self.active_label.set_text(g.get('module') or 'N/D');n=sum(p['present'] for d in self.devices for p in d['drivers']);self.summary.set_text(f'{len(self.devices)} dispositivo(s) detectado(s)');self.summary2.set_text(f'{n} componente(s) disponível(is) / instalado(s)');self.status.set_text(self.operation_message or ('Reinicialização necessária para aplicar as mudanças.' if self.needs_reboot else 'Verificação concluída.'))
   self.render();self.update_telemetry(m);self.update_details()
   if self.qa:GLib.timeout_add(800,self.capture)
  return False
 def render(self):
  if not hasattr(self,'cards'):return
  while self.cards.get_first_child():self.cards.remove(self.cards.get_first_child())
  selected=[d for d in self.devices if self.filter=='Proprietários' and any(p.get('type')=='prop' for p in d['drivers']) or self.filter=='Todos' or d['type']==self.filter or self.filter=='Rede' and d['type'] in ('WiFi','Bluetooth')]
  for d in selected:
   drivers=[p for p in d['drivers'] if (not self.only_installed or p['present']) and (self.filter!='Proprietários' or p.get('type')=='prop')]
   self.cards.append(self.device_card(d,drivers))
  if not selected:self.cards.append(label('Nenhum dispositivo nesta categoria.','muted',True))
  for key,b in self.tab_buttons.items():
   n=sum(sum(p.get('type')=='prop' for p in d['drivers']) if key=='Proprietários' else len(d['drivers']) for d in self.devices if key in ('Todos','Proprietários') or d['type']==key or key=='Rede' and d['type'] in ('WiFi','Bluetooth'));names={'Todos':'Todos','GPU':'Placa de vídeo','Áudio':'Áudio','Rede':'Rede e outros','Proprietários':'Proprietários'};b.get_child().get_first_child().set_text(f'{names[key]} ({n})')
 def device_card(self,d,drivers):
  exp=Gtk.Expander(expanded=True);exp.add_css_class('device-card');header=box(False,12,css='device-header');header.append(icon(d['icon'],30));t=box(spacing=5);t.set_hexpand(True);name=label(d.get('display_name',d['name']),'device-title');name.set_ellipsize(Pango.EllipsizeMode.END);name.set_max_width_chars(45);name.set_tooltip_text(d['name']);t.append(name);t.append(label(f"{d['type']} · {d['vendor']}"+(f" · {d['module']}" if d.get('module') else ''),'muted'));header.append(t)
  if d.get('module'):header.append(label('Em uso','badge installed'))
  exp.set_label_widget(header);rows=box(spacing=8,css='device-rows')
  for p in drivers:rows.append(self.driver_row(p))
  if not drivers:rows.append(label('Driver do kernel: '+(d.get('module') or 'não informado')+'. Nenhum pacote adicional listado para este dispositivo.','muted',True))
  exp.set_child(rows);return exp
 def driver_row(self,p):
  row=box(False,12,css='driver-row');row.append(icon('computer-symbolic',30));t=box(spacing=6);t.set_hexpand(True);heading=box(False,8);name=label(p['name'],'driver-title');name.set_ellipsize(Pango.EllipsizeMode.END);heading.append(name)
  tags={'rec':'RECOMENDADO','ok':'ALTERNATIVA','free':'LIVRE'}
  if p.get('tag') in tags:heading.append(label(tags[p['tag']],'badge '+('recommended' if p['tag']=='rec' else 'alternative')))
  t.append(heading)
  if p.get('type')=='prop':t.append(label('PROPRIETÁRIO','badge proprietary'))
  desc=label(p.get('desc',''),'muted',True);desc.set_max_width_chars(44);t.append(desc);t.append(label(p['pkg'],'package'));row.append(t);actions=box(spacing=6);actions.set_size_request(138,-1)
  if p.get('native'):
   actions.append(label('✓ Incluído no StackOS','installed'))
  elif p['present']:
   actions.append(label('✓ Instalado' if p['exact'] else '✓ Suporte disponível','installed'))
   source=p.get('provider') or p.get('module') or ''
   version=label(('versão '+p['version']) if p['exact'] else 'via '+source,'version');version.set_ellipsize(Pango.EllipsizeMode.MIDDLE);version.set_max_width_chars(23);version.set_tooltip_text(p['version'] or source);actions.append(version)
   if p['exact']:actions.append(button('Remover',lambda _,pkg=p['pkg']:self.confirm('remove',pkg),'remove','user-trash-symbolic'))
   else:actions.append(button('Instalar específico',lambda _,pkg=p['pkg']:self.confirm('install',pkg),'secondary'))
  else:actions.append(button('Instalar',lambda _,pkg=p['pkg']:self.confirm('install',pkg),'secondary','folder-download-symbolic'))
  row.append(actions);return row
 def confirm(self,action,pkg):
  if self.busy:return
  core.action_command(action,pkg)
  dialog=Gtk.MessageDialog(transient_for=self.win,modal=True,buttons=Gtk.ButtonsType.YES_NO,text=('Instalar ' if action=='install' else 'Remover ')+pkg+'?',secondary_text='O APT pode ajustar dependências. A operação exige autenticação do sistema.'+(' A remoção pode afetar o hardware que usa este pacote.' if action=='remove' else ''))
  def response(d,r):
   d.destroy()
   if r==Gtk.ResponseType.YES:self.operate(action,pkg)
  dialog.connect('response',response);dialog.present()
 def operate(self,action,pkg):
  if self.busy:return
  self.set_busy(True);self.status.set_text(('Instalando ' if action=='install' else 'Removendo ')+pkg+'… Aguarde a autenticação e a conclusão do APT.')
  def worker():
   try:r=core.perform(action,pkg);GLib.idle_add(self.operated,action,pkg,r.returncode,r.stderr or r.stdout)
   except Exception as e:GLib.idle_add(self.operated,action,pkg,1,str(e))
  threading.Thread(target=worker,daemon=True).start()
 def operated(self,action,pkg,code,output):
  self.set_busy(False)
  if code==0:self.needs_reboot=True;self.operation_message=f'{pkg}: operação concluída. Reinicie para aplicar as mudanças.'
  else:self.operation_message=f'Falha em {pkg}: '+output.strip()[-350:]
  self.status.set_text(self.operation_message);self.scan();return False
 def update_telemetry(self,m):
  if self.closed or not self.state:return False
  g=next((d for d in self.devices if d['type']=='GPU'),{});m=m or {}
  fields={'kernel':self.state['kernel'],'distro':self.state['distro'],'arch':self.state['arch'],'driver':g.get('module') or 'N/D'}
  for k,v in fields.items():self.system_fields[k].set_text(v);self.system_fields[k].set_tooltip_text(v)
  self.gpu_name.set_text(g.get('display_name',g.get('name','Nenhuma GPU detectada.')));total=m.get('vram_total');usage=m.get('usage');temp=m.get('temperature');power=m.get('power_w');values={'driver':g.get('module') or 'N/D','vram':f'{total/1024**3:.1f} GB' if total is not None else 'N/D','usage':f'{usage:.0f} %' if usage is not None else 'N/D','temperature':f'{temp:.0f} °C' if temp is not None else 'N/D','power':f'{power:.0f} W' if power is not None else 'N/D'}
  for k,v in values.items():self.gpu_fields[k].set_text(v)
  self.usage_bar.set_fraction(max(0,min(1,usage/100)) if usage is not None else 0);self.temp_bar.set_fraction(max(0,min(1,temp/110)) if temp is not None else 0);self.telemetry_busy=False;return False
 def refresh_telemetry(self):
  if self.closed:return False
  if self.telemetry_busy or not self.state:return True
  self.telemetry_busy=True
  def worker():
   try:m=core.telemetry(next((d for d in self.devices if d['type']=='GPU'),{}))
   except Exception:m={}
   GLib.idle_add(self.update_telemetry,m)
  threading.Thread(target=worker,daemon=True).start();return True
 def update_details(self):
  data=[f"Kernel: {self.state['kernel']}\nSistema: {self.state['distro']}\nArquitetura: {self.state['arch']}\nVerificação: {self.state['checked_at']}"]
  for d in self.devices:data.append(f"{d['name']}\nTipo: {d['type']} · PCI: {d.get('pci_address') or 'USB'}\nMódulo em uso: {d.get('module') or 'Não informado'}\n"+'\n'.join(p['pkg']+(' — instalado' if p['exact'] else ' — suporte: '+str(p.get('provider') or p.get('module')) if p['present'] else ' — não instalado') for p in d['drivers']))
  self.detail_text.set_text('\n\n'.join(data))
 def launch(self,path):
  try:subprocess.Popen([path],start_new_session=True)
  except OSError as e:self.status.set_text('Não foi possível abrir: '+str(e))
 def on_close(self,*_):
  if self.busy:self.status.set_text('Aguarde a operação terminar. Você pode minimizar a janela.');return True
  self.closed=True
  if self.timer:GLib.source_remove(self.timer);self.timer=None
  self.win=None;return False
 def capture(self):
  snapshot=Gtk.Snapshot();paint=Gtk.WidgetPaintable.new(self.win);paint.snapshot(snapshot,self.win.get_width(),self.win.get_height());texture=self.win.get_renderer().render_texture(snapshot.to_node(),None);out=BASE.parent/'qa';out.mkdir(exist_ok=True);texture.save_to_png(str(out/'preview.png'));print('RENDER_OK',self.win.get_width(),self.win.get_height(),flush=True);self.win.close();return False
if __name__=='__main__':raise SystemExit(Drivers('--qa' in sys.argv).run([sys.argv[0]]))

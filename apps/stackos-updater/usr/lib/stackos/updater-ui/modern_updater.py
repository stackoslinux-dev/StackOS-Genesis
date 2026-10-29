#!/usr/bin/python3
"""Interface StackOS Updater; instalação e configurações herdadas da versão original."""
import os, sys, json, threading, subprocess, tempfile, platform, shutil
from pathlib import Path
from datetime import datetime
os.environ.setdefault('GSK_RENDERER','cairo')
import gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,Gdk,GLib,Gio,Pango

import sys as _appearance_sys
_appearance_sys.path.insert(0, '/usr/lib/stackos')
import stackos_appearance
import stackos_window
stackos_appearance.install()
import legacy_updater as original
from state import validate,status,filtered
BASE=Path(__file__).resolve().parent

def label(text,css='',wrap=False):
    w=Gtk.Label(label=text,xalign=0,wrap=wrap)
    if css:
        for name in css.split():w.add_css_class(name)
    return w

def box(vertical=True,spacing=10,css=''):
    w=Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL,spacing=spacing)
    if css:
        for name in css.split():w.add_css_class(name)
    return w

def image(name,size=24):
    if name.endswith('.svg') or name.endswith('.png'):w=Gtk.Image.new_from_file(str(BASE/'assets'/name))
    else:w=Gtk.Image.new_from_icon_name(name)
    w.set_pixel_size(size);return w

def button(text,callback,icon=None,css=''):
    b=Gtk.Button();r=box(False,10)
    if icon:r.append(image(icon,22))
    r.append(label(text));b.set_child(r);b.connect('clicked',callback)
    if css:b.add_css_class(css)
    return b

def atomic_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def signature_link():
    link=Gtk.LinkButton.new_with_label('https://github.com/stackoslinux-dev','StackOS Linux · GitHub')
    link.set_tooltip_text('Autoria: StackOS Linux <stackoslinux@gmail.com>')
    link.add_css_class('stackos-signature')
    link.set_halign(Gtk.Align.START)
    return link

class Updater(original.StackOSUpdater):
    def __init__(self,qa=False):
        super().__init__();self.qa=qa;self.busy=False;self.query='';self.filter_mode='all';self.nav={};self.current_page='updates';self.last_stamp=None
        if qa:
            self.set_application_id('org.stackos.Updater.Preview');self.set_flags(Gio.ApplicationFlags.NON_UNIQUE)
            original.CONFIG_DIR=BASE.parent/'qa/config';original.CONFIG_FILE=original.CONFIG_DIR/'updater.json';original.STATUS_DIR=BASE.parent/'qa/cache';original.STATUS_FILE=original.STATUS_DIR/'status.json'
        self.history_file=original.STATUS_DIR/'history.json'
    def do_activate(self):
        if self.window:self.window.present();return
        provider=Gtk.CssProvider();provider.load_from_data((BASE/'theme.css').read_bytes());Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.window=Gtk.ApplicationWindow(application=self,title='StackOS Updater');stackos_window.fit_window(self.window);self.window.add_css_class('updater')
        self.window.connect('close-request',self.close_request)
        root=box(spacing=0,css='main-root');self.window.set_child(root)
        # HeaderBar supplies native dragging and window controls.
        header=Gtk.HeaderBar();header.add_css_class('chrome');header.set_title_widget(label('StackOS Updater','window-caption'));self.window.set_titlebar(header)
        top=box(False,16,'header');top.append(image('updater.svg',56));titles=box(spacing=4);titles.set_hexpand(True);titles.append(label('StackOS Updater','title'));titles.append(label('ATUALIZAÇÕES DO SISTEMA','subtitle'));top.append(titles)
        top.append(button('Atualizações',lambda *_:self.navigate('updates'),'software-update-available-symbolic','suggested-action'));top.append(button('Configurações',lambda *_:self.navigate('settings'),'emblem-system-symbolic'))
        self.check_button=button('Verificar',self.on_check_clicked,'system-search-symbolic');top.append(self.check_button);root.append(top)
        body=box(False,0);body.set_vexpand(True);root.append(body)
        sidebar=box(spacing=8,css='sidebar');sidebar.set_size_request(215,-1);body.append(sidebar)
        for key,text,icon in [('updates','Visão geral','go-home-symbolic'),('packages','Atualizações','folder-download-symbolic'),('history','Histórico','document-open-recent-symbolic'),('settings','Configurações','emblem-system-symbolic'),('repos','Repositórios','drive-harddisk-symbolic'),('system','Sistema','computer-symbolic'),('about','Sobre','help-about-symbolic')]:
            b=button(text,lambda _,k=key:self.navigate(k),icon,'nav');sidebar.append(b);self.nav[key]=b
        spacer=box();spacer.set_vexpand(True);sidebar.append(spacer);promo=box(spacing=9,css='promo');promo.append(image('updater.svg',64));promo.append(label('StackOS Updater','section-title'));promo.append(label('Modular. Leve. Poderoso.','muted'));promo.append(label('v1.1.0','muted'));sidebar.append(promo);sidebar.append(signature_link())
        self.stack=Gtk.Stack();self.stack.set_vhomogeneous(False);self.stack.set_hhomogeneous(False);self.stack.set_hexpand(True);self.stack.set_vexpand(True);body.append(self.stack)
        self.build_updates_page();self.build_settings_page()
        settings=self.stack.get_child_by_name('settings');self.stack.remove(settings);scroll=Gtk.ScrolledWindow();scroll.set_child(settings);self.stack.add_named(scroll,'settings')
        for key,title in [('history','Histórico de atividades'),('repos','Repositórios'),('system','Informações do sistema'),('about','Sobre o StackOS Updater')]:
            p=box(spacing=18,css='content');p.append(label(title,'title'));detail=label('','muted',True);detail.set_selectable(True);detail.set_valign(Gtk.Align.START);p.append(detail);setattr(self,key+'_text',detail);sc=Gtk.ScrolledWindow();sc.set_child(p);self.stack.add_named(sc,key)
        self.navigate('updates');self.render_packages();self.load_cached_status();self.window.present();self.monitor=GLib.timeout_add_seconds(3,self.poll_cache)
        if self.qa:GLib.timeout_add(900,self.qa_capture)
    def build_updates_page(self):
        page=box(spacing=16,css='content');self.stack.add_named(page,'updates')
        self.status_box=box(False,18,'status-yellow');page.append(self.status_box);self.status_icon=image('dialog-question-symbolic',48);self.status_box.append(self.status_icon)
        text=box(spacing=7);text.set_hexpand(True);self.status_title=label('Ainda não verificado','title');self.status_text=label('Verifique os repositórios para conhecer o estado atual.','status-description',True);text.append(self.status_title);text.append(self.status_text);self.status_box.append(text)
        self.last_checked=label('Última verificação\nNão disponível','muted');self.status_box.append(self.last_checked);self.verify_now=button('Verificar agora',self.on_check_clicked,'view-refresh-symbolic','suggested-action');self.status_box.append(self.verify_now)
        stats=box(False,12);stats.set_homogeneous(True);self.stats={}
        for key,title,ico in [('total','Pacotes disponíveis','package-x-generic-symbolic'),('critical','Segurança e críticas','security-high-symbolic'),('normal','Atualizações comuns','emblem-system-symbolic'),('blocked','Pacotes bloqueados','changes-prevent-symbolic')]:
            card=box(False,12,'stat '+key);card.append(image(ico,30));t=box(spacing=5);value=label('—','number');t.append(value);t.append(label(title,'muted',True));card.append(t);stats.append(card);self.stats[key]=value
        page.append(stats)
        self.progress=Gtk.ProgressBar();self.progress.set_visible(False);page.append(self.progress)
        panel=box(spacing=14,css='card');panel.set_vexpand(True);page.append(panel);row=box(False,12);title=label('Pacotes disponíveis','section-title');title.set_hexpand(True);row.append(title)
        self.search=Gtk.SearchEntry(placeholder_text='Pesquisar pacotes…');self.search.set_size_request(220,-1);self.search.connect('search-changed',self.search_changed);row.append(self.search)
        self.filter_button=Gtk.ToggleButton(label='Só críticas');self.filter_button.connect('toggled',self.filter_changed);row.append(self.filter_button);self.count_label=label('— pacotes','muted');row.append(self.count_label);panel.append(row)
        scroll=Gtk.ScrolledWindow();scroll.set_vexpand(True);scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);self.packages_box=box(spacing=8);self.packages_box.set_vexpand(True);scroll.set_child(self.packages_box);panel.append(scroll)
        footer=box(False,12,'card footer');footer.append(image('help-about-symbolic',32));self.detail_label=label('Novas atualizações serão mostradas aqui quando estiverem disponíveis.','muted',True);self.detail_label.set_hexpand(True);footer.append(self.detail_label)
        self.reboot_button=button('Reiniciar agora',self.on_reboot_clicked,'system-reboot-symbolic','destructive-action');self.reboot_button.set_visible(False);footer.append(self.reboot_button)
        self.install_button=button('Atualizar agora',self.on_install_clicked,'folder-download-symbolic','suggested-action');self.install_button.set_sensitive(False);footer.append(self.install_button);page.append(footer)
    def navigate(self,key):
        self.current_page=key;self.stack.set_visible_child_name('updates' if key=='packages' else key)
        for k,b in self.nav.items():b.add_css_class('selected') if k==key else b.remove_css_class('selected')
        if key=='packages':self.search.grab_focus()
        if key=='history':self.show_history()
        elif key=='repos':self.show_repos()
        elif key=='system':self.show_system()
        elif key=='about':self.about_text.set_text('StackOS Updater 1.1.0\n\nVerificação, instalação com progresso, atualizações automáticas e políticas originais do StackOS.\n\nIndicador: verde — atualizado; laranja — atualizações comuns, bloqueios ou estado ainda não verificado; vermelho — segurança/críticas, falhas ou reinicialização pendente.\n\nFechar esta janela mantém o serviço e o indicador ativos.')
    def search_changed(self,entry):self.query=entry.get_text();self.render_packages()
    def filter_changed(self,b):self.filter_mode='critical' if b.get_active() else 'all';self.render_packages()
    def render_packages(self):
        self.clear_packages();updates=filtered(self.updates,self.query,self.filter_mode);blocked=filtered(self.blocked,self.query,self.filter_mode);self.count_label.set_text(f'{len(updates)} de {len(self.updates)} pacotes')
        if not updates and not blocked:
            empty=box(spacing=14,css='empty');empty.set_vexpand(True);empty.set_valign(Gtk.Align.CENTER);empty.append(image('empty.svg',110));t='Nenhum pacote corresponde ao filtro.' if self.updates or self.blocked else 'Nenhum pacote aguardando atualização.';empty.append(label(t,'section-title',True));empty.append(label('Estado baseado na última verificação dos repositórios.','muted',True));self.packages_box.append(empty)
        for p in updates:self.add_package_row(p,False)
        for p in blocked:self.add_package_row(p,True)
    def apply_data(self,data):
        data=validate(data);original.StackOSUpdater.apply_data(self,data)
        total=len(self.updates);critical=data['critical_count']
        for key,value in [('total',total),('critical',critical),('normal',total-critical),('blocked',len(self.blocked))]:self.stats[key].set_text(str(value))
        checked=data.get('checked_at');self.last_checked.set_text('Última verificação\n'+self.format_time(checked));self.install_button.set_sensitive(bool(self.updates) and not self.busy)
        if data.get('reboot_required'):self.set_status('red','Reinicialização necessária','As alterações precisam de uma reinicialização para serem concluídas.')
        elif not checked and data['status']!='red':self.set_status('yellow','Ainda não verificado','Execute uma verificação para conhecer o estado atual.')
        elif not self.updates and self.blocked:self.set_status('yellow','Pacotes bloqueados','Consulte a lista para ver os motivos dos bloqueios.')
    @staticmethod
    def format_time(value):
        try:return datetime.fromisoformat(value).strftime('%d/%m/%Y, %H:%M')
        except (ValueError,TypeError):return 'Não disponível'
    def set_status(self,color,title,text):
        original.StackOSUpdater.set_status(self,color,title,text);self.status_icon.set_from_icon_name({'green':'object-select-symbolic','yellow':'dialog-warning-symbolic','red':'security-high-symbolic'}.get(color,'dialog-question-symbolic'))
    def set_busy(self,busy,text=''):
        self.busy=busy;original.StackOSUpdater.set_busy(self,busy,text);self.verify_now.set_sensitive(not busy);self.reboot_button.set_sensitive(not busy)
    def on_check_clicked(self,b):
        if self.busy:return
        original.StackOSUpdater.on_check_clicked(self,b)
    def on_install_clicked(self,b):
        if self.busy or not self.updates:return
        original.StackOSUpdater.on_install_clicked(self,b)
    def check_updates(self):
        try:original.StackOSUpdater.check_updates(self)
        except Exception as e:GLib.idle_add(self.finish_check,1,'',str(e))
    def install_updates(self):
        try:original.StackOSUpdater.install_updates(self)
        except Exception as e:GLib.idle_add(self.finish_install,1,None,str(e))
    def finish_check(self,code,stdout,stderr):
        self.set_busy(False)
        try:
            if code:raise RuntimeError(stderr.strip() or stdout.strip() or 'Não foi possível verificar os repositórios.')
            data=validate(json.loads(stdout));self.write_status(data);self.apply_data(data);self.detail_label.set_text('Verificação concluída.');self.record('Verificação',True,f"{data['count']} pacotes; {data['critical_count']} críticos")
        except Exception as e:self.failure('Falha na verificação',str(e));self.record('Verificação',False,str(e))
        return False
    def finish_install(self,code,data,last):
        self.set_busy(False)
        if code or data is None:
            self.failure('Instalação não confirmada',last or 'O instalador não retornou o resultado final. Verifique novamente antes de considerar o sistema atualizado.');self.record('Instalação',False,last or 'Resultado final ausente');return False
        try:
            data=validate(data);self.progress.set_visible(True);original.StackOSUpdater.finish_install(self,code,data,last);self.record('Instalação',True,f"{data['count']} pacotes restantes")
        except Exception as e:self.failure('Resultado inválido',str(e));self.record('Instalação',False,str(e))
        return False
    def failure(self,title,text):
        data=dict(self.current_data or {'packages':[],'blocked':[]});data['service_error']=text;data['status']='red';self.write_status(data);self.set_status('red',title,text);self.detail_label.set_text(text)
    def write_status(self,data):atomic_json(original.STATUS_FILE,data)
    def save_config(self,data):atomic_json(original.CONFIG_FILE,data)
    def load_cached_status(self):
        try:
            if original.STATUS_FILE.exists():self.apply_data(json.loads(original.STATUS_FILE.read_text()));self.last_stamp=original.STATUS_FILE.stat().st_mtime_ns
        except (ValueError,OSError) as e:self.set_status('yellow','Estado indisponível',str(e))
    def poll_cache(self):
        if not self.busy:
            try:
                if original.STATUS_FILE.stat().st_mtime_ns!=self.last_stamp:self.load_cached_status()
            except OSError:pass
        return True
    def record(self,action,ok,detail):
        try:
            history=json.loads(self.history_file.read_text()) if self.history_file.exists() else []
            if not isinstance(history,list):history=[]
            history.append({'at':datetime.now().isoformat(timespec='seconds'),'action':action,'ok':ok,'detail':detail});atomic_json(self.history_file,history[-200:])
        except (OSError,ValueError):pass
    def show_history(self):
        try:
            history=json.loads(self.history_file.read_text()) if self.history_file.exists() else []
            self.history_text.set_text('\n\n'.join(f"{self.format_time(e.get('at'))} · {e.get('action')} · {'Concluído' if e.get('ok') else 'Falhou'}\n{e.get('detail','')}" for e in reversed(history)) or 'Nenhuma atividade registrada por esta interface ainda.\n\nLog de instalações do sistema: /var/log/apt/history.log\nLog do StackOS: /var/log/stackos-updater.log')
        except (OSError,ValueError) as e:self.history_text.set_text(str(e))
    def show_repos(self):
        paths=[Path('/etc/apt/sources.list')]+sorted(Path('/etc/apt/sources.list.d').glob('*.list'))+sorted(Path('/etc/apt/sources.list.d').glob('*.sources'))
        sections=[]
        for p in paths:
            try:
                lines=[l for l in p.read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')];sections.append(p.name+'\n'+'\n'.join(lines))
            except OSError:pass
        self.repos_text.set_text('Fontes configuradas no APT (somente leitura).\n\n'+'\n\n'.join(sections))
    def show_system(self):
        info=platform.freedesktop_os_release();space=shutil.disk_usage('/');self.system_text.set_text(f"Sistema: {info.get('PRETTY_NAME','Não informado')}\nKernel: {platform.release()}\nArquitetura: {platform.machine()}\nEspaço livre em /: {space.free/1024**3:.1f} GB\n\nPreferências: {original.CONFIG_FILE}\nEstado do indicador: {original.STATUS_FILE}\nServiço: stackos-updater.service\n\nOs horários exibidos seguem o horário local do computador.")
    def on_reboot_clicked(self,b):
        if self.busy:return
        # Mantém o helper autorizado; pede confirmação para evitar reinício acidental.
        dialog=Gtk.MessageDialog(transient_for=self.window,modal=True,text='Reiniciar o computador agora?',secondary_text='Salve seu trabalho antes de continuar.',buttons=Gtk.ButtonsType.YES_NO)
        def response(d,r):
            d.destroy()
            if r==Gtk.ResponseType.YES:original.StackOSUpdater.on_reboot_clicked(self,b)
        dialog.connect('response',response);dialog.present()
    def close_request(self,*_):
        if self.busy:
            self.detail_label.set_text('Aguarde a operação terminar antes de fechar. Você pode minimizar a janela.');return True
        if self.monitor:GLib.source_remove(self.monitor);self.monitor=None
        self.window=None;return False
    def qa_capture(self):
        try:
            snapshot=Gtk.Snapshot();paint=Gtk.WidgetPaintable.new(self.window);paint.snapshot(snapshot,self.window.get_width(),self.window.get_height());texture=self.window.get_renderer().render_texture(snapshot.to_node(),None);out=BASE.parent/'qa';out.mkdir(exist_ok=True);texture.save_to_png(str(out/'preview.png'));print('RENDER_OK',self.window.get_width(),self.window.get_height(),flush=True)
        finally:self.window.close()
        return False
if __name__=='__main__':raise SystemExit(Updater('--qa' in sys.argv).run([sys.argv[0]]))

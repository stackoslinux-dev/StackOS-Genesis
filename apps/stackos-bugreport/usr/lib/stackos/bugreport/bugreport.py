#!/usr/bin/python3
import os,sys,threading,json
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
import engine
BASE=Path(__file__).resolve().parent

def label(text,css='',wrap=False):
    w=Gtk.Label(label=text,xalign=0,wrap=wrap)
    for name in css.split():w.add_css_class(name)
    return w

def box(vertical=True,spacing=10,css=''):
    w=Gtk.Box(orientation=Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL,spacing=spacing)
    for name in css.split():w.add_css_class(name)
    return w

def image(name,size):
    w=Gtk.Image.new_from_file(str(BASE/'assets'/name)) if name.endswith(('.svg','.png')) else Gtk.Image.new_from_icon_name(name)
    w.set_pixel_size(size);return w

def button(title,callback,css='',ico=None):
    w=Gtk.Button();row=box(False,10)
    if ico:row.append(image(ico,22))
    row.append(label(title));w.set_child(row)
    for name in css.split():w.add_css_class(name)
    w.connect('clicked',callback);return w

def text(buffer):return buffer.get_text(buffer.get_start_iter(),buffer.get_end_iter(),False)

def signature_link():
    link=Gtk.LinkButton.new_with_label('https://github.com/stackoslinux-dev','StackOS Linux · GitHub')
    link.set_tooltip_text('Autoria: StackOS Linux <stackoslinux@gmail.com>')
    link.add_css_class('stackos-signature')
    link.set_halign(Gtk.Align.START)
    return link

class BugReport(Gtk.Application):
    def __init__(self,qa=False):
        super().__init__(application_id='com.stackos.bugreport' if not qa else 'com.stackos.bugreport.Preview',flags=Gio.ApplicationFlags.DEFAULT_FLAGS if not qa else Gio.ApplicationFlags.NON_UNIQUE)
        self.qa=qa;self.win=None;self.busy=False;self.info=None;self.review=None;self.sent_url=None
    def do_activate(self):
        if self.win:self.win.present();return
        css=Gtk.CssProvider();css.load_from_data((BASE/'theme.css').read_bytes());Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.win=Gtk.ApplicationWindow(application=self,title='StackOS — Relatar Bug');stackos_window.fit_window(self.win);self.win.add_css_class('bugreport');self.win.connect('close-request',self.close_requested)
        bar=Gtk.HeaderBar();bar.add_css_class('header');brand=box(False,10);brand.append(image('stackos-symbol.png',42));brand.append(label('StackOS\nGenesis','brand'));bar.pack_start(brand);bar.set_title_widget(label('Relatar Bug','header-title'));self.win.set_titlebar(bar)
        root=box(spacing=0,css='root');self.win.set_child(root);scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC);scroll.set_vexpand(True);root.append(scroll)
        content=box(spacing=12,css='content');scroll.set_child(content)
        hero=box(False,20,css='hero');left=box(spacing=13);left.set_hexpand(True);intro=box(False,20);intro.append(image('bug.svg',64));titles=box(spacing=5);titles.append(label('Relatar Bug','hero-title'));titles.append(label('StackOS Genesis','accent-title'));intro.append(titles);left.append(intro);left.append(label('Descreva o problema e revise o diagnóstico antes de enviar.\nO relatório ajuda a investigar erros do sistema e dos drivers.','subtitle',True));hero.append(left);hero.append(image('report-art.svg',135));content.append(hero)
        titlecard=box(spacing=12,css='card');heading=box(False,12);heading.append(image('document-edit-symbolic',25));t=label('Título do problema','section-title');t.set_hexpand(True);heading.append(t);self.title_count=label('0 / 120','muted');heading.append(self.title_count);titlecard.append(heading)
        self.entry_title=Gtk.Entry(placeholder_text='Ex: Rede não conecta após instalação',max_length=120);self.entry_title.connect('changed',self.count_changed);titlecard.append(self.entry_title);content.append(titlecard)
        desc_card=box(spacing=12,css='card');heading=box(False,12);heading.append(image('text-x-generic-symbolic',25));t=label('Descrição detalhada','section-title');t.set_hexpand(True);heading.append(t);self.desc_count=label('0 / 5000','muted');heading.append(self.desc_count);desc_card.append(heading)
        self.text_desc=Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR);self.text_desc.set_top_margin(14);self.text_desc.set_bottom_margin(14);self.text_desc.set_left_margin(14);self.text_desc.set_right_margin(14);self.text_desc.get_buffer().connect('changed',self.count_changed)
        self.text_desc.set_tooltip_text('Descreva o que aconteceu, o que esperava e como reproduzir o problema.');ds=Gtk.ScrolledWindow();ds.set_min_content_height(130);ds.set_child(self.text_desc);ds.add_css_class('description');desc_card.append(ds);content.append(desc_card)
        hints=box(False,12);hints.set_homogeneous(True)
        for name,title,desc in [('text-x-generic-symbolic','Logs do sistema','Inclusão opcional. Revise antes de enviar.'),('security-high-symbolic','Privacidade','Identificadores comuns são ocultados. Confira o conteúdo.'),('computer-symbolic','Drivers e análise','Diagnóstico de hardware, módulos e erros recentes.')]:
            c=box(False,10,css='hint');c.append(image(name,28));t=box(spacing=5);t.append(label(title,'hint-title'));t.append(label(desc,'muted',True));c.append(t);hints.append(c)
        content.append(hints)
        options=box(False,12);self.include_logs=Gtk.CheckButton(label='Incluir logs do sistema');self.include_logs.set_active(True);options.append(self.include_logs);spacer=box();spacer.set_hexpand(True);options.append(spacer);self.drivers_button=button('Abrir StackOS Drivers',self.open_drivers,'secondary','computer-symbolic');options.append(self.drivers_button);content.append(options)
        self.status=label('O envio ao GitHub é opcional. Você também pode salvar o relatório.','muted',True);self.status.set_margin_start(30);self.status.set_margin_end(30);self.status.set_margin_bottom(8);root.append(self.status)
        footer=box(False,14,css='footer');root.append(footer);self.cancel=button('Cancelar',lambda *_:self.win.close(),'secondary');footer.append(self.cancel);footer.append(signature_link());spacer=box();spacer.set_hexpand(True);footer.append(spacer);self.spinner=Gtk.Spinner();footer.append(self.spinner);self.send_button=button('Revisar e enviar relatório',self.on_review,'primary','mail-send-symbolic');footer.append(self.send_button)
        self.win.present()
        if self.qa:GLib.timeout_add(1100,self.capture)
    def count_changed(self,*_):
        n=len(text(self.text_desc.get_buffer()));self.title_count.set_text(f'{len(self.entry_title.get_text())} / 120');self.desc_count.set_text(f'{n} / 5000')
        self.desc_count.add_css_class('error') if n>5000 else self.desc_count.remove_css_class('error')
    def set_busy(self,value,message=''):
        self.busy=value;self.send_button.set_sensitive(not value);self.entry_title.set_sensitive(not value);self.text_desc.set_sensitive(not value);self.include_logs.set_sensitive(not value)
        self.spinner.start() if value else self.spinner.stop()
        if message:self.status.set_text(message)
    def on_review(self,*_):
        if self.busy:return
        title=self.entry_title.get_text().strip();desc=text(self.text_desc.get_buffer()).strip()
        try:engine.validate_input(title,desc)
        except ValueError as e:self.status.set_text(str(e));return
        logs=self.include_logs.get_active();self.set_busy(True,'Coletando diagnóstico do sistema e dos drivers…')
        def work():
            try:info=engine.collect();body=engine.report_body(desc,info,logs);GLib.idle_add(self.collected,title,body,info)
            except Exception as e:GLib.idle_add(self.collection_failed,str(e))
        threading.Thread(target=work,daemon=True).start()
    def collection_failed(self,message):self.set_busy(False,'Falha na coleta: '+message);return False
    def collected(self,title,body,info):
        self.set_busy(False,'Diagnóstico coletado. Revise o conteúdo antes de enviar.');self.info=info;self.show_review(title,body);return False
    def show_review(self,title,body):
        if self.review:self.review.present();return
        self.pending_title=title;self.sent_url=None
        self.review=Gtk.Window(title='Revisar relatório',transient_for=self.win,modal=True,default_width=830,default_height=690);self.review.add_css_class('bugreport');self.review.connect('close-request',self.close_review)
        root=box(spacing=14,css='content root');self.review.set_child(root);root.append(label('Revise o relatório','hero-title'));root.append(label(f'Destino público: github.com/{engine.REPO}\nO conteúdo abaixo é editável e será o conteúdo enviado. Confira nomes, dados de rede e detalhes pessoais.','muted',True))
        scroll=Gtk.ScrolledWindow();scroll.set_vexpand(True);self.preview=Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR,monospace=True);self.preview.set_top_margin(12);self.preview.set_left_margin(12);self.preview.set_right_margin(12);self.preview.set_bottom_margin(12);self.preview.get_buffer().set_text(body);scroll.set_child(self.preview);scroll.add_css_class('description');root.append(scroll)
        self.review_status=label('Nenhum dado foi enviado.','muted',True);root.append(self.review_status)
        self.review_actions=box(False,10);root.append(self.review_actions);self.review_actions.append(button('Voltar',lambda *_:self.review.close(),'secondary'));self.review_actions.append(button('Salvar relatório',self.save_report,'secondary','document-save-symbolic'))
        if engine.token():self.api_button=button('Enviar ao GitHub',self.on_send,'primary','mail-send-symbolic');self.review_actions.append(self.api_button)
        else:self.review_actions.append(button('Abrir no GitHub',self.open_github,'primary','web-browser-symbolic'));self.review_status.set_text('Sem token configurado. Você pode salvar ou copiar o relatório para o formulário do GitHub.')
        self.review.present()
    def close_review(self,*_):
        if self.busy:return True
        self.review=None;return False
    def on_send(self,*_):
        if self.busy or not self.review or self.sent_url:return
        body=text(self.preview.get_buffer())
        if not body.strip() or len(body)>60000:self.review_status.set_text('O relatório deve conter entre 1 e 60000 caracteres.');return
        title=self.pending_title;self.set_busy(True,'Enviando relatório revisado…');self.review_actions.set_sensitive(False);self.preview.set_editable(False);self.review_status.set_text('Enviando ao GitHub…')
        def work():
            try:url=engine.send_issue(title,body);GLib.idle_add(self.sent,url,None)
            except Exception as e:GLib.idle_add(self.sent,None,str(e))
        threading.Thread(target=work,daemon=True).start()
    def sent(self,url,error):
        self.set_busy(False)
        if not self.review:return False
        self.review_actions.set_sensitive(True)
        if error:self.preview.set_editable(True);self.review_status.set_text('Erro: '+error);self.status.set_text('O envio não foi confirmado. O relatório continua disponível para salvar.');return False
        self.sent_url=url;self.api_button.set_sensitive(False);self.review_status.set_text('Enviado com sucesso: '+url);self.status.set_text('Relatório enviado. Obrigado por ajudar a melhorar o StackOS.');self.review_actions.append(button('Ver issue',lambda *_:Gtk.show_uri(self.review,url,Gdk.CURRENT_TIME),'secondary'));return False
    def open_github(self,*_):
        body=text(self.preview.get_buffer());self.review.get_clipboard().set(body);Gtk.show_uri(self.review,engine.github_form(self.pending_title),Gdk.CURRENT_TIME);self.review_status.set_text('Relatório copiado. Cole-o na descrição do formulário do GitHub. O envio será feito somente quando você confirmar no site.')
    def save_report(self,*_):
        chooser=Gtk.FileChooserNative.new('Salvar relatório',self.review,Gtk.FileChooserAction.SAVE,'Salvar','Cancelar');chooser.set_current_name('stackos-bugreport.md')
        content='# '+self.pending_title+'\n\n'+text(self.preview.get_buffer())
        def done(dialog,response):
            if response==Gtk.ResponseType.ACCEPT:
                try:
                    p=Path(dialog.get_file().get_path());p.write_text(content,encoding='utf8');self.review_status.set_text('Relatório salvo em '+str(p))
                except (OSError,TypeError) as e:self.review_status.set_text('Não foi possível salvar: '+str(e))
            dialog.destroy()
        chooser.connect('response',done);chooser.show()
    def open_drivers(self,*_):
        try:subprocess=__import__('subprocess');subprocess.Popen(['/usr/local/bin/stackos-drivers'],start_new_session=True)
        except OSError as e:self.status.set_text('Não foi possível abrir o StackOS Drivers: '+str(e))
    def close_requested(self,*_):
        if self.busy:self.status.set_text('Aguarde a coleta ou o envio terminar. Você pode minimizar a janela.');return True
        if self.review:self.review.close()
        self.win=None;return False
    def capture(self):
        snapshot=Gtk.Snapshot();paint=Gtk.WidgetPaintable.new(self.win);paint.snapshot(snapshot,self.win.get_width(),self.win.get_height());texture=self.win.get_renderer().render_texture(snapshot.to_node(),None);path=BASE.parent/'qa';path.mkdir(exist_ok=True);texture.save_to_png(str(path/'preview.png'));print('RENDER_OK',self.win.get_width(),self.win.get_height(),flush=True);self.win.close();return False
if __name__=='__main__':raise SystemExit(BugReport('--qa' in sys.argv).run([sys.argv[0]]))

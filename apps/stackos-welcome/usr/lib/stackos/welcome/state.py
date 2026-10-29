"""Preferência por usuário usando o padrão XDG Autostart."""
from pathlib import Path
import os,configparser,tempfile,platform
NAME='stackos-welcome.desktop'

def config_home():return Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))
def autostart_file(root=None):return (Path(root) if root is not None else config_home())/'autostart'/NAME

def startup_enabled(root=None):
 p=autostart_file(root)
 if not p.exists():return True
 cp=configparser.ConfigParser(interpolation=None,strict=False)
 try:
  cp.read(p,encoding='utf8');entry=cp['Desktop Entry']
  return entry.get('Hidden','false').lower()!='true' and entry.get('X-GNOME-Autostart-enabled','true').lower()!='false'
 except (OSError,KeyError,configparser.Error):return True

def set_startup(enabled,root=None):
 p=autostart_file(root);p.parent.mkdir(parents=True,exist_ok=True)
 content='''[Desktop Entry]
Type=Application
Name=Bem-vindo ao StackOS
Comment=Guia de primeiros passos do StackOS Genesis
Exec=/usr/local/bin/stackos-welcome --autostart
Icon=org.stackos.Welcome
Terminal=false
X-GNOME-Autostart-Delay=3
'''+f'Hidden={str(not enabled).lower()}\nX-GNOME-Autostart-enabled={str(bool(enabled)).lower()}\n'
 fd,tmp=tempfile.mkstemp(prefix='.stackos-welcome-',dir=p.parent)
 try:
  with os.fdopen(fd,'w') as file:file.write(content);file.flush();os.fsync(file.fileno())
  os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
 return p

def system_info():
 try:data=platform.freedesktop_os_release()
 except OSError:data={}
 name=data.get('NAME','StackOS Genesis');version=data.get('VERSION_ID','');base=data.get('UBUNTU_CODENAME','')
 return {'name':name,'version':version,'display':data.get('PRETTY_NAME',(name+' '+version).strip()),'base':'Ubuntu · '+base if base else data.get('ID_LIKE','Linux'),'kernel':platform.release(),'arch':platform.machine()}

APPS={'store':['/usr/local/bin/stackos-store'],'drivers':['/usr/local/bin/stackos-drivers'],'updater':['/usr/local/bin/stackos-updater'],'gpu':['/usr/bin/stackos-gpu-manager'],'bugreport':['/usr/local/bin/stackos-bugreport'],'settings':['gnome-control-center']}
LINKS={'site':'https://stackoslinux-dev.github.io','docs':'https://stackoslinux-dev.github.io/docs','forum':'https://github.com/stackoslinux-dev/repo/discussions','contact':'mailto:stackoslinux@gmail.com'}

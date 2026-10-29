"""Catálogo DEB local: APT e AppStream, sem executar comandos de busca via shell."""
import apt,gzip,yaml,json,re,subprocess,hashlib,os,html
from pathlib import Path
from datetime import datetime
BASE=Path(__file__).resolve().parent
BACKUP_ROOT=Path('/var/backups/stackos')
CATEGORIES={'Internet':{'Network','WebBrowser'},'Desenvolvimento':{'Development'},'Multimídia':{'AudioVideo','Audio','Video','Graphics'},'Office':{'Office'},'Jogos':{'Game'},'Segurança':{'Security'},'Sistema':{'System','Settings','Utility'}}
BLOCKED={'snapd','snap-store','snapcraft','gnome-software-plugin-snap'}
PROTECTED={'stackos-c3-runtime','apt','dpkg','systemd','systemd-sysv','libc6','sudo','pkexec','gnome-shell','gnome-session','gdm3','stackos-store','stackos-desktop-minimal','stackos-session','stackos-base-files','ubuntu-desktop','ubuntu-minimal','linux-generic'}
def valid_name(s):return isinstance(s,str) and re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?',s) is not None

def native(candidate):
 if not candidate:return False
 if candidate.package.name in BLOCKED:return False
 if any(a.name in BLOCKED for dep in candidate.dependencies for a in dep.or_dependencies):return False
 desc=(candidate.summary+' '+candidate.description).lower()
 return not ('snap' in desc and any(s in desc for s in ('transitional','transition','transição','dummy package','snap version','snap package')))

def trusted(version):return bool(version and any(o.trusted for o in version.origins if o.archive!='now'))

def choose_text(value):
 if isinstance(value,str):return value
 if not isinstance(value,dict):return ''
 return next((value[k] for k in ('pt_BR','pt','pt_PT','C','en','en_GB') if value.get(k)),next(iter(value.values()),''))

def category(cats):
 for name,terms in CATEGORIES.items():
  if terms.intersection(cats):return name
 return 'Outros'

def strip_markup(value):return html.unescape(re.sub('<[^>]+>',' ',value)).strip()

def read_appstream(paths=None):
 apps={};errors=[]
 paths=paths if paths is not None else sorted(Path('/var/lib/apt/lists').glob('*dep11_Components-*.yml.gz'))
 for path in paths:
  try:
   with gzip.open(path,'rt',encoding='utf8') as stream:
    for d in yaml.load_all(stream,Loader=yaml.CSafeLoader):
     if not isinstance(d,dict) or d.get('Type') not in ('desktop-application','console-application'):continue
     pkg=d.get('Package');pkg=pkg[0] if isinstance(pkg,list) and pkg else pkg
     if not valid_name(pkg):continue
     ico=d.get('Icon') or {};launch=d.get('Launchable') or {};desktop=launch.get('desktop-id',[]);url=d.get('Url') or {}
     if pkg not in apps:apps[pkg]={'pkg':pkg,'name':choose_text(d.get('Name')) or pkg,'summary':choose_text(d.get('Summary')),'description':strip_markup(choose_text(d.get('Description'))),'category':category(set(d.get('Categories') or [])),'icon':ico.get('stock') or (d.get('ID') or 'application-x-executable').replace('.desktop',''),'url':url.get('homepage','') if isinstance(url,dict) else '', 'desktop':desktop[0] if desktop else '', 'license':d.get('ProjectLicense','Não informada'),'appstream':True,'cached_icon':next((x.get('name','') for x in ico.get('cached',[]) if x.get('width')==64),'')}
  except (OSError,ValueError,yaml.YAMLError) as e:errors.append(path.name+': '+str(e)[:150])
 return apps,errors

def read_native_desktops(owned_paths, known_packages):
 import configparser,shlex,shutil
 rows={}
 for path in sorted(Path('/usr/share/applications').glob('*.desktop')):
  if str(path) in owned_paths:continue
  cp=configparser.ConfigParser(interpolation=None,strict=False)
  try:
   cp.read(path,encoding='utf8');entry=cp['Desktop Entry']
   if entry.get('Type','Application')!='Application' or entry.get('NoDisplay','false').lower()=='true' or entry.get('Hidden','false').lower()=='true':continue
   only=set(entry.get('OnlyShowIn','').strip(';').split(';'))
   if entry.get('OnlyShowIn') and not only.intersection({'GNOME','StackOS','stackos'}):continue
   args=shlex.split(entry.get('Exec',''))
   if not args:continue
   if Path(args[0]).name=='env':
    args=args[1:]
    while args and ('=' in args[0] or args[0].startswith('-')):args=args[1:]
   if not args:continue
   executable=entry.get('TryExec') or args[0]
   if not (Path(executable).is_file() and os.access(executable,os.X_OK) if '/' in executable else shutil.which(executable)):continue
   name=entry.get('Name[pt_BR]',entry.get('Name','')).strip()
   if not name:continue
   pkg='c3-desktop-'+re.sub('[^a-z0-9+.-]','-',path.stem.casefold())
   if pkg in known_packages:continue
   rows[pkg]={'pkg':pkg,'name':name,'summary':entry.get('Comment[pt_BR]',entry.get('Comment','Aplicativo incluído no StackOS C3')),'description':'Aplicativo nativo presente no sistema.','category':category(set(entry.get('Categories','').split(';'))),'icon':entry.get('Icon','application-x-executable'),'url':entry.get('X-Website',''),'desktop':path.name,'license':'Consulte os arquivos de licença do aplicativo','appstream':False,'installed':True,'upgradable':False,'version':'Incluído no sistema C3','candidate':None,'source':'StackOS C3 · instalação nativa','trusted':True,'native':True,'can_install':False,'protected':True,'size':None,'system_native':True}
  except (OSError,KeyError,ValueError,configparser.Error):continue
 return rows

class Catalog:
 def __init__(self):
  self.cache=apt.Cache();metadata,self.errors=read_appstream();self.apps={};curated=json.loads((BASE/'curated.json').read_text());self.featured=[]
  for cat,rows in curated.items():
   for pkg,name,summary,icon,url in rows:
    if pkg not in metadata:metadata[pkg]={'pkg':pkg,'name':name,'summary':summary,'description':'','category':cat,'icon':icon,'url':url,'desktop':'','license':'Não informada','appstream':False}
    else:metadata[pkg].update(icon=icon,url=url or metadata[pkg]['url'],category=cat if cat!='Jogos Nativos' else 'Jogos')
    if pkg not in self.featured:self.featured.append(pkg)
  for cat,packages in json.loads((BASE/'popular.json').read_text()).items():
   for pkg in packages:
    if pkg not in self.cache:continue
    candidate=self.cache[pkg].candidate
    if not candidate or not native(candidate) or not trusted(candidate):continue
    if pkg not in metadata:metadata[pkg]={'pkg':pkg,'name':pkg,'summary':candidate.summary,'description':candidate.description,'category':cat,'icon':pkg,'url':candidate.homepage or '', 'desktop':'','license':'Não informada','appstream':False}
    if pkg not in self.featured:self.featured.append(pkg)
  # Apps instalados com atalhos desktop entram na área Instalados mesmo sem AppStream.
  ownership={}
  p=subprocess.run(['dpkg-query','-S','/usr/share/applications/*.desktop'],capture_output=True,text=True,timeout=15)
  for line in p.stdout.splitlines():
   if ': /' in line:
    owner,path=line.rsplit(': ',1);ownership[path]=owner.split(',')[0].split(':')[0]
  import configparser
  for path,pkg in ownership.items():
   if pkg in metadata or pkg not in self.cache:continue
   cp=configparser.ConfigParser(interpolation=None,strict=False)
   try:
    cp.read(path,encoding='utf8');entry=cp['Desktop Entry']
    if entry.get('NoDisplay','false').lower()=='true':continue
    metadata[pkg]={'pkg':pkg,'name':entry.get('Name[pt_BR]',entry.get('Name',pkg)),'summary':entry.get('Comment[pt_BR]',entry.get('Comment','')),'description':'','category':category(set(entry.get('Categories','').split(';'))),'icon':entry.get('Icon','application-x-executable'),'desktop':Path(path).name,'url':'','license':'Não informada','appstream':False}
   except (OSError,KeyError,configparser.Error):pass
  for pkg,info in metadata.items():
   if pkg not in self.cache or pkg in BLOCKED:continue
   p=self.cache[pkg];c=p.candidate
   if not p.is_installed and (not native(c) or not trusted(c) or not c.downloadable):continue
   if c and not native(c):continue
   if pkg=='firefox':info['name']='Firefox'
   self.apps[pkg]=self.decorate(info,p)
  self.apps.update(read_native_desktops(ownership,self.apps))
  self.featured=[p for p in self.featured if p in self.apps]
  if not self.featured:self.featured=sorted(self.apps)
  resolve_icons(self.apps)
  self.updates=[{'pkg':p.name,'name':p.name,'version':p.candidate.version} for p in self.cache if p.is_installed and p.is_upgradable and p.candidate]
 def decorate(self,info,p):
  c=p.candidate;i=p.installed;v=c or i
  source=', '.join(dict.fromkeys((o.origin or o.site or 'APT')+(' · '+o.component if o.component else '') for o in v.origins if o.archive!='now')) if v else ''
  return dict(info,upgradable=p.is_upgradable,installed=p.is_installed,version=i.version if i else None,candidate=c.version if c else None,summary=info.get('summary') or (v.summary if v else ''),description=info.get('description') or (v.description if v else ''),source=source or 'Instalação local / sem origem no índice atual',trusted=trusted(c),native=native(c),can_install=bool(c and trusted(c) and native(c) and c.downloadable),protected=p.essential or p.name in PROTECTED,size=c.size if c else None)
 def lookup(self,pkg):
  if pkg not in self.cache or pkg in BLOCKED:return None
  p=self.cache[pkg];c=p.candidate
  if not p.is_installed and not (native(c) and trusted(c) and c.downloadable):return None
  if c and not native(c):return None
  return self.apps.get(pkg) or self.decorate({'pkg':pkg,'name':pkg,'summary':c.summary if c else '', 'description':'','category':'Pacotes','icon':'package-x-generic-symbolic','desktop':'','url':c.homepage if c else '', 'license':'Não informada','appstream':False},p)
 def search(self,query='',cat='Todos',installed=False,packages=False):
  needle=query.strip().casefold()
  apps=list(self.apps.values())
  if packages and needle:
   known=set(self.apps)
   for p in self.cache:
    c=p.candidate
    if p.name not in known and c and native(c) and trusted(c) and c.downloadable and (needle in p.name.casefold() or needle in c.summary.casefold()):apps.append(self.decorate({'pkg':p.name,'name':p.name,'summary':c.summary,'description':c.description,'category':'Pacotes','icon':'package-x-generic-symbolic','desktop':'','url':c.homepage or '', 'license':'Não informada','appstream':False},p))
  result=[a for a in apps if (not installed or a['installed']) and (cat=='Todos' or a['category']==cat or cat=='Jogos Nativos' and a['category']=='Jogos') and (not needle or needle in (a['name']+' '+a['pkg']+' '+a['summary']).casefold())]
  return sorted(result,key=lambda a:(self.featured.index(a['pkg']) if not needle and a['pkg'] in self.featured else len(self.featured),a['name'].casefold()))

def simulate(action,pkg,cache=None):
 if action not in ('install','remove') or not valid_name(pkg):raise ValueError('Pacote ou ação inválida.')
 cache=cache if cache is not None else apt.Cache()
 if action=='install' and pkg.split(':')[0] in BLOCKED:raise RuntimeError('Snap está bloqueado nesta loja.')
 if pkg not in cache:raise RuntimeError('Pacote não encontrado no APT.')
 p=cache[pkg]
 if action=='install' and not (native(p.candidate) and trusted(p.candidate) and p.candidate.downloadable):raise RuntimeError('O pacote não possui um DEB nativo disponível em origem confiável configurada.')
 if action=='remove' and not p.is_installed:raise RuntimeError('O pacote já não está instalado.')
 result=subprocess.run(['apt-get','-s',action,pkg],capture_output=True,text=True,timeout=45,env={**os.environ,'LC_ALL':'C'})
 if result.returncode:raise RuntimeError(result.stderr.strip() or result.stdout[-1500:])
 changes=[]
 for line in result.stdout.splitlines():
  if line.startswith(('Inst ','Remv ')):
   kind,name=line.split()[:2]
   if kind=='Inst' and name.split(':')[0] in BLOCKED:raise RuntimeError('A transação tentaria instalar Snap; operação bloqueada.')
   if kind=='Remv' and (name.split(':')[0] in PROTECTED or name in cache and cache[name].essential or name.startswith(('linux-image-','linux-modules-'))):raise RuntimeError('A transação removeria um componente essencial: '+name)
   changes.append(line)
 payload={'action':action,'package':pkg,'changes':changes,'candidate':p.candidate.version if p.candidate else None}
 payload['digest']=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest();return payload

def vote(votes,pkg,kind):
 if kind not in ('up','down'):raise ValueError('Voto inválido.')
 v=dict(votes.get(pkg,{'up':0,'down':0,'mine':None}));old=v.get('mine')
 if old in ('up','down'):v[old]=max(0,int(v.get(old,0))-1)
 v['mine']=None if old==kind else kind
 if v['mine']:v[kind]=int(v.get(kind,0))+1
 return v

def backup_path(name,root=None):
 root=BACKUP_ROOT if root is None else root
 if not re.fullmatch(r'\d{8}_\d{6}',name):raise ValueError('Nome de backup inválido.')
 path=root/name
 if path.is_symlink() or not path.is_dir() or path.resolve().parent!=root.resolve():raise ValueError('Backup inválido ou fora da pasta autorizada.')
 return path

def backup_action(action,name):
 import shutil
 root=BACKUP_ROOT;root.mkdir(parents=True,exist_ok=True)
 exclude=['--exclude=/proc/***','--exclude=/sys/***','--exclude=/dev/***','--exclude=/tmp/***','--exclude=/run/***','--exclude=/var/backups/stackos/***']
 if action=='create':
  entries=[p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and re.fullmatch(r'\d{8}_\d{6}',p.name)]
  if len(entries)>=3:raise RuntimeError('Já existem 3 backups. Apague um explicitamente antes de criar outro.')
  target=root/datetime.now().strftime('%Y%m%d_%H%M%S');target.mkdir();(target/'.stackos-backup-incomplete').touch();previous=max(entries,key=lambda p:p.name) if entries else None;link=['--link-dest='+str(previous.resolve())] if previous and not (previous/'.stackos-backup-incomplete').exists() else [];result=subprocess.call(['rsync','-aAX','--numeric-ids',*link,*exclude,'/',str(target)+'/'])
  if result!=0:raise RuntimeError('O backup não foi concluído (rsync código '+str(result)+'). A pasta parcial foi preservada para inspeção.')
  (target/'.stackos-backup-incomplete').unlink();marker=target/'.stackos-backup-complete';marker.write_text('StackOS Store\n');latest=root/'latest'
  if latest.is_symlink():latest.unlink()
  if not latest.exists():latest.symlink_to(target)
  return 0
 path=backup_path(name,root)
 if action=='delete':shutil.rmtree(path);return 0
 if action=='restore' and (path/'.stackos-backup-incomplete').exists():raise RuntimeError('Este backup está incompleto e não pode ser restaurado.')
 if action=='restore':return subprocess.call(['rsync','-aAX','--numeric-ids','--delete',*exclude,'--exclude=/.stackos-backup-complete',str(path)+'/', '/'])
 raise ValueError('Ação de backup inválida.')


def resolve_icons(apps,cache_dir=None):
 import tarfile
 cache_dir=Path(cache_dir) if cache_dir else Path(os.environ.get('STACKOS_STORE_ICON_CACHE',str(Path.home()/'.cache/stackos-store/icons')))
 wanted={Path(a.get('cached_icon','')).name for a in apps.values() if a.get('cached_icon')}
 found={}
 try:
  cache_dir.mkdir(parents=True,exist_ok=True)
  for name in wanted:
   p=cache_dir/name
   if p.is_file() and p.stat().st_size>0:found[name]=str(p)
  missing=wanted-set(found)
  for archive in sorted(Path('/var/lib/apt/lists').glob('*dep11_icons-64x64.tar.gz')):
   if not missing:break
   try:
    with tarfile.open(archive,'r:gz') as tar:
     for member in tar:
      name=Path(member.name).name
      if name not in missing or not member.isfile() or member.size>512000:continue
      data=tar.extractfile(member).read()
      if not data.startswith(b'\x89PNG\r\n\x1a\n'):continue
      p=cache_dir/name;p.write_bytes(data);found[name]=str(p);missing.remove(name)
   except (OSError,tarfile.TarError):continue
  for a in apps.values():
   name=Path(a.get('cached_icon','')).name
   if name in found:a['icon']=found[name]
 except OSError:pass
 return len(found)

def updater_status():
 result=subprocess.run(['/usr/lib/stackos/stackos-updater-helper','check'],capture_output=True,text=True,timeout=60)
 if result.returncode:raise RuntimeError(result.stderr.strip() or 'O StackOS Updater não respondeu.')
 data=json.loads(result.stdout)
 if not isinstance(data,dict) or not isinstance(data.get('packages'),list):raise ValueError('Resposta inválida do StackOS Updater.')
 for p in data['packages']:
  if not isinstance(p,dict) or not valid_name(p.get('name')):raise ValueError('Pacote inválido na resposta do Updater.')
  if p['name'] in BLOCKED:raise RuntimeError('O Updater retornou um componente Snap bloqueado pela loja.')
 return data

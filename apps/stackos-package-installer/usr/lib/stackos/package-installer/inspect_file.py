"""Inspeção de arquivos sem executar instaladores."""
import subprocess,hashlib,re,shlex,os
from pathlib import Path
BLOCKED={'snapd','snap-confine','snapd-xdg-open','ubuntu-core-launcher','snap-store','snapcraft','gnome-software-plugin-snap'}
FORMATS={'deb':('DEB','Pacote nativo'),'appimage':('AppImage','Aplicativo portátil'),'run':('RUN','Instalador Linux'),'script':('SH','Script de shell'),'executable':('Executável','Binário Linux'),'flatpak':('Flatpak','Pacote Flatpak'),'flatpakref':('Flatpak','Referência Flatpak'),'archive':('Arquivo portátil','ZIP/TAR'),'windows':('Windows','Compatibilidade Wine')}

def output(args):
 try:
  p=subprocess.run(args,capture_output=True,text=True,errors='replace',timeout=15,env={**os.environ,'LC_ALL':'C'})
  if p.returncode:raise ValueError(p.stderr.strip() or 'Não foi possível analisar o arquivo.')
  return p.stdout.strip()
 except subprocess.TimeoutExpired:raise ValueError('A análise do arquivo excedeu o tempo limite.') from None

def fingerprint(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as file:
  for chunk in iter(lambda:file.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()

def detect(path):
 name=path.name.casefold()
 if name.endswith('.snap'):return 'snap'
 desc=output(['file','-b','--',str(path)]).casefold()
 if any(x in desc for x in ('pe32 executable','pe32+ executable','ms-dos executable','msi installer','windows installer')):return 'windows'
 if name.endswith(('.exe','.msi')):return 'windows'
 if name.endswith('.deb'):return 'deb'
 if name.endswith('.rpm'):return 'rpm'
 if name.endswith(('.zip','.tar','.tar.gz','.tar.xz','.tar.bz2','.tgz','.txz')):return 'archive'
 if name.endswith('.flatpakref'):return 'flatpakref'
 if name.endswith('.flatpak'):return 'flatpak'
 if name.endswith('.appimage') or 'appimage' in desc:
  if 'elf ' not in desc:raise ValueError('O arquivo não contém um executável AppImage Linux válido.')
  return 'appimage'
 if name.endswith('.run'):return 'run'
 if name.endswith('.sh') or 'shell script' in desc or 'bash script' in desc:return 'script'
 if 'elf ' in desc and 'executable' in desc:return 'executable'
 return 'unknown'

def inspect(source):
 path=Path(source).expanduser().resolve(strict=True)
 if not path.is_file():raise ValueError('Selecione um arquivo regular.')
 kind=detect(path);data={'path':path,'kind':kind,'name':path.name,'size':path.stat().st_size,'sha256':fingerprint(path),'ready':kind in FORMATS,'metadata':{},'message':'Arquivo reconhecido. Confira a origem antes de continuar.'}
 if kind=='snap':data.update(ready=False,message='Snap é bloqueado pela política do StackOS.')
 elif kind=='windows':
  import shutil
  data.update(ready=bool(shutil.which('wine')),message='Aplicativo Windows. A execução será feita pela compatibilidade Wine como usuário; nem todo aplicativo é compatível.' if shutil.which('wine') else 'Aplicativo Windows. Wine não está instalado. Procure uma versão Linux na loja ou configure Wine/Bottles.')
 elif kind=='rpm':data.update(ready=False,message='RPM reconhecido. O StackOS usa DEB; procure uma versão compatível na loja ou no site do projeto.')
 elif kind=='archive':
  validate_archive(path);data['message']='Arquivo portátil reconhecido. Os arquivos serão extraídos para Applications, sem executar scripts automaticamente.'
 elif kind=='unknown':data.update(ready=False,message='Formato não reconhecido como instalador Linux compatível.')
 elif kind in ('appimage','run','executable'):
  check_elf_arch(path)
 elif kind=='deb':
  raw=output(['dpkg-deb','-f',str(path),'Package','Version','Architecture','Depends','Pre-Depends','Description']);values={}
  for line in raw.splitlines():
   if ': ' in line:key,value=line.split(': ',1);values[key]=value
  package=values.get('Package','');arch=values.get('Architecture','');native=output(['dpkg','--print-architecture']);foreign=output(['dpkg','--print-foreign-architectures']).splitlines()
  if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*',package):raise ValueError('Metadados do pacote DEB inválidos.')
  deps=values.get('Depends','')+' '+values.get('Pre-Depends','');description=values.get('Description','').casefold()
  if package in BLOCKED or any(re.search(r'(?<![a-z0-9-])'+re.escape(p)+r'(?![a-z0-9-])',deps) for p in BLOCKED) or 'snap' in description and ('transitional' in description or 'transition' in description):raise ValueError('Este DEB usa Snap ou é um pacote de transição. Instalação bloqueada.')
  if arch not in ('all',native,*foreign):raise ValueError(f'Arquitetura {arch} não habilitada neste PC ({native}).')
  check_deb_scripts(path)
  data['metadata']=values;data['name']=package;data['message']='DEB válido. O helper autenticado fará nova conferência e resolverá as dependências pelo APT.'
 if kind in ('flatpak','flatpakref'):
  import shutil
  if not shutil.which('flatpak'):data.update(ready=False,message='Flatpak não está instalado. O suporte continua disponível quando a ferramenta estiver instalada.')
 return data

def execution_command(data):
 path=Path(data['path'])
 if data['kind']=='windows':return ['wine','msiexec','/i',str(path)] if path.suffix.casefold()=='.msi' else ['wine',str(path)]
 if data['kind']=='script':return ['/usr/bin/bash',str(path)]
 if data['kind'] in ('run','appimage','executable'):return [str(path)]
 raise ValueError('Este formato não deve ser executado diretamente.')


def validate_archive(path):
 import zipfile,tarfile
 if zipfile.is_zipfile(path):
  with zipfile.ZipFile(path) as archive:entries=[(i.filename,i.file_size) for i in archive.infolist()]
 elif tarfile.is_tarfile(path):
  with tarfile.open(path) as archive:entries=[(i.name,i.size) for i in archive.getmembers()]
 else:raise ValueError('O arquivo não é um ZIP/TAR válido.')
 if len(entries)>20000 or sum(size for _,size in entries)>8*1024**3:raise ValueError('Arquivo excede o limite de extração (20 mil itens / 8 GB).')
 for name,size in entries:
  p=Path(name)
  if p.is_absolute() or '..' in p.parts:raise ValueError('O arquivo contém caminhos fora da pasta de extração.')
 return entries

def extract_archive(path,destination=None):
 import zipfile,tarfile,time,stat,shutil
 path=Path(path);validate_archive(path);root=Path(destination) if destination else Path.home()/'Applications';root.mkdir(parents=True,exist_ok=True);name=re.sub(r'[^A-Za-z0-9._-]','_',path.name)[:80];target=root/(name+'-'+str(time.time_ns()));target.mkdir()
 try:
  if zipfile.is_zipfile(path):
   with zipfile.ZipFile(path) as archive:
    for item in archive.infolist():
     mode=item.external_attr>>16
     if stat.S_ISLNK(mode):raise ValueError('Link simbólico ZIP não é aceito para extração automática.')
    archive.extractall(target)
  else:
   with tarfile.open(path) as archive:archive.extractall(target,filter='data')
  return target
 except BaseException:
  shutil.rmtree(target,ignore_errors=True);raise


def check_elf_arch(path):
 import platform,struct
 with Path(path).open('rb') as stream:header=stream.read(20)
 if not header.startswith(b'\x7fELF'):return
 if len(header)<20:raise ValueError('Cabeçalho ELF incompleto.')
 machine=struct.unpack('<H' if header[5]==1 else '>H',header[18:20])[0]
 accepted={'x86_64':{62,3},'amd64':{62,3},'i686':{3},'aarch64':{183},'arm64':{183},'armv7l':{40},'riscv64':{243},'ppc64le':{21}}
 host=platform.machine().lower()
 if host in accepted and machine not in accepted[host]:raise ValueError('Este executável usa uma arquitetura diferente da máquina ('+host+').')


def check_deb_scripts(path):
 import tarfile,io
 process=subprocess.Popen(['dpkg-deb','--ctrl-tarfile',str(path)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
 try:
  content=process.stdout.read(2_000_001)
  if len(content)>2_000_000:raise ValueError('Metadados de controle excedem o limite de análise.')
  if process.wait(timeout=15):raise ValueError('Não foi possível ler os scripts de manutenção.')
  with tarfile.open(fileobj=io.BytesIO(content)) as archive:
   for member in archive.getmembers():
    if not member.isfile() or member.name.rsplit('/',1)[-1] not in ('preinst','postinst','prerm','postrm'):continue
    if member.size>1_000_000:raise ValueError('Script de manutenção grande demais para análise automática.')
    script=archive.extractfile(member).read().decode('utf8',errors='replace')
    if re.search(r'(?im)(?:^|[;\n&|])\s*(?:/usr/bin/)?snap\s+(?:install|refresh|run)\b',script) or re.search(r'(?is)apt(?:-get)?\s+install[^\n]*\bsnapd\b',script):raise ValueError('O script deste DEB tenta usar Snap. Instalação bloqueada.')
 finally:
  if process.poll() is None:process.kill()
  process.wait()

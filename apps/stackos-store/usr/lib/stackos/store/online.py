"""Pesquisa externa explícita em diretórios oficiais; não baixa nem instala binários."""
import urllib.request,urllib.parse,re,platform
from html.parser import HTMLParser
from backend import valid_name
class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  if urllib.parse.urlparse(newurl).scheme!='https':raise RuntimeError('Redirecionamento sem HTTPS bloqueado.')
  return super().redirect_request(req,fp,code,msg,headers,newurl)

def open_https(req,timeout):return urllib.request.build_opener(HTTPSRedirect()).open(req,timeout=timeout)

class Parser(HTMLParser):
 def __init__(self,base):super().__init__();self.base=base;self.items={}
 def handle_starttag(self,tag,attrs):
  if tag!='a':return
  href=dict(attrs).get('href','');url=urllib.parse.urljoin(self.base,href);p=urllib.parse.urlparse(url)
  if p.scheme!='https' or p.netloc!=urllib.parse.urlparse(self.base).netloc:return
  parts=p.path.strip('/').split('/')
  if len(parts) not in (2,3) or p.query or p.fragment:return
  pkg=parts[-1]
  if not valid_name(pkg) or parts[0] in ('search','about','doc','changelogs','copyright'):return
  # Links de suites/categorias têm um caminho simples; o pacote é validado contra a busca.
  self.items.setdefault(pkg,{'pkg':pkg,'url':url,'source':p.netloc})
def search(query):
 query=query.strip()
 if len(query)<2:raise ValueError('Digite pelo menos dois caracteres para pesquisar na internet.')
 distro=platform.freedesktop_os_release();debian=distro.get('ID')=='debian';base='https://packages.debian.org' if debian else 'https://packages.ubuntu.com'
 url=base+'/search?'+urllib.parse.urlencode({'keywords':query,'searchon':'names','suite':distro.get('UBUNTU_CODENAME',distro.get('VERSION_CODENAME','stable' if debian else 'all')),'section':'all'})
 req=urllib.request.Request(url,headers={'User-Agent':'StackOS-Store/2.0'})
 with open_https(req,timeout=15) as response:
  if urllib.parse.urlparse(response.url).netloc!=urllib.parse.urlparse(base).netloc:raise RuntimeError('O diretório oficial redirecionou para uma origem inesperada.')
  document=response.read(3_000_001)
  if len(document)>3_000_000:raise RuntimeError('A resposta excedeu o limite da pesquisa.')
 parser=Parser(base);parser.feed(document.decode('utf8',errors='replace'))
 words=query.casefold().split();items=[v for k,v in parser.items.items() if all(w in k for w in words)]
 return {'items':items[:80],'search_url':url,'source':base,'note':'Resultados de outras versões da distribuição podem exigir dependências diferentes. Instale pelo APT local quando disponível.'}

# Endpoints de distribuição dos próprios fabricantes; nenhuma loja de terceiros.
VENDORS=[
 {'pkg':'google-chrome-stable','name':'Google Chrome','terms':'google chrome navegador','page':'https://www.google.com/chrome/','download':'https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb','arch':'amd64'},
 {'pkg':'code','name':'Visual Studio Code','terms':'code vscode visual studio editor microsoft','page':'https://code.visualstudio.com/docs/setup/linux','download':'https://update.code.visualstudio.com/latest/linux-deb-x64/stable','arch':'amd64'},
 {'pkg':'discord','name':'Discord','terms':'discord chat voz jogos','page':'https://discord.com/download','download':'https://discord.com/api/download?platform=linux&format=deb','arch':'amd64'},
]
_directory_search=search

def launchpad_search(query):
 import json,subprocess,apt_pkg
 distro=platform.freedesktop_os_release();suite=distro.get('UBUNTU_CODENAME','')
 if not suite:return _directory_search(query)
 arch=subprocess.check_output(['dpkg','--print-architecture'],text=True).strip()
 params={'ws.op':'getPublishedBinaries','binary_name':query,'exact_match':'false','status':'Published','distro_arch_series':f'https://api.launchpad.net/1.0/ubuntu/{suite}/{arch}','ws.size':'75'}
 url='https://api.launchpad.net/1.0/ubuntu/+archive/primary?'+urllib.parse.urlencode(params)
 req=urllib.request.Request(url,headers={'User-Agent':'StackOS-Store/2.0','Accept':'application/json'})
 with open_https(req,timeout=20) as response:data=json.loads(response.read(4000000))
 items={}
 for entry in data.get('entries',[]):
  pkg=entry.get('binary_package_name','');link=entry.get('self_link','')
  if not valid_name(pkg) or entry.get('pocket')=='Proposed' or not re.fullmatch(r'https://api\.launchpad\.net/1\.0/ubuntu/\+archive/primary/\+binarypub/\d+',link):continue
  version=entry.get('binary_package_version','')
  if pkg in items and apt_pkg.version_compare(version,items[pkg]['version'])<=0:continue
  items[pkg]={'pkg':pkg,'url':'https://launchpad.net/ubuntu/+source/'+entry.get('source_package_name',pkg),'source':'Ubuntu · Launchpad oficial','publication':link,'version':version}
 result=sorted(items.values(),key=lambda x:(x['pkg']!=query,x['pkg']))
 return {'items':result[:60],'search_url':'https://launchpad.net/ubuntu/+search?text='+urllib.parse.quote(query),'source':'Ubuntu · Launchpad','note':f'Pacotes publicados para Ubuntu {suite}, arquitetura {arch}. Instalação pelo APT local quando disponível; DEB direto pode exigir dependências adicionais.'}

_original_search=launchpad_search
def search(query):
 if len(query.strip())<2:raise ValueError('Digite pelo menos dois caracteres.')
 import subprocess
 arch=subprocess.check_output(['dpkg','--print-architecture'],text=True).strip()
 vendors=[dict(v,url=v['page'],source=urllib.parse.urlparse(v['page']).netloc,vendor=True) for v in VENDORS if all(w in (v['name']+' '+v['terms']).casefold() for w in query.casefold().split()) and v['arch']==arch]
 try:result=_original_search(query)
 except Exception as e:
  if not vendors:raise
  result={'items':[],'search_url':'https://packages.ubuntu.com/','source':'Fabricantes oficiais','note':'O diretório de pacotes não respondeu: '+str(e)}
 result['items']=vendors+result['items'];return result

def download_deb(url,destination=None,progress=None):
 import hashlib,subprocess,os,tempfile
 from pathlib import Path
 if urllib.parse.urlparse(url).scheme!='https':raise ValueError('O download exige HTTPS.')
 folder=Path(destination) if destination else Path.home()/'Downloads/StackOS';folder.mkdir(parents=True,exist_ok=True)
 fd,temporary=tempfile.mkstemp(prefix='.download-',suffix='.part',dir=folder);os.close(fd);temporary=Path(temporary)
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'StackOS-Store/2.0'})
  digest=hashlib.sha256();count=0
  with open_https(req,timeout=30) as response,temporary.open('wb') as out:
   if urllib.parse.urlparse(response.url).scheme!='https':raise RuntimeError('Redirecionamento sem HTTPS recusado.')
   size=int(response.headers.get('Content-Length',0));limit=2*1024**3
   if size>limit:raise RuntimeError('Arquivo maior que 2 GB.')
   while True:
    chunk=response.read(262144)
    if not chunk:break
    count+=len(chunk)
    if count>limit:raise RuntimeError('Arquivo excedeu 2 GB.')
    out.write(chunk);digest.update(chunk)
    if progress:progress(count,size)
  metadata=subprocess.run(['dpkg-deb','-f',str(temporary),'Package','Version','Architecture','Depends','Pre-Depends','Description'],capture_output=True,text=True,timeout=15)
  if metadata.returncode:raise RuntimeError('O arquivo baixado não é um pacote DEB válido.')
  values={}
  for line in metadata.stdout.splitlines():
   if ': ' in line:key,value=line.split(': ',1);values[key]=value
  from backend import BLOCKED
  pkg=values.get('Package')
  deps=values.get('Depends','')+' '+values.get('Pre-Depends','')
  description=values.get('Description','').casefold()
  if pkg in BLOCKED or re.search(r'(?<![a-z0-9-])(?:snapd|snap-store|snapcraft)(?![a-z0-9-])',deps) or 'snap' in description and ('transitional' in description or 'transition' in description):raise RuntimeError('Este DEB depende de Snap ou é um pacote de transição; download bloqueado para instalação.')
  arch=values.get('Architecture');system_arch=subprocess.check_output(['dpkg','--print-architecture'],text=True).strip()
  if not valid_name(pkg):raise RuntimeError('Nome de pacote inválido no download.')
  if arch not in ('all',system_arch):raise RuntimeError('A arquitetura do pacote não corresponde a este PC: '+str(arch))
  check_control_scripts(temporary)
  final=folder/(pkg+'-'+digest.hexdigest()[:12]+'.deb');os.replace(temporary,final)
  plan_error=local_install_check(final)
  return {'dependency_error':plan_error,'path':str(final),'pkg':pkg,'version':values.get('Version',''),'arch':arch,'sha256':digest.hexdigest(),'source':url,'bytes':count}
 finally:
  if temporary.exists():temporary.unlink()

class Links(HTMLParser):
 def __init__(self):super().__init__();self.urls=[]
 def handle_starttag(self,tag,attrs):
  if tag=='a':
   href=dict(attrs).get('href','')
   if href:self.urls.append(href)
def resolve_deb(item):
 import subprocess
 if item.get('download'):return item['download']
 if item.get('publication'):
  import json
  link=item['publication']
  if not re.fullmatch(r'https://api\.launchpad\.net/1\.0/ubuntu/\+archive/primary/\+binarypub/\d+',link):raise ValueError('Publicação não autorizada.')
  with open_https(urllib.request.Request(link.replace('/1.0/','/devel/')+'?ws.op=binaryFileUrls',headers={'User-Agent':'StackOS-Store/2.0'}),timeout=20) as response:urls=json.loads(response.read(1000000))
  for value in urls:
   u=urllib.parse.urlparse(value)
   if u.scheme=='https' and (u.hostname in ('launchpad.net','archive.ubuntu.com','security.ubuntu.com') or (u.hostname or '').endswith('.launchpadlibrarian.net')) and u.path.endswith('.deb'):return value
  raise RuntimeError('A publicação não disponibilizou um DEB oficial.')
 parsed=urllib.parse.urlparse(item['url']);allowed={'packages.ubuntu.com','packages.debian.org'}
 if parsed.scheme!='https' or parsed.netloc not in allowed:raise ValueError('Diretório de pacotes não autorizado.')
 distro=platform.freedesktop_os_release();suite=distro.get('UBUNTU_CODENAME',distro.get('VERSION_CODENAME',''))
 if not suite:raise RuntimeError('Não foi possível determinar a versão-base do sistema.')
 arch=subprocess.check_output(['dpkg','--print-architecture'],text=True).strip()
 pkg=item['pkg']
 if not valid_name(pkg):raise ValueError('Nome de pacote inválido.')
 url=f'https://{parsed.netloc}/{suite}/{arch}/{pkg}/download'
 req=urllib.request.Request(url,headers={'User-Agent':'StackOS-Store/2.0'})
 with open_https(req,timeout=15) as response:document=response.read(2000000).decode('utf8',errors='replace')
 links=Links();links.feed(document)
 hosts={'archive.ubuntu.com','security.ubuntu.com','ports.ubuntu.com'} if parsed.netloc=='packages.ubuntu.com' else {'deb.debian.org','security.debian.org'}
 for link in links.urls:
  value=urllib.parse.urlparse(link)
  if value.hostname in hosts and value.path.endswith('.deb'):return urllib.parse.urlunparse(value._replace(scheme='https'))
 raise RuntimeError('Nenhum DEB compatível foi encontrado nos mirrors oficiais desta versão. Use o APT ou consulte a página do projeto.')


def check_control_scripts(path):
 import subprocess,tarfile,io
 process=subprocess.Popen(['dpkg-deb','--ctrl-tarfile',str(path)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
 try:
  control=process.stdout.read(2_000_001)
  if len(control)>2_000_000:process.kill();raise RuntimeError('Metadados de controle excedem o limite aceito.')
  if process.wait(timeout=15):raise RuntimeError('Não foi possível ler os metadados de controle.')
  with tarfile.open(fileobj=io.BytesIO(control)) as archive:
   for entry in archive.getmembers():
    if not entry.isfile() or entry.name.rsplit('/',1)[-1] not in ('preinst','postinst','prerm','postrm'):continue
    if entry.size>1_000_000:raise RuntimeError('Script de manutenção excede o limite aceito.')
    script=archive.extractfile(entry).read().decode('utf8',errors='replace')
    if re.search(r'(?im)(?:^|[;\n&|])\s*(?:/usr/bin/)?snap\s+(?:install|refresh|run)\b',script) or re.search(r'(?is)apt(?:-get)?\s+install[^\n]*\bsnapd\b',script):raise RuntimeError('O script do pacote tenta usar Snap; instalação bloqueada.')
 finally:
  if process.poll() is None:process.kill()
  process.wait()


def local_install_check(path):
 import subprocess,os
 from backend import BLOCKED,PROTECTED
 p=subprocess.run(['apt-get','-s','install',str(path)],capture_output=True,text=True,timeout=45,env={**os.environ,'LC_ALL':'C'})
 for line in p.stdout.splitlines():
  if line.startswith('Inst '):
   name=line.split()[1].split(':')[0]
   if name in BLOCKED:raise RuntimeError('O plano deste DEB instalaria Snap; instalação bloqueada.')
  if line.startswith('Remv '):
   name=line.split()[1].split(':')[0]
   if name in PROTECTED or name.startswith(('linux-image-','linux-modules-')):raise RuntimeError('O plano removeria um componente essencial: '+name)
 return None if p.returncode==0 else (p.stderr.strip() or p.stdout[-1500:] or 'As dependências não puderam ser resolvidas.')

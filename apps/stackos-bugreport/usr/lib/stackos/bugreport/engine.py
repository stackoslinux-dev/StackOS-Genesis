"""Diagnóstico somente leitura e envio opcional ao repositório original."""
import os,re,json,socket,platform,subprocess,urllib.request,urllib.error,urllib.parse,ipaddress
from pathlib import Path
from datetime import datetime
REPO='stackoslinux-dev/bugs'
TOKEN_FILE=Path.home()/'.config/stackos/bugreport.env'
COMMANDS={
 'packages':['dpkg-query','-W','-f=${binary:Package} ${Version}\n','stackos-*'],
 'logs':['journalctl','-b','-n','50','--no-pager','--no-hostname','-o','short'],
 'errors':['journalctl','-b','-p','err','-n','50','--no-pager','--no-hostname','-o','short'],
 'hardware':['lspci','-nnk'],
 'modules':['lsmod'],
 'drivers':['ubuntu-drivers','devices'],
}
def token(path=None):
    # O mesmo arquivo da versão original; não exige credencial para abrir a interface.
    try:
        for line in (Path(path) if path else TOKEN_FILE).read_text().splitlines():
            if line.strip().startswith('GITHUB_TOKEN='):return line.split('=',1)[1].strip().strip('"').strip("'")
    except OSError:pass
    return ''

def redact(text,secret='',identities=None):
    text=str(text)
    if secret:text=text.replace(secret,'[CREDENCIAL REMOVIDA]')
    text=re.sub(r'\b(?:github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9_]+)\b','[TOKEN REMOVIDO]',text)
    text=re.sub(r'(?i)(authorization\s*[:=]\s*)(?:bearer|token|basic)?\s*[^\s,;]+',r'\1[REMOVIDO]',text)
    text=re.sub(r'(?i)((?:password|passwd|senha|secret|api[_-]?key|access[_-]?token|github_token)\s*[:=]\s*)(?:"[^"]*"|\x27[^\x27]*\x27|[^\s,;]+)',r'\1[REMOVIDO]',text)
    text=re.sub(r'/home/[^/\s:]+','/home/[USUARIO]',text)
    text=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[EMAIL]',text)
    text=re.sub(r'(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b','[MAC]',text)
    text=re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b','[IP]',text)
    def ipv6(match):
        value=match.group()
        try:return '[IP]' if ipaddress.ip_address(value).version==6 else value
        except ValueError:return value
    text=re.sub(r'(?i)(?<![\w:])[0-9a-f:]*:[0-9a-f:]+(?![\w:])',ipv6,text)
    text=re.sub(r'(?i)\b(serial(?:number)?|uuid|machine[_-]?id)\s*[:=]\s*[^\s,;]+',r'\1=[REMOVIDO]',text)
    identities=identities if identities is not None else [os.environ.get('USER',''),socket.gethostname()]
    for value in identities:
        if value and len(value)>1:text=re.sub(r'(?<![\w-])'+re.escape(value)+r'(?![\w-])','[IDENTIDADE]',text)
    return text

def run_readonly(args):
    try:
        result=subprocess.run(args,capture_output=True,text=True,timeout=8,check=False)
        if result.returncode:return {'ok':False,'output':result.stderr.strip()[:500] or 'Comando não disponível ou acesso negado.'}
        return {'ok':True,'output':result.stdout[:24000].strip() or 'Nenhum registro retornado.'}
    except subprocess.TimeoutExpired:return {'ok':False,'output':'Tempo limite excedido (8 s).'}
    except OSError as e:return {'ok':False,'output':str(e)}

def collect():
    # Limita duração de cada fonte e mantém falhas explícitas, sem inventar diagnósticos.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        values=dict(zip(COMMANDS,pool.map(run_readonly,COMMANDS.values())))
    try:os_name=platform.freedesktop_os_release().get('PRETTY_NAME','Não informado')
    except OSError:os_name=platform.system()
    data={'os':os_name,'kernel':platform.release(),'collected_at':datetime.now().isoformat(timespec='seconds'),'diagnostics':values,'driver_manager':Path('/usr/local/bin/stackos-drivers').exists()}
    credential=token()
    for result in values.values():result['output']=redact(result['output'],credential)
    return data

def validate_input(title,description):
    if not title.strip():raise ValueError('Informe o título do problema.')
    if len(title)>120:raise ValueError('O título aceita até 120 caracteres.')
    if len(description)>5000:raise ValueError('A descrição aceita até 5000 caracteres.')

def report_body(description,info,include_logs=True):
    text=['## Descrição',description.strip() or 'Sem descrição adicional.','\n## Sistema',f"{info.get('os','Não informado')}\nKernel: {info.get('kernel','Não informado')}\nColeta: {info.get('collected_at','Não informada')}"]
    names={'packages':'Pacotes StackOS','hardware':'Hardware e drivers em uso (PCI/kernel)','modules':'Módulos carregados','drivers':'Diagnóstico ubuntu-drivers (mesma fonte do StackOS Drivers)','errors':'Erros recentes da sessão','logs':'Logs recentes'}
    for key,name in names.items():
        if key in ('errors','logs') and not include_logs:continue
        result=info.get('diagnostics',{}).get(key,{})
        output=result.get('output','Não coletado.').replace('```','~~~')
        text.extend(['\n## '+name,('Fonte indisponível.\n' if result and not result.get('ok') else '')+'```text\n'+output+'\n```'])
    text.append('\nIdentificadores e credenciais comuns foram ocultados automaticamente. Conteúdo revisável pelo usuário.')
    body=redact('\n\n'.join(text),token())
    # Limite de conteúdo do relatório; mantém o texto que será revisado igual ao enviado.
    if len(body)>60000:body=body[:59900]+'\n\n[Relatório truncado por limite de tamanho.]'
    return body

class SendError(Exception):pass

def send_issue(title,body,credential=None):
    credential=token() if credential is None else credential
    if not credential:raise SendError('Token não configurado. Salve o relatório ou abra o formulário do GitHub.')
    payload=json.dumps({'title':'[Bug] '+title,'body':body,'labels':['bug']}).encode()
    req=urllib.request.Request(f'https://api.github.com/repos/{REPO}/issues',data=payload,headers={'Authorization':'Bearer '+credential,'Content-Type':'application/json','Accept':'application/vnd.github+json','User-Agent':'StackOS-BugReport/1.1.0'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=25) as response:result=json.loads(response.read(1024*1024))
    except urllib.error.HTTPError as e:
        messages={401:'Credencial do GitHub inválida.',403:'Sem permissão de envio ou limite da API atingido.',404:'Repositório indisponível ou credencial sem acesso.',422:'O GitHub recusou o título, o conteúdo ou o rótulo do relatório.'}
        raise SendError(messages.get(e.code,f'Falha do GitHub (HTTP {e.code}).')) from None
    except (OSError,ValueError,urllib.error.URLError):raise SendError('Não foi possível confirmar o envio. Confira as issues do repositório antes de tentar novamente.') from None
    url=result.get('html_url','')
    if not re.fullmatch(r'https://github\.com/'+re.escape(REPO)+r'/issues/\d+',url):raise SendError('Resposta sem link válido. Confira o repositório antes de tentar novamente.')
    return url

def github_form(title):return f'https://github.com/{REPO}/issues/new?'+urllib.parse.urlencode({'title':'[Bug] '+title})

"""Detecção somente leitura e planos explícitos para ações sobre pacotes."""
import subprocess,shlex,re,platform,json,os,shutil
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from catalog import get_drivers,ALT_PKGS,KMOD_MAP
from gpu_metrics import metrics
STATE=Path.home()/'.local/state/stackos-drivers'

def command(args,timeout=8):
    try:return subprocess.run(args,capture_output=True,text=True,timeout=timeout,check=False,env={**os.environ,'LC_ALL':'C'})
    except subprocess.TimeoutExpired:raise RuntimeError('Tempo limite excedido: '+args[0]) from None
    except OSError as e:raise RuntimeError(str(e)) from None

def vendor(name):
    name=name.upper()
    for terms,value in [(('NVIDIA','GEFORCE','QUADRO'),'NVIDIA'),(('AMD','ATI','RADEON'),'AMD'),(('INTEL',),'Intel'),(('REALTEK',),'Realtek'),(('BROADCOM',),'Broadcom'),(('ATHEROS','QUALCOMM'),'Atheros'),(('MEDIATEK',),'MediaTek')]:
        if any(re.search(r'(?<![A-Z0-9])'+re.escape(term)+r'(?![A-Z0-9])',name) for term in terms):return value
    return 'Generic'

def parse_pci(output,sysroot=Path('/sys/bus/pci/devices')):
    result=[]
    for line in output.splitlines():
        try:fields=shlex.split(line)
        except ValueError:continue
        if len(fields)<4:continue
        pci,kind,maker,name=fields[:4];kind=kind.casefold()
        if any(x in kind for x in ('vga','3d controller','display controller')):dtype='GPU';icon='video-display-symbolic'
        elif any(x in kind for x in ('audio','multimedia')):dtype='Áudio';icon='audio-speakers-symbolic'
        elif 'ethernet' in kind:dtype='Rede';icon='network-wired-symbolic'
        elif 'network' in kind:dtype='WiFi';icon='network-wireless-symbolic'
        else:continue
        root=sysroot/pci
        try:module=(root/'driver').resolve(strict=True).name
        except OSError:module=''
        try:vid=(root/'vendor').read_text().strip()
        except OSError:vid=''
        result.append({'type':dtype,'vendor':{'0x1002':'AMD','0x10de':'NVIDIA','0x8086':'Intel','0x10ec':'Realtek','0x14e4':'Broadcom','0x168c':'Atheros','0x14c3':'MediaTek'}.get(vid,vendor(maker+' '+name)),'name':maker+' '+name,'pci_address':pci,'module':module,'vendor_id':vid,'icon':icon,'display_name':(('AMD Radeon '+fields[-1]) if dtype=='GPU' and (vid=='0x1002' or vendor(maker)=='AMD') and re.match(r'^RX \d',fields[-1]) else maker+' '+name)})
    return result

def installed_packages():
    p=command(['dpkg-query','-W','-f=${binary:Package}\t${Version}\t${db:Status-Status}\n'])
    if p.returncode:raise RuntimeError(p.stderr.strip() or 'Não foi possível consultar os pacotes instalados.')
    packages={}
    for line in p.stdout.splitlines():
        values=line.split('\t')
        if len(values)==3 and values[2]=='installed':packages[values[0].split(':',1)[0]]=values[1]
    return packages

def catalog_for(device):
    # native_component: source-built C3 capabilities are not Ubuntu APT packages.
    if 'StackOS C3' in platform.freedesktop_os_release().get('PRETTY_NAME',''):
        drivers=[]
        def included(name,desc):
            drivers.append({'pkg':'StackOS C3 · componente da base','name':name,'desc':desc,'type':'free','native':True})
        if device.get('module'):
            included('Driver do kernel: '+device['module'],'Detectado e carregado automaticamente para este dispositivo.')
        if device['type']=='Áudio' and shutil.which('pulseaudio'):
            included('PulseAudio','Servidor de áudio já incluído na base do StackOS.')
        if device['type']=='Bluetooth' and Path('/usr/libexec/bluetooth/bluetoothd').is_file():
            included('BlueZ','Serviço Bluetooth já incluído na base do StackOS.')
        if device['type'] in ('GPU','WiFi','Bluetooth') and Path('/usr/lib/firmware').is_dir():
            included('Firmware da imagem','Arquivos incluídos no StackOS; o kernel seleciona o firmware correspondente ao hardware.')
        return drivers
    if device['type']=='Rede':
        choices=[]
        if device['vendor']=='Realtek':choices.append({'pkg':'r8168-dkms','name':'Realtek r8168 (alternativa)','desc':'Módulo DKMS alternativo para controladores compatíveis. O driver do kernel em uso continua indicado acima.','tag':'ok','type':'free'})
        return choices
    drivers=get_drivers(device)
    if device['type']=='GPU' and device['vendor']=='AMD' and package_available('amdgpu-pro'):
        drivers.append({'pkg':'amdgpu-pro','name':'AMDGPU Pro','desc':'Driver proprietário AMD disponível no repositório configurado. Verifique a compatibilidade com a versão do sistema.','tag':'ok','type':'prop'})
    if device['type']=='WiFi' and device['vendor']=='Broadcom':drivers.append({'pkg':'bcmwl-kernel-source','name':'Broadcom STA (Ubuntu)','desc':'Driver proprietário Broadcom disponível em repositórios Ubuntu compatíveis.','tag':'ok','type':'prop'})
    return drivers

def package_state(driver,device,installed):
    if driver.get('native'):
        return dict(driver,exact=False,present=True,provider='base do StackOS',version='',module=device.get('module'))
    pkg=driver['pkg'];provider=pkg if pkg in installed else next((p for p in ALT_PKGS.get(pkg,[]) if p in installed),None)
    module=KMOD_MAP.get(pkg);provided_module=bool(module and device.get('module')==module)
    return dict(driver,exact=pkg in installed,present=bool(provider or provided_module),provider=provider,version=installed.get(provider,'') if provider else '',module=module if provided_module else None)

def scan():
    pci=command(['lspci','-Dmm'])
    if pci.returncode:raise RuntimeError(pci.stderr.strip() or 'Falha ao consultar os dispositivos PCI.')
    devices=parse_pci(pci.stdout)
    try:
        usb=command(['lsusb'])
        for line in usb.stdout.splitlines():
            if 'bluetooth' in line.casefold():devices.append({'type':'Bluetooth','vendor':vendor(line),'name':line.split(' ID ',1)[-1],'pci_address':'','module':'','icon':'bluetooth-symbolic'})
    except RuntimeError:pass
    devices.sort(key=lambda d:({'GPU':0,'Áudio':1,'Rede':2,'WiFi':3,'Bluetooth':4}.get(d['type'],5),d.get('pci_address','')))
    installed=installed_packages()
    for d in devices:d['drivers']=[package_state(p,d,installed) for p in catalog_for(d)]
    return {'devices':devices,'kernel':platform.release(),'distro':platform.freedesktop_os_release().get('PRETTY_NAME','Não informada'),'arch':platform.machine(),'checked_at':datetime.now().isoformat(timespec='seconds'),'reboot':Path('/var/run/reboot-required').exists()}

def telemetry(device):
    if not device:return {}
    data=metrics(device);temps=[]
    for p in (Path('/sys/bus/pci/devices')/device.get('pci_address','')/'hwmon').glob('hwmon*/temp1_input'):
        try:temps.append(float(p.read_text())/1000)
        except (OSError,ValueError):pass
    data['temperature']=temps[0] if temps else None
    return data

def valid_package(package):return isinstance(package,str) and re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?',package) is not None

def action_command(action,package):
    if action not in ('install','remove') or not valid_package(package):raise ValueError('Ação ou nome de pacote inválido.')
    return ['pkexec','apt-get',action,'-y',package]

def package_available(package):
    if not valid_package(package):return False
    result=command(['apt-cache','policy',package])
    return result.returncode==0 and bool(re.search(r'(?:Candidate|Candidato):\s*(?!\(none\)|\(nenhum\))\S+',result.stdout))

def perform(action,package):
    args=action_command(action,package)
    if action=='install' and not package_available(package):raise RuntimeError('Este pacote não tem candidato disponível nos repositórios configurados. Nenhum pacote foi alterado.')
    # Autenticação e apt recebem argumentos separados. Não há shell.
    result=command(args,timeout=3600)
    record(action,package,result.returncode,(result.stdout+'\n'+result.stderr)[-60000:])
    return result

def record(action,package,code,output):
    try:
        STATE.mkdir(parents=True,exist_ok=True)
        with (STATE/'operations.log').open('a',encoding='utf8') as f:f.write(f'\n[{datetime.now().isoformat(timespec="seconds")}] {action} {package} · código {code}\n{output}\n')
        os.chmod(STATE/'operations.log',0o600)
    except OSError:pass

def read_logs():
    try:return (STATE/'operations.log').read_text(errors='replace')[-120000:]
    except OSError:return 'Nenhuma operação registrada nesta versão ainda.'

"""Leitura opcional de telemetria. Ausência de sensor nunca vira valor inventado."""
from pathlib import Path
import re,subprocess

def number(path,scale=1):
 try:return float(Path(path).read_text().strip())/scale
 except (OSError,ValueError):return None

def metrics(gpu):
 root=Path('/sys/bus/pci/devices')/str(gpu.get('pci_address',''))
 d={'usage':number(root/'gpu_busy_percent'),'vram_used':number(root/'mem_info_vram_used'),'vram_total':number(root/'mem_info_vram_total'),'clock_mhz':None,'power_w':None}
 try:
  for line in (root/'pp_dpm_sclk').read_text().splitlines():
   if '*' in line:
    match=re.search(r'(\d+)\s*[Mm][Hh][Zz]',line)
    if match:d['clock_mhz']=float(match.group(1))
 except OSError:pass
 for h in sorted((root/'hwmon').glob('hwmon*')):
  for name in ('power1_average','power1_input'):
   p=number(h/name,1_000_000)
   if p is not None:d['power_w']=p;break
  if d['power_w'] is not None:break
 if gpu.get('vendor_id')=='0x10de':
  try:
   p=subprocess.run(['nvidia-smi','-i',gpu['pci_address'],'--query-gpu=utilization.gpu,memory.used,memory.total,clocks.current.graphics,power.draw','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2,check=False)
   if p.returncode==0:
    vals=p.stdout.strip().split(',');keys=['usage','vram_used','vram_total','clock_mhz','power_w']
    for k,v in zip(keys,vals):
     try:d[k]=float(v.strip())*(1024*1024 if k.startswith('vram') else 1)
     except ValueError:pass
  except (OSError,subprocess.TimeoutExpired):pass
 return d

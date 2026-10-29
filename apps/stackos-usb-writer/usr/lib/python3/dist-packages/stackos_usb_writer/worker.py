"""Worker autenticado. Revalida mídia e destino antes de qualquer escrita."""
from __future__ import annotations
import argparse,json,os,sys,stat,signal,subprocess,time,threading,fcntl,struct,hashlib
from pathlib import Path
from .devices import discover_usb_devices
from .operations import CHUNK_SIZE,validate_image,image_stream,expanded_size
CANCEL=threading.Event()

def emit(event,**values):print(json.dumps({'event':event,**values}),flush=True)
def check_cancel():
 if CANCEL.is_set():raise InterruptedError('Operação cancelada. O USB pode estar parcialmente alterado.')
def cancellation_reader():
 pending=b''
 while True:
  chunk=os.read(sys.stdin.fileno(),64)
  if not chunk:return
  pending+=chunk
  if b'cancel\n' in pending:CANCEL.set();return
  pending=pending[-128:]

def allowed_device(path):
 real=str(Path(path).resolve());return any(d.path==real and not d.protected for d in discover_usb_devices())
def require_safe_device(path,identity=''):
 real=str(Path(path).resolve());d=next((d for d in discover_usb_devices() if d.path==real and not d.protected),None)
 if not real.startswith('/dev/') or d is None:raise PermissionError('Destino recusado: não é um USB/removível permitido ou contém partição crítica.')
 if identity and d.identity!=identity:raise PermissionError('O dispositivo mudou. Atualize a lista e confirme o destino novamente.')
 return d

def nodes_for_device(device):
 p=subprocess.run(['lsblk','--json','--output','PATH,MOUNTPOINTS,MAJ:MIN',device],check=True,capture_output=True,text=True,timeout=10)
 roots=json.loads(p.stdout).get('blockdevices',[])
 nodes=[]
 def visit(n):
  for child in n.get('children') or []:visit(child)
  nodes.append(n)
 for n in roots:visit(n)
 return nodes

def unmount_children(device):
 for node in nodes_for_device(device):
  if any(node.get('mountpoints') or []):subprocess.run(['udisksctl','unmount','--block-device',node['path']],check=True,capture_output=True,text=True,timeout=30)

def safe_target_fd(device):
 fd=os.open(device.path,os.O_RDWR|os.O_CLOEXEC|getattr(os,'O_NOFOLLOW',0)|os.O_EXCL)
 try:
  st=os.fstat(fd)
  if not stat.S_ISBLK(st.st_mode):raise PermissionError('O destino não é um dispositivo de blocos.')
  actual=f'{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}'
  if device.major_minor and actual!=device.major_minor:raise PermissionError('Identidade do dispositivo mudou ao abrir.')
  return fd
 except BaseException:os.close(fd);raise

def fd_signature(fd):
 st=os.fstat(fd);return ':'.join(str(v) for v in (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns))

def write_image(image_path,device_path,verify,identity='',source_signature='',expected_sha=''):
 image=validate_image(image_path);selected=require_safe_device(device_path,identity);identity=selected.identity
 source_fd=os.open(image,os.O_RDONLY|os.O_CLOEXEC|getattr(os,'O_NOFOLLOW',0))
 try:
  initial=fd_signature(source_fd)
  if not stat.S_ISREG(os.fstat(source_fd).st_mode):raise ValueError('A imagem não é um arquivo regular.')
  if source_signature and source_signature!=initial:raise ValueError('A imagem mudou depois da seleção.')
  source_device=f'{os.major(os.fstat(source_fd).st_dev)}:{os.minor(os.fstat(source_fd).st_dev)}'
  if any(n.get('maj:min')==source_device for n in nodes_for_device(selected.path)):raise ValueError('A imagem está armazenada no próprio USB de destino.')
  check_cancel();emit('stage',name='preparing',total=0)
  if expected_sha:
   if len(expected_sha)!=64 or any(c not in '0123456789abcdef' for c in expected_sha.lower()):raise ValueError('SHA-256 esperado inválido.')
   digest=hashlib.sha256();os.lseek(source_fd,0,0)
   while chunk:=os.read(source_fd,CHUNK_SIZE):check_cancel();digest.update(chunk)
   if digest.hexdigest()!=expected_sha.lower():raise ValueError('O SHA-256 da imagem não corresponde ao esperado.')
  total=expanded_size(image,selected.size,source_fd,check_cancel)
  if fd_signature(source_fd)!=initial:raise ValueError('A imagem mudou durante a preparação.')
  unmount_children(selected.path);check_cancel();selected=require_safe_device(selected.path,identity)
  target_fd=safe_target_fd(selected)
  try:
   capacity=struct.unpack('Q',fcntl.ioctl(target_fd,0x80081272,struct.pack('Q',0)))[0]
   if total>capacity:raise ValueError('A imagem é maior que o destino aberto.')
   processed=0;started=time.monotonic();emit('stage',name='writing',total=total)
   with image_stream(image,source_fd) as source:
    while chunk:=source.read(CHUNK_SIZE):
     check_cancel();view=memoryview(chunk)
     while view:
      written=os.write(target_fd,view)
      if written<=0:raise IOError('Não foi possível concluir a escrita.')
      view=view[written:]
     processed+=len(chunk);emit('progress',current=processed,total=total,speed=int(processed/max(time.monotonic()-started,.001)))
   if processed!=total or fd_signature(source_fd)!=initial:raise IOError('A imagem mudou ou não foi lida por completo.')
   os.fsync(target_fd);check_cancel()
   if verify:
    emit('stage',name='verifying',total=total);os.lseek(target_fd,0,0);processed=0
    with image_stream(image,source_fd) as source:
     while chunk:=source.read(CHUNK_SIZE):
      check_cancel();read=b''
      while len(read)<len(chunk):
       part=os.read(target_fd,len(chunk)-len(read))
       if not part:break
       read+=part
      if read!=chunk:raise IOError('A verificação encontrou diferenças na gravação.')
      processed+=len(chunk);emit('progress',current=processed,total=total,speed=0)
    if fd_signature(source_fd)!=initial:raise IOError('A imagem mudou durante a verificação.')
  finally:
   try:os.fsync(target_fd)
   finally:os.close(target_fd)
  subprocess.run(['blockdev','--rereadpt',selected.path],check=False,capture_output=True,timeout=10);emit('complete',device=selected.path)
 finally:os.close(source_fd)

def erase_device(device_path,filesystem,label,identity=''):
 selected=require_safe_device(device_path,identity);identity=selected.identity
 if filesystem not in ('fat32','exfat','ntfs'):raise ValueError('Sistema de arquivos não permitido.')
 if not label or len(label)>11 or not all(c.isascii() and (c.isalnum() or c in '_- ') for c in label):raise ValueError('Use um rótulo ASCII de 1 a 11 caracteres (letras, números, espaço, _ ou -).')
 unmount_children(selected.path);check_cancel();selected=require_safe_device(selected.path,identity)
 # Abre e valida o dispositivo de blocos antes de chamar ferramentas de formatação.
 fd=safe_target_fd(selected);os.close(fd);emit('stage',name='formatting',total=0)
 commands=[['wipefs','--all',selected.path],['parted','--script',selected.path,'mklabel','gpt','mkpart','primary','1MiB','100%'],['udevadm','settle']]
 partition=selected.path+('p1' if selected.path[-1].isdigit() else '1')
 commands.append({'fat32':['mkfs.vfat','-F','32','-n',label,partition],'exfat':['mkfs.exfat','-n',label,partition],'ntfs':['mkfs.ntfs','-F','-L',label,partition]}[filesystem])
 for command in commands:
  check_cancel();require_safe_device(selected.path,identity);subprocess.run(command,check=True,capture_output=True,text=True,timeout=180)
 check_cancel();emit('progress',current=1,total=1,speed=0);emit('complete',device=selected.path)

def parser():
 p=argparse.ArgumentParser(prog='stackos-usb-writer-worker');sub=p.add_subparsers(dest='operation',required=True)
 w=sub.add_parser('write');w.add_argument('--image',required=True);w.add_argument('--device',required=True);w.add_argument('--verify',action='store_true');w.add_argument('--device-id',default='');w.add_argument('--source-signature',default='');w.add_argument('--sha256',default='')
 f=sub.add_parser('format');f.add_argument('--device',required=True);f.add_argument('--filesystem',choices=('fat32','exfat','ntfs'),required=True);f.add_argument('--label',default='STACKOS');f.add_argument('--device-id',default='')
 return p

def main():
 try:
  if os.geteuid()!=0:raise PermissionError('Este worker exige autenticação administrativa.')
  CANCEL.clear();args=parser().parse_args();signal.signal(signal.SIGINT,lambda *_:CANCEL.set());signal.signal(signal.SIGTERM,lambda *_:CANCEL.set())
  if not sys.stdin.isatty():threading.Thread(target=cancellation_reader,daemon=True).start()
  if args.operation=='write':write_image(args.image,args.device,args.verify,args.device_id,args.source_signature,args.sha256)
  else:erase_device(args.device,args.filesystem,args.label,args.device_id)
  return 0
 except InterruptedError as error:emit('cancelled',message=str(error));return 130
 except Exception as error:emit('error',message=str(error));return 1
if __name__=='__main__':raise SystemExit(main())

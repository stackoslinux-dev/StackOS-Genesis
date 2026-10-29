#!/usr/bin/env python3
from pathlib import Path
import subprocess,sys,tempfile,shutil,re,os
version=sys.argv[1] if len(sys.argv)>1 else subprocess.check_output(['uname','-r'],text=True).strip()
assert re.fullmatch(r'[a-zA-Z0-9.+_-]+',version)
template=Path('/usr/share/stackos/installed-initramfs-template');assert template.is_dir()
with tempfile.TemporaryDirectory(prefix='stackos-initramfs-') as directory:
 root=Path(directory);shutil.copytree(template,root,dirs_exist_ok=True,symlinks=True)
 shutil.copytree('/usr/lib/modules/'+version,root/'usr/lib/modules'/version,symlinks=True,dirs_exist_ok=True)
 done=set()
 def copy_exec(name):
  path=Path(name)
  if str(path) in done:return
  done.add(str(path));target=root/str(path).lstrip('/');target.parent.mkdir(parents=True,exist_ok=True)
  shutil.copy2(path,target,follow_symlinks=True)
  output=subprocess.run(['ldd',str(path)],capture_output=True,text=True).stdout
  for library in re.findall(r'(/[\w./+_-]+)',output):
   if Path(library).is_file():copy_exec(library)
 for executable in ['/usr/bin/sha256sum','/usr/bin/rsync','/usr/sbin/findfs','/usr/sbin/blkid','/usr/sbin/mkfs.ext4','/usr/sbin/e2fsck','/usr/bin/openssl','/usr/bin/stty','/usr/bin/tr']:
  copy_exec(executable)
 script=root/'scripts/local-bottom/stackos-factory-reset';script.parent.mkdir(parents=True,exist_ok=True)
 shutil.copy2('/etc/initramfs-tools/scripts/local-bottom/stackos-factory-reset',script)
 target=Path('/boot/initrd.img-'+version)
 subprocess.run("set -o pipefail; find . -print0 | /bin/busybox cpio --null -o -H newc | gzip -1 > "+str(target),shell=True,executable='/bin/bash',cwd=root,check=True)
 link=Path('/boot/initrd.img');link.unlink(missing_ok=True);link.symlink_to(target.name)
print('INSTALLED_INITRAMFS_READY',version,flush=True)

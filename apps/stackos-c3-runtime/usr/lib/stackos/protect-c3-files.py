#!/usr/bin/env python3
import subprocess,sys,tarfile,os
from pathlib import Path
for line in sys.stdin:
 deb=line.strip()
 if not deb.endswith('.deb') or not Path(deb).is_file():continue
 owner=subprocess.check_output(['dpkg-deb','-f',deb,'Package'],text=True).strip()
 if owner in {'snapd','snap-confine','ubuntu-core-launcher'}:
  print('Snap bloqueado pela política StackOS.',file=sys.stderr);raise SystemExit(1)
 proc=subprocess.Popen(['dpkg-deb','--fsys-tarfile',deb],stdout=subprocess.PIPE)
 try:
  with tarfile.open(fileobj=proc.stdout,mode='r|') as archive:
   for entry in archive:
    if not entry.isfile() and not entry.issym():continue
    path=Path('/')/entry.name.removeprefix('./').lstrip('/')
    if not path.exists() and not path.is_symlink():continue
    result=subprocess.run(['dpkg-query','-S',str(path)],text=True,capture_output=True)
    owners=[x.split(': ',1)[0] for x in result.stdout.splitlines() if ': ' in x]
    if owner in owners:continue
    print(f'Proteção C3: {owner} substituiria {path}, pertencente à base por fontes ou a outro pacote.',file=sys.stderr)
    proc.terminate();raise SystemExit(1)
 finally:
  proc.stdout.close();proc.wait()

#!/usr/bin/python3
"""Ponto privilegiado limitado: revalida o plano aprovado antes de executar o APT."""
import os,sys,json,subprocess
from pathlib import Path
import backend

def main(args):
 if os.geteuid()!=0:raise RuntimeError('Autenticação administrativa necessária.')
 if len(args)==2 and args[0] in ('backup-create','backup-restore','backup-delete'):return backend.backup_action(args[0].split('-')[1],args[1])
 if len(args)==1 and args[0]=='refresh':
  return subprocess.call(['apt-get','-o','APT::Update::Error-Mode=any','update'])
 if len(args)!=3:raise ValueError('Argumentos inválidos.')
 action,pkg,digest=args
 plan=backend.simulate(action,pkg)
 if digest!=plan['digest']:raise RuntimeError('O plano de dependências mudou. Revise a operação novamente na loja.')
 return subprocess.call(['apt-get','-o','APT::Status-Fd=1',action,'-y',pkg],env={**os.environ,'LC_ALL':'C'})
if __name__=='__main__':
 try:raise SystemExit(main(sys.argv[1:]))
 except Exception as e:print('Erro: '+str(e),file=sys.stderr);raise SystemExit(1)

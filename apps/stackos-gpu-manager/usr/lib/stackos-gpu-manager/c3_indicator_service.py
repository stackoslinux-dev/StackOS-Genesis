#!/usr/bin/env python3
import json,time,os,fcntl
from pathlib import Path
from stackos_gpu_indicator import gpu_usage_state,highest_usage,indicator_level
cache=Path.home()/'.cache/stackos-gpu-manager';cache.mkdir(parents=True,exist_ok=True)
lock=(cache/'indicator.lock').open('w')
try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError: raise SystemExit(0)
while True:
 try:
  gpus=gpu_usage_state();gpu=highest_usage(gpus);usage=gpu['usage_percent'] if gpu else None
  data={'usage_percent':usage,'level':indicator_level(usage),'gpus':gpus,'updated_at':time.time()}
  tmp=cache/'indicator.json.tmp';tmp.write_text(json.dumps(data));os.replace(tmp,cache/'indicator.json')
 except Exception as e:
  print(str(e),flush=True)
 time.sleep(2)

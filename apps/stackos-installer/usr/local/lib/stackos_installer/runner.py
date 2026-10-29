import subprocess
from .logger import log
class CommandError(Exception): pass
def run(cmd, check=True, input=None):
    log.debug(f"RUN: {cmd}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, input=input)
    if r.stdout.strip(): log.debug(f"STDOUT: {r.stdout.strip()}")
    if r.stderr.strip(): log.debug(f"STDERR: {r.stderr.strip()}")
    if check and r.returncode != 0:
        raise CommandError(f"Falhou (rc={r.returncode}): {cmd}\n{r.stderr.strip()}")
    return r

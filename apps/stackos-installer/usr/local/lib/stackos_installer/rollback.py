import subprocess
from .logger import log
class Rollback:
    def __init__(self): self._mounts = []
    def register_mount(self, path):
        self._mounts.append(path)
        log.debug(f"Rollback registrado: {path}")
    def cleanup(self):
        log.info("Cleanup de mounts...")
        for path in reversed(self._mounts):
            subprocess.run(f"umount -lf {path}", shell=True, capture_output=True)
        self._mounts.clear()

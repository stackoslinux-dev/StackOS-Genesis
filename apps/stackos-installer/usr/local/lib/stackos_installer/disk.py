import subprocess, os, re
from .logger import log
def list_disks():
    r = subprocess.run(["lsblk","-rno","NAME,TYPE,SIZE,RM,MODEL"], capture_output=True, text=True)
    disks = []
    for line in r.stdout.splitlines():
        p = line.split(None, 4)
        if len(p) >= 4 and p[1] == "disk" and p[3] == "0":
            disks.append({"path":f"/dev/{p[0]}","name":p[0],"size":p[2],"model":p[4].strip() if len(p)>4 else ""})
    return disks
def is_uefi(): return os.path.isdir("/sys/firmware/efi")
def get_disk_size_mb(disk):
    r = subprocess.run(["blockdev","--getsize64",disk], capture_output=True, text=True)
    return int(r.stdout.strip()) // (1024*1024) if r.returncode == 0 else 0
def find_existing_esp(disk):
    r = subprocess.run(["lsblk","-rno","NAME,PARTTYPE,FSTYPE"], capture_output=True, text=True)
    base = disk.replace("/dev/","")
    for line in r.stdout.splitlines():
        p = line.split()
        if len(p) >= 1 and base in p[0]:
            parttype = p[1] if len(p)>1 else ""
            fstype   = p[2] if len(p)>2 else ""
            if "c12a7328" in parttype.lower() or fstype == "vfat":
                return f"/dev/{p[0]}"
    return None
def get_free_space_mb(disk):
    r = subprocess.run(["parted","-s",disk,"unit","MiB","print","free"], capture_output=True, text=True)
    max_free = 0
    for line in r.stdout.splitlines():
        if "Free Space" in line:
            m = re.findall(r"([\d]+(?:[.,]\d+)?)MiB", line)
            if len(m) >= 3:
                size = float(m[2].replace(",","."))
                if size > max_free: max_free = size
    return int(max_free)

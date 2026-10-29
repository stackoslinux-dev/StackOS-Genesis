import subprocess, time
from .runner import run
from .disk import find_existing_esp, is_uefi
from .rollback import Rollback
from .logger import log
MOUNT_ROOT = "/mnt/stackos-install"
def _partprobe(disk):
    run(f"partprobe {disk}", check=False)
    run("udevadm settle", check=False)
    time.sleep(3)
def partition_erase(disk):
    run(f"wipefs -af {disk}")
    run(f"sgdisk --zap-all {disk}")
    if is_uefi():
        run(f"sgdisk -n 1:0:+512M -t 1:ef00 -c 1:EFI {disk}")
        run(f"sgdisk -n 2:0:0 -t 2:8300 -c 2:ROOT {disk}")
    else:
        run(f"sgdisk -n 1:0:+1M -t 1:ef02 -c 1:BIOS {disk}")
        run(f"sgdisk -n 2:0:0 -t 2:8300 -c 2:ROOT {disk}")
    _partprobe(disk)
    efi  = disk + "p1" if "nvme" in disk else disk + "1"
    root = disk + "p2" if "nvme" in disk else disk + "2"
    if is_uefi(): run(f"mkfs.fat -F32 -n EFI {efi}")
    run(f"mkfs.ext4 -F -L StackOS {root}")
    return efi, root
def partition_dual(disk, start_mb, size_mb):
    esp = find_existing_esp(disk)
    end_mb = start_mb + size_mb
    if is_uefi() and esp is None:
        efi_end = start_mb + 512
        run(f"parted -s -a optimal {disk} mkpart primary fat32 {start_mb}MiB {efi_end}MiB")
        run(f"parted -s -a optimal {disk} mkpart primary ext4 {efi_end}MiB {end_mb}MiB")
    else:
        run(f"parted -s -a optimal {disk} mkpart primary ext4 {start_mb}MiB {end_mb}MiB")
    _partprobe(disk)
    r = subprocess.run(["lsblk","-rno","NAME,FSTYPE,MOUNTPOINT"], capture_output=True, text=True)
    base = disk.replace("/dev/","")
    new_parts = [f"/dev/{l.split()[0]}" for l in r.stdout.splitlines()
                 if base in l.split()[0] and l.split()[0] != base and (len(l.split())<3 or l.split()[2]=="")]
    if esp is None and is_uefi():
        efi = new_parts[-2]; root = new_parts[-1]
        run(f"mkfs.fat -F32 -n EFI {efi}")
    else:
        efi = esp; root = new_parts[-1]
    run(f"mkfs.ext4 -F -L StackOS {root}")
    return efi, root
def mount_partitions(efi, root, rollback):
    run(f"mkdir -p {MOUNT_ROOT}")
    run(f"mount {root} {MOUNT_ROOT}"); rollback.register_mount(MOUNT_ROOT)
    run(f"mkdir -p {MOUNT_ROOT}/boot/efi")
    run(f"mount {efi} {MOUNT_ROOT}/boot/efi"); rollback.register_mount(f"{MOUNT_ROOT}/boot/efi")
def mount_pseudo(rollback):
    for p in ["dev","proc","sys"]:
        run(f"mount --bind /{p} {MOUNT_ROOT}/{p}"); rollback.register_mount(f"{MOUNT_ROOT}/{p}")
    r = run(f"mount --bind /sys/firmware/efi/efivars {MOUNT_ROOT}/sys/firmware/efi/efivars", check=False)
    if r.returncode == 0: rollback.register_mount(f"{MOUNT_ROOT}/sys/firmware/efi/efivars")

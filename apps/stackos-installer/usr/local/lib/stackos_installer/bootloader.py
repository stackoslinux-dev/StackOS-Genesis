from .runner import run
from .disk import is_uefi
from .partition import MOUNT_ROOT
from .logger import log
def install_grub(disk):
    if is_uefi():
        run(f"chroot {MOUNT_ROOT} grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=StackOS --recheck {disk}")
    else:
        run(f"chroot {MOUNT_ROOT} grub-install --target=i386-pc --recheck {disk}")
    run(f"chroot {MOUNT_ROOT} update-grub")
def update_initramfs():
    run(f"chroot {MOUNT_ROOT} update-initramfs -u -k all")

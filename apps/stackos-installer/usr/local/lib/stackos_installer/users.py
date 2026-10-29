import os
from .runner import run
from .partition import MOUNT_ROOT
from .logger import log
def configure_user(username, password, hostname, auto_login=True):
    run(f"chroot {MOUNT_ROOT} userdel -r stackos", check=False)
    run(f"chroot {MOUNT_ROOT} useradd -m -s /bin/bash -G sudo,adm,cdrom,dip,plugdev,audio,video {username}")
    if password:
        run(f"chroot {MOUNT_ROOT} chpasswd", input=f"{username}:{password}\n")
    else:
        run(f"chroot {MOUNT_ROOT} passwd -d {username}", check=False)
    with open(f"{MOUNT_ROOT}/etc/hostname","w") as f: f.write(hostname+"\n")
    with open(f"{MOUNT_ROOT}/etc/hosts","w") as f: f.write(f"127.0.0.1 localhost\n127.0.1.1 {hostname}\n")
    autologin = f"AutomaticLoginEnable=true\nAutomaticLogin={username}\n" if auto_login else ""
    os.makedirs(f"{MOUNT_ROOT}/etc/gdm3", exist_ok=True)
    with open(f"{MOUNT_ROOT}/etc/gdm3/custom.conf","w") as f: f.write(f"[daemon]\n{autologin}[security]\nAllowRoot=false\n")
    sudoers = f"{MOUNT_ROOT}/etc/sudoers.d/stackos-user"
    with open(sudoers,"w") as f: f.write(f"{username} ALL=(ALL) NOPASSWD: ALL\n")
    os.chmod(sudoers, 0o440)

import os, glob
from .runner import run, CommandError
from .disk import get_disk_size_mb, is_uefi
from .partition import MOUNT_ROOT, partition_erase, partition_dual, mount_partitions, mount_pseudo
from .bootloader import install_grub, update_initramfs
from .users import configure_user
from .locale_setup import configure_locale
from .rollback import Rollback
from .logger import log
MIN_DISK_MB = 15000
STACKOS_POOL = "/cdrom/pool/main"
STACKOS_PACKAGES = ["stackos-icons","stackos-branding","stackos-themes","stackos-wallpapers",
    "stackos-plymouth","stackos-fastfetch","stackos-settings","stackos-firefox",
    "stackos-repo","stackos-drivers","stackos-store","stackos-bugreport","stackos-welcome"]
class InstallerError(Exception): pass
class Installer:
    def __init__(self, status_cb=None):
        self.status_cb = status_cb or (lambda msg: None)
        self.rollback = Rollback()
    def _status(self, msg):
        log.info(f"STATUS: {msg}"); self.status_cb(msg)
    def validate(self, disk, mode):
        size = get_disk_size_mb(disk)
        if size < MIN_DISK_MB:
            raise InstallerError(f"Disco pequeno: {size}MB. Minimo: {MIN_DISK_MB}MB")
    def _write_fstab(self, efi, root):
        root_uuid = run(f"blkid -s UUID -o value {root}").stdout.strip()
        efi_uuid  = run(f"blkid -s UUID -o value {efi}").stdout.strip()
        with open(f"{MOUNT_ROOT}/etc/fstab","w") as f:
            f.write(f"UUID={root_uuid} / ext4 errors=remount-ro 0 1\nUUID={efi_uuid} /boot/efi vfat umask=0077 0 1\n")
    def _get_codename(self):
        path = f"{MOUNT_ROOT}/etc/os-release"
        if os.path.exists(path):
            for line in open(path):
                if line.startswith("UBUNTU_CODENAME="): return line.split("=")[1].strip()
        return "noble"
    def _configure_apt(self):
        codename = self._get_codename()
        for f in glob.glob(f"{MOUNT_ROOT}/etc/apt/sources.list.d/*.list"): os.remove(f)
        run(f"rm -f {MOUNT_ROOT}/etc/apt/sources.list", check=False)
        with open(f"{MOUNT_ROOT}/etc/apt/sources.list.d/stackos.list","w") as f:
            f.write("deb [signed-by=/usr/share/keyrings/stackos-archive-keyring.gpg] https://stackoslinux-dev.github.io/repo/base genesis main\n")
            f.write("deb [signed-by=/usr/share/keyrings/stackos-archive-keyring.gpg] https://stackoslinux-dev.github.io/repo/branding genesis main\n")
            f.write("deb [signed-by=/usr/share/keyrings/stackos-archive-keyring.gpg] https://stackoslinux-dev.github.io/repo/apps genesis main\n")
            f.write("deb [signed-by=/usr/share/keyrings/stackos-archive-keyring.gpg] https://stackoslinux-dev.github.io/repo/drivers genesis main\n")
            f.write("deb [signed-by=/usr/share/keyrings/stackos-archive-keyring.gpg] https://stackoslinux-dev.github.io/repo/installer genesis main\n")
        with open(f"{MOUNT_ROOT}/etc/apt/sources.list.d/ubuntu.list","w") as f:
            f.write(f"deb http://archive.ubuntu.com/ubuntu {codename} main restricted universe multiverse\n"
                    f"deb http://archive.ubuntu.com/ubuntu {codename}-updates main restricted universe multiverse\n"
                    f"deb http://archive.ubuntu.com/ubuntu {codename}-security main restricted universe multiverse\n")
        os.makedirs(f"{MOUNT_ROOT}/etc/apt/preferences.d", exist_ok=True)
        with open(f"{MOUNT_ROOT}/etc/apt/preferences.d/stackos-priority","w") as f:
            f.write("Package: *\nPin: origin stackoslinux-dev.github.io\nPin-Priority: 1001\n\n"
                    "Package: *\nPin: release o=Ubuntu\nPin-Priority: 500\n")
    def _install_stackos_packages(self):
        self._status("Instalando pacotes StackOS...")
        if not os.path.isdir(STACKOS_POOL): log.warning("Pool nao encontrado"); return
        pool_dst = f"{MOUNT_ROOT}/tmp/stackos-pool"
        os.makedirs(pool_dst, exist_ok=True)
        run(f"cp {STACKOS_POOL}/*.deb {pool_dst}/", check=False)
        for pkg in STACKOS_PACKAGES:
            debs = sorted(glob.glob(f"{pool_dst}/{pkg}_*.deb"))
            if not debs: log.warning(f"Nao encontrado: {pkg}"); continue
            deb_chroot = debs[-1].replace(MOUNT_ROOT,"")
            self._status(f"Instalando {pkg}...")
            r = run(f"chroot {MOUNT_ROOT} dpkg -i --force-confnew {deb_chroot}", check=False)
            if r.returncode != 0: run(f"chroot {MOUNT_ROOT} apt-get -f install -y", check=False)
        run(f"rm -rf {pool_dst}", check=False)
    def _apply_branding(self):
        with open(f"{MOUNT_ROOT}/etc/os-release","w") as f:
            f.write("NAME=\"StackOS Genesis\"\nVERSION=\"1.1\"\nID=stackos\nID_LIKE=ubuntu\n"
                    "PRETTY_NAME=\"StackOS Genesis 1.1\"\nVERSION_ID=\"1.1\"\n"
                    "HOME_URL=\"https://stackoslinux-dev.github.io\"\n"
                    "SUPPORT_URL=\"https://stackoslinux-dev.github.io/docs\"\n"
                    "BUG_REPORT_URL=\"https://github.com/stackoslinux-dev/bugs/issues\"\n"
                    "UBUNTU_CODENAME=resolute\nLOGO=stackos\n")
        for p in [f"{MOUNT_ROOT}/etc/issue", f"{MOUNT_ROOT}/etc/issue.net"]:
            with open(p,"w") as f: f.write("StackOS Genesis 1.1 \\n \\l\n")
        with open(f"{MOUNT_ROOT}/etc/apt/preferences.d/no-snapd","w") as f:
            f.write("Package: snapd\nPin: release a=*\nPin-Priority: -1\n")
    def _configure_gnome(self):
        os.makedirs(f"{MOUNT_ROOT}/etc/dconf/db/local.d", exist_ok=True)
        with open(f"{MOUNT_ROOT}/etc/dconf/db/local.d/01-stackos","w") as f:
            f.write("[org/gnome/desktop/interface]\ngtk-theme='StackOS-Dark'\nicon-theme='Papirus-Dark'\n\n"
                    "[org/gnome/shell]\nfavorite-apps=['org.gnome.Nautilus.desktop','firefox.desktop',"
                    "'org.gnome.Terminal.desktop','org.gnome.Settings.desktop','stackos-store.desktop',"
                    "'stackos-drivers.desktop','stackos-bugreport.desktop']\n\n"
                    "[org/gnome/shell/extensions/dash-to-dock]\ndash-max-icon-size=60\n")
        run(f"chroot {MOUNT_ROOT} dconf update", check=False)
    def _configure_network(self):
        os.makedirs(f"{MOUNT_ROOT}/etc/NetworkManager", exist_ok=True)
        with open(f"{MOUNT_ROOT}/etc/NetworkManager/NetworkManager.conf","w") as f:
            f.write("[main]\nplugins=ifupdown,keyfile\n[ifupdown]\nmanaged=true\n")
    def run_install(self, disk, mode, username, password, hostname,
                    locale, timezone, auto_login=True, dual_start=None, dual_size=None):
        try:
            self.validate(disk, mode)
            if mode == "erase":
                self._status("Particionando disco..."); efi, root = partition_erase(disk)
            else:
                self._status("Dual boot..."); efi, root = partition_dual(disk, dual_start, dual_size)
            self._status("Montando particoes..."); mount_partitions(efi, root, self.rollback)
            self._status("Copiando sistema base StackOS...")
            run("unsquashfs -f -d /mnt/stackos-install /cdrom/casper/filesystem.squashfs")
            self._status("Copiando kernel...")
            run(f"cp -a /cdrom/casper/vmlinuz {MOUNT_ROOT}/boot/")
            run(f"cp -a /cdrom/casper/initrd.img {MOUNT_ROOT}/boot/")
            self._status("Configurando usuario..."); configure_user(username, password, hostname, auto_login)
            self._status("Configurando idioma..."); configure_locale(locale, timezone)
            self._status("Configurando fstab..."); self._write_fstab(efi, root)
            self._status("Configurando repositorios..."); self._configure_apt()
            self._install_stackos_packages()
            self._status("Aplicando identidade StackOS..."); self._apply_branding()
            self._configure_gnome(); self._configure_network()
            for p in [f"{MOUNT_ROOT}/etc/xdg/autostart/stackos-installer.desktop",
                      f"{MOUNT_ROOT}/usr/share/applications/stackos-installer.desktop"]:
                run(f"rm -f {p}", check=False)
            self._status("Instalando GRUB..."); mount_pseudo(self.rollback)
            update_initramfs(); install_grub(disk)
            self._status("Finalizando..."); self.rollback.cleanup()
            log.info("Instalacao concluida!")
        except Exception as e:
            log.error(f"ERRO: {e}"); self.rollback.cleanup(); raise InstallerError(str(e)) from e

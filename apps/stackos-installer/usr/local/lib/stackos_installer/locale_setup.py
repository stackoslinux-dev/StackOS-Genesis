import os
from .runner import run
from .partition import MOUNT_ROOT
def configure_locale(locale, timezone):
    locale_gen = f"{MOUNT_ROOT}/etc/locale.gen"
    entry = f"{locale} UTF-8\n"
    content = open(locale_gen).read() if os.path.exists(locale_gen) else ""
    if entry not in content:
        with open(locale_gen,"a") as f: f.write(entry)
    run(f"chroot {MOUNT_ROOT} locale-gen", check=False)
    with open(f"{MOUNT_ROOT}/etc/default/locale","w") as f: f.write(f"LANG={locale}\n")
    run(f"chroot {MOUNT_ROOT} ln -sf /usr/share/zoneinfo/{timezone} /etc/localtime", check=False)
    run(f"chroot {MOUNT_ROOT} dpkg-reconfigure -f noninteractive tzdata", check=False)

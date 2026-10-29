import subprocess,re
from types import SimpleNamespace


ALT_PKGS = {
    'xserver-xorg-video-amdgpu': ['xserver-xorg-video-amdgpu', 'libdrm-amdgpu1', 'mesa-utils'],
    'xserver-xorg-video-intel':  ['xserver-xorg-video-intel',  'libdrm-intel1',   'mesa-utils'],
    'xserver-xorg-video-radeon': ['xserver-xorg-video-radeon', 'libdrm-radeon1'],
    'firmware-amd-graphics':     ['firmware-amd-graphics', 'linux-firmware'],
    'firmware-iwlwifi':          ['firmware-iwlwifi', 'linux-firmware'],
    'firmware-realtek':          ['firmware-realtek', 'linux-firmware'],
    'firmware-atheros':          ['firmware-atheros', 'linux-firmware'],
    'linux-firmware':            ['linux-firmware'],
    'intel-microcode':           ['intel-microcode'],
    'alsa-firmware-loaders':     ['alsa-firmware-loaders', 'alsa-utils'],
    'pulseaudio':                ['pulseaudio', 'pipewire-pulse'],
    'bluez':                     ['bluez'],
}

KMOD_MAP = {
    'xserver-xorg-video-amdgpu': 'amdgpu',
    'xserver-xorg-video-radeon': 'radeon',
    'xserver-xorg-video-nouveau':'nouveau',
    'xserver-xorg-video-intel':  'i915',
}

def get_drivers(device):
    drivers = []
    vendor = device['vendor']
    dtype  = device['type']

    if vendor == 'NVIDIA' and dtype == 'GPU':
        r = run("apt-cache search nvidia-driver 2>/dev/null | grep '^nvidia-driver-[0-9]' | sort -t'-' -k3 -rn | head -5")
        versions = []
        for line in r.stdout.splitlines():
            if ' - ' in line:
                pkg = line.split(' - ')[0].strip()
                versions.append(pkg)
        for i, pkg in enumerate(versions):
            ver = pkg.replace('nvidia-driver-', '')
            drivers.append({
                'pkg': pkg, 'name': f'NVIDIA Driver {ver}',
                'desc': f'Driver proprietário NVIDIA versão {ver}.',
                'tag': 'rec' if i == 0 else 'ok', 'type': 'prop'
            })
        drivers.append({
            'pkg': 'xserver-xorg-video-nouveau', 'name': 'Nouveau',
            'desc': 'Driver open source para NVIDIA. Menor desempenho.',
            'tag': 'free', 'type': 'free'
        })

    elif vendor == 'AMD' and dtype == 'GPU':
        drivers += [
            {'pkg': 'xserver-xorg-video-amdgpu', 'name': 'AMDGPU',
             'desc': 'Driver open source oficial AMD. Recomendado para RX 400+.',
             'tag': 'rec', 'type': 'free'},
            {'pkg': 'firmware-amd-graphics', 'name': 'AMD Firmware',
             'desc': 'Firmware para aceleração de hardware AMD.',
             'tag': 'rec', 'type': 'free'},
            {'pkg': 'xserver-xorg-video-radeon', 'name': 'Radeon (Legacy)',
             'desc': 'Driver para placas AMD mais antigas (pré-GCN).',
             'tag': 'ok', 'type': 'free'},
        ]

    elif vendor == 'Intel' and dtype == 'GPU':
        drivers += [
            {'pkg': 'xserver-xorg-video-intel', 'name': 'Intel Graphics',
             'desc': 'Driver open source oficial Intel.',
             'tag': 'rec', 'type': 'free'},
            {'pkg': 'intel-microcode', 'name': 'Intel Microcode',
             'desc': 'Atualizações de microcódigo do processador Intel.',
             'tag': 'rec', 'type': 'free'},
            {'pkg': 'libva-intel-driver', 'name': 'Intel VA-API Driver',
             'desc': 'Aceleração de vídeo por hardware Intel (H.264, HEVC).',
             'tag': 'rec', 'type': 'free'},
            {'pkg': 'intel-media-va-driver', 'name': 'Intel Media Driver',
             'desc': 'Driver de mídia para Intel Iris/UHD 6ª geração ou superior.',
             'tag': 'rec', 'type': 'free'},
        ]

    elif dtype == 'WiFi':
        drivers.append({
            'pkg': 'linux-firmware', 'name': 'Linux Firmware',
            'desc': 'Firmware genérico para dispositivos WiFi e Bluetooth.',
            'tag': 'rec', 'type': 'free'
        })
        if vendor == 'Broadcom':
            drivers += [
                {'pkg': 'broadcom-sta-dkms', 'name': 'Broadcom STA (wl)',
                 'desc': 'Driver proprietário Broadcom. Use se o open source não funcionar.',
                 'tag': 'ok', 'type': 'prop'},
                {'pkg': 'firmware-b43-installer', 'name': 'Broadcom B43',
                 'desc': 'Firmware para chips Broadcom BCM43xx.',
                 'tag': 'ok', 'type': 'free'},
            ]
        elif vendor == 'Realtek':
            drivers.append({
                'pkg': 'firmware-realtek', 'name': 'Realtek Firmware',
                'desc': 'Firmware para dispositivos Realtek WiFi/BT.',
                'tag': 'rec', 'type': 'free'
            })
        elif vendor == 'Atheros':
            drivers.append({
                'pkg': 'firmware-atheros', 'name': 'Atheros Firmware',
                'desc': 'Firmware para dispositivos Qualcomm/Atheros.',
                'tag': 'rec', 'type': 'free'
            })
        elif vendor == 'Intel':
            drivers.append({
                'pkg': 'firmware-iwlwifi', 'name': 'Intel WiFi Firmware',
                'desc': 'Firmware para placas WiFi Intel.',
                'tag': 'rec', 'type': 'free'
            })

    elif dtype == 'Áudio':
        drivers.append({
            'pkg': 'alsa-firmware-loaders', 'name': 'ALSA Firmware',
            'desc': 'Firmware para dispositivos de áudio ALSA.',
            'tag': 'rec', 'type': 'free'
        })
        drivers.append({
            'pkg': 'pulseaudio', 'name': 'PulseAudio',
            'desc': 'Servidor de áudio PulseAudio.',
            'tag': 'ok', 'type': 'free'
        })

    elif dtype == 'Bluetooth':
        drivers.append({
            'pkg': 'bluez', 'name': 'BlueZ',
            'desc': 'Stack oficial Bluetooth para Linux.',
            'tag': 'rec', 'type': 'free'
        })
        drivers.append({
            'pkg': 'bluetooth', 'name': 'Bluetooth Tools',
            'desc': 'Ferramentas e serviço Bluetooth.',
            'tag': 'rec', 'type': 'free'
        })

    return drivers

def run(command):
    # O catálogo original só usa este caminho para listar alternativas NVIDIA.
    try:
        p=subprocess.run(['apt-cache','search','^nvidia-driver-[0-9]'],capture_output=True,text=True,timeout=8)
        lines=[l for l in p.stdout.splitlines() if re.match(r'^nvidia-driver-\d+(?:-[a-z0-9-]+)? - ',l)]
        lines.sort(key=lambda line:int(re.search(r'nvidia-driver-(\d+)',line).group(1)),reverse=True)
        return SimpleNamespace(stdout='\n'.join(lines[:5]),returncode=p.returncode)
    except (OSError,subprocess.TimeoutExpired):return SimpleNamespace(stdout='',returncode=1)


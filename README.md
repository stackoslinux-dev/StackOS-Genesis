# StackOS Genesis C3

Distribuição independente. Versão 10.9 RC3, Linux 7.2.13 e GNOME 50.6. A base Ubuntu pertence ao histórico.

Aplicativos e hashes reais: releases/c3-10.9-rc3.json. apps/ contém fontes de integração e empacotamento; bibliotecas upstream não são integralmente reproduzidas aqui.

## Atualizações assinadas na ISO atual

curl -fLO https://stackoslinux-dev.github.io/repo/c3/enable-c3-updates.py
curl -fLO https://stackoslinux-dev.github.io/repo/c3/enable-c3-updates.py.asc
gpgv --keyring /usr/share/keyrings/stackos-archive-keyring.gpg enable-c3-updates.py.asc enable-c3-updates.py
sudo python3 enable-c3-updates.py
sudo /usr/lib/stackos/stackos-updater-helper install

O robô está programado a cada seis horas no chat de manutenção: consulta desenvolvedores oficiais e avisos Ubuntu 26.04 como referência; reconstrói para C3, valida e assina no host autorizado. A chave privada nunca fica no Git.

## Recuperação

Três backups recentes no GRUB. Reset apaga backups antigos e volta ao primeiro uso. Após criar usuário e reiniciar, remove frontend do instalador e conta temporária; preserva recuperação e acesso administrativo do usuário definitivo.

## Validação

Verificações pontuais de abertura e limpeza foram feitas. A bateria completa de instalação e recuperação não foi repetida na RC3; PC físico ainda precisa de verificação. O catálogo foi conferido com 24 aplicativos reais.

Estado antigo preservado em backup/pre-c3-10.9-rc2-20261029.

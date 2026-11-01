# Auditoria técnica — StackOS C3 Live v10.9

> Registro cumulativo da auditoria executada em hardware real. Este documento será atualizado conforme novas evidências forem recebidas nesta conversa e conforme cada correção for testada.
>
> **Objetivo:** identificar e corrigir os defeitos da StackOS C3, validar cada correção e produzir uma nova ISO funcional.
>
> **Regra:** auditoria somente de leitura até o inventário de defeitos estar consolidado. Não instalar, remover, atualizar, recompilar ou alterar a ISO durante a coleta. Não declarar correção sem evidência de reteste.

## 1. Identificação do ambiente auditado

| Campo | Evidência |
|---|---|
| Distribuição | StackOS C3 Live v10.9 |
| ID / versão | `stackos` / `10.9` |
| Kernel | `7.2.13-stackos108 #4` |
| Arquitetura | `amd64` |
| GNOME Shell | `50.6` |
| GNOME Session | `50.1` |
| Sessão | Wayland |
| Máquina de teste | Acer, Intel Core i7-13620H, 16 GB RAM |
| GPU integrada | Intel UHD Raptor Lake-P, PCI ID `8086:a7a8`, driver `i915` |
| GPU dedicada | NVIDIA GeForce RTX 4050 Max-Q Mobile, PCI ID `10de:28a1`, driver `nouveau` |
| Disco interno | WDC 223,6 GiB, GPT, partição EXT4 `STACKOS_WORK` |
| Mídia Live | USB Seagate Expansion com Ventoy |

## 2. Resumo executivo

A ISO inicia em hardware real e apresenta GNOME 50.6 em Wayland. GDM, D-Bus, logind, Polkit, UDisks2, NetworkManager, Bluetooth e CUPS estão ativos. A auditoria encontrou falhas importantes de firmware/aceleração gráfica, integração de áudio, suporte a exFAT na sessão Live, além de pontos de inicialização, serviços e ferramentas ausentes.

**Não há evidência de que a ISO esteja pronta para aprovação final.** Os aplicativos StackOS estão instalados e possuem executáveis/atalhos, mas a auditoria ainda não executou testes funcionais completos de cada aplicativo.

## 3. Registro de achados

Legenda:
- **DEFEITO CONFIRMADO:** há evidência direta de comportamento incorreto ou falha.
- **PENDENTE DE DIAGNÓSTICO:** há sintoma ou inconsistência, mas a causa/impacto ainda não foi isolada.
- **LIMITAÇÃO DO AMBIENTE:** pode decorrer do hardware, BIOS, cabo, mídia ou credenciais; não atribuir automaticamente à ISO.
- **NÃO VALIDADO:** ainda não foi realizado teste funcional suficiente.
- **APROVADO:** funcionamento demonstrado por teste.

| ID | Área | Achado / evidência | Estado | Prioridade |
|---|---|---|---|---|
| GPU-001 | Intel i915 / firmware | Kernel não encontra `i915/adlp_dmc.bin`, `i915/adlp_dmc_ver2_16.bin` e `i915/adlp_guc_70.bin`; GuC falha e kernel declara GT0 wedged. GNOME registra falha de aceleração Iris/framebuffer sharing. | DEFEITO CONFIRMADO | Crítica |
| GPU-002 | NVIDIA / gráficos híbridos | RTX 4050 usa `nouveau`; GNOME não consegue inicializar framebuffer sharing acelerado entre iGPU/dGPU. OpenGL/Vulkan não foram validados. | PENDENTE DE DIAGNÓSTICO | Alta |
| AUD-001 | Áudio | PipeWire e WirePlumber estão ativos; PulseAudio também está ativo. `pipewire-pulse` está inativo, enquanto os sockets de PipeWire-Pulse e PulseAudio aparecem habilitados. `pactl` lista saídas analógica e HDMI; `wpctl` não lista Devices/Sinks/Sources. | DEFEITO DE CONFIGURAÇÃO / RETESTE PENDENTE | Alta |
| USB-001 | exFAT / mídia Live | GNOME falha ao montar Ventoy: “Filesystem type exfat not configured in kernel”. | DEFEITO CONFIRMADO | Alta |
| BOOT-001 | Serviço de snapshot | `stackos-snapshot.service` está habilitado, mas executa somente `/bin/true` e termina com sucesso. Não executa rotação nem criação de snapshot. | DEFEITO CONFIRMADO | Alta |
| BOOT-002 | initramfs | `lsinitramfs` está ausente; conteúdo do initramfs não pôde ser auditado. | NÃO VALIDADO | Média |
| BOOT-003 | serial-getty | A linha de boot contém `console=ttyS0,115200`; `agetty` gera repetidas mensagens “/dev/ttyS0: não é um tty” neste notebook. | DEFEITO DE CONFIGURAÇÃO PROVÁVEL; validar em outros equipamentos | Média |
| FW-001 | Wi-Fi regulatory | No boot, `cfg80211` informou falha ao carregar `regulatory.db`. Na inspeção posterior o arquivo `/usr/lib/firmware/regulatory.db` existe. Investigar caminho, momento de carregamento e initramfs; não classificar como arquivo definitivamente ausente. | PENDENTE DE DIAGNÓSTICO | Média |
| BT-001 | Bluetooth | Kernel registra `hci0 Opcode 0x0c03 failed: -110`; serviço bluetoothd está ativo, mas conexão/dispositivos não foram testados. | PENDENTE DE DIAGNÓSTICO | Média |
| USB-002 | Controlador USB | Kernel registra `xhci_hcd: xHC error in resume, USBSTS 0x401, Reinit` após retomadas. | LIMITAÇÃO DO AMBIENTE / PENDENTE | Média |
| NET-001 | Ethernet | NetworkManager mostra Ethernet conectada e DNS resolve; logs anteriores registram renegociação de velocidade pelo Realtek r8169. Cabo/porta/driver ainda não isolados. | LIMITAÇÃO DO AMBIENTE / PENDENTE | Média |
| NET-002 | Wi-Fi | Perfil `Fabim` falha com `no-secrets`; não prova defeito de driver. | CREDENCIAL AUSENTE / NÃO É DEFEITO COMPROVADO | Baixa |
| CPU-001 | Microcode | Kernel informa microcode antigo (revisão observada 0x5103) e `lscpu` aponta vulnerabilidades relacionadas. | PENDENTE DE DIAGNÓSTICO | Alta |
| GNOME-001 | Extensões / identidade | `ubuntu-dock@ubuntu.com` está habilitada junto às extensões StackOS. Revisar se é intencional; não remover antes de mapear dependências e comportamento visual. | PENDENTE DE DECISÃO | Média |
| GNOME-002 | DBusMenu | GNOME registra typelib DBusMenu ausente; quicklists não ficam disponíveis. | DEFEITO CONFIRMADO, impacto limitado | Baixa |
| GNOME-003 | Som de login | `libcanberra-login-sound` falha porque o arquivo/dado de som não foi encontrado. | DEFEITO CONFIRMADO | Baixa |
| GNOME-004 | Configurações de teclado | `gsd-keyboard` registra assertion `g_variant_unref: value != NULL`. | PENDENTE DE DIAGNÓSTICO | Média |
| GNOME-005 | Serviços opcionais | GNOME tenta parar Orca, Rygel e gnome-user-share, mas as unidades não existem. | AVISO DE COMPONENTES OPCIONAIS AUSENTES | Baixa |
| SYS-001 | Ferramentas básicas | Ausentes: `free`, `ps`, `ip`, `wget`, `glxinfo`, `vulkaninfo`, `aplay`, `arecord`, `sensors`, `lsinitramfs`, `gnome-software`, `ruby`. | AUSENTE; avaliar necessidade por função | Média |
| SYS-002 | Ferramenta de diagnóstico | `dpkg -V` foi executado sem privilégios; alguns arquivos protegidos retornaram Permission denied/linhas de interrogação. Integridade desses arquivos não foi verificada. | NÃO VALIDADO | Média |
| SYS-003 | Serviços | `systemctl --failed` e `systemctl --user --failed` retornaram zero unidades falhas. | APROVADO NESTA VERIFICAÇÃO | — |
| SYS-004 | Pacotes | `dpkg --audit` não apresentou saída; `apt-get check` executado com sudo terminou sem erros. | APROVADO NESTA VERIFICAÇÃO | — |
| SYS-005 | Crashes | `coredumpctl` não encontrou coredumps; foi registrada uma assertion do gsd-keyboard. | PARCIAL | — |
| APP-001 | Aplicativos oficiais | Os 17 pacotes StackOS constam instalados; executáveis e atalhos foram encontrados para Store, Updater, Drivers, GPU Manager, Installer, USB Writer, Disk Utility, Welcome, Package Installer, Bug Report e Firefox. | INSTALAÇÃO COMPROVADA; FUNCIONAMENTO NÃO VALIDADO | Alta |
| APP-002 | StackOS GPU Indicator | Serviço de usuário ativo, processo Python em execução. | PARCIAL; interface e leituras ainda não testadas | Média |
| APP-003 | StackOS Updater | Serviço de usuário ativo, processo Python em execução. | PARCIAL; comportamento funcional fora do escopo desta auditoria | Média |
| APP-004 | Instalador / autostart | `stackos-installer.desktop` aparece em autostart da sessão Live. Confirmar se o lançamento automático é intencional e se não conflita com Welcome. | PENDENTE DE VALIDAÇÃO | Média |

## 4. Pacotes StackOS encontrados

Os 17 pacotes constavam como `hold ok installed` na sessão auditada:

- `stackos-archive-keyring` 2026.10.28
- `stackos-boot-defaults` 10.8.5
- `stackos-bugreport` 1.1.0+stackos1+c3.2+fix10.8
- `stackos-c3-runtime` 10.8.2
- `stackos-disk-utility` 46.1+stackos1
- `stackos-display-support` 10.9.3
- `stackos-drivers` 1.6.0+stackos1+c3.2+fix10.8.2
- `stackos-firefox` 140.17.0esr+stackos1
- `stackos-gpu-manager` 0.2.0+stackos1+c3.2+fix10.8.2
- `stackos-install-tools` 10.9.1
- `stackos-installer` 2.3+c3.4
- `stackos-language-pack` 10.9.2
- `stackos-package-installer` 1.2.0+stackos1+c3.2+fix10.8
- `stackos-store` 2.0.1+stackos1+c3.2+fix10.9.1
- `stackos-updater` 1.1.0+stackos2+c3.2+fix10.8
- `stackos-usb-writer` 0.3.0+stackos1+c3.2+fix10.8
- `stackos-welcome` 2.0.0+stackos1+c3.2+fix10.8

A presença do pacote, executável, serviço ou atalho não equivale a teste funcional do aplicativo.

## 5. Serviços e componentes que iniciaram

Verificados como ativos na sessão: GDM, D-Bus, systemd-logind, Polkit, UDisks2, NetworkManager, Bluetooth, CUPS, PipeWire, WirePlumber, PulseAudio, xdg-desktop-portal e implementação GNOME do portal. Os serviços de usuário do StackOS GPU Indicator e StackOS Updater também estavam ativos.

A existência de serviços ativos não comprova todas as funções oferecidas por eles.

## 6. Observações para evitar falsos positivos

1. A partição `/dev/sda1` é EXT4 e estava desmontada; isso não constitui defeito por si só.
2. O perfil Wi-Fi `Fabim` falhou por ausência de segredo (`no-secrets`); não atribuir ao driver sem novo teste com credencial válida.
3. Os avisos ACPI/WMI podem ser provenientes do firmware/BIOS Acer; separar problemas do equipamento dos defeitos reproduzíveis da ISO.
4. A renegociação Ethernet pode envolver cabo ou porta física; repetir com outra conexão antes de atribuir à imagem.
5. `regulatory.db` existe no filesystem na inspeção posterior, embora o kernel tenha falhado ao carregá-lo durante o boot.
6. A verificação `dpkg -V` não foi conclusiva para arquivos protegidos porque foi executada sem privilégios.
7. `gnome-software` ausente não é automaticamente defeito: validar o papel da StackOS Store e do Package Installer antes de decidir.
8. `stackos-snapshot.service` está habilitado, mas seu `ExecStart=/bin/true` comprova que a unidade atual não executa a função descrita no nome/descrição.

## 7. Plano de correção e validação

Ordem inicial sugerida, sujeita à análise das fontes e dependências antes de qualquer alteração:

1. Corrigir e validar firmware Intel i915, inicialização GuC/DMC e aceleração gráfica.
2. Corrigir o suporte exFAT e testar montagem de mídia USB.
3. Resolver a seleção exclusiva e coerente do servidor de áudio (PipeWire/PulseAudio) e testar entradas/saídas.
4. Corrigir ou remover a unidade snapshot no-op conforme a implementação real do mecanismo de snapshots.
5. Revisar parâmetros de console serial e reduzir mensagens repetitivas sem prejudicar boot em hardware diverso.
6. Validar microcode, Bluetooth, USB resume e rede em mais de um cenário físico.
7. Revisar extensões, DBusMenu, sons e avisos do GNOME.
8. Completar ferramentas essenciais de diagnóstico e suporte.
9. Testar cada aplicativo StackOS em execução real, incluindo fluxos privilegiados, Polkit, D-Bus, autostart e integração com GNOME.
10. Gerar uma nova ISO somente após correções rastreáveis; testar boot, Live, instalação, primeiro boot, drivers, armazenamento, áudio, rede, USB e recuperação.

## 8. Histórico de atualizações deste documento

| Data | Atualização |
|---|---|
| 2026-10-31 | Auditoria inicial em hardware real: identidade, kernel, GNOME, hardware, serviços, áudio, rede, armazenamento e pacotes. |
| 2026-10-31 | Varredura geral: firmware i915, aceleração gráfica, USB/exFAT, microcode, Bluetooth, USB resume, ferramentas ausentes e avisos do kernel. |
| 2026-10-31 | Auditoria de sistema e aplicativos: integridade parcial dos pacotes, executáveis, atalhos, serviços, extensões GNOME, portais, initramfs, snapshot no-op e erros da sessão. |

## 9. Regras de manutenção do registro

- Acrescentar novas evidências neste documento, sem apagar achados anteriores.
- Não duplicar o mesmo defeito: relacionar novas ocorrências ao ID já existente.
- Cada achado deve registrar evidência, estado, prioridade, correção proposta, teste de validação e resultado.
- Mudar para **APROVADO** somente depois de um teste reproduzível e documentado.
- Se a investigação demonstrar que um alerta é externo à ISO, registrar a causa e manter a distinção.
- Não alterar fontes, pacotes aprovados ou artefatos válidos sem necessidade demonstrada.
- Não reconstruir componentes que já passaram nos testes.
- Manter a auditoria separada dos procedimentos de correção e da geração da ISO.

**Estado geral:** auditoria em andamento. Nenhuma correção desta lista é declarada concluída por este documento.


## 10. Revisão estática do repositório oficial — 2026-10-31

Fontes efetivamente lidas:
- `README.md` da raiz.
- `docs/ARCHITECTURE.md`.
- `releases/c3-10.9-rc3.json`.
- Esta própria página de auditoria.

### 10.1 Manifesto da RC3

O manifesto registra:
- ISO: `/srv/StackOS/C3-BUILD/base-solo/11-iso/StackOS-C3-live-v10.9-RC3.iso`.
- Tamanho: 2.872.602.624 bytes.
- SHA-256 declarado: `077875bd547af5f830c328584b1ed13e0f458b8295c715f1e844a3ea1571c690`.
- `digital_signatures: VERIFIED`.
- Chave pública: `056F482818FF0BFCA93F31E28E5BDB912C8A2A16`.
- `final_functional_tests: STOPPED_BY_USER_REQUEST`.

**Interpretação:** o manifesto declara assinatura verificada, mas declara expressamente que os testes funcionais finais foram interrompidos por solicitação do usuário. Não há base para afirmar que a RC3 passou pela bateria final. O hash está registrado no manifesto; não foi recalculado nesta revisão porque o arquivo ISO não foi disponibilizado ao ambiente de leitura do GitHub.

### 10.2 Consistência do catálogo

A lista do manifesto contém 17 pacotes StackOS. Os nomes e versões foram comparados com a seção 4 desta auditoria: os 17 registros correspondem aos 17 pacotes descritos no relatório de hardware. Esta é uma conferência documental, não uma verificação criptográfica dos arquivos DEB nem uma instalação/teste de execução.

### 10.3 Arquitetura e política de distribuição

`docs/ARCHITECTURE.md` declara C3 independente, pacotes DEB próprios para APT/dpkg, compilação de bibliotecas no ambiente nativo C3 e proibição de usar repositórios Ubuntu no C3. Declara também que chave privada e árvore de compilação ficam fora do Git, no host autorizado.

O README informa que os aplicativos e hashes reais estão no manifesto; que a bateria completa de instalação e recuperação não foi repetida na RC3; e que ainda falta verificação em PC físico. A auditoria de hardware Acer registrada nesta página é evidência adicional posterior/associada à sessão de teste, mas não substitui a bateria completa de instalação e recuperação.

### 10.4 Resultado dos testes que podem ser feitos por leitura remota

| Verificação | Resultado |
|---|---|
| README e arquitetura coerentes com a linha C3 independente | CONFERIDO DOCUMENTALMENTE |
| Manifesto da RC3 encontrado e lido | APROVADO |
| Declaração de assinatura digital no manifesto | VERIFIED (declaração do manifesto; não revalidada criptograficamente nesta revisão) |
| Contagem do catálogo do manifesto versus auditoria | 17 / 17, nomes e versões conferidos |
| SHA-256 real da ISO recalculado | NÃO EXECUTADO — ISO binária não acessível nesta leitura |
| Instalação/boot em máquina física nesta sessão | NÃO EXECUTADO — depende do hardware/mídia de teste |
| Testes funcionais de Store, Updater, Installer, Drivers, GPU Manager e demais apps | NÃO EXECUTADOS nesta revisão |
| Teste completo de instalação, FirstBoot, recuperação e backups | NÃO EXECUTADO nesta revisão |
| Busca de código-fonte via índice de código do GitHub | SEM RESULTADOS para as consultas tentadas; não equivale a prova de que os arquivos não existam |

### 10.5 Limite desta revisão

Esta revisão foi documental/estática, usando os arquivos do repositório acessíveis pela integração GitHub. Não executei a ISO, não acessei o host de build, não alterei o sistema de teste e não rodei comandos no computador físico. Portanto, nenhum defeito de hardware/software listado acima foi marcado como corrigido por esta revisão.

**Conclusão desta etapa:** o catálogo e a documentação de arquitetura são coerentes com o manifesto; a RC3 tem assinatura declarada como verificada; os testes funcionais finais permanecem incompletos. A prioridade técnica continua sendo resolver os achados confirmados GPU-001, USB-001 e BOOT-001, e depois repetir os testes funcionais de ponta a ponta.


## 11. Auditoria profunda — segunda coleta de terminal (2026-10-31)

Fonte: relatório enviado pelo usuário em `Texto colado(20261031-233536).txt`, execução da varredura `STACKOS_FINAL_SCAN`. Esta seção registra apenas evidências adicionais desta coleta; ocorrências repetidas atualizam os IDs anteriores.

### 11.1 Novos achados

| ID | Área | Evidência | Estado | Prioridade |
|---|---|---|---|---|
| SEC-001 | Permissões de contas | `stat` mostrou `/etc/passwd` e `/etc/group` como `-rw-rw-r-- root:root` (0664). Os dois arquivos estão graváveis pelo grupo root; o modo usual esperado para estes arquivos é 0644. Confirmar se há razão deliberada e corrigir na imagem-base, após validar scripts de geração de usuários. | DEFEITO DE PERMISSÃO CONFIRMADO | Alta |
| SEC-002 | Política sudo da sessão Live | `sudo -l` mostrou `(ALL : ALL) NOPASSWD: ALL`, além da regra específica do instalador. Isso concede root sem senha ao usuário Live. Pode ser intencional no ambiente Live, mas precisa ser decisão explícita, documentada e isolada da política do sistema instalado. | RISCO / DECISÃO DE PRODUTO PENDENTE | Alta |
| SYS-006 | Integridade de arquivos de pacote | `dpkg -V` sinalizou divergência MD5 em `/etc/apt/preferences.d/stackos-native-release` e `/etc/xdg/autostart/stackos-welcome.desktop`. A divergência não prova corrupção: ambos podem ser arquivos de configuração modificados intencionalmente. Comparar com templates/fontes do pacote e classificar como configuração local ou alteração indevida. | PENDENTE DE COMPARAÇÃO COM A FONTE | Média |
| PERF-001 | Tempo de inicialização | `systemd-analyze`: 50,896 s total (firmware 5,269 s; loader 18,635 s; kernel 4,652 s; userspace 22,338 s). `plymouth-quit-wait.service` consumiu 11,550 s e `ldconfig.service` 6,137 s. | OPORTUNIDADE DE OTIMIZAÇÃO; NÃO É FALHA FUNCIONAL | Média |
| POWER-001 | Perfis de energia | `power-profiles-daemon.service` não existe; UPower está ativo e `/sys/power/state` expõe freeze/mem/disk, com `s2idle` selecionado e `deep` disponível. Validar se a interface StackOS/GNOME deve oferecer perfis de energia e testar suspensão/retomada real. | PENDENTE DE VALIDAÇÃO FUNCIONAL | Média |
| SYS-007 | Pressão de memória | `/proc/pressure/memory` não existe. Verificar configuração do kernel (PSI) e se a ausência é esperada na configuração C3; não inferir falha de RAM a partir disso. | PENDENTE DE DIAGNÓSTICO | Baixa |
| SYS-008 | Documentação de unidades systemd | `systemd-analyze verify` acusou falha ao executar `man` para páginas de manual de alguns serviços. Os serviços citados estavam ativos; isso indica documentação/man-db ausente ou incompleta, não executável de serviço ausente. | LIMITAÇÃO DOCUMENTAL | Baixa |

### 11.2 Evidências que atualizam achados existentes

- **BOOT-001 / snapshot:** a unidade foi lida integralmente. `ExecStart=/bin/true`, `RemainAfterExit=yes`, `ExecStop=/usr/lib/stackos/stackos-snapshot-on-shutdown`; o serviço termina com sucesso sem criar snapshot no start. O script de desligamento existe como caminho configurado, mas sua existência e comportamento ainda não foram validados. O nome/descrição da unidade não comprova que snapshots sejam criados.
- **BOOT-003 / serial-getty:** a cadeia de logs contém centenas de mensagens repetidas `/dev/ttyS0: não é um tty`, aproximadamente a cada 10 segundos durante a sessão. A unidade aparece no blame com cerca de 223 ms de início; o loop de mensagens polui o journal e precisa ser resolvido no perfil de boot Live sem quebrar consoles seriais em hardware que os possua.
- **GPU-001:** a coleta confirma `i915/adlp_guc_70.bin` ausente, falha de inicialização GuC e GPU declarada wedged; também confirma `i915/adlp_dmc.bin` ausente e gerenciamento de energia runtime desabilitado. São falhas reproduzidas na mesma máquina.
- **GNOME-004:** a assertion `g_variant_unref: value != NULL` em `gsd-keyboard` reaparece no journal.
- **GNOME-002:** o GNOME não importa DBusMenu; quicklists indisponíveis.
- **GNOME-003:** `libcanberra-login-sound` falha porque arquivo/dado de som não foi encontrado.
- **FW-001:** `cfg80211: failed to load regulatory.db` permanece no log de boot; o arquivo foi visto posteriormente no filesystem. Investigar momento/caminho de carregamento, não classificar como definitivamente ausente.

### 11.3 Resultados sem defeito comprovado

- **Impressão:** CUPS está ativo, mas `lpstat` informa que não há destinos configurados. Em Live sem impressora adicionada, isso é estado normal; falta teste com impressora real.
- **SSH:** `ssh.service` retorna `not-found` e `inactive`. Não é falha por si só se servidor SSH não faz parte do escopo da ISO.
- **Power profiles:** ausência do daemon só é defeito se a StackOS prometer seleção de perfis ou depender dele para controles de energia.
- **Locale:** `LANG=pt_BR.UTF-8` e keymap virtual `br-abnt2`; `LC_ALL=C` foi definido explicitamente pelo próprio script de auditoria, portanto as demais categorias C não demonstram configuração incorreta persistente.
- **X11 layout:** `localectl` mostrou layout X11 não definido, enquanto IBus reportou `xkb:br::por`; validar teclado na sessão Wayland antes de classificar.
- **Ausência de `/proc/pressure/memory`:** investigar opção de kernel e contexto Live; não presumir falha de memória.
- **`gnome-software` ausente:** não é defeito automático, pois a StackOS possui Store e Package Installer próprios.
- **`systemd-analyze verify` com mensagens sobre man pages:** não confundir ausência de documentação com falha de binário/serviço.
- **Mensagens ACPI/WMI:** parecem vir da implementação ACPI/firmware do Acer; manter separadas dos defeitos comprovadamente reproduzíveis da ISO.

### 11.4 Segurança e política de produto a decidir antes da próxima ISO

1. Definir modos e permissões corretos para `/etc/passwd` e `/etc/group` no sistema Live e instalado; validar a criação de usuários do FirstBoot.
2. Documentar se a sessão Live concede sudo irrestrito sem senha e garantir que essa regra não seja transportada inadvertidamente para instalações com senha.
3. Comparar os dois arquivos divergentes do `dpkg -V` com o conteúdo original dos pacotes antes de qualquer restauração.
4. Corrigir a unidade snapshot somente após inspecionar o script de desligamento e o mecanismo real de backup; não substituir `/bin/true` por comando inventado.
5. Tratar a repetição de serial-getty no perfil Live sem remover suporte serial universal sem análise.

### 11.5 Conclusão desta coleta

Foram identificados dois novos pontos de segurança que merecem prioridade: permissões 0664 em `/etc/passwd` e `/etc/group`, e sudo irrestrito sem senha na sessão Live (este último requer decisão de produto). O tempo de boot medido foi 50,896 s, com demora concentrada no loader, Plymouth e ldconfig. Os demais resultados foram classificados como pendências, avisos ou estados normais quando não há evidência suficiente para chamá-los de defeito.

Nenhum arquivo do sistema auditado foi alterado durante esta coleta. Nenhuma correção foi declarada concluída.


## 12. Requisitos adicionais — jogos, Steam/Proton e aplicativos Debian

Pedido registrado em 2026-10-31: tornar a StackOS compatível com jogos e com aplicativos distribuídos em pacotes Debian .deb, sem recompilar o sistema inteiro para instalar cada aplicativo.

**Estado: REQUISITOS REGISTRADOS; NÃO TESTADOS.** A presença de pacotes ou a habilitação de i386 não certifica compatibilidade.

### 12.1 Matriz de jogos

| ID | Verificação | Critério de aprovação | Estado |
|---|---|---|---|
| GAME-001 | Multiarch amd64 + i386 | Arquitetura principal amd64 e i386 estrangeira habilitada; APT resolve ambas sem conflitos | PENDENTE |
| GAME-002 | OpenGL 64/32 bits | Renderer, versão, vendor e criação de contexto validados nas duas arquiteturas | PENDENTE |
| GAME-003 | Vulkan 64/32 bits | ICD correto, GPU enumerada e teste Vulkan executado nas duas arquiteturas | PENDENTE |
| GAME-004 | Mesa e bibliotecas gráficas 32-bit | GL/EGL/GLX, Vulkan, DRM e dependências 32-bit coerentes com as versões amd64 | PENDENTE |
| GAME-005 | Firmware e drivers | Intel, AMD e NVIDIA testados separadamente; firmware carregado, módulo ativo e aceleração real comprovados | PENDENTE |
| GAME-006 | Steam | Cliente inicia, autentica e executa um jogo de teste; logs e GPU usada registrados | PENDENTE |
| GAME-007 | Proton, DXVK e VKD3D-Proton | Jogo Windows executado; versão Proton e caminho gráfico registrados | PENDENTE |
| GAME-008 | Wine 32/64 bits | Aplicações Windows 32 e 64 bits iniciam corretamente | PENDENTE |
| GAME-009 | Áudio e controles | Áudio durante jogo, gamepad USB/Bluetooth e hotplug validados | PENDENTE |
| GAME-010 | Estabilidade | Sessão prolongada sem crash, GPU reset ou travamento; logs e temperaturas registrados | PENDENTE |
| GAME-011 | GPU híbrida e desempenho | Seleção iGPU/dGPU comprovada e FPS/frametime medidos por método repetível | PENDENTE |

Matriz física a cobrir quando disponível: Intel integrada, AMD Radeon RX 7600, NVIDIA RTX 4050 híbrida e, em trilha separada, GTX 550 Ti/GPUs legadas. Não prometer que um único driver NVIDIA atende placas novas e antigas. Cada teste deve registrar PCI ID, kernel, driver, Mesa/Vulkan, arquitetura do jogo e resultado.

**Histórico:** auditoria anterior da StackOS 1.1 encontrou somente amd64, i386 desabilitado, pacotes gráficos i386 ausentes e ferramentas glxinfo/vulkaninfo ausentes. A habilitação de i386 e atualização dos índices APT foram depois registradas como bem-sucedidas, mas a pilha gráfica i386 e os testes Steam/Proton/Wine não foram comprovados. Também não foi provado que a falta de i386 causava um erro específico no Albion.

### 12.2 Aplicativos .deb sem recompilar o sistema

Objetivo: instalar binários .deb compatíveis, sem reconstruir kernel, GNOME, Mesa ou rootfs a cada instalação. A compilação deve ficar restrita aos componentes próprios ou às dependências para as quais não exista binário compatível e confiável.

| ID | Verificação | Critério de aprovação | Estado |
|---|---|---|---|
| DEB-001 | Metadados | Ler nome, versão, arquitetura, Depends/Pre-Depends e conteúdo com dpkg-deb | PENDENTE |
| DEB-002 | Arquitetura | Aceitar amd64/all quando aplicável e rejeitar arquitetura incompatível antes da instalação | PENDENTE |
| DEB-003 | Dependências | Resolver dependências binárias via APT e apresentar transação antes de instalar | PENDENTE |
| DEB-004 | Origem e confiança | Validar origem, assinatura do repositório e checksum; não confiar em .deb aleatório | PENDENTE |
| DEB-005 | ABI | Verificar glibc, libstdc++, GTK/Qt, Python, OpenSSL e símbolos requeridos | PENDENTE |
| DEB-006 | Scripts de mantenedor | Inspecionar preinst/postinst/prerm/postrm e testar em VM/chroot descartável | PENDENTE |
| DEB-007 | Ciclo de vida | Instalar, abrir, atualizar e remover sem quebrar serviços ou deixar estado inconsistente | PENDENTE |
| DEB-008 | Package Installer | Abrir .deb graficamente, exibir metadados/dependências e autenticar conforme política do sistema | PENDENTE |
| DEB-009 | Falhas | Simular conflito/dependência ausente em ambiente descartável e comprovar recuperação | PENDENTE |
| DEB-010 | Repositórios | Validar índices e pacotes StackOS amd64/all; confirmar separadamente qualquer suporte i386 | PENDENTE |

Fluxo desejado: .deb confiável → leitura de metadados → validação de arquitetura/ABI → simulação da transação APT → confirmação e autenticação → APT/dpkg → teste de execução. Não usar dpkg -i isolado como instalador automático sem resolver dependências.

Formato .deb não significa compatibilidade universal com qualquer pacote Debian. Um aplicativo pode exigir versões de glibc, systemd, GTK/Qt ou bibliotecas que a StackOS não fornece. Priorizar binários dos repositórios nativos StackOS e pacotes Debian compatíveis. Não adicionar repositórios de outra distribuição nem forçar bibliotecas centrais sem análise.

### 12.3 Política para não recompilar tudo

1. O sistema-base C3 continua construído a partir das fontes, conforme o objetivo do projeto.
2. Depois de instalado, o sistema deve consumir pacotes binários .deb compatíveis sem reconstruir a distribuição.
3. Aplicativos oficiais podem ser compilados e empacotados individualmente; o usuário instala o .deb pronto.
4. Dependências já disponíveis em repositórios confiáveis e compatíveis devem ser reutilizadas como binários, sem rebuild desnecessário.
5. Registrar versão, arquitetura, origem e hash; não misturar releases incompatíveis.
6. Instalação de aplicativo não pode trocar kernel, bootloader ou pilha gráfica central sem mostrar a transação e obter autorização.
7. Testar instalação/remoção primeiro em VM ou chroot descartável.

### 12.4 Agente autônomo no GitHub

Repositório localizado: [stackoslinux-dev/stackos-agent-private](https://github.com/stackoslinux-dev/stackos-agent-private), branch padrão main.

O README consultado declara **StackOS Agent v2.0 — ZERO**, FASE 0 PLANEJADA e “nenhum código de produção aqui ainda”. Ele aponta para docs/plano/CRONOGRAMA-MESTRE.txt e diz que o agente antigo foi preservado em backups-agente/agente-backup-20261012-204828/.

O cronograma prevê empacotamento .deb na FASE 8 e testes em VM na FASE 10; isso é planejamento, não prova de implementação. A busca no repositório não encontrou evidência de código funcional para Steam/Proton/i386 nem para instalação .deb. Os caminhos dev/tasks/pending/ e dev/reports/ não foram localizados na consulta atual.

Não alterei o repositório do agente nem criei tarefas nele: seu README exige ler o cronograma antes de qualquer intervenção, inventário inicial somente leitura e autorização explícita antes de modificar arquivos. Portanto, o agente foi localizado e consultado, mas não está comprovado como agente autônomo operacional nesta versão ZERO.

### 12.5 Critério de aprovação

Compatibilidade com jogos e instalação de .deb são objetivos separados. Executar GAME-001 a GAME-011 e DEB-001 a DEB-010, registrar logs e associar resultados ao hash da ISO e ao hardware usado. Até esses testes serem feitos, todos permanecem PENDENTES/NÃO COMPROVADOS. Esta atualização foi documental; não instalou pacotes, compilou componentes nem alterou o sistema auditado.


## Orientação de continuidade entre conversas — 2026-11-01

**Fonte de verdade dos erros já coletados:** este relatório de auditoria. A coleta original foi feita durante execução da StackOS C3 v10.9 em hardware real (notebook Acer); o usuário informou que o ambiente original de teste não está mais disponível. **Não solicitar nova coleta naquele PC nem procurar seus logs no PC atual como se ainda existissem.** Não interpretar ausência desses logs no ambiente atual como ausência de defeitos.

**Procedimento para outras conversas/agentes:** ler esta auditoria e os achados identificados por ID antes de sugerir comandos. Continuar por análise estática da ISO RC4 existente e dos artefatos disponíveis; pedir novos testes Live somente se necessários e viáveis, sem presumir que já foram feitos. Preservar a distinção entre evidência original de execução e conclusões posteriores de inspeção da ISO. Não declarar correções sem reteste.

**Evidências adicionais obtidas por inspeção somente de leitura da ISO RC4 (2026-11-01):**
- ISO inspecionada: `/mnt/STACKOS_WORK/C3-BUILD/base-solo/11-iso/StackOS-C3-live-v10.9-RC4.iso` (caminho observado no ambiente atual, não presumir disponibilidade em outros computadores).
- `/live/filesystem.squashfs`: LBA inicial 8407, offset 17.217.536 bytes, tamanho 2.792.288.256 bytes. Inspeção com `unsquashfs -offset` confirmou `usr/lib/firmware/i915/adlp_dmc.bin.zst`, `adlp_dmc_ver2_16.bin.zst`, `adlp_guc_70.bin.zst` e `adlp_guc_70.1.1.bin.zst` dentro do sistema Live.
- Inspeção do `/live/initramfs.cpio.gz` da mesma RC4 encontrou somente `regulatory.db` e `regulatory.db.p7s` sob `usr/lib/firmware`, **sem os firmwares Intel i915**.
- Script `/init` do initramfs inicia `systemd-udevd`, executa `udevadm trigger` e `udevadm settle` antes de montar o SquashFS e executar `switch_root`.
- Configuração examinada em `boot-v10.9/release-root/boot/config-7.2.13-stackos108`: `CONFIG_DRM_I915=y`, `CONFIG_FW_LOADER=y`, `CONFIG_FW_LOADER_COMPRESS_ZSTD=y`, `CONFIG_EXTRA_FIRMWARE=""`. A configuração pertence à árvore de build; ainda não foi comprovada equivalência binária independente com o kernel dentro da ISO RC4.
- `/boot/grub/grub.cfg` da RC4 possui modo normal (`quiet splash loglevel=3`) e diagnóstico (`stackos.debug=1 loglevel=6`); não há `nomodeset` ou parâmetro explícito de desativação do i915.
- **Interpretação:** a indisponibilidade antecipada dos firmwares i915 no initramfs é comprovada e é uma hipótese forte para as falhas de carregamento durante o boot. Ainda **não** foi demonstrado que ela seja a causa única do `GT0 wedged` ou dos problemas Mesa/GNOME. Não declarar GPU-001 corrigido.
- Uma busca por mensagens i915 em arquivos `*.log`/`*.txt` de `boot-v10.9` não encontrou resultados; outra busca por nomes genéricos de relatórios retornou majoritariamente arquivos de código-fonte. **Essas buscas não invalidam o relatório original já documentado aqui.**

**Estado:** auditoria e investigação em andamento, sem alteração ou reconstrução da ISO durante essas verificações.


## 11. Plano de correção incremental — iniciado em 2026-11-01

**Decisão do projeto:** corrigir os defeitos documentados antes de produzir uma nova ISO de teste. Não iniciar build de ISO enquanto houver correções pendentes ou sem validação. Atualizar esta auditoria no GitHub a cada etapa relevante, preservando o histórico e sem substituir evidências anteriores.

### 11.1 Ordem de trabalho

1. **GPU-001 — Intel i915 / firmware / Mesa (em investigação; não corrigido).** Primeiro separar a falha de disponibilidade antecipada do firmware da compatibilidade/integração Mesa. Inspecionar a receita real de geração do initramfs, a configuração e os artefatos do kernel, os pacotes Mesa instalados e a ligação entre DRI driver, GBM, EGL e Gallium. Propor a menor correção rastreável; preservar os artefatos aprovados e não reconstruir componentes sem necessidade demonstrada.
2. **GPU-002 — NVIDIA / nouveau e gráficos híbridos.** Investigar após estabilizar a base i915/Mesa, evitando misturar causas.
3. **AUD-001 — áudio PipeWire/PulseAudio.** Resolver a arquitetura de serviços e sockets antes de retestar dispositivos.
4. **USB-001 — exFAT e mídia removível.** Confirmar suporte no kernel e userspace.
5. **BOOT-001 — snapshot no-op.** Conferir implementação real, integração com backups/recuperação e só então corrigir a unidade.
6. **Demais achados:** BOOT-002/003, FW-001, BT-001, USB-002, NET-001, CPU-001, GNOME-001 a GNOME-005, SYS-001/002 e APP-001 a APP-004. Reclassificar limitações externas e decisões de produto sem mascará-las como bugs da ISO.
7. **QA final:** testes de integração, instalação, FirstBoot, armazenamento, áudio, rede, USB, recuperação e aplicativos. Só depois gerar ISO candidata para QEMU e hardware.

### 11.2 Evidência adicional relevante para GPU-001 / RC4

Na inspeção estática da ISO RC4 em 2026-11-01, foram comprovados os seguintes fatos:
- A imagem `/live/initramfs.cpio.gz` contém `usr/lib/firmware/regulatory.db` e `regulatory.db.p7s`, mas não contém `i915/adlp_dmc*` nem `i915/adlp_guc*`.
- O SquashFS da mesma ISO contém `usr/lib/firmware/i915/adlp_dmc.bin.zst`, `adlp_dmc_ver2_16.bin.zst`, `adlp_guc_70.bin.zst` e `adlp_guc_70.1.1.bin.zst`, entre outras versões.
- O `/init` do initramfs inicia udev e executa `udevadm trigger/settle` antes de montar o SquashFS e fazer `switch_root` para o sistema Live.
- A configuração examinada do kernel `7.2.13-stackos108` informa `CONFIG_DRM_I915=y`, `CONFIG_FW_LOADER=y`, `CONFIG_FW_LOADER_COMPRESS_ZSTD=y` e `CONFIG_EXTRA_FIRMWARE=""`.
- A receita/fonte exata que produziu o initramfs RC4 ainda precisa ser identificada e lida antes de escolher onde corrigir. Não assumir que basta copiar firmware manualmente para um arquivo sem corrigir o processo reprodutível.

**Hipótese técnica a testar:** como i915 está integrado ao kernel e o initramfs não inclui os blobs Intel, o driver pode solicitar firmware antes de o SquashFS estar disponível como raiz. A presença dos blobs no SquashFS não garante que estejam disponíveis no momento inicial da solicitação. Isso é uma hipótese forte e coerente com os sintomas da auditoria original, mas a inspeção estática, sozinha, ainda não prova que explique todos os erros GuC/GT0 ou os avisos Mesa/GNOME.

### 11.3 Estado atual da correção

| Item | Estado | Critério para avançar |
|---|---|---|
| Consolidar inventário de bugs | CONCLUÍDO documentalmente | IDs e evidências mantidos nesta auditoria |
| GPU-001: localizar receita real do initramfs e cadeia de firmware | EM INVESTIGAÇÃO | Ler receita, parâmetros, cópia de firmware e logs de build existentes |
| GPU-001: definir correção mínima | NÃO INICIADO | Causa isolada e mudança proposta revisada |
| GPU-001: aplicar e validar correção | NÃO INICIADO | Build reproduzível e teste de carregamento/firmware com evidência |
| GPU-001: validar Mesa/Iris/EGL/GBM | NÃO INICIADO | Dependências coerentes e teste OpenGL/renderer sem erro |
| Gerar nova ISO | BLOQUEADO | Bugs corrigidos e QA pré-ISO concluído |

**Limite operacional:** esta atualização foi feita no GitHub por leitura/escrita do documento. Nenhum comando foi executado no notebook/PC, nenhum arquivo local foi alterado e nenhum bug foi declarado corrigido. Para executar a próxima inspeção no ambiente de build, o usuário fornecerá a saída dos comandos propostos; as conclusões e decisões serão então registradas aqui.

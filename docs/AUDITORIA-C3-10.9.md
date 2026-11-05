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


### 11.4 Inspeção da receita `build-installed-initramfs.py` — 2026-11-01

Arquivo inspecionado pelo usuário: `boot-v10.9/build-installed-initramfs.py`.

**Fatos comprovados pelo código apresentado:**
- A receita usa `/usr/share/stackos/installed-initramfs-template` como template.
- Copia `/usr/lib/modules/<versão>` para a árvore temporária do initramfs.
- Copia ferramentas de recuperação (`sha256sum`, `rsync`, `findfs`, `blkid`, `mkfs.ext4`, `e2fsck`, `openssl`, `stty`, `tr`) e dependências ELF encontradas via `ldd`.
- Copia o script `/etc/initramfs-tools/scripts/local-bottom/stackos-factory-reset`.
- Empacota a árvore em CPIO newc + gzip e grava `/boot/initrd.img-<versão>`, atualizando o link `/boot/initrd.img`.
- Não há no código apresentado cópia de `/usr/lib/firmware/i915` nem inclusão explícita dos firmwares DMC/GuC.
- O grep apresentado pelo usuário em `boot-v10.9/logs` não retornou linhas para `initramfs`, `firmware/i915` ou `mkinitramfs` nos arquivos `*.log` pesquisados.

**Conclusão limitada:** esta receita gera o initramfs do sistema instalado (`/boot/initrd.img-*`) e não demonstra ser a origem do initramfs Live `/live/initramfs.cpio.gz` da RC4. Não alterar esta receita como correção do problema Live sem evidência de que ela participa da geração da imagem Live. A ausência de cópia de firmware nesta receita pode ser uma questão separada para o initramfs do sistema instalado e deve ser avaliada no escopo próprio.

**Próxima investigação:** localizar, no processo de build já existente, a rotina que constrói `boot-v10.9/initramfs` e produz o arquivo CPIO/GZIP incorporado como `/live/initramfs.cpio.gz`. Inspecionar essa rotina e seus parâmetros antes de editar qualquer coisa. Não criar uma segunda implementação nem reconstruir a ISO nesta etapa.

**Estado GPU-001:** firmware Intel presente no SquashFS e ausente do initramfs Live RC4 continuam comprovados. Causa provável permanece em investigação; nenhuma correção aplicada ou validada.


### 11.5 Identificação do gerador do initramfs Live RC4 — 2026-11-01

A busca somente leitura feita pelo usuário encontrou a receita correta em `boot-v10.9/seal.py`:
- Linha 18: `find . -print0 | cpio --null -o --format=newc | gzip -1 > ../iso-tree/live/initramfs.cpio.gz`, executada com `cwd=O/'initramfs'`.
- Linha 19 contém comentário distinguindo o initramfs Live (`/live/initramfs.cpio.gz`) do initramfs do instalador.
- A mesma busca encontrou apenas referências a `build-installed-initramfs.py` fora de `seal.py`; portanto, a receita instalada anteriormente inspecionada não é o gerador Live.

**Estado confirmado:** `seal.py` é o ponto de empacotamento do diretório `boot-v10.9/initramfs` para a árvore ISO Live. O initramfs RC4 extraído contém `usr/lib/firmware/regulatory.db*`, mas não contém `usr/lib/firmware/i915/*`. O SquashFS RC4 contém os firmwares Intel ADLP DMC e GuC listados na seção anterior.

**Próxima etapa:** inspecionar integralmente `seal.py`, a origem/configuração de `O` e o conteúdo de `boot-v10.9/initramfs/usr/lib/firmware` antes de propor qualquer alteração. Ainda não foi aplicada correção, não foi reconstruído initramfs e não foi criada ISO nova.


## 13. Auditoria adicional em hardware AMD — 2026-11-02

**Origem:** relatório de terminal fornecido pelo usuário, `auditoria-stackos-amd-20261102-113400.txt`, StackOS C3 v10.9, kernel `7.2.13-stackos108`, host `gm-pc`. **Natureza:** evidência de execução real, não teste reproduzido pelo revisor. Nenhuma correção aplicada.

### 13.1 Hardware e inicialização comprovados

- GPU `1002:7480`, ASRock RX 7600 Challenger OC `1849:5313` (Navi 33), driver em uso `amdgpu`; módulo carregado.
- VRAM de 8176 MiB, dispositivos `/dev/dri/card1` e `/dev/dri/renderD128`, DRM `amdgpu 3.64.0` inicializado; SMU inicializado com sucesso.
- Firmware AMD presente em arquivos compactados `/lib/firmware/amdgpu/gc_11_0_3_*.bin.zst` e `dcn_3_2_1_dmcub.bin.zst`; logs indicam carregamento DMUB/VCN.
- Sessão GNOME Wayland; `DISPLAY` vazio e `WAYLAND_DISPLAY=wayland-0`. A ausência de DISPLAY deve ser avaliada no contexto Wayland, não é prova isolada de falha.

### 13.2 Novos achados e classificação

| ID | Evidência | Classificação / ação pendente |
|---|---|---|
| AMD-001 | `glxinfo` e `vulkaninfo` não encontrados | Ferramentas diagnósticas ausentes; não comprova ausência do Mesa nem falha de aceleração |
| AMD-002 | `ldconfig -p` lista `libGLX_mesa.so`, `libEGL_mesa.so`, `libGL.so`, `libEGL.so`, `libgbm.so`, `libdrm_amdgpu.so`; varredura de arquivos DRI encontrou somente `/usr/lib/dri/libdril_dri.so` | Mesa parcialmente presente; `radeonsi_dri.so` e `libvulkan_radeon.so` não localizados pelos padrões consultados. Verificar layout/empacotamento e ICD antes de concluir ausência funcional |
| AMD-003 | `dpkg --print-architecture` = `amd64`; `dpkg --print-foreign-architectures` vazio | `i386` não habilitado nesta sessão; bloqueio provável para bibliotecas 32-bit necessárias a jogos e Wine |
| AMD-004 | `dmesg`: dois `REG_WAIT timeout ... optc32_disable_crtc line:196` | Anomalia de inicialização do controlador de display; investigar repetição, conexão e impacto |
| AMD-005 | `dmesg`: `Failed to setup vendor infoframe on connector HDMI-A-1: -22` | Falha específica de configuração HDMI; impacto ainda não demonstrado |
| AMD-006 | `dpkg-query -W | grep -Ei 'mesa|vulkan|...'` não retornou pacotes, apesar de bibliotecas gráficas existentes | Rastreabilidade/registro de pacotes a investigar; não inferir ausência das bibliotecas |
| AMD-007 | Fontes APT: StackOS C3 GitHub Pages, AMDGPU/ROCm para Ubuntu Noble e Debian Trixie simultaneamente | Fontes externas configuradas; auditar pinning, assinatura, compatibilidade ABI e política de mistura de distribuições. Não afirmar que GitHub Git e APT são a mesma coisa |

**Fontes APT observadas literalmente:** `https://stackoslinux-dev.github.io/repo/c3`, `https://repo.radeon.com/amdgpu/31.60/ubuntu` (noble), `https://repo.radeon.com/rocmradeon/apt/26.16` (noble), `https://repo.radeon.com/graphics/26.16/ubuntu` (noble), `https://deb.debian.org/debian` (trixie). O relatório mostra configuração, **não** prova conectividade, atualização, resolução de dependências nem integridade do conteúdo desses repositórios.

**Observações negativas relevantes:** `systemctl --failed` mostrou zero unidades falhadas; logs de GPU incluem avisos sobre RAS/RAP/SecureDisplay opcionais, insuficientes para declarar defeito.

### 13.3 Próximos critérios de validação

1. Identificar origem dos arquivos Mesa presentes, bibliotecas DRI efetivas, caminhos de ICD Vulkan e dependências ELF, sem instalar nem modificar nada.
2. Testar renderer OpenGL e dispositivos Vulkan quando ferramentas estiverem disponíveis; diferenciar aceleração por hardware de software.
3. Auditar suporte 32-bit e compatibilidade de pacotes para Steam/Proton/Wine antes de habilitar i386.
4. Inspecionar prioridades APT e misturas de repositórios antes de qualquer instalação.
5. Correlacionar `REG_WAIT` e infoframe HDMI com conectores, resolução, sintomas visíveis e novos boots.

**Estado:** novos achados documentados; nenhuma falha declarada corrigida, nenhuma ISO reconstruída.


## 14. Revisão comparativa da candidata no mesmo PC AMD — 2026-11-04

**Origem:** auditoria Live relatada pelo usuário em 04/11, no PC de testes com RX 7600, comparada à seção 13 de 02/11. A sessão atual se identifica como StackOS C3 Live v10.9, kernel 7.2.13-stackos108, GNOME Shell 50.6 / Wayland. **Não presumir que a ISO binária ou seu hash são idênticos aos da coleta anterior.**

### 14.1 Revisão dos achados já existentes — não duplicar nem apagar

| ID anterior | Situação na candidata de 04/11 |
|---|---|
| AMD-001 | `glxinfo` e `vulkaninfo` continuam ausentes; `eglinfo` também não encontrado. Não há teste de renderer. |
| AMD-002 | RX 7600 usa `amdgpu`, mas `radeonsi_dri.so` e `libvulkan_radeon.so` não foram encontrados na varredura; existem bibliotecas GL/EGL/GBM. Mesa/Vulkan acelerados continuam não comprovados. |
| AMD-003 | `dpkg --print-foreign-architectures` vazio: i386 ainda não habilitado. |
| AMD-004 e AMD-005 | Os avisos anteriores REG_WAIT e HDMI infoframe não foram demonstrados como corrigidos; verificar recorrência e impacto em novo teste específico. |
| AMD-006 | Só 17 pacotes StackOS registrados pelo dpkg, apesar de bibliotecas compiladas existentes: integração APT/dpkg continua pendente. |
| AMD-007 | **Mudança observada:** APT da candidata aponta para repositório local StackOS e StackOS C3 no GitHub Pages. Fontes Debian Trixie e AMD Noble observadas no teste anterior não constam da configuração atual. Isso não prova correção definitiva da política de repositórios. |
| AUD-001 | PulseAudio 17.0 fornece saídas em `pactl`; PipeWire 1.6.8/WirePlumber ativos, mas `wpctl` não enumera dispositivos ou saídas. Conflito de arquitetura de áudio permanece provável. |
| FW-001 | Falha `regulatory.db` reaparece no boot; confirmar causa. |
| SYS-003/SYS-004 | `systemctl --failed` sem falhas e `dpkg --audit` vazio nesta sessão: verificações aprovadas apenas localmente. |
| APP-001 | 17 pacotes StackOS instalados; execução funcional dos aplicativos ainda não testada. |

### 14.2 Achados novos ou mais específicos

| ID | Evidência | Estado |
|---|---|---|
| AMD-008 | Não localizado driver Gallium RadeonSI para a RX 7600 na árvore DRI consultada. | PENDENTE CRÍTICO — testar OpenGL acelerado e corrigir cobertura de driver se ausência confirmada. |
| AMD-009 | RADV `libvulkan_radeon.so` e ferramenta `vulkaninfo` não localizados; ICD Vulkan AMD não comprovado. | PENDENTE CRÍTICO — conferir ICD, loader e execução real. |
| AUD-002 | Kernel registra `hdaudioC0D3: Unable to configure, disabling`; `aplay` ausente. | FALHA DE CONFIGURAÇÃO REGISTRADA; impacto funcional não medido. |
| BOOT-004 | Boot medido em 67,831 s, com 28,967 s no loader e 14,691 s em `ldconfig.service`. | OTIMIZAÇÃO / INVESTIGAÇÃO. |
| KERN-001 | Mensagens repetidas `watchdog_print_freq_timeout` no journal. | ANOMALIA REPRODUZIDA; causa não isolada. |
| SYS-009 | Ausentes `uptime`, `free`, `ip`, `aplay`, `glxinfo`, `eglinfo` e `vulkaninfo`. | FERRAMENTAS AUSENTES; decidir pacote-base. |
| MEM-001 | Sem swap ou ZRAM ativos na sessão Live (`SwapTotal: 0 kB`). | POLÍTICA/TESTE PENDENTE. |
| SEC-003 | `sudo -n true` bem-sucedido no Live. | POLÍTICA LIVE CONFIRMADA; não transportar automaticamente para instalado. |

### 14.3 Teste destrutivo anterior, separado da candidata

Na instalação de teste anterior, após desativação deliberada do hook APT, a transação tentou instalar `libc6 2.41` Debian sobre glibc nativa 2.42. Após iniciar o desempacotamento, `dpkg-deb`/tar apresentou SIGSEGV para múltiplos .deb e a operação falhou. **DEB-011: falha grave de compatibilidade/integração em transação de pacotes Debian, confirmada naquele ambiente.** Não atribuir a falha à candidata atual: nesta, glibc 2.42 é relatada e `dpkg --audit` não acusou erros.

### 14.4 Critério de remoção do registro ativo

Nenhum ID antigo será apagado sem evidência de correção reproduzível; após reteste, mover o estado para **CORRIGIDO/VALIDADO** preservando o histórico. Achados específicos do notebook Acer (i915/NVIDIA/exFAT) não podem ser encerrados por testes no PC AMD. Permanecem não validados: instalação em disco, FirstBoot, reset/backups, áudio real, Bluetooth, OpenGL/Vulkan, jogos e compatibilidade geral de aplicativos Debian.

**Conclusão:** sem correções confirmadas nesta atualização documental; foram acrescentadas evidências novas sem remover o histórico anterior.


## 15. Correção incremental de proteção APT e diagnóstico — 2026-11-04

**Escopo:** correções nos fontes do SSD e reteste descartável em QEMU. A ISO Dock5 existente não foi alterada, não foi gerada outra ISO e nenhuma release foi aprovada.

### 15.1 DEB-004 / DEB-009 / DEB-011 — proteção antes do desempacotamento

O hook anterior só comparava arquivos e proprietários. Foi criada a fonte `boot-v10.9/protect-c3-files.py` e integrada às receitas `build-lean-iso.py` e `seal.py`, usando o caminho do hook APT já existente. Store, Package Installer e Updater usam APT; seus fluxos gráficos completos ainda precisam de reteste próprio.

A proteção exige correspondência exata entre nome, versão, arquitetura e SHA-256 do arquivo e um registro APT confiável com Origin StackOS/Codename c3 para alterações em pacotes centrais ou com nome StackOS. Confiança e hash são conferidos no mesmo registro de índice. Também rejeita substituições de arquivos da base por pacotes externos, caminhos inseguros, tipos especiais, colisões por hardlink, links de payload usados como diretório, entradas duplicadas e erros de descompressão.

**Reteste executado:** 19 testes passaram no host e os mesmos 19 no Python/dpkg-deb nativos da C3 em QEMU. Dois registros de pacotes reais do catálogo nativo foram aceitos e hashes adulterados rejeitados. Uma reinstalação real de stackos-archive-keyring passou pelo hook novo.

Um aplicativo sintético sem dependências externas foi criado com dpkg-deb dentro da C3, instalado pelo APT, executado, atualizado para versão 2, executado novamente e removido. Todos retornaram 0. Um pacote descartável chamado libc6 foi bloqueado pelo hook com APT=100 antes de dpkg desempacotar. O SHA-256 da libc permaneceu igual; dpkg --audit não apresentou pendências e apt-get check retornou 0.

**Limites:** esse teste não instalou libc Debian real nem comprova compatibilidade geral com aplicativos Debian. Metadados de provedores nativos e análise ABI permanecem pendentes. O hook não é sandbox de scripts de mantenedor, não cobre dpkg -i direto e não impede que root desative a proteção deliberadamente. Portanto, DEB-011 não está encerrado como requisito geral.

### 15.2 SYS-001 / SYS-009 — ferramentas básicas já disponíveis

O BusyBox incluído na candidata contém ps, free, uptime e ip. A fonte configure-c3-diagnostics.py disponibiliza esses quatro comandos por links, sem substituir implementações completas existentes; foi integrada às duas receitas. Na sessão descartável, os quatro comandos foram executados com retorno 0. São implementações BusyBox, com opções mais limitadas que procps/iproute2. glxinfo, eglinfo, vulkaninfo, ferramentas ALSA e demais diagnósticos não foram declarados resolvidos.

### 15.3 AMD-008 / AMD-009 — evidência adicional, sem correção declarada

As bibliotecas da release-root libgallium-24.3.1.so e libgallium-24.3.4.so contêm a mensagem literal “radeonsi: driver missing”. A fonte Mesa 24.3.4 em target-helpers/drm_helper.h associa essa mensagem ao descriptor stub usado quando o driver não é compilado. Isso reforça que criar apenas um alias radeonsi_dri.so não é uma correção suficiente.

A árvore mesa-24.3.4-amd-intel-ply tem configuração Gallium radeonsi/iris/llvmpipe, Vulkan amd/intel e LLVM habilitado, mas não foi encontrada sua biblioteca Gallium final no destino de build examinado. GLX está desabilitado nessa configuração. Não foi iniciada recompilação, nem validada aceleração física; RadeonSI, RADV e loader Vulkan continuam bloqueadores.

### 15.4 Rastreabilidade e estado de entrega

- ISO usada no teste: Dock5, SHA-256 `9ba30927c12aa6f1ecade54e3c48b7e7256714faf2965c2c41d127694dbf4c58`.
- QEMU TCG, boot diagnóstico com kernel/initramfs extraídos dessa ISO; nenhuma unidade física e rede desabilitada. Não equivale a novo teste do bootloader normal nem de instalação.
- Evidências no SSD: `C3-BUILD/base-solo/C3-BUILD/codex-2026-11-04/correcao-p0-apt/`: relatório original, snapshot desta auditoria anterior à alteração, backups dos fontes anteriores, testes, log serial e resultado.json.
- SHA-256 da fonte do hook: `d57bb5052f5e8a8c246bfda2050c0c0302b16e70b960eeb6184fb56e913727b8`.
- As mudanças testadas existem nos fontes e na RAM da VM; **não estão incorporadas à ISO Dock5 distribuída**.
- Permanecem pendentes Mesa/Vulkan, i386/jogos, kernel exFAT/PSI, integração de provedores/ABI, fluxos gráficos, instalação/FirstBoot/recuperação e testes físicos de GPU, áudio, USB e rede. Nenhum achado histórico foi apagado.


## 16. Continuidade e limite de armazenamento — 2026-11-05

O usuário autorizou corrigir as pendências e compilar os componentes faltantes, mas escolheu expressamente **manter o limite total de 40.000.000.000 bytes**, sem liberar temporários acima dele nesta etapa. O uso observado é aproximadamente 76,66 GB. Nenhuma compilação ou nova ISO foi iniciada.

Inventário de espaço alocado (du; diretórios inacessíveis foram sinalizados, portanto não é uma auditoria completa de todos os arquivos): sources 28.545.916.928 bytes; lfs-root 16.907.653.120; boot-v10.9 8.661.639.168; builds-organizados 2.087.231.488; ISOs em 11-iso 14.525.894.656. O diretório Firefox de fontes ocupa 4,62 GB principalmente de fontes/testes/third_party; não foi tratado como cache descartável.

A pasta C3-BUILD tem montagem separada rw. A montagem ro do diretório superior observada no sandbox **não comprova que o SSD do PC esteja com erro ou bloqueado para escrita**. As árvores antigas sources, lfs-root, builds-organizados e release-root não estão graváveis pelo usuário do processo nesta sessão. Foi solicitada ao usuário uma ACL restrita a sources e builds-organizados, preservando propriedade e o SDK. Nenhum arquivo dessas árvores foi apagado, compactado ou alterado nesta etapa.

Foi preparado no harness QEMU o modo opcional --native-sdk, que exporta o SDK C3 por virtio-9p somente para leitura. A configuração do kernel existente inclui CONFIG_NET_9P_VIRTIO=y e CONFIG_9P_FS=y. Isso é preparação de uma rota para executar o compilador nativo dentro da C3 sem root no host; **o modo e o compilador ainda não foram validados em execução**. O bloqueio de orçamento foi testado: retorna 1 antes de iniciar QEMU ou extrair kernel/initramfs quando o limite seria excedido.

Evidências locais: codex-2026-11-04/continuidade-2026-11-05/estado-bloqueios.json e teste-limite.json. Continuam abertos os bloqueadores da seção 15. Nenhuma correção adicional de Mesa/Vulkan/kernel/jogos foi declarada concluída.


## 17. Compilação C3, provedores reais e compatibilidade DEB — 2026-11-05

**Autorização atualizada:** o usuário liberou ultrapassar temporariamente os 40 GB para concluir correções, com limpeza posterior, e reiterou: **não gerar outra ISO enquanto os defeitos relatados não estiverem corrigidos e validados**. As ACLs das duas pastas foram efetivamente aplicadas pelo usuário e o executor voltou a funcionar. Nenhuma ISO nova foi gerada.

### 17.1 Ambiente e componentes compilados

Foi iniciado QEMU com a Dock5 de hash já registrado, sem discos físicos e sem rede, exportando SDK/fontes originais somente para leitura e uma área nova de trabalho no SSD. O GCC/G++ nativo 15.2.0, glibc 2.42 e LLVM 19.1.7 foram executados dentro da C3; os módulos Python de build foram conferidos.

Vulkan Headers/Loader/Tools 1.3.296 e a dependência volk indicada pelo known_good foram obtidos dos projetos oficiais com commits/hashes registrados. **Vulkan Loader e vulkaninfo compilaram na C3.** glxinfo e eglinfo também compilaram a partir de Mesa-demos 9.0.0. Estão em staging; enumeração Vulkan/renderização com os novos ICDs ainda aguarda o Mesa.

O build Mesa 24.3.4 expôs defeitos concretos no encadeamento anterior: LLVM AMDGPU sem RTTI, PLY ausente e dois LLVM embutidos carregados pelo compilador Intel CLC. As bibliotecas compartilhadas Clang/LLVM-SPIRV antigas incorporam LLVM; o patch C3 passa a usar seus componentes estáticos com um runtime LLVM único. Os componentes Clang estáticos precisam de RTTI. Por isso foi recompilado **somente o runtime LLVM 19.1.7 com X86/AMDGPU e RTTI**, sem reconstruir GNOME ou o SDK inteiro. A compilação LLVM terminou com retorno 0 e exporta os typeinfos antes ausentes.

Para acelerar o trabalho pesado, foram preparados adaptadores do SDK que executam o carregador, Clang 19.1.7/GCC 15.2.0 e binutils C3 com sysroot C3; CMake/Ninja do host apenas coordenam. Os testes C++ verificaram glibc 2.42, todos os caminhos de headers/LOAD e bibliotecas efetivamente carregadas no SDK, sem bibliotecas/headers do host no alvo. O produto libLLVM não tem RPATH temporário; o llvm-config de staging tem interpretador normal /lib64/ld-linux-x86-64.so.2. Os artefatos serão retestados dentro da C3.

A comparação confirmou LLVM 19.1.7 e ABI-breaking-checks=0 nos dois conjuntos. RTTI é agora coerente no runtime reconstruído e na configuração Mesa. **O teste final do CLC e o build completo do Mesa permanecem em andamento; AMD-008/009 não estão encerrados.**

### 17.2 DEB-001 a DEB-011 — provedores nativos com payload real

A fonte package-native-core.py gera candidatos libc6/libc-bin 2.42+stackos1 e libgcc-s1/libstdc++6 15.2.0+stackos1 a partir dos arquivos reais da C3, com licenças, checksums e tamanhos. Não usa pacotes vazios Provides e não importa bibliotecas Debian/Ubuntu. Não habilita nem declara multiarch: a disposição atual foi inventariada somente para amd64.

Na VM descartável foi criado um repositório assinado com **chave de laboratório efêmera, não a chave oficial**, separado da distribuição. O hook de proteção novo verificou os arquivos pelo índice autenticado; os quatro provedores foram instalados pelo APT. **284 arquivos nativos preexistentes permaneceram com SHA-256 idêntico.** dpkg --audit, apt-get check e dpkg -V dos quatro pacotes passaram. Os candidatos ainda precisam de assinatura/publicação oficiais e integração na receita da candidata; não estão na Dock5.

### 17.3 Teste real de binários Debian

As assinaturas InRelease de bookworm/trixie, hashes dos índices e os dois .deb GNU hello foram verificados; as chaves públicas foram conferidas com os fingerprints publicados pelo Debian. Nenhum repositório Debian foi adicionado à C3 e nenhuma biblioteca central Debian foi instalada.

- hello 2.10-3: instalação pelo helper real do StackOS Package Installer, com checksum esperado; execução aprovada.
- hello 2.10-5: atualização pelo APT e execução aprovadas.
- Remoção, apt-get check, dpkg --audit e integridade dos provedores: aprovados.
- Requisitos GLIBC dos ELF foram extraídos com LC_ALL=C e conferidos contra 110 versões exportadas pela base; o parser exige resultado não vazio. Foram encontrados requisitos até GLIBC_2.34 e GLIBC_2.38, todos presentes.
- A rejeição de checksum adulterado pelo helper passou antes da instalação.
- Os mesmos 284 arquivos da base permaneceram inalterados.

Isso comprova compatibilidade **desses dois binários**, não de todos os aplicativos Debian. A interface gráfica do Package Installer/Store ainda precisa de reteste próprio; o helper e o APT foram efetivamente exercitados.

### 17.4 Scripts de mantenedor e runtime C++

Um programa de teste C++ nativo com exceções, thread/future, vector e filesystem foi compilado com GCC C3, em executável portátil sem RPATH temporário. Dois pacotes controlados foram instalados/atualizados pelo helper real e removidos. Os oito eventos esperados preinst/postinst/prerm/postrm ocorreram, o programa retornou o resultado 42 nas duas versões e seus arquivos/marcadores foram removidos. APT/dpkg e os 284 arquivos nativos continuaram íntegros.

Isso valida esse fluxo controlado; não é sandbox de scripts arbitrários nem aprovação de todo pacote externo.

### 17.5 Kernel e limites restantes

Foi preparada reconstrução incremental do kernel 7.2.13 com GCC/binutils C3 para exFAT e PSI, em diretório novo, sem editar a árvore original. A comparação olddefconfig não desativou nenhuma opção preexistente y/m. O kernel está compilando; boot, montagem exFAT e métricas PSI ainda não foram retestados. Não declarar USB-001/SYS-007 corrigidos antes disso.

Continuam abertos testes físicos AMD/Intel/NVIDIA, áudio/USB/Bluetooth/rede, i386/jogos, fluxos gráficos, instalação/FirstBoot/recuperação e demais hipóteses do relatório. As correções e candidatos desta seção **não foram incorporados a uma ISO**.

Evidências no SSD: codex-2026-11-04/compilacao-nativa-2026-11-05/, incluindo manifests de fontes, logs de build, native-providers-integrity.json, hello-compatibility-result.json, maintainer-lifecycle-result.json, probes do SDK e comparação de configuração do kernel. Os resultados da VM estão sob work/.


## 18. Mesa, teclado GNOME e kernel — retestes de 2026-11-05

**Nenhuma nova ISO foi gerada; Dock5 permanece inalterada.** Fontes/SDK originais preservados. Os resultados abaixo são dos artefatos em staging e de VM descartável, não aprovação de release nem de hardware físico.

### 18.1 Mesa 24.3.4 / LLVM 19.1.7

O runtime LLVM com RTTI passou no teste nativo Intel CLC, eliminando os erros de LLVM duplicado/typeinfo observados no build anterior. O Mesa completo compilou e instalou com GCC/G++ C3, sysroot C3 e dependências C3. Gallium inclui RadeonSI, Iris, Nouveau e software; Vulkan inclui RADV, Intel e Lavapipe; GLX/EGL/GBM habilitados.

Foi corrigido um defeito de compilação adicional com Wayland 1.24: loader_wayland_helper.c usa timespec_sub_saturate mesmo quando a API de timeout do Wayland está disponível, mas não incluía util/timespec.h nesse caso. Patch mínimo registrado, sem editar a fonte original.

Em QEMU/C3, os artefatos novos passaram em EGL 1.5, OpenGL 4.5, OpenGL ES 3.2 e Vulkan 1.3.296 com llvmpipe/Lavapipe, Mesa 24.3.4 e LLVM 19.1.7. **Isso é renderização por software**, não prova aceleração RX 7600/Intel/NVIDIA. A varredura genérica eglinfo -B de todas as plataformas apresentou SIGSEGV ao incluir dispositivos indisponíveis; o teste explícito surfaceless passou. A falha genérica permanece sob investigação, sem ser ocultada pelo teste limitado.

Foram verificados 14 payloads ELF de Mesa/LLVM/teclado: sem RPATH temporário do diretório de build. Os caminhos produtivos dos manifests ICD não foram alterados; o teste usou JSON separado apontando ao staging.

### 18.2 GNOME-004 — CORRIGIDO/VALIDADO no componente, integração pendente

A causa foi confirmada em gnome-settings-daemon 50.1: g_settings_get_user_value pode retornar NULL, mas o gerenciador de teclado chamava g_variant_unref incondicionalmente após buscar a configuração XKB. Patch g_clear_pointer(&options, g_variant_unref), compilando somente o alvo de teclado e dependência comum necessária.

Reteste comparativo na C3, com D-Bus privado, configurações novas e G_DEBUG=fatal-criticals: binário original terminou com 133 e a assertion registrada; o corrigido permaneceu ativo até timeout 124, sem a assertion. Aviso de SessionManager ausente é esperado nesse barramento privado. Isso não substitui teste da sessão gráfica completa. Patch e binário portátil estão em staging; não na Dock5.

### 18.3 USB-001 / SYS-007 — kernel e reteste descartável

Kernel 7.2.13-stackos109-fix1 compilado com GCC/binutils C3. EXFAT_FS=y e PSI=y; comparação do baseline não retirou opções y/m existentes. Módulos instalados/strip com ferramentas C3, depmod executado na VM; initramfs diagnóstico empacotado com BusyBox C3 e proprietário 0:0 conferido.

Boot diagnóstico em QEMU UEFI passou usando kernel/initramfs novos e o SquashFS antigo somente como raiz de teste. uname confirmou fix1, /proc/pressure/memory apresentou métricas e exfat constou em /proc/filesystems. Em arquivo descartável de 64 MiB: mkfs.exfat, montagem, escrita, desmontagem, remontagem somente leitura, leitura do conteúdo e fsck.exfat -n passaram. O arquivo foi removido automaticamente. **Valida o suporte do kernel; o pendrive/controlador do Acer ainda requer reteste físico.**

MEM-001 continua em correção: kernel original não habilita ZRAM; foi iniciada uma variante incremental fix2 com ZRAM/LZ4. Não declarar swap ativo antes de testar o serviço e o kernel correspondente.

### 18.4 Evidências e bloqueadores

Área: codex-2026-11-04/compilacao-nativa-2026-11-05/. Evidências: mesa-host-result.json, mesa-runtime-result.json, new-components-elf-manifest.json, keyboard-runtime-result.json, kernel-initrd-result.json e logs de runtime sob work/. Nenhum erro histórico foi apagado.

Permanecem testes físicos de GPU/áudio/Bluetooth/USB/rede/energia, i386/jogos, interfaces gráficas, instalação/FirstBoot/recuperação, empacotamento/assinatura e integração dos candidatos. Não há declaração de que todos os erros estejam corrigidos.


## 19. Kernel final, ZRAM e integração Wayland — 2026-11-05

Kernel 7.2.13-stackos109-fix2 com ZRAM modular, LZ4, exFAT e PSI compilou com a toolchain C3. Nenhuma opção baseline y/m foi retirada. Boot, montagem exFAT e PSI passaram novamente; serviço ZRAM passou em start/stop e em ativação automática no boot integrado. Política: metade de MemTotal, máximo 4 GiB, prioridade 100, sem backing em disco. Na VM de 6 GiB, capacidade calculada 3.105.501.184 bytes.

ALSA-utils 1.2.14 foi obtido do upstream, compilando aplay/arecord com GCC/libasound C3. Reprodução/captura de 48 kHz estéreo passaram no HDA virtual com backend nulo: valida o caminho virtual, não som físico. O comando lsinitramfs foi acrescentado às receitas de diagnóstico e listou o initramfs C3 real, sem extração.

O SIGSEGV da enumeração EGL forçada foi isolado por stack trace em drisw_init_screen: LIBGL_ALWAYS_SOFTWARE chegava à plataforma de dispositivo físico com loader incompatível. Corrigida a recusa antecipada dessa combinação em platform_device.c. Reteste completo terminou com os erros esperados de plataformas indisponíveis, sem SIGSEGV; surfaceless e Vulkan continuaram aprovados.

Foi criado somente um initramfs de diagnóstico que aplica em RAM kernel/módulos, Mesa/LLVM, Vulkan, teclado, ZRAM e ferramentas novos sobre a raiz da Dock5. Primeiro ensaio expôs comportamento de BusyBox cp -a ao substituir aliases existentes; a sobreposição foi corrigida para cp -af, testada e reiniciada. GNOME chegou ao desktop, carregou Mesa novo, EGL Wayland executado pelo usuário Live confirmou OpenGL 4.5/GLES3.2 por software; Vulkan passou em caminhos produtivos /usr. Nenhuma unidade de sistema falhada foi listada. Isso não é teste do bootloader normal de uma ISO reconstruída nem aprovação física.

**Novo bloqueador confirmado de compatibilidade X11/jogos:** Xwayland está ausente, Mutter foi compilado com xwayland=false/HAVE_XWAYLAND indefinido e GNOME Shell também com HAVE_XWAYLAND indefinido. glxinfo não tem servidor DISPLAY; não é correto atribuir isso a falha do Mesa novo. Xwayland 24.1.14 e dependências libfontenc/libXfont2/libxkbfile/xkbcomp foram obtidos dos diretórios oficiais e compilados com C3. É necessária reconstrução específica de Mutter/Shell para habilitar essa função; em andamento, sem declarar X11 resolvido.

A receita prepare-installer.py aplicava migrações antigas por s.index em código já migrado e referenciava desktop FirstBoot removido na preparação anterior. Foi substituída por preparação repetível em diretório separado, preservando a fonte existente; atualiza o gerador nativo de initramfs, templates, metadados/checksums e remove ttyS0 forçado das entradas normais instaladas. Dois preparos deram payload idêntico. Não comprova instalação/FirstBoot/reset; esses testes continuam pendentes.

Fontes/patches/receitas e resultados pequenos foram salvos no repositório privado, commit 1669f91a48c01e3241f440608464006d77368a88, sob CORRECOES/2026-11-05/. Binários e árvores grandes permanecem no SSD. O snapshot descreve X11 em correção; não contém chaves nem binaries de release.

**Nenhuma ISO nova foi gerada e nenhuma release oficial foi aprovada.** Permanecem integração/assinatura produtiva, X11, i386/jogos, instalação/FirstBoot/recuperação, fluxos gráficos e testes físicos já exigidos no relatório.


## 20. Continuidade: X11, provedores desktop e Calculator — 2026-11-05

Retomada autorizada após relatório de parada. Preservados SDK/fontes/chaves/ISOs; nenhuma nova ISO gerada nesta atualização. O usuário pediu candidata para teste físico posterior, sem tratar renderização virtual como prova de hardware.

Xwayland 24.1.14, Mutter 50.6 e GNOME Shell 50.6 com X11 foram compilados nativamente; o caminho DRI final é /usr/lib/dri. Corrigido initramfs diagnóstico desatualizado: boot frio com kernel fix2 passou em GNOME, GLX, EGL Wayland e janela glxgears. Vulkan vkcube passou em Wayland e XCB, 60 frames por backend. Renderer llvmpipe/Lavapipe/CPU, não GPU física. O antigo integrated-x11-initramfs antecede a correção e não deve ser reutilizado como aprovado.

Core4+Desktop13 foram instalados por APT em laboratório assinado separado: dpkg --audit, apt-get check e dpkg -V aprovados, SHA256 de 307 arquivos nativos preexistentes preservado. GNOME Calculator Debian Bookworm 1:43.0.1-2 instalou pelo helper real, abriu janela e calculou 6*7=42; reinstalação e remoção aprovadas. Trixie 1:48.1-2+b1 recusada por GTK>=4.17; base4.16.7 preservada. Não equivale a aprovação geral de .deb nem teste completo das interfaces StackOS.

O teste revelou libxml2 nativa2.13.5 sem versões de símbolos LIBXML2 requeridas pelo binário Debian. Recompilada a mesma versão com version-script upstream e THREAD_ALLOC, sem retirar funcionalidades ou as 1587 exportações anteriores. Atualização nativa 2.13.5+stackos2 via APT laboratório aprovada: único arquivo deliberadamente substituído usr/lib/libxml2.so.2.13.5; outros306 preexistentes com SHA igual. Teste conjunto .so.2/.so.16 leu/liberou100 documentos por ABI; Calculator repetida sem aviso de versionamento. Não constitui prova para todos os aplicativos ou de inexistência universal de conflitos ABI. Avisos GTK Compose>16bit e schemas antigos permanecem registrados.

Evidências e diário detalhado: repositório privado StackOS-C3-Privado, DIARIO/2026-11-05.md e CORRECOES/2026-11-05/. SSD: /run/media/not/STACKOS_WORK/C3-BUILD/base-solo/C3-BUILD/codex-2026-11-04/compilacao-nativa-2026-11-05/, resultados sob work/. Chaves efêmeras de laboratório não são oficiais e não foram publicadas como chaves de release.

Permanecem integração da raiz candidata, instalação/FirstBoot/recuperação, fluxos GUI completos, testes físicos GPU/áudio/rede/USB/BT, i386/jogos e demais registros não encerrados. Nenhum achado histórico foi apagado.

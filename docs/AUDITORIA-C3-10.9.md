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

# Continuidade obrigatória entre chats — StackOS Genesis C3

> **Instrução operacional para qualquer ChatGPT, agente ou sessão que trabalhe neste repositório. Leia este documento antes de analisar, diagnosticar, sugerir comandos ou continuar uma tarefa.**

## Regra principal

Não comece do zero. Antes de responder sobre o StackOS, reconstrua o estado real do trabalho a partir das fontes disponíveis. O fato de uma conversa ser nova não autoriza ignorar o histórico anterior.

## Leitura obrigatória antes de qualquer investigação

1. Leia este documento por inteiro.
2. Leia o documento de auditoria vigente: [AUDITORIA-C3-10.9.md](AUDITORIA-C3-10.9.md), incluindo as seções relevantes ao problema atual.
3. Consulte os arquivos de continuidade, relatórios, evidências, decisões e histórico já existentes no repositório. Pesquise pelo nome do componente, erro, script, versão e caminho antes de propor nova coleta.
4. Consulte o histórico disponível das conversas anteriores e os arquivos anexados/gerados nelas. Use a busca de arquivos da conversa/biblioteca para localizar relatórios e saídas de terminal anteriores; abra e leia os resultados relevantes. Não afirme que um arquivo não existe sem pesquisar.
5. Examine as saídas de terminal que o usuário já forneceu, inclusive em mensagens anteriores e anexos de texto. Uma saída de terminal é evidência técnica e deve ser tratada como parte do histórico do projeto.
6. Compare o que foi encontrado com o estado atual do GitHub e com os caminhos/arquivos atuais informados pelo usuário. Registre divergências, datas, versões e proveniência. Não suponha que o Git contenha todos os logs locais.

## Proibições

- Não peça ao usuário para repetir comandos, logs, relatórios ou anexos antes de procurar no histórico de conversas, arquivos anexados/biblioteca e repositório.
- Não repita uma auditoria ou comando que já produziu evidência suficiente. Só solicite nova coleta quando houver uma lacuna concreta, mudança posterior no sistema ou necessidade de confirmar o estado atual.
- Não trate uma busca parcial, um trecho de arquivo ou uma saída truncada como leitura integral.
- Não declare que um relatório, arquivo, ISO ou log não existe apenas porque não apareceu no diretório pesquisado. Verifique os caminhos alternativos e o histórico já conhecido.
- Não invente resultados, não transforme hipótese em fato e não atribua ao usuário ações que não estejam comprovadas.
- Não altere arquivos, não execute comandos no computador do usuário e não publique/promova uma ISO sem autorização explícita. O papel padrão é consultoria e revisão técnica.
- Não crie outro agente, aplicativo ou mecanismo de memória para resolver continuidade sem pedido explícito.

## Método de trabalho obrigatório

Antes de recomendar qualquer comando, apresente internamente (e, quando útil, ao usuário) esta síntese:

- **Já verificado:** fatos apoiados por saídas, arquivos ou commits concretos.
- **Já tentado:** comandos, testes e investigações anteriores e seus resultados.
- **Resolvido:** problemas cuja correção foi comprovada; não reabrir sem evidência nova.
- **Pendente:** questões ainda sem resposta.
- **Contradições:** diferença entre relatórios, logs, Git e estado atual.
- **Próxima verificação mínima:** apenas a coleta necessária para fechar uma lacuna identificada.

Ao citar uma evidência, informe o arquivo/caminho, data ou contexto e o resultado relevante. Preserve o texto original das saídas quando necessário. Se não houver acesso ao histórico ou a algum arquivo, diga exatamente o que não pôde consultar; não finja que leu.

## Continuidade das auditorias e correções

Mantenha a auditoria como registro cumulativo: novos achados devem ser acrescentados sem apagar evidências anteriores. Para cada achado, registre identificação, gravidade/prioridade, evidência reproduzível, impacto confirmado (separado do impacto provável), causa-raiz (ou “a investigar”), correção proposta, teste de aceitação e estado. Não marque como corrigido apenas porque um comando foi executado; exija validação posterior.

Não crie ISO de teste enquanto houver correções ainda em andamento ou achados bloqueadores não tratados. Quando o usuário decidir gerar uma ISO, confira primeiro quais alterações foram aplicadas, quais testes passaram e quais pendências foram aceitas.

## Contexto técnico já confirmado — RC4 / firmware Intel

As evidências apresentadas em 1 de novembro de 2026 estabeleceram:

- A ISO examinada foi `StackOS-C3-live-v10.9-RC4.iso`, em `/mnt/STACKOS_WORK/C3-BUILD/base-solo/11-iso/`.
- O initramfs Live foi extraído de `/live/initramfs.cpio.gz`; nele, `usr/lib/firmware` continha somente `regulatory.db` e `regulatory.db.p7s`, sem firmware Intel i915.
- O SquashFS da mesma ISO continha firmware Intel em `usr/lib/firmware/i915/`, incluindo `adlp_dmc_ver2_16.bin.zst` e `adlp_guc_70.bin.zst`. Portanto, a ausência no initramfs não prova ausência no sistema Live completo.
- O kernel `7.2.13-stackos108` tinha `CONFIG_FW_LOADER=y`, `CONFIG_FW_LOADER_COMPRESS=y`, suporte XZ/ZSTD e `CONFIG_DRM_I915=y`.
- O GRUB da RC4 carrega `/live/vmlinuz` e `/live/initramfs.cpio.gz`.
- A receita `boot-v10.9/seal.py` copia os módulos do kernel para `boot-v10.9/initramfs/usr/lib/modules` e empacota esse diretório em `iso-tree/live/initramfs.cpio.gz`. Ela não copia firmware do `release-root` para o initramfs.
- A receita `clean-old-kernel.py` limpa gerações antigas de módulos no sistema-base e nos dois initramfs/template. `prepare-tools-languages.py` prepara ferramentas, template de initramfs instalado e locales. `kernel-userns.sh` recompila/instala o kernel e módulos. Esses scripts já foram lidos nas saídas de terminal de 1/11/2026; não solicitar sua leitura novamente sem motivo concreto.
- O ponto ainda em aberto é determinar a política correta de firmware no initramfs Live e a origem/etapa de staging apropriada. Não presumir que copiar todo o firmware para o initramfs seja necessário: primeiro avaliar o fluxo real de descoberta/carregamento do firmware depois do mount do SquashFS e o comportamento observado no hardware.

Use esses fatos como ponto de partida, mas confirme se commits ou relatórios posteriores alteraram o estado.

## Regra de encerramento de cada sessão

Ao terminar uma sessão técnica, atualize a documentação de continuidade/auditoria no repositório com:
- data e versão;
- arquivos e commits consultados/alterados;
- comandos e testes efetivamente executados pelo usuário;
- resultados observados, sem extrapolação;
- decisões tomadas;
- pendências e próximo passo mínimo.

Não registre como executado algo que foi apenas sugerido. Não deixe a próxima sessão depender da memória implícita deste chat.

## Confirmação exigida

Antes de qualquer nova investigação, a sessão deve declarar que consultou esta instrução, a auditoria vigente e o histórico/arquivos relevantes encontrados. Se não conseguiu consultar algum deles, deve declarar a limitação e trabalhar somente com evidências efetivamente disponíveis.

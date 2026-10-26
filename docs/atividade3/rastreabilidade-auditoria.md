# Da elicitação aos requisitos — Épico "Auditoria e transparência da votação"

> As descobertas D-AUD-xx estão em `benchmarking-auditoria.md`, seção 7.

## 1. Rastreabilidade: descoberta → análise → requisito

| Descoberta da elicitação | Análise / interpretação | Requisito relacionado |
|---|---|---|
| **D-AUD-01** — Helios, Belenios e TSE mantêm uma referência de integridade fora do sistema (quadro assinado, monitoramento por auditor, boletim de urna impresso). No nosso log, uma reescrita completa da cadeia passa na verificação (experimento, seção 6). | O hash encadeado só prova consistência interna. Sem um valor guardado por terceiros no encerramento, a comissão não tem como contestar um log refeito por quem opera o sistema. | **RF** — Âncora de encerramento · História **[#27](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/27)**<br>**RNF-AUD-03** (integridade) |
| **D-AUD-02** — No Helios e no Belenios, o rastreador identifica a cédula *cifrada*. Nosso protocolo leva a um registro com a opção em claro (experimento, seção 6). | O comprovante atual permite ao eleitor *provar* em quem votou, o que viabiliza compra de voto e coação. Ele deve provar a **inclusão**, não o **conteúdo**. | **RF** — Comprovante que não revela a opção · História **[#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28)**<br>**RNF-AUD-01** (privacidade) |
| **D-AUD-03** — O RDV do TSE grava cada voto em posição aleatória para impedir ligar a ordem de chegada ao voto. Nosso log grava os votos em ordem, com horário em microssegundos. | Quem observa a ordem dos votantes (um mesário no CA, por exemplo) desanonimiza o voto. Retirar o `eleitor_id` não basta: a ordem e o horário também identificam. | **RF** — Comprovante que não revela a opção · História **[#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28)** (cédulas embaralhadas no encerramento)<br>**RNF-AUD-02** (ordem não derivável) |
| **D-AUD-11** — O Helios 2.0 removeu o jargão técnico da verificação. O Belenios separa as instruções por papel. Exibimos um hash de 64 caracteres sem orientação. | Um comprovante que o eleitor não entende não é usado, e a verificação individual deixa de acontecer. | **RNF-AUD-05** (usabilidade) · critério de aceitação em **[#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28)** |
| **D-AUD-05** — Belenios, TSE e Câmara permitem recontar a partir dos dados publicados. No nosso sistema, o resultado chega pronto ao log e nada o confere. | Não há garantia de que o resultado proclamado corresponda aos votos auditados. A integridade do log, sozinha, não protege o resultado. | **RF** — Recontagem a partir do log · História **[#29](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/29)** |
| **D-AUD-09** — UCLouvain: com cerca de 4.000 votantes, o 1º turno foi decidido por 2 votos. | Margens pequenas são plausíveis em eleições de CA. A verificação e a recontagem precisam ser rápidas e confiáveis para logs desse porte. | **RNF-AUD-04** (10.000 votos em ≤ 2 s) · Histórias **[#27](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/27)**, **[#29](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/29)** |
| **D-AUD-12** — A verificação depende de que "pelo menos uma pessoa honesta" a faça (instruções do Belenios), e as referências separam votante e auditor. | São dois atores com necessidades diferentes: o eleitor quer conferir o próprio voto, e o fiscal ou a comissão quer conferir tudo. | Atores das histórias: comissão ([#27](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/27)), eleitor ([#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28)), fiscal ([#29](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/29)) |
| **D-AUD-04, 06, 07, 08, 10** | Ver decisões 3 e 4 na seção 3. | Fora do escopo deste épico |

Todas as histórias e RNFs pertencem ao **Épico [#26](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/26) — Auditoria e transparência da votação**.

## 2. Requisitos não funcionais identificados

| ID | Categoria | Requisito (verificável) | Origem | Impacta |
|---|---|---|---|---|
| RNF-AUD-01 | Privacidade | Nenhum registro contém `eleitor_id`, e o registro localizado por um comprovante não contém opção nem peso. | D-AUD-02, D-AUD-03 | [#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28) |
| RNF-AUD-02 | Privacidade | A ordem das cédulas publicadas não é derivável da ordem de chegada. O embaralhamento usa `secrets.SystemRandom`. | D-AUD-03 | [#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28) |
| RNF-AUD-03 | Integridade | Alteração, remoção, inserção ou reescrita completa até o encerramento é detectada na verificação contra a âncora. | D-AUD-01 | [#27](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/27) |
| RNF-AUD-04 | Desempenho | Verificar e recontar um log de 10.000 votos leva no máximo 2 s no CI. | D-AUD-09 | [#27](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/27), [#29](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/29) |
| RNF-AUD-05 | Usabilidade | O comprovante vem com instrução não técnica sobre o que comprova e o que não revela. | D-AUD-11 | [#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28) |

Categorias não incluídas e por quê:
- **Disponibilidade:** o projeto ainda é uma biblioteca, sem serviço em execução.
- **Acessibilidade:** não há interface gráfica no escopo atual.

Ambas devem ser reavaliadas quando houver interface.

## 3. Dependências, conflitos, ambiguidades e decisões

| # | Tipo | Situação | Como foi tratada |
|---|---|---|---|
| 1 | **Conflito** | Transparência × sigilo: publicar opção, ordem e horário de cada voto maximiza a recontagem, mas quebra o sigilo (D-AUD-02, D-AUD-03). | O conteúdo dos votos só é gravado no encerramento, embaralhado ([#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28)). Assim a recontagem ([#29](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/29)) continua possível, e nem o comprovante nem a ordem dos registros revelam votos. |
| 2 | **Conflito** | Recibo verificável × venda de voto. Helios e Belenios resolvem com cifragem de cédula. | **Decisão:** não adotar criptografia de cédula, por complexidade fora do escopo da disciplina. A garantia vem da separação entre inclusão e conteúdo ([#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28)). Limitação aceita: o eleitor confere que o voto entrou, não que foi contado na opção certa. Esse risco é coberto pela recontagem feita pelo fiscal ([#29](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/29)). |
| 3 | **Decisão** | Manter o épico restrito ao módulo de auditoria. | As três histórias alteram só `auditoria.py` e mantêm a interface que a sessão usa. Por isso não dependem de outros épicos nem exigem mudanças no código de colegas. |
| 4 | **Decisão** | Descobertas que exigiriam mexer em outros módulos ficam fora deste épico e registradas para backlog futuro:<br>• contexto (D-AUD-04) e procuração (D-AUD-08) dependem da interface de regras e do fluxo de procurações;<br>• a abertura com as opções (D-AUD-07) depende da sessão;<br>• a exportação aberta (D-AUD-06) e a assinatura do comprovante (D-AUD-10) foram adiadas porque não bloqueiam o fluxo de verificação. | O motivo de cada uma está na coluna "Situação". Em particular, no D-AUD-04, o comportamento atual (anonimizar todos os contextos) é o mais restritivo e não fere o sigilo de nenhum deles. Apenas deixa de oferecer a transparência nominal do Congresso. |
| 5 | **Ambiguidade** | "Auditável por quem?". | Resolvida pelas referências: o **eleitor** faz a verificação individual ([#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28)), e a **comissão / fiscal** faz a verificação universal ([#27](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/27), [#29](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/29)). |
| 6 | **Dependência** | [#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28) → [#27](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/27); [#29](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/29) → [#27](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/27), [#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28). | Refletida na ordem de prioridade (seção 4). |

## 4. Priorização das histórias do épico

| Prioridade | História | Incluída na primeira entrega de valor? | Justificativa |
|---|---|---|---|
| 1 | [#27](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/27) — Âncora de encerramento | **Sim** | Corrige a falha mais grave encontrada: um log reescrito por inteiro é aprovado. Comprovante e recontagem partem de um log que precisa ser confiável, então esta história vem antes de tudo. |
| 2 | [#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28) — Comprovante que não revela a opção | **Sim** | Hoje o comprovante permite provar o voto, e a ordem do log liga voto e eleitor. Isso afeta diretamente a eleição de CA, onde mesários veem quem vota e quando. Sem esta história, o log não pode ser mostrado a ninguém sem expor votos. |
| 3 | [#29](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/29) — Recontagem a partir do log | Não | Depende das cédulas gravadas no encerramento ([#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28)) e da âncora ([#27](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/27)). Com as duas entregues, o log já é íntegro e sigiloso, e a recontagem estende essa confiança ao resultado. É a próxima a ser feita, mas não é necessária para que o registro em si seja confiável. |

**Conjunto da primeira entrega ([#27](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/27) + [#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28)):** forma um fluxo completo para uma eleição secreta de CA. O eleitor vota e recebe um comprovante que não revela o voto; o log não preserva a ordem de chegada; no encerramento a comissão guarda a âncora e, a qualquer momento, detecta adulterações; o eleitor confere a inclusão do seu voto contra essa âncora. Sem [#27](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/27), o comprovante não prova nada, porque o log poderia ter sido refeito. Sem [#28](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/28), mostrar o log expõe votos.

## 5. Proposta para a tabela de priorização entre épicos

Esta seção deve ser decidida com a equipe. Fica aqui o argumento para posicionar este épico:

> **Auditoria e transparência** — incluir na primeira entrega, logo depois dos épicos que produzem uma votação funcional (sessão e apuração/regras). Justificativa: num sistema de votação, um resultado que não pode ser conferido não é aceito pelos perdedores. O benchmarking mostrou que o log atual não sustenta uma contestação: aceita reescrita e o comprovante revela o voto. Como as histórias se limitam ao módulo de auditoria, este épico não bloqueia nem é bloqueado pelos demais.

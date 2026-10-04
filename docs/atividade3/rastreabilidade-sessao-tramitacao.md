# Da elicitação aos requisitos — rito deliberativo e legislativo

> As descobertas D-RITO-xx estão em [`jornadas-sessao-tramitacao.md`](jornadas-sessao-tramitacao.md),
> seção 7, e as evidências Exx na seção 6 do mesmo documento.

## 1. Rastreabilidade: descoberta → análise → requisito

| Descoberta da elicitação | Análise / interpretação | Requisito relacionado |
|---|---|---|
| **D-RITO-01** — Projeto emendado pela Casa revisora volta à Casa iniciadora (CF art. 65, § único). O sistema conclui o rito na aprovação da revisora e `registrar_resultado` não tem por onde receber a informação de que houve emenda (evidência E1). | O caminho mais frequente de uma matéria relevante é o único que o sistema não percorre. Pior que uma funcionalidade ausente: o sistema **afirma** um desfecho — matéria aprovada — que o rito não autorizaria. | **RF** — Retorno à Casa iniciadora por emenda · História **[#33](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/33)**<br>**RNF-RITO-01** (auditabilidade) |
| **D-RITO-02** — PEC é promulgada pelas Mesas (CF art. 60, § 3º); projeto de lei vai à sanção, com veto apreciado em sessão conjunta e derrubado por maioria absoluta, em votação aberta desde a EC 76/2013 (CF art. 66). O sistema encerra os dois tipos de forma idêntica (E1). | `TURNOS_POR_MATERIA` já reconhece que o tipo da matéria muda o rito; a conclusão é o único ponto em que essa distinção foi perdida. A apreciação do veto é uma deliberação a mais, com quórum próprio. | **RF** — Conclusão distinta por tipo de matéria · História **[#34](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/34)**<br>**RNF-RITO-01** (auditabilidade) |
| **D-RITO-03** — A deliberação exige presença da maioria absoluta dos membros (CF art. 47). O quórum é aferido só na apuração, a partir da contagem de votos, com a sessão já encerrada (E4). | Aferir no fim converte um impedimento em um resultado: dez parlamentares votaram numa sessão que nunca poderia ter deliberado. Além disso, contar votos como presença é aproximação — quem comparece e não vota não é contado. | **RF** — Quórum de instalação aferido na abertura · História **[#37](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/37)**<br>**RNF-RITO-01** (auditabilidade) |
| **D-RITO-04** — Sessões reais são suspensas e retomadas, e votações viciadas são anuladas. A máquina de estados é estritamente progressiva e não tem nem suspensão nem anulação (E5). | Sem suspensão, toda interrupção obriga a abandonar a sessão e convocar outra — e o histórico da tramitação passa a registrar como duas deliberações o que foi uma só. A anulação é o que distingue uma sessão viciada de uma sessão válida. | **RF** — Suspensão e retomada · História **[#38](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/38)**<br>**RF** — Anulação com motivo · História **[#39](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/39)**<br>**RNF-RITO-01** (auditabilidade) |
| **D-RITO-05** — Matéria rejeitada só volta na mesma sessão legislativa mediante maioria absoluta (CF art. 67); PEC rejeitada não volta (art. 60, § 5º). Nada impede reinstanciar a tramitação no instante seguinte (E2). Pelo mesmo motivo, não há como arquivar uma matéria ou retirá-la de pauta: só se sai de `EM_TRAMITACAO` por aprovação ou rejeição. | A regra protege o Congresso de reapresentação indefinida da mesma matéria. Irrepetibilidade e arquivamento dependem das mesmas duas noções que o projeto não tem: sessão legislativa (o ano) e matéria arquivada — por isso são tratados numa história só. | **RF** — Irrepetibilidade de matéria rejeitada na mesma sessão legislativa · História **[#35](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/35)** |
| **D-RITO-06** — Os dois turnos de PEC exigem interstício de cinco sessões, dispensável por requerimento de líderes (RICD art. 202, § 6º). Os turnos podem ser consecutivos (E3). | O interstício é contado em **sessões**, não em dias, e o projeto não tem calendário de sessões. Implementá-lo exigiria um conceito novo e transversal, de valor baixo frente às demais descobertas. | Fora do escopo deste épico — ver decisão 5 |

Todas as histórias pertencem a um dos dois épicos da seção 4: **[#32](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/32)** (rito legislativo)
ou **[#36](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/36)** (sessão deliberativa).

## 2. Requisitos não funcionais identificados

| ID | Categoria | Requisito (verificável) | Origem | Impacta |
|---|---|---|---|---|
| RNF-RITO-01 | Auditabilidade | Toda transição relevante gera registro no log de auditoria: no rito, o avanço de turno, a troca de Casa, o retorno por emenda e a conclusão, identificando a etapa de origem e a de destino; na sessão, a instalação, a suspensão, a retomada e a anulação, com o motivo quando houver. | D-RITO-01 a D-RITO-04 | [#33](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/33), [#34](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/34), [#37](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/37), [#38](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/38), [#39](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/39) |
| RNF-RITO-02 | Confiabilidade | Tramitações sem emenda e sessões sem suspensão preservam o comportamento atual: a suíte existente passa sem alteração (283 testes em `develop` em 04/10/2026). | Todas | [#32](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/32), [#36](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/36) |
| RNF-RITO-03 | Manutenibilidade | Cada regra de rito implementada cita, no docstring ou no teste, o dispositivo que a fundamenta (artigo da CF ou do regimento). | D-RITO-01 a D-RITO-05 | [#32](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/32), [#36](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/36) |

RNF-RITO-03 não é formalismo: o rito muda por emenda constitucional — a própria EC 76/2013
alterou o art. 66, § 4º durante a vigência do sistema que ele rege. Sem a citação no código,
uma mudança de norma não tem como ser localizada no que precisa ser alterado.

Categorias deliberadamente **não** incluídas, e por quê:

- **Desempenho:** os volumes são conhecidos e pequenos — 513 deputados e 81 senadores. O
  épico de auditoria já cobre o caso de volume alto (10.000 votos), que não se aplica aqui.
- **Usabilidade e acessibilidade:** não há interface no escopo atual.
- **Disponibilidade:** o projeto é uma biblioteca, sem serviço em execução.

As três devem ser reavaliadas quando houver interface e serviço.

## 3. Dependências, conflitos, ambiguidades e decisões

| # | Tipo | Situação | Como foi tratada |
|---|---|---|---|
| 1 | **Ambiguidade** | A palavra "sessão" tem três sentidos no domínio: `SessaoVotacao` (uma votação), *sessão* como reunião do Plenário (unidade em que o interstício é contado) e *sessão legislativa* como o período anual (CF art. 57), que é a unidade da irrepetibilidade. O código usa o primeiro sentido para tudo. | Os documentos e as histórias passam a usar **sessão de votação**, **sessão plenária** e **sessão legislativa**, sempre por extenso. A história [#35](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/35) introduz a sessão legislativa como conceito próprio, e não como mais um uso de `SessaoVotacao`. |
| 2 | **Conflito** | Fidelidade ao rito × generalidade da biblioteca: quanto mais o modelo incorpora etapas constitucionais, menos ele serve aos contextos de CA e assembleia, que compartilham `SessaoVotacao`. | **Decisão:** tudo que é específico do Congresso fica em `TramitacaoLegislativa`, que já é um módulo do contexto legislativo. `SessaoVotacao` só recebe o que é comum aos três contextos — suspensão, anulação e quórum de instalação são genéricos e cabem lá; emenda, sanção e irrepetibilidade não são e ficam fora. |
| 3 | **Dependência** | A história [#37](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/37) precisa do quórum de instalação, que existe só em `RegraCongresso.quorum_instalacao` e **não** na interface `RegraDeVotacao` (`src/votacao/regras/base.py`), de outro integrante. | **Decisão:** não alterar a interface. A sessão recebe o quórum de instalação como parâmetro, e `TramitacaoLegislativa.nova_sessao` o fornece a partir da `RegraCongresso` que ela já instancia. CA e assembleia seguem sem quórum de instalação, que de fato não se aplica a elas. |
| 4 | **Conflito** | Aferir quórum na abertura exige saber **quem está presente**, e o sistema só conhece quem **votou**. Contar votos como presença é justamente o que torna a aferição tardia. | A história [#37](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/37) declara a presença como entrada explícita da abertura da sessão, separada do voto. É dado novo, e isso está assumido no critério de aceitação em vez de contornado. |
| 5 | **Decisão** | D-RITO-06 (interstício entre turnos de PEC) fica fora do épico. | O interstício é contado em sessões plenárias, e o projeto não tem calendário. Implementá-lo exigiria um conceito transversal novo para atender à descoberta de menor impacto das seis. Fica registrada no backlog, com a fonte. |
| 6 | **Dependência entre histórias** | [#34](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/34) reorganiza a conclusão do rito que [#33](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/33) altera; [#38](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/38) e [#39](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/39) mexem na mesma máquina de estados. | Refletida na ordem de prioridade da seção 4: [#33](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/33) antes de [#34](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/34), e [#38](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/38) antes de [#39](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/39). [#35](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/35) e [#37](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/37) são independentes das demais. |
| 7 | **Dependência entre épicos** | A descoberta **D-AUD-04** do épico de auditoria ([#26](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/26)) — a política de sigilo deveria ser configurável por contexto, já que no Congresso a votação nominal é pública — foi adiada por depender da sessão, ou seja, deste módulo. | Registrada como entrada de backlog compartilhada. Não entra neste épico porque exige decisão conjunta sobre a interface de regras, mas a história [#37](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/37), ao tornar explícito o que a sessão sabe sobre os presentes, é pré-requisito natural dela. |

## 4. Priorização

### 4.1 Entre os épicos

Posicionamento proposto destes dois épicos em relação ao de auditoria, já cadastrado. A
tabela consolidada da equipe é montada na entrega.

| Prioridade | Épico | Incluído na primeira entrega de valor? | Justificativa |
|---|---|---|---|
| 1 | **[#32](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/32)** — Condução fiel do rito legislativo bicameral | **Sim** | Corrige o único defeito encontrado que faz o sistema **afirmar algo falso**: uma PEC emendada pela Casa revisora é dada por aprovada sem voltar à iniciadora (E1). Um sistema de votação legislativa que conclui o rito de forma que a Constituição não autoriza não pode ser usado nem como protótipo. |
| 2 | **[#36](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/36)** — Governança da sessão deliberativa | **Sim** | Sem quórum na abertura, a sessão colhe votos que não valem (E4); sem suspensão, qualquer interrupção real vira uma segunda deliberação no histórico (E5). Os dois defeitos corrompem a própria entrada do [#32](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/32), que consome os resultados das sessões. |
| 3 | [#26](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/26) — Auditoria e transparência | Sim | Mantida a justificativa do épico: um resultado que não pode ser conferido não é aceito pelos perdedores. Vem depois porque audita um rito que precisa, antes, estar correto — auditar fielmente um desfecho inconstitucional não resolve o problema. |

**Conjunto da primeira entrega ([#32](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/32) + [#36](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/36)):** forma um rito legislativo completo e
defensável. A sessão só delibera com quórum e pode ser suspensa sem perder o que colheu; a
matéria percorre as duas Casas, volta à iniciadora se emendada, e termina em promulgação ou
sanção conforme o tipo. Sem [#36](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/36), os resultados que alimentam [#32](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/32) podem vir de sessões
que nunca deveriam ter deliberado. Sem [#32](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/32), a sessão é bem conduzida mas o rito que ela
alimenta chega a um desfecho errado.

### 4.2 Histórias do épico [#32](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/32) — rito legislativo bicameral

| Prioridade | História | Incluída na primeira entrega? | Justificativa |
|---|---|---|---|
| 1 | **[#33](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/33)** — Retorno à Casa iniciadora quando a revisora emenda a matéria | **Sim** | É o desvio que produz o desfecho inconstitucional (E1), não depende das outras e reorganiza a etapa de conclusão sobre a qual [#34](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/34) se apoia. |
| 2 | **[#34](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/34)** — Conclusão do rito distinta por tipo: promulgação, sanção e veto | **Sim** | Completa o rito: hoje uma PEC e uma lei ordinária terminam idênticas, e a PEC seria enviada a uma sanção que a Constituição não prevê. Depende de [#33](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/33), que define onde a conclusão acontece. |
| 3 | [#35](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/35) — Irrepetibilidade de matéria rejeitada na mesma sessão legislativa | Não | Independente das duas anteriores, mas protege contra um uso indevido — reapresentar a matéria rejeitada — e não contra um erro do sistema. Exige introduzir a sessão legislativa como conceito, o que é custo novo para valor menor nesta entrega. |

### 4.3 Histórias do épico [#36](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/36) — sessão deliberativa

| Prioridade | História | Incluída na primeira entrega? | Justificativa |
|---|---|---|---|
| 1 | **[#37](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/37)** — Quórum de instalação aferido na abertura da sessão | **Sim** | Hoje a sessão colhe votos que serão descartados e só descobre o impedimento quando já está encerrada (E4). É também a história que torna explícito o que a sessão sabe sobre os presentes, de que dependem a [#38](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/38) e, mais adiante, a D-AUD-04 do épico de auditoria. |
| 2 | **[#38](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/38)** — Suspensão e retomada da sessão | **Sim** | Sem ela, a queda de quórum que a [#37](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/37) passa a detectar não tem desfecho possível além de abandonar a sessão. As duas juntas é que fecham o ciclo: detectar o problema e tratá-lo. |
| 3 | [#39](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/39) — Anulação da sessão com motivo registrado | Não | Trata de vício apurado depois da votação, situação mais rara que a queda de quórum e sem dependência das demais. O registro do motivo tem valor para a auditoria, mas não bloqueia o fluxo principal. |

# Elicitação de requisitos — Cenários: jornada do rito deliberativo e legislativo

**Épicos relacionados:** Condução fiel do rito legislativo bicameral ([#32](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/32)) e Governança da sessão deliberativa ([#36](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/36))
**Responsáveis:** Lucas Lembo de Lara e Rafael Scalabrin Dosso
**Período de execução:** 03 e 04/10/2026
**Objeto analisado no projeto:** módulos `src/votacao/sessao.py` e `src/votacao/tramitacao.py`,
na branch `develop` (estado após a entrega da Atividade 2, issue
[#20](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/20))

---

## 1. Técnica escolhida e justificativa

A técnica aplicada foi a de **cenários, na forma de jornada do usuário**: descrever, passo a
passo e do ponto de vista de quem conduz o processo, como uma matéria atravessa o sistema do
início ao fim e, em cada passo, o que pode dar errado.

A escolha não é genérica: ela decorre de três características específicas destes dois módulos.

1. **O objeto é um processo, não uma funcionalidade.** `TramitacaoLegislativa` e
   `SessaoVotacao` não calculam nada; elas governam *ordem*. A pergunta que o módulo responde
   é "o que pode acontecer agora, e o que vem depois". Cenários são a técnica que se pauta em
   situações concretas e em fluxos de eventos, que é exatamente o formato do objeto.
2. **Os desvios são a parte interessante, e eles são previstos em norma.** O rito legislativo
   não é um caminho feliz com exceções acidentais: a emenda da Casa revisora, o veto
   presidencial e a perda de quórum são *etapas previstas* da Constituição e dos Regimentos.
   O terceiro elemento do cenário ("o que pode dar errado e como lidar") deixa de ser
   especulação e passa a ter fonte verificável.
3. **Limitações reconhecidas.** Entrevista e brainstorming exigem participantes externos,
   e não houve acesso a parlamentares, servidores de Mesa ou membros de comissão no prazo da
   atividade. Benchmarking já foi empregado por outro integrante da equipe, sobre o módulo de
   auditoria.

**Risco assumido.** O material da disciplina registra que cenários "não [são] muito útil[eis]
para sistemas não (ou pouco) interativos". A técnica foi mantida porque a interatividade
relevante aqui não é entre usuário e tela, e sim **entre atores institucionais**: a Mesa
convoca, o Plenário delibera, a Casa revisora emenda, a iniciadora reaprecia. É esse
vaivém que o módulo precisa representar, e é ele que a jornada expõe. A consequência prática
da ressalva é que as jornadas abaixo descrevem *decisões de processo*, e não telas.

## 2. Fontes utilizadas

A elicitação foi conduzida pelos dois responsáveis, sem participação externa. As fontes são
documentais e o próprio código, e estão listadas para que qualquer afirmação da seção 7
possa ser reconferida.

| ID | Fonte | O que foi extraído | Acesso |
|---|---|---|---|
| F1 | [Constituição Federal de 1988](https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm), arts. 47, 60, 65, 66, 67 e 69 | Quórum de deliberação, rito da PEC, revisão bicameral, sanção e veto, irrepetibilidade, quórum da lei complementar | 03/10/2026 |
| F2 | [Regimento Interno da Câmara dos Deputados](https://www.camara.leg.br/internet/legislacao/regimento_interno/RIpdf/regInterno.pdf), art. 202 | Interstício de cinco sessões entre os dois turnos de PEC e sua dispensa por requerimento de líderes | 03/10/2026 |
| F3 | [EC nº 76/2013](https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc76.htm) | Revogação do escrutínio secreto na apreciação de veto (altera o art. 66, § 4º) | 03/10/2026 |
| F4 | [Câmara dos Deputados — o processo legislativo](https://www.camara.leg.br/entenda-o-processo-legislativo/) | Sequência das etapas e papéis da Mesa, do relator e do Plenário | 03/10/2026 |
| P0 | Código em `develop`: `sessao.py`, `tramitacao.py`, `regras/congresso.py`, `regras/base.py` | Comportamento atual, confrontado com as jornadas na seção 6 | 04/10/2026 |

## 3. Como a atividade foi conduzida

A elicitação propriamente dita são os passos 1 a 3. Os passos 4 e 5 não pertencem à técnica:
são o confronto entre a jornada e o que o sistema faz hoje, e é esse confronto que transforma
uma narrativa do rito em lista de requisitos. A distinção importa porque a jornada se sustenta
sozinha — ela sai da norma, não do código — enquanto o passo 3 de cada jornada só vira
descoberta depois de confrontado.

1. **Escolha das jornadas.** Duas, uma por módulo: a travessia de uma matéria pelo rito
   bicameral (J1) e a condução de uma sessão deliberativa do início ao
   encerramento (J2).
2. **Redação no plano do dever-ser, antes de olhar o código.** Cada jornada foi escrita a
   partir de F1, F2 e F4, descrevendo o processo como ele ocorre no Congresso. A ordem é
   deliberada: o material da disciplina aponta, como risco da técnica, a "visão apenas da
   solução ao invés do problema", e escrever primeiro a partir da norma evita que a jornada
   seja apenas uma narração do que o código já faz.
3. **Estrutura fixa.** Cada jornada tem os cinco elementos indicados em aula: expectativas no
   início, fluxo normal, o que pode dar errado, atividades em paralelo e estado final.
4. **Confronto com o código.** Cada desvio do passo 3 foi procurado no módulo
   correspondente, na branch `develop`.
5. **Montagem dos casos concretos.** Ausência de etapa é difícil de demonstrar lendo código:
   ela não aparece como erro, aparece como algo que simplesmente não está escrito. Para cada
   etapa que a leitura apontou como ausente — do fluxo normal ou dos desvios — foi montado um
   caso com os parâmetros que deveriam provocar a reação prevista na jornada. Da **J1**:
   aprovar a PEC nos dois turnos das duas Casas e observar onde o rito para; rejeitar uma
   matéria e reapresentá-la em seguida; convocar os dois turnos no mesmo instante. Da **J2**:
   abrir uma sessão da Câmara com dez votos, muito abaixo dos 257 exigidos; tentar reabrir uma
   sessão já aberta. A reação do sistema a cada caso está na seção 6.
6. **Síntese.** Os resultados do confronto viraram as seis descobertas `D-RITO-xx` da seção 7,
   que a rastreabilidade liga a requisitos, histórias e épicos.

## 4. Jornada J1 — a Mesa conduz uma PEC da apresentação à promulgação

**Atores:** Mesa da Casa iniciadora, Plenário da Casa iniciadora, Mesa e Plenário da Casa
revisora, relator, líderes partidários.
**Matéria de referência:** uma Proposta de Emenda à Constituição, por ser o rito mais longo
(dois turnos por Casa, CF art. 60, § 2º) e o único que termina em promulgação pelas Mesas.

### 4.1 O que os atores esperam quando o cenário inicia

A matéria está cadastrada, ativa e pautada na Casa iniciadora. A Mesa sabe o tipo da matéria
e, a partir dele, quantos turnos precisa vencer em cada Casa e qual o quórum de aprovação. O
sistema deve ser capaz de dizer, a qualquer momento, em que Casa e em que turno a matéria
está — porque é dessa informação que depende quem tem direito a voto.

### 4.2 Fluxo normal de eventos

1. A Mesa convoca a sessão do turno corrente na Casa iniciadora.
2. O Plenário delibera e a matéria é aprovada pelo quórum exigido (3/5 dos membros, para PEC).
3. Vencido o primeiro turno, observa-se o interstício regimental e convoca-se o segundo.
4. Aprovada nos dois turnos, a matéria segue à **Casa revisora**, que repete o rito.
5. Aprovada sem alterações na revisora, a PEC é **promulgada pelas Mesas da Câmara e do
   Senado**, com o respectivo número de ordem (CF art. 60, § 3º). PEC não vai a sanção.
6. A matéria deixa de tramitar e o histórico de todas as sessões fica disponível.

### 4.3 O que pode dar errado e como lidar

| Desvio | Como o rito trata | Como o sistema trata hoje |
|---|---|---|
| **A Casa revisora emenda o texto** | O projeto **volta à Casa iniciadora**, que aprecia apenas as emendas (CF art. 65, § único). É a hipótese mais comum em matéria relevante. | Não existe. `registrar_resultado` só recebe a sessão apurada; não há como informar que a aprovação veio com emenda, e a aprovação na revisora conclui o rito (evidência E1) |
| **A matéria é rejeitada** | Arquiva-se, e a mesma matéria só volta na mesma sessão legislativa mediante proposta da maioria absoluta (CF art. 67); para PEC, não volta de forma alguma (art. 60, § 5º) | A tramitação vira `REJEITADA`, mas nada impede instanciar outra idêntica no instante seguinte (evidência E2) |
| **A sessão não atinge quórum** | Não há deliberação; a sessão não se instala e a matéria permanece na mesma etapa | Tratado corretamente: a sessão entra no histórico como inválida e a etapa se mantém (`RegistroTramitacao.valida`) |
| **Os dois turnos são convocados sem intervalo** | O interstício de cinco sessões é exigido e só se dispensa por requerimento de líderes aprovado (RICD art. 202, § 6º) | Os dois turnos podem ocorrer no mesmo instante, sem recusa e sem registro de dispensa (evidência E3) |
| **A matéria é retirada de pauta ou arquivada** | Decisão do autor ou da Mesa, a qualquer tempo | Não existe: só se sai de `EM_TRAMITACAO` por aprovação ou rejeição (recolhido em D-RITO-05, que depende do mesmo conceito de matéria arquivada) |

### 4.4 Atividades em paralelo

Várias matérias tramitam ao mesmo tempo, em Casas diferentes e em turnos diferentes; uma
mesma Casa realiza outras sessões no intervalo entre os turnos de uma PEC — e é justamente a
contagem dessas sessões que define o interstício. Nada disso é representado hoje: a
tramitação é um objeto isolado, sem noção de calendário nem de sessão legislativa.

### 4.5 Estado do sistema quando o cenário finaliza

A matéria está promulgada e inativa; o histórico registra cada sessão com Casa, turno e
resultado; e o log de auditoria da votação permite reconferir cada etapa. Hoje o primeiro e o
terceiro itens ficam incompletos: não há distinção entre promulgação e sanção, e a conclusão
do rito não gera registro no log de auditoria — só as sessões individuais geram.

## 5. Jornada J2 — o presidente conduz uma sessão deliberativa

**Atores:** presidente da sessão, parlamentares, secretaria da Mesa.

### 5.1 O que os atores esperam quando o cenário inicia

A sessão foi convocada para uma matéria específica. O presidente precisa, **antes de abrir a
deliberação**, verificar se há quórum: a Constituição condiciona a deliberação à presença da
maioria absoluta dos membros (art. 47). Os parlamentares esperam que o voto registrado conte.

### 5.2 Fluxo normal de eventos

1. O presidente declara aberta a sessão e **verifica o quórum de presença**.
2. Havendo quórum, abre-se a votação, com prazo definido.
3. Os parlamentares votam, um voto por parlamentar.
4. O presidente encerra a votação.
5. Apura-se o resultado e ele é proclamado.
6. A sessão é encerrada e o resultado é incorporado à tramitação da matéria.

### 5.3 O que pode dar errado e como lidar

| Desvio | Como o rito trata | Como o sistema trata hoje |
|---|---|---|
| **Não há quórum na abertura** | A sessão não delibera; o presidente aguarda ou encerra. Ninguém vota. | A sessão abre normalmente, aceita votos, e só na apuração se descobre que nunca houve quórum — com a sessão já encerrada e os votos colhidos em vão (evidência E4) |
| **O quórum cai durante a votação** | O presidente suspende a sessão e retoma quando houver quórum | Não há suspensão: a máquina de estados é estritamente progressiva (evidência E5) |
| **A sessão precisa ser interrompida** (obstrução, questão de ordem, falta de tempo) | Suspende-se e retoma-se, preservando o que já foi colhido | Idem: só é possível seguir adiante ou abandonar a sessão |
| **Apura-se vício que invalida a votação** | A votação é anulada e repetida, com o motivo registrado | Não existe estado de anulação; uma sessão viciada fica `ENCERRADA` e indistinguível de uma válida |
| **Um eleitor tenta votar duas vezes** | Recusa-se o segundo voto | Tratado corretamente, inclusive para voto por procuração e voto consolidado (`SessaoVotacao._identidades`) |
| **Voto fora da janela de votação** | Recusa-se | Tratado corretamente (`_exigir_dentro_da_janela`) |

### 5.4 Atividades em paralelo

O log de auditoria é alimentado ao longo de toda a sessão, e o serviço de elegibilidade
consulta a Casa em que a matéria se encontra para decidir quem pode votar — ou seja, a
tramitação e a sessão se influenciam durante o cenário, e não apenas no fim.

### 5.5 Estado do sistema quando o cenário finaliza

A sessão está encerrada, com resultado apurado e cadeia de auditoria íntegra; se a sessão foi
inválida, isso precisa estar explícito, para que a matéria não seja dada por deliberada. Hoje
a invalidade por falta de quórum é registrada pela tramitação, mas a sessão em si não carrega
a distinção.

## 6. Evidência experimental

Esta seção não faz parte da técnica de cenários: ela é o confronto descrito no passo 5 da
seção 3. A jornada diz o que deveria acontecer; os casos abaixo mostram o que acontece. Foram
executados contra o pacote em `develop` em 04/10/2026.

O script está versionado ao lado deste documento, em
[`evidencia-jornadas.py`](evidencia-jornadas.py), e é organizado em cinco funções, uma por
desvio (`e1_pec_aprovada_nas_duas_casas`, `e2_irrepetibilidade`, `e3_intersticio_entre_turnos`,
`e4_quorum_aferido_tarde`, `e5_sessao_nao_suspende`). Ele usa apenas a API pública do pacote
e um relógio fixo, de modo que a saída é reproduzível:

```bash
PYTHONPATH=src python docs/atividade3/evidencia-jornadas.py
```

Saída obtida:

```
E1 | J1 passo 3: PEC aprovada nas duas Casas
     CAMARA  T1 -> EM_TRAMITACAO
     CAMARA  T2 -> EM_TRAMITACAO
     SENADO  T1 -> EM_TRAMITACAO
     SENADO  T2 -> APROVADA
     status final: APROVADA
     nao ha etapa de emenda da revisora nem de promulgacao: o rito termina aqui.
     registrar_resultado so recebe a sessao:
     nao ha como informar 'aprovada com emenda'.

E2 | J1 passo 3: irrepetibilidade na mesma sessao legislativa
     1a tramitacao -> REJEITADA
     mesma materia reinstanciada -> EM_TRAMITACAO  (nenhuma recusa)

E3 | J1 passo 3: intersticio entre os dois turnos de PEC
     turno 1 e turno 2 convocados no mesmo instante (2026-10-04T14:00:00+00:00)
     turno atual: 2 | sessao: PEC-51/2026-CAMARA-T2  (nenhuma recusa)

E4 | J2 passo 3: quorum so e aferido na apuracao
     quorum_instalacao da Camara: 257 de 513
     sessao aberta sem nenhuma afericao de presenca -> estado EM_VOTACAO
     10 votos aceitos sem recusa
     apuracao -> QUORUM_INSUFICIENTE | quorum_atingido=False
     estado da sessao: ENCERRADA  (os votos foram colhidos em vao)

E5 | J2 passo 3: suspensao da sessao
     estados disponiveis: ['CRIADA', 'ABERTA', 'EM_VOTACAO', 'EM_APURACAO', 'ENCERRADA']
     nao ha estado de suspensao nem metodo para suspender/retomar
     a maquina de estados e estritamente progressiva: TransicaoInvalidaError
```

O que a saída mostra:

- **E1.** As quatro etapas saem na ordem certa, o que confirma que o número de turnos por
  tipo de matéria e o quórum de 3/5 estão corretos: o defeito está só no desfecho. Vencidos
  os dois turnos nas duas Casas, a matéria é dada por aprovada. Não existe a etapa de retorno
  à Casa iniciadora, e `registrar_resultado` nem sequer tem por onde receber a informação de
  que a revisora emendou. O caminho mais comum de uma PEC relevante no Congresso é o único
  que o sistema não sabe percorrer.
- **E2.** A matéria rejeitada é reapresentada no instante seguinte, sem recusa. Faltam tanto a
  noção de sessão legislativa quanto a de matéria arquivada.
- **E3.** Os dois turnos da PEC ocorrem no mesmo instante. O interstício não é apenas uma
  formalidade: ele existe para dar prazo de reflexão entre as duas votações.
- **E4.** Dez parlamentares votam numa sessão que nunca teve quórum. O sistema só percebe na
  apuração, quando a sessão já está `ENCERRADA` e os votos já foram colhidos. No rito, o
  quórum é condição de **abertura**, não de fechamento.
- **E5.** A sessão não pode ser suspensa. Qualquer interrupção real — queda de quórum,
  questão de ordem, obstrução — não tem representação possível.

## 7. Principais descobertas

| ID | Descoberta | Fonte | Implicação para o projeto |
|---|---|---|---|
| **D-RITO-01** | Projeto emendado pela Casa revisora volta à Casa iniciadora, que aprecia só as emendas (CF art. 65, § único). O sistema conclui o rito na aprovação da revisora e não tem como representar a emenda (E1). | F1, P0 | É o desvio mais grave: o sistema produz um desfecho que o rito não autoriza. Exige uma etapa de retorno e um modo de sinalizar aprovação com emenda. |
| **D-RITO-02** | PEC é promulgada pelas Mesas (CF art. 60, § 3º); projeto de lei vai à sanção, com veto apreciado em sessão conjunta e derrubado por maioria absoluta, em votação aberta desde a EC 76/2013 (CF art. 66). O sistema encerra os dois tipos de forma idêntica. | F1, F3, P0 | A conclusão do rito precisa ser distinta por tipo de matéria, e a apreciação de veto é mais uma deliberação a registrar. |
| **D-RITO-03** | Deliberação exige presença da maioria absoluta dos membros (CF art. 47). O quórum é aferido só na apuração, a partir dos votos, e a sessão já encerrada (E4). | F1, P0 | Quórum é condição de abertura. Aferi-lo no fim transforma um impedimento em um resultado, e desperdiça os votos colhidos. |
| **D-RITO-04** | Sessões reais são suspensas e retomadas; votações viciadas são anuladas. A máquina de estados é estritamente progressiva e não tem nem suspensão nem anulação (E5). | F4, P0 | Sem suspensão, qualquer interrupção obriga a abandonar a sessão e convocar outra, o que o histórico registra como se fossem deliberações distintas. |
| **D-RITO-05** | Matéria rejeitada só volta na mesma sessão legislativa mediante maioria absoluta (CF art. 67); PEC rejeitada não volta (art. 60, § 5º). Nada impede reinstanciar a tramitação (E2). Pelo mesmo motivo, não há como arquivar uma matéria ou retirá-la de pauta: só se sai de `EM_TRAMITACAO` por aprovação ou rejeição. | F1, P0 | Falta a noção de sessão legislativa e de matéria arquivada, sem as quais nem a irrepetibilidade nem o arquivamento são representáveis. As duas dependem do mesmo conceito, e por isso são uma descoberta só. |
| **D-RITO-06** | Os dois turnos de PEC exigem interstício de cinco sessões, dispensável por requerimento de líderes aprovado (RICD art. 202, § 6º). Os turnos podem ser consecutivos, sem registro de dispensa (E3). | F2, P0 | Depende de uma noção de calendário de sessões que o projeto não tem; menos grave que as demais e candidata natural a backlog futuro. |

## 8. Conflitos, dependências e ambiguidades

Esta etapa levantou o conflito entre **fidelidade ao rito e simplicidade do modelo**. Quanto
mais etapas constitucionais o sistema representa, mais distante ele fica de uma biblioteca de
votação genérica, reutilizável nos contextos de CA e assembleia. Levantou também a
dependência entre a aferição de quórum e o módulo de regras, que pertence a outro integrante.
A análise e o tratamento de cada ponto estão no arquivo `rastreabilidade-sessao-tramitacao.md`,
tópico 3.

## 9. Limitações

- **Não houve participação de stakeholders.** As jornadas foram elaboradas em conjunto
  pelos dois responsáveis, a partir de norma e documentação oficial, mas sem a participação
  de quem conduz sessões reais — mesas diretoras, secretarias e parlamentares. É a dimensão
  que a técnica prevê e que não foi possível exercer no prazo da atividade.
- **A norma não é a prática.** O regimento prevê acordos de líderes, destaques, requerimentos
  de quebra de interstício e votação simbólica, que alteram o rito concreto. As jornadas
  descrevem o rito formal, e a distância entre um e outro não foi medida.
- **Cenários rendem menos em sistema pouco interativo**, conforme a ressalva registrada na
  seção 1. As jornadas capturam decisões de processo, não interação com interface, o que é
  adequado ao estágio atual do projeto, mas precisará ser revisitado quando houver interface.
- **Escopo restrito ao Congresso.** J1 e J2 foram construídas sobre o contexto legislativo. Os
  contextos de CA e assembleia têm ritos próprios, não cobertos aqui.

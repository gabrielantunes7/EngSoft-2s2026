# Elicitação de requisitos — Benchmarking: Auditoria e transparência da votação

**Épico relacionado:** Auditoria e transparência da votação ([#26](https://github.com/gabrielantunes7/EngSoft-2s2026/issues/26))
**Responsável:** Gabriel Mattias Antunes
**Período de execução:** 01/10/2026
**Objeto analisado no projeto:** módulo `src/votacao/auditoria.py` e sua integração com `sessao.py`, na branch `develop` (estado após a entrega da Atividade 2)

---

## 1. Técnica escolhida e justificativa

A técnica aplicada foi o **benchmarking**: a comparação sistemática do nosso log de auditoria com sistemas e processos reais que resolvem o mesmo problema, ou seja, permitir que alguém confie no resultado de uma votação sem precisar confiar em quem a organizou.

O benchmarking é adequado a esta parte do projeto por quatro razões concretas.

1. **O problema de auditoria tem soluções de referência publicamente documentadas.** Votação verificável é um campo com sistemas em produção. Exemplos:
   - Helios, usado na eleição de reitor da UCLouvain e nas eleições da IACR;
   - Belenios;
   - a urna eletrônica brasileira.

   Todos publicam como fazem a verificação. Comparar com eles mostra lacunas que dificilmente seriam percebidas por usuários entrevistados, que em geral não sabem o que é possível exigir de um sistema auditável.
2. **O projeto atende três contextos com regras de transparência diferentes:** Centro Acadêmico (CA), assembleia de acionistas e Congresso. Para cada um existe uma referência real:
   - Helios e Belenios são usados em eleições universitárias e associativas;
   - a regulação da CVM rege as assembleias de companhias abertas;
   - a Câmara dos Deputados publica as votações nominais.

   Isso permite levantar requisitos *por contexto*, o que é coerente com o motor de regras extensível do projeto.
3. **O módulo já existe.** Diferentemente de uma funcionalidade nova, aqui é possível confrontar cada prática de referência com o comportamento atual do código e verificar experimentalmente as diferenças (seção 6).
4. **Limitação reconhecida.** A equipe não teve acesso, no prazo da atividade, a membros de comissão eleitoral ou a fiscais para entrevistas. Por isso o benchmarking foi escolhido como fonte principal desta parte. A seção 9 discute o efeito dessa escolha.

## 2. Fontes utilizadas

| ID | Sistema / processo | Contexto equivalente no projeto | Fontes consultadas (acesso em 01/10/2026) |
|---|---|---|---|
| B1 | **Helios Voting** | Eleição de CA | [FAQ oficial](https://vote.heliosvoting.org/faq); [Wikipedia – Helios Voting](https://en.wikipedia.org/wiki/Helios_Voting); artigo *Electing a University President using Open-Audit Voting* (Adida, de Marneffe, Pereira, Quisquater), sobre a eleição da UCLouvain em 2009 ([PDF – NIST](https://csrc.nist.gov/csrc/media/events/end-to-end-voting-system-workshop/documents/papers/demarneffe_papere2e.pdf)) |
| B2 | **Belenios** | Eleição de CA; assembleia (voto ponderado) | [Site oficial](https://www.belenios.org/); [Instruções por papel](https://www.belenios.org/instructions.html); [LWN – Belenios: a system for secret voting](https://lwn.net/Articles/887077/); [doc/tool.md no repositório](https://github.com/glondu/belenios/blob/master/doc/tool.md) |
| B3 | **Urna eletrônica / TSE** | Referência geral de auditoria de votação oficial | [TSE – Votação segura](https://www.tse.jus.br/eleicoes/historia/processo-eleitoral-brasileiro/votacao/votacao-segura); [TSE – Zerésima](https://www.tse.jus.br/comunicacao/noticias/2018/Outubro/falta-1-dia-conheca-a-zeresima-relatorio-que-atesta-a-transparencia-da-urna-eletronica); [TRE-MS – RDV permite recontagem](https://www.tre-ms.jus.br/comunicacao/noticias/2024/Outubro/registro-digital-do-voto-permite-recontagem-e-amplia-transparencia-do-processo-eleitoral); [Minuto da Segurança – como o sistema é auditado](https://minutodaseguranca.blog.br/seguranca-urna-eletronica-brasileira-voto-auditoria-riscos/) |
| B4 | **Mapas de votação da CVM** (Resolução CVM 81) | Assembleia de acionistas | [Resolução CVM 81](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/001/resol081consolid.pdf); [Bocater – ofício sobre mapas de votação](https://www.bocater.com.br/en_us/boletim-bocater/cvm-divulga-oficio-sobre-mapas-de-votacao-em-assembleias-gerais/); [Capital Aberto – alterações no processo de votação](https://capitalaberto.com.br/regulamentacao/cvm-altera-processo-de-votacao-em-assembleias/) |
| B5 | **Votações nominais da Câmara dos Deputados** | Congresso | [Câmara – votação no painel eletrônico](https://www2.camara.leg.br/comunicacao/assessoria-de-imprensa/guia-para-jornalistas/votacao); [Dados Abertos – votações detalhadas](https://www.camara.leg.br/assessoria-de-imprensa/641667-dados-abertos-disponibiliza-informacoes-detalhadas-de-votacoes/); [Portal Dados Abertos](https://dadosabertos.camara.leg.br/) |
| P0 | **Nosso sistema** | — | Código em `develop`: `auditoria.py`, `sessao.py`, `procuracoes.py`; script de verificação da seção 6 |

## 3. Como a atividade foi conduzida

1. **Definição dos critérios de comparação.** Os critérios partiram das responsabilidades que o log de auditoria já assume no código: emitir comprovante, provar integridade e preservar o sigilo. A eles se somaram perguntas que um fiscal faria ("consigo recontar?", "consigo contestar?"). O resultado são os 11 critérios da seção 4.
2. **Seleção das referências.** Pelo menos uma por contexto do projeto (CA, assembleia, Congresso), mais o TSE como referência nacional de votação auditável.
3. **Levantamento documental.** Documentação oficial, regulamentação e um artigo com relato de uso real (UCLouvain). Sempre que possível, a fonte primária foi preferida a reportagens.
4. **Preenchimento da matriz comparativa** (seção 5). Células marcadas com "—" indicam que o critério não se aplica ou não foi levantado nas fontes. Nada foi presumido.
5. **Confronto com o código atual.** Cada prática de referência foi comparada com o comportamento de `develop`. As duas diferenças mais graves foram verificadas por um script executado contra o pacote (seção 6).
6. **Síntese das descobertas** (seção 7), numeradas como D-AUD-xx para serem rastreadas até épicos, histórias e requisitos não funcionais (RNFs).

## 4. Critérios de comparação

| # | Critério | Pergunta que o critério responde |
|---|---|---|
| K1 | Comprovante ao votante | O votante sai com algo que identifica o seu voto? |
| K2 | Verificação individual | O votante consegue conferir que o seu voto está no registro? |
| K3 | Verificação universal / recontagem | Qualquer interessado consegue recontar o resultado a partir dos dados publicados? |
| K4 | Proteção contra reescrita | Um operador com acesso ao armazenamento consegue refazer o registro inteiro sem ser detectado? |
| K5 | Desvinculação eleitor × voto | Dá para ligar um voto a quem votou (por identificador, ordem ou horário)? |
| K6 | Recibo que não prova o conteúdo | O comprovante permite que o votante *prove a terceiros* em quem votou (venda de voto, coação)? |
| K7 | Estado inicial atestado | Há prova de que a urna começou vazia e de quais eram as opções e o eleitorado? |
| K8 | Elegibilidade e peso auditáveis | Dá para conferir quantos podiam votar e de onde veio o peso de cada voto? |
| K9 | Dados abertos + especificação | Os dados são exportáveis em formato aberto, com especificação suficiente para um verificador independente? |
| K10 | Procedimento de contestação | Existe uma fase ou procedimento formal para contestar, com evidência? |
| K11 | Linguagem acessível | A verificação é compreensível para quem não é especialista? |

## 5. Matriz comparativa

| | **B1 Helios** | **B2 Belenios** | **B3 Urna / TSE** | **B4 CVM (assembleias)** | **B5 Câmara (nominal)** | **P0 Nosso sistema** |
|---|---|---|---|---|---|---|
| **K1** | Rastreador da cédula: impressão digital da cédula *cifrada* | *Smart ballot tracker*, mostrado na tela e enviado por e-mail | Não há comprovante do conteúdo do voto | — | — | ✅ Protocolo = hash SHA-256 do registro |
| **K2** | Sim, no quadro público (*bulletin board*) | Sim, na urna pública; tracker do e-mail deve coincidir com o da tela | Não individual; conferência por seção | Mapa detalhado permite ao acionista conferir o próprio voto | Sim (voto nominal publicado) | ⚠️ `contem_protocolo` existe, mas o log não é publicado nem consultável fora do processo |
| **K3** | Sim, apuração verificável publicamente | Sim, "qualquer um pode recontar"; `belenios-tool election verify` | BU por seção publicado e confrontável com a totalização; RDV permite recontagem | Mapa final sintético e mapa detalhado por acionista | Sim, voto de cada deputado em dados abertos | ⚠️ Os dados para recontar estão no log, mas não há recontagem e a apuração usa a lista em memória, não o log |
| **K4** | UCLouvain: recibos assinados digitalmente; quadro congelado, assinado e publicado em arquivo único | Auditor verifica que os dados da eleição "não mudam ao longo do tempo" | BU assinado digitalmente e impresso na seção no encerramento, antes da transmissão | — | — | ❌ Cadeia reescrita por inteiro passa na verificação (seção 6) |
| **K5** | Voto cifrado no navegador; quadro com *aliases* em vez de nomes (UCLouvain) | Voto cifrado; chave dividida entre autoridades; arquivo que liga eleitor e cédula é destruído após a apuração | RDV grava cada voto em posição aleatória, impedindo reconstruir a ordem dos votantes | **Não há sigilo**: mapa detalhado identifica o acionista pelos 5 primeiros dígitos do CPF/CNPJ | **Não há sigilo**: votação nominal é pública | ⚠️ `eleitor_id` não é gravado, mas os votos ficam em ordem de chegada e com horário exato |
| **K6** | Rastreador é hash do texto cifrado e não revela o voto; recomendado para ambientes de baixa coerção | Tracker não revela o voto; coerção para revelar credenciais é limitação conhecida | Não há recibo, por desenho | — (voto não é secreto) | — (voto não é secreto) | ❌ Protocolo aponta para registro com a opção em claro (seção 6) |
| **K7** | — | Autoridades conferem chaves e impressões digitais publicadas antes da votação | Zerésima impressa antes do início, assinada pelos presentes e afixada | Mapas sintéticos prévios publicados 24h antes da assembleia | — | ⚠️ `VOTACAO_ABERTA` registra janela e total de aptos, mas não as opções em disputa |
| **K8** | Quadro permite conferir que cada cédula corresponde a um votante | Autoridade de credenciais confere número de votantes e **pesos** (suporte nativo a voto ponderado) | BU traz eleitores aptos e comparecimento | Peso = ações; mapa detalhado por acionista | — | ⚠️ Grava o peso total do voto, mas não a origem (próprio × delegado por procuração) |
| **K9** | Especificação formal de verificação publicada para ferramentas de terceiros | Especificação pública (v3.0) e ferramenta de verificação | BU, RDV e logs no Portal de Dados Abertos | Mapas em formato padronizado | Arquivos em 5 formatos, inclusive planilha | ❌ Não há exportação nem formato documentado |
| **K10** | UCLouvain: um dia de auditoria do quadro; reclamação com recibo assinado; voto em quarentena | Eleitor deve protestar se os trackers divergirem | Fiscalização por partidos, OAB e MP; teste de integridade com cédulas de fiscais | — | — | ❌ Nenhum procedimento |
| **K11** | Helios 2.0 removeu linguagem técnica da fase de auditoria e adicionou barra de progresso | Instruções separadas por papel (eleitor, autoridade, auditor) | — | — | Dados utilizáveis "sem conhecimentos de programação" | ⚠️ Protocolo é um hash hexadecimal de 64 caracteres, sem orientação ao votante |

Legenda da coluna P0: ✅ atende · ⚠️ atende parcialmente · ❌ não atende.

## 6. Evidência experimental: confronto com o código atual

Para não basear as descobertas mais graves só na leitura do código, o script abaixo foi executado contra o pacote de `develop` em 01/10/2026.

```python
from dataclasses import replace
from votacao.auditoria import LogDeAuditoria, TipoEvento, RegistroAuditoria, HASH_GENESE
from votacao.modelos import Voto

log = LogDeAuditoria("ca-2026")
log.registrar(TipoEvento.VOTACAO_ABERTA, {})
p1 = log.registrar_voto(Voto(eleitor_id="ra111", opcao="Chapa A")).hash
p2 = log.registrar_voto(Voto(eleitor_id="ra222", opcao="Chapa B")).hash

# 1) recibo revela o voto: quem tem o protocolo acha o registro e lê a opção
reg = next(r for r in log.registros if r.hash == p1)
print("1) protocolo ->", reg.dados, "| timestamp:", reg.timestamp.isoformat())

# 2) adulteração simples é detectada
log._registros[1] = replace(log._registros[1], dados={"opcao": "Chapa B", "peso": 1})
print("2) adulteração simples:", log.verificar_integridade())

# 3) reescrita completa da cadeia (recalculando todos os hashes) passa
ant, nova = HASH_GENESE, []
for r in log.registros:
    n = RegistroAuditoria.criar(r.indice, r.evento, r.id_votacao, r.timestamp, r.dados, ant)
    nova.append(n)
    ant = n.hash
log._registros = nova
print(
    "3) cadeia reescrita:",
    log.verificar_integridade(),
    "| protocolo original ainda presente?",
    log.contem_protocolo(p1),
)
```

Saída obtida:

```
1) protocolo -> {'opcao': 'Chapa A', 'peso': 1} | timestamp: 2026-10-01T11:15:13.802155+00:00
2) adulteração simples: ResultadoVerificacao(integro=False, indice_divergente=1, motivo='O conteúdo do registro não corresponde ao hash gravado.')
3) cadeia reescrita: ResultadoVerificacao(integro=True, indice_divergente=None, motivo=None) | protocolo original ainda presente? False
```

O que a saída mostra:

- **Caso 1.** Com o protocolo em mãos, qualquer pessoa com acesso ao log encontra o registro e lê a opção votada e o horário exato. É o oposto do rastreador do Helios e do Belenios, que identifica uma cédula *cifrada*.
- **Caso 2.** A adulteração isolada é detectada e localizada, conforme o projeto da Atividade 2.
- **Caso 3.** Se o operador recalcula toda a cadeia, a verificação aprova o log adulterado. A fraude só seria percebida se o votante conferisse o próprio protocolo, que deixou de existir. Nenhuma referência externa ao log permite à comissão detectá-la. Helios (quadro assinado e congelado), Belenios (monitoramento por auditor) e TSE (BU assinado e impresso na seção) resolvem isso com uma cópia ou assinatura *fora* do sistema.

## 7. Principais descobertas

| ID | Descoberta | Fonte | Implicação para o projeto |
|---|---|---|---|
| **D-AUD-01** | Todas as referências de voto secreto (B1, B2, B3) garantem que a integridade possa ser conferida por alguém de fora do sistema: quadro assinado e publicado, monitoramento por auditor, BU impresso na seção. O nosso hash encadeado só garante consistência interna, e uma reescrita completa passa (seção 6, caso 3). | B1, B2, B3, P0 | Publicar uma **âncora** (hash final e totais) no encerramento, fora do controle do operador, e verificar a cadeia contra ela. |
| **D-AUD-02** | Helios e Belenios entregam ao votante um identificador da cédula *cifrada*, que não revela o voto. O nosso protocolo leva a um registro com a opção em claro (seção 6, caso 1), o que viabiliza venda de voto e coação. | B1, B2, P0 | **Conflito transparência × sigilo** a resolver: o comprovante deve provar *que* o voto foi registrado, não *qual* foi o voto. |
| **D-AUD-03** | O TSE grava cada voto do RDV em posição aleatória justamente para impedir a ligação entre a ordem de chegada na seção e o voto. O nosso log grava os votos em ordem de chegada com horário de microssegundos. | B3, P0 | Quem conhece a ordem ou o horário de quem votou (por exemplo, um mesário no CA) pode desanonimizar o voto. É um RNF de privacidade. |
| **D-AUD-04** | O sigilo **depende do contexto**: obrigatório no TSE e nas eleições universitárias (B1–B3), mas nas assembleias da CVM o voto é identificado (5 primeiros dígitos do CPF/CNPJ) e na Câmara a votação nominal é pública. O nosso log aplica a mesma política (anonimizar) aos três contextos. | B3, B4, B5, P0 | A política de identificação no log deve ser **configurável por regra de votação**, como quórum e peso já são. |
| **D-AUD-05** | Em B2, B3 e B5 qualquer interessado reconta o resultado a partir dos dados publicados. O nosso log contém opção e peso de cada voto, mas não há função de recontagem, e `SessaoVotacao.apurar` usa a lista de votos em memória, não o log. | B2, B3, B5, P0 | Nada garante hoje que o resultado proclamado corresponda aos votos auditados. Falta uma recontagem a partir do log, comparada ao `RESULTADO_PROCLAMADO`. |
| **D-AUD-06** | Helios publica especificação formal para verificadores de terceiros; Belenios publica especificação e ferramenta; TSE e Câmara publicam dados em formatos abertos. Não temos exportação. | B1, B2, B3, B5, P0 | Exportar o log em formato aberto e documentado (JSON), suficiente para recalcular os hashes fora do sistema. |
| **D-AUD-07** | A zerésima do TSE atesta o estado inicial antes do primeiro voto, assinada pelos presentes. O nosso `VOTACAO_ABERTA` registra janela e total de aptos, mas não as opções em disputa. | B3, P0 | O registro de abertura deve trazer tudo o que for necessário para conferir a apuração depois: opções, total de aptos ou capital, regra aplicada. |
| **D-AUD-08** | No Belenios, a autoridade de credenciais confere os **pesos** de cada votante em eleições ponderadas. Na CVM, o peso é o número de ações. O nosso log grava só o peso total, sem distinguir peso próprio de peso recebido por procuração (`PoderDeVoto`). | B2, B4, P0 | Na assembleia, o outorgante precisa conseguir conferir pelo log que suas ações entraram no voto do procurador designado, e uma única vez. `Voto.representados` já traz essa informação. |
| **D-AUD-09** | Na UCLouvain (≈4.000 votantes, primeiro turno decidido por **2 votos**), houve um dia dedicado à auditoria do quadro e à contestação com recibo assinado. Os autores concluem que reclamações ficam *mais fáceis* de resolver em eleições auditáveis, porque há evidência e contraevidência. | B1 | Uma fase de contestação entre o encerramento e a proclamação definitiva dá utilidade prática ao log. |
| **D-AUD-10** | O protocolo da UCLouvain era **assinado pelo servidor**, para que o votante pudesse provar que o sistema o emitiu e a comissão não pudesse negá-lo. O nosso é um hash sem assinatura. | B1, P0 | Sem assinatura, o votante não prova que recebeu aquele protocolo. Para a primeira entrega, a âncora pública de D-AUD-01 mitiga parte do problema; a assinatura fica como evolução. |
| **D-AUD-11** | O Helios 2.0 removeu jargão técnico da auditoria porque "muitos usuários não seriam especialistas", e o Belenios separa as instruções por papel. Exibimos um hash hexadecimal de 64 caracteres sem orientação. | B1, B2, P0 | RNF de usabilidade: o comprovante deve vir acompanhado de instrução de uso e de um formato que permita conferência visual. |
| **D-AUD-12** | Só a recontagem e a verificação feitas por terceiros dão confiança, e elas dependem de que "pelo menos uma pessoa honesta" faça as verificações (instruções do Belenios). Ainda não temos o papel de fiscal ou auditor modelado. | B2, P0 | As histórias do épico devem ter como atores o **eleitor** *e* o **fiscal / membro da comissão eleitoral**, com necessidades distintas. |

## 8. Conflitos, dependências e ambiguidades

Esta etapa levantou dois conflitos principais: transparência × sigilo e recibo verificável × venda de voto. Também levantou a ambiguidade "auditável por quem?" e as dependências das descobertas D-AUD-04, D-AUD-06, D-AUD-07, D-AUD-08 e D-AUD-10 em relação a outros módulos. A análise e o tratamento de cada ponto estão em `rastreabilidade-auditoria.md`, seção 3.

## 9. Limitações (ameaças à validade)

- Não houve participação direta de usuários. As necessidades vêm de sistemas, normas e de um relato de uso real (UCLouvain), não de entrevistas. Recomenda-se validar as descobertas D-AUD-09 a D-AUD-11 com um membro de comissão eleitoral de CA em uma iteração futura.
- Helios e Belenios usam criptografia de cédula que não será reproduzida. O que se aproveitou deles foram os *requisitos* (o que o votante e o auditor conseguem verificar), não a solução técnica.

# EngSoft-2s2026

Sistema de votação digital com motor de regras extensível, desenvolvido na disciplina de
Engenharia de Software (MC656) da Unicamp, no segundo semestre de 2026. O tema é alinhado
ao ODS 16 da ONU (Paz, Justiça e Instituições Eficazes).

## Sobre o projeto

O sistema conduz processos de decisão coletiva cujas regras são muito diferentes entre si,
usando um único núcleo de software. São atendidos três contextos:

| Contexto | Quem vota | Peso do voto | Quórum e critério de decisão | Sigilo |
| --- | --- | --- | --- | --- |
| **Eleição de Centro Acadêmico** | Discentes com matrícula ativa | 1 por eleitor | Quórum mínimo de votantes e percentual dos aptos; vence a chapa com maioria simples dos votos válidos | Secreto |
| **Assembleia de acionistas** | Acionistas com ações ordinárias, diretamente ou por procuração | Proporcional ao número de ações | Quórum de instalação sobre o capital; maioria simples, absoluta ou qualificada (2/3, 3/5) conforme a pauta | Aberto e nominal |
| **Congresso Nacional** | Deputados e senadores em exercício | 1 por parlamentar | Quórum de instalação de cada Casa; maioria simples (PL), absoluta (PLP) ou 3/5 em dois turnos (PEC), com tramitação bicameral | Nominal |

Cada voto é registrado em um log de auditoria encadeado por SHA-256. O eleitor recebe um
protocolo que comprova a inclusão do voto, e a comissão guarda uma âncora de encerramento
que permite detectar qualquer adulteração do log, inclusive uma reescrita completa.

## Como executar

### Pré-requisitos

- Python 3.12 ou superior
- `make` e `git`
- Em Debian/Ubuntu, o pacote `python3.12-venv` (detalhes em [CONTRIBUTING.md](CONTRIBUTING.md#pré-requisitos))

O projeto não tem dependências de execução além da biblioteca padrão do Python e não usa
variáveis de ambiente, banco externo nem serviços de terceiros. As dependências de
desenvolvimento (Ruff, pytest, pytest-cov e build) são instaladas pelo `make install`.

### Instalação

```bash
git clone git@github.com:gabrielantunes7/EngSoft-2s2026.git
cd EngSoft-2s2026
make install
```

O `make install` cria o ambiente virtual `.venv/` e instala o projeto em modo editável.

### Interface gráfica web

```bash
make ui
```

Abra http://127.0.0.1:8080 no navegador. Opções do servidor:

```bash
.venv/bin/python -m UI --porta 8080 --abrir   # abre o navegador automaticamente
.venv/bin/python -m UI --host 0.0.0.0         # acessível por outros dispositivos da rede
```

A interface já inicia com um cenário de demonstração: a eleição do CA e uma assembleia
extraordinária em votação, e a PL-101/2026 em tramitação. Os dados vêm de cadastros
fictícios (8 discentes, 6 acionistas, 3 procuradores e 7 parlamentares). Todo o estado fica em
memória e é perdido ao encerrar o servidor; os botões **Restaurar Padrão** e **Recarregar
SQL**, no rodapé da barra lateral, reiniciam o cenário a partir do código Python ou dos
scripts `schema.sql` e `seeds.sql`.

| Tela | O que permite fazer |
| --- | --- |
| Painel Geral | Ver os indicadores do sistema e consultar a aptidão e o peso do voto de um eleitor |
| Sessões & Urna | Criar sessões com a regra de cada contexto, conduzir o ciclo de vida (inclusive suspender, retomar e anular), registrar presença no Congresso, votar e apurar |
| Centro Acadêmico | Cadastrar discentes e chapas |
| Assembleia S.A. | Cadastrar acionistas, procuradores e candidatos; outorgar e revogar procurações |
| Congresso & Leis | Protocolar matérias, cadastrar parlamentares e conduzir a tramitação entre as Casas |
| Auditoria SHA-256 | Inspecionar a cadeia de registros, a âncora de encerramento e verificar um protocolo |

### Uso como biblioteca

O pacote `votacao` pode ser usado diretamente, sem a interface:

```python
from votacao import BancoDadosMock, FabricaCA, LogDeAuditoria, ServicoElegibilidade

servico = ServicoElegibilidade(BancoDadosMock())
log = LogDeAuditoria("ELEICAO-CA")
sessao = FabricaCA().criar_sessao("ELEICAO-CA", total_aptos=6, quorum_minimo_votantes=2, log=log)

sessao.abrir()
sessao.liberar_votacao()
for ra, chapa in [("247314", "Chapa Renova"), ("242352", "Chapa Renova")]:
    voto = servico.autorizar_voto(eleitor_id=ra, opcao=chapa, contexto="CA")
    protocolo = sessao.registrar_voto(voto)  # recibo SHA-256 entregue ao eleitor

sessao.encerrar_votacao()
resultado = sessao.apurar()
print(resultado.status, resultado.vencedor_ou_decisao)  # ELEITO CHAPA RENOVA
print(log.verificar_integridade().integro)  # True
```

## Arquitetura

A arquitetura combina dois estilos: **camadas** (relaxadas, sem dependência que suba de
camada) e **repositório compartilhado** (a tramitação e a autorização do voto trocam
informação pelo cadastro da matéria, sem se chamarem). O detalhamento, com o diagrama C4 de
componentes, está no relatório da Atividade 4.

| Camada | Módulos | Responsabilidade |
| --- | --- | --- |
| Apresentação | `UI/` | Servidor HTTP com API REST e interface web; não contém regra de negócio |
| Orquestração do rito | `tramitacao.py` | Conduz uma matéria pela Casa iniciadora e pela revisora, com 1 ou 2 turnos por Casa |
| Condução e autorização do voto | `sessao.py`, `servicos.py`, `procuracoes.py`, `fabricas/`, `elegibilidade/` | Máquina de estados da sessão; autenticação, aptidão e peso do voto; procurações; criação das famílias de componentes de cada contexto |
| Regras de domínio | `regras/`, `motor.py`, `auditoria.py`, `observadores.py` | Quórum e apuração de cada contexto; log de auditoria encadeado |
| Acesso a dados | `dados/` | Cadastros em memória dos três contextos, com espelho relacional em SQLite |
| Base | `modelos.py` | Modelos de domínio compartilhados (`Voto`, `ResultadoApuracao`, enums) |

Decisões e padrões principais:

- **Variação por contexto isolada atrás de uma interface (Strategy).** Tudo o que muda entre
  CA, Assembleia e Congresso na apuração fica em `RegraCA`, `RegraAssembleia` e
  `RegraCongresso`, que implementam `RegraDeVotacao`. A sessão só conhece essa interface:
  um novo contexto não exige alterar a sessão nem a tramitação.
- **Famílias de componentes por contexto (Abstract Factory).** `FabricaCA`,
  `FabricaAssembleia` e `FabricaCongresso` entregam regra, validador, repositório e sessão
  coerentes entre si, o que impede combinar o validador de um contexto com o cadastro de
  outro.
- **Eventos da sessão desacoplados (Observer).** A sessão publica transições e votos para
  observadores; a auditoria é um deles (`ObservadorAuditoria`).
- **Autorização separada da condução.** "Esta pessoa pode votar, e com que peso?"
  (`ServicoElegibilidade`) é respondido fora da sessão; a sessão só controla o estado da
  urna e o voto duplo.
- **Quórum de instalação aferido na abertura (Congresso).** A presença é registrada à
  parte do voto, e a votação só é liberada com a maioria absoluta da Casa presente
  (CF, art. 47). Na apuração, a regra ainda exige o mínimo de votos registrados,
  inclusive abstenções.
- **Retorno à Casa iniciadora por emenda.** Se a Casa revisora aprova com emendas, a
  matéria volta à iniciadora, que aprecia apenas as emendas em sessão única (CF, art. 65,
  parágrafo único); o histórico registra qual texto prevaleceu, e a troca de Casa fica
  no log de auditoria da tramitação.
- **Suspensão e retomada da sessão.** A votação pode ser suspensa com motivo e retomada
  quantas vezes for preciso, preservando os votos colhidos e sem estender a janela de
  votação; as duas transições ficam no log de auditoria. Uma sessão viciada pode ser
  anulada com motivo a partir da abertura: ANULADA é terminal, não produz resultado, e a
  tramitação mantém a etapa para que outra sessão seja convocada.
- **Sigilo por contexto na interface.** No CA, a UI não expõe votos individuais, parciais,
  nem a opção ou o horário dos registros de voto; na Assembleia e no Congresso, o voto é
  aberto e nominal.

## Estrutura do repositório

```
.
├── src/
│   ├── votacao/                  # Pacote de domínio (biblioteca)
│   │   ├── regras/               # RegraDeVotacao e as regras de CA, Assembleia e Congresso
│   │   ├── elegibilidade/        # Validadores de aptidão ao voto de cada contexto
│   │   ├── fabricas/             # Abstract Factory com as famílias de cada contexto
│   │   ├── dados/                # Repositórios em memória, seeds e espelho SQLite
│   │   ├── sessao.py             # Ciclo de vida da sessão de votação
│   │   ├── tramitacao.py         # Rito bicameral do Congresso
│   │   ├── auditoria.py          # Log encadeado por SHA-256 e âncora de encerramento
│   │   ├── observadores.py       # Observer dos eventos da sessão
│   │   ├── procuracoes.py        # Procurações e poder de voto consolidado
│   │   ├── servicos.py           # Autenticação, aptidão e autorização do voto
│   │   ├── motor.py              # Orquestrador de apuração
│   │   └── modelos.py            # Modelos de domínio compartilhados
│   └── UI/                       # Interface web
│       ├── app.py                # Fachada do domínio e serialização em JSON
│       ├── servidor.py           # Servidor HTTP e API REST
│       └── static/               # index.html, app.js e styles.css
├── tests/                        # Testes automatizados (pytest)
├── docs/atividade3/              # Registros de elicitação e rastreabilidade de requisitos
├── .github/workflows/ci.yml      # Pipeline de integração contínua
├── Makefile                      # Automação de instalação, lint, testes, build e UI
├── pyproject.toml                # Metadados do pacote e configuração das ferramentas
└── CONTRIBUTING.md               # Fluxo de trabalho, padrões e processo de release
```

## Qualidade e integração contínua

```bash
make lint      # Ruff: análise estática e formatação
make test      # pytest
make coverage  # pytest com cobertura de linhas e desvios (mínimo de 80%)
make build     # wheel e sdist em dist/
make verify    # instala o wheel em ambiente limpo e valida a importação
```

- **Testes:** suíte com testes unitários das regras de cada contexto, testes de regressão
  (marcador `regressao`) que garantem que um contexto novo não quebra os anteriores, e
  testes da interface e da API HTTP.
- **Técnicas de teste aplicadas (Atividade 5):** particionamento em classes de
  equivalência e análise de valor limite nas regras de CA e Congresso e nas procurações;
  teste estrutural com cobertura de desvios; teste de mutação com `mutmut` em `sessao.py`
  e `regras/congresso.py`.
- **Cobertura:** medida sobre o pacote `votacao`, com cobertura de desvios (`branch = true`).
  A interface web é coberta por `tests/test_ui.py`, mas não entra no percentual.
- **Pipeline (GitHub Actions):** os jobs `Lint`, `Tests` e `Build` rodam em todo Pull
  Request e após a integração em `develop` e `main`. Os três são obrigatórios para o
  merge, e as branches protegidas exigem a aprovação de outro integrante.

## Processo e versões

O trabalho segue Scrum adaptado com práticas de XP, descrito no relatório da Atividade 1.
O código é integrado por Pull Request em `develop`, e cada entrega é consolidada em `main`
por uma branch `release/*` e identificada por uma tag:

| Tag | Entrega |
| --- | --- |
| `a2-v1.0.0` | Gerência de configuração, CI e primeiras funcionalidades |
| `a4-v1.0.0` | Arquitetura, padrões de projeto e refatoração |
| `a5-v1.0.0` | Teste funcional, estrutural e de mutação |

O fluxo completo está em [CONTRIBUTING.md](CONTRIBUTING.md).

## Limitações conhecidas

- O estado é mantido em memória; não há persistência entre execuções.
- Não há autenticação real: a interface funciona como console do operador, que escolhe o
  votante, e as identidades vêm de cadastros fictícios.
- O log de auditoria grava os votos na ordem de chegada. O sigilo no CA é garantido pela
  interface, e o embaralhamento das cédulas no próprio log está no backlog (#28).
- A tramitação conclui a matéria como aprovada ou rejeitada; promulgação, sanção e veto
  estão no backlog (#34).

## Membros da equipe

| Nome | RA |
| --- | --- |
| Gabriel de Macedo Cavassani Montagna | 242352 |
| Gabriel Mattias Antunes | 281199 |
| Lucas Gomes Bussinger da Silva | 247314 |
| Lucas Lembo de Lara | 254467 |
| Rafael Scalabrin Dosso | 205237 |

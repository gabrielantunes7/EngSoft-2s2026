# Guia de contribuição

Este documento descreve como preparar o ambiente, executar as verificações locais e
integrar mudanças no repositório. Vale para todos os integrantes da equipe.

## Pré-requisitos

- **Python 3.12 ou superior**
- **make**
- **git**

Em distribuições baseadas em Debian e Ubuntu, o módulo `venv` não vem junto do Python do
sistema e precisa ser instalado à parte:

```bash
sudo apt install python3.12-venv
```

Sem esse pacote, o `make install` falha com a mensagem `ensurepip is not available`.

> **Não instale as dependências no Python do sistema.** Distribuições recentes adotam o
> PEP 668 e recusam `pip install` global com o erro `externally-managed-environment`.
> Todos os alvos do `Makefile` já trabalham dentro do ambiente virtual `.venv/`.

## Preparando o ambiente

```bash
git clone git@github.com:gabrielantunes7/EngSoft-2s2026.git
cd EngSoft-2s2026
make install
```

O `make install` cria o `.venv/` e instala o projeto em modo editável junto das
dependências de desenvolvimento.

## Comandos disponíveis

| Comando | O que faz |
| --- | --- |
| `make help` | Lista todos os alvos |
| `make install` | Cria o `.venv/` e instala o projeto em modo editável |
| `make lint` | Executa a análise estática; falha se houver violação |
| `make format` | Corrige automaticamente o que for corrigível e formata o código |
| `make test` | Executa a suíte de testes |
| `make coverage` | Executa os testes medindo a cobertura e gera os relatórios |
| `make build` | Gera os artefatos de distribuição em `dist/` |
| `make verify` | Instala o wheel gerado em um ambiente limpo e valida a importação |
| `make clean` | Remove artefatos de build, relatórios e caches |

## Fluxo de trabalho

As branches `main` e `develop` são protegidas: não é possível commitar diretamente nelas.
Toda mudança segue o caminho abaixo.

1. **Abra uma issue** descrevendo a mudança e adicione a label `Atividade2`.
2. **Crie a branch a partir de `develop`**, nunca de `main`:

   ```bash
   git checkout develop
   git pull
   git checkout -b feature/nome-da-feature
   ```

3. **Desenvolva na branch**, com commits que registrem a evolução do trabalho.
4. **Escreva os testes automatizados** da funcionalidade na mesma branch.
5. **Abra um Pull Request para `develop`**, vinculando-o à issue.
6. **Solicite revisão** a outro integrante da equipe.
7. **Aguarde os checks obrigatórios** ficarem verdes.
8. **Faça o merge** somente após a aprovação e os checks concluídos.

A rastreabilidade precisa ficar evidente em todo o caminho:
`issue` → `feature/*` → `commits` → `Pull Request` → `revisão` → `develop`.

### Nomenclatura de branches

| Prefixo | Uso |
| --- | --- |
| `feature/` | Funcionalidades do produto |
| `chore/` | Infraestrutura, pipeline e configuração |
| `docs/` | Documentação |
| `fix/` | Correção de defeito |
| `release/` | Preparação de versão para entrega |

### Vinculando o Pull Request à issue

Inclua no corpo do commit ou do PR uma das palavras-chave do GitHub seguida do número da
issue, para que ela seja encerrada automaticamente no merge:

```
Closes #12
```

### Padrão de mensagens de commit

```
tipo: resumo no imperativo, em minúsculas

Corpo opcional explicando o que mudou e por quê.

Closes #N
```

Tipos em uso: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`.

## Antes de abrir um Pull Request

Rode as mesmas verificações que o pipeline executa. Assim você descobre os problemas em
segundos, em vez de esperar o CI:

```bash
make format    # corrige formatação e violações corrigíveis
make lint      # confirma que não sobrou violação
make test      # confirma que a suíte passa
make coverage  # confirma que a cobertura atinge o mínimo
```

## Testes

- Ficam no diretório `tests/`, fora de `src/`.
- Arquivos seguem o padrão `test_*.py` e funções, `test_*`.
- Cada funcionalidade precisa de testes que verifiquem o **comportamento** implementado,
  e não apenas a existência do código.
- Testes que garantem que um contexto já entregue continua funcionando devem usar o
  marcador `regressao`:

  ```python
  import pytest


  @pytest.mark.regressao
  def test_eleicao_de_ca_permanece_valida_apos_nova_regra():
      resultado = apurar(votos_da_eleicao, regra=RegraCA())

      assert resultado.vencedor == "Chapa A"
  ```

  Marcadores não declarados no `pyproject.toml` causam falha, por conta do
  `--strict-markers`. Isso é intencional: evita que um teste seja ignorado em silêncio.

### Cobertura

A cobertura mínima definida pela equipe é de **80%**, medida com cobertura de desvio
(*branch coverage*). Abaixo disso a verificação falha, **mesmo que todos os testes
passem**.

Ao rodar `make coverage`, o relatório detalhado fica em `htmlcov/index.html` e mostra
exatamente quais linhas e desvios não foram exercitados. Na execução do pipeline, o mesmo
relatório é publicado como artefato e um resumo aparece na página do run.

## Integração contínua

O pipeline roda automaticamente nos Pull Requests e após a integração em `develop` e
`main`, com três verificações obrigatórias:

| Check | Verifica |
| --- | --- |
| `Lint` | Análise estática e formatação |
| `Tests` | Suíte de testes e cobertura mínima |
| `Build` | Geração dos artefatos e instalação a partir de um clone limpo |

Um Pull Request com qualquer check reprovado não pode ser integrado. Se algo falhar,
corrija na própria branch da mudança e envie um novo commit.

## Release

A entrega de uma versão segue o fluxo abaixo.

1. Criar a branch `release/*` a partir de `develop`.
2. Fazer apenas os ajustes de preparação da versão, sem novas funcionalidades.
3. Abrir um Pull Request da `release/*` para `main`.
4. Fazer o merge após aprovação e checks concluídos.
5. Criar a tag da versão no commit correspondente em `main`.
6. Atualizar a `develop` com as alterações presentes na `main`.

## Estrutura do projeto

```
.
├── .github/workflows/ci.yml   # Pipeline de integração contínua
├── src/votacao/               # Código-fonte do pacote
├── tests/                     # Testes automatizados
├── Makefile                   # Automação de build, lint, testes e cobertura
├── pyproject.toml             # Metadados, dependências e configuração das ferramentas
└── CONTRIBUTING.md
```

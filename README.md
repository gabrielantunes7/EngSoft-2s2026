# EngSoft-2s2026

Repositório de atividades desenvolvidas na disciplina de Engenharia de Software na Unicamp no segundo semestre de 2026.

## Sobre o projeto

Sistema de votação digital desenvolvido para gerenciar diferentes processos de decisão coletiva, como eleições acadêmicas, assembleias de acionistas e votações legislativas. A aplicação possui um motor de regras extensível, permitindo configurar diferentes critérios de elegibilidade, quórum, peso dos votos e formas de apuração para cada contexto.

## Desenvolvimento

Requer Python 3.12 ou superior e `make`.

```bash
git clone git@github.com:gabrielantunes7/EngSoft-2s2026.git
cd EngSoft-2s2026
make install
```

Verificações locais, as mesmas executadas pelo pipeline:

```bash
make lint      # análise estática
make test      # testes automatizados
make coverage  # testes com relatório de cobertura
make build     # geração dos artefatos de distribuição
make ui        # inicia a interface gráfica web (navegador: http://127.0.0.1:8080)
```

### Interface Gráfica Web (Desktop & Mobile)

A aplicação conta com uma interface gráfica web moderna e responsiva (Single Page Application nativa, sem dependências externas de frontend):

```bash
make ui
# ou diretamente via módulo Python:
.venv/bin/python -m UI --porta 8080 --abrir
```

A interface disponibiliza:
- **Painel Geral:** Visão executiva de quóruns e sessões ativas com consulta instantânea de aptidão.
- **Sessões & Urna Eletrônica:** Criação de sessões, avanço do ciclo de vida (`CRIADA` → `ABERTA` → `EM_VOTACAO` → `EM_APURACAO` → `ENCERRADA`), cabine de votação com recibo criptográfico SHA-256 e apuração visual com gráficos de barras.
- **Centro Acadêmico:** Gestão de discentes e homologação de chapas.
- **Assembleia de Acionistas:** Voto proporcional por ações, delegação e revogação de procurações com poder consolidado.
- **Congresso Nacional:** Tramitação legislativa bicameral (Câmara e Senado) com simulação de bancada para matérias PL, PLP e PEC.
- **Auditoria Criptográfica:** Inspetor de blocos da cadeia SHA-256, verificação independente de recibo de voto e âncora de encerramento (`ResumoEncerramento`).


O guia completo — pré-requisitos por sistema operacional, fluxo de branches e Pull
Requests, padrão de commits, escrita de testes e processo de release — está em
[CONTRIBUTING.md](CONTRIBUTING.md).

## Membros da equipe

Gabriel de Macedo Cavassani Montagna:   RA 242352

Gabriel Mattias Antunes:                RA 281199

Lucas Gomes Bussinger da Silva:         RA 247314

Lucas Lembo de Lara:                    RA 254467

Rafael Scalabrin Dosso:                 RA 205237

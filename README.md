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
```

O guia completo — pré-requisitos por sistema operacional, fluxo de branches e Pull
Requests, padrão de commits, escrita de testes e processo de release — está em
[CONTRIBUTING.md](CONTRIBUTING.md).

## Membros da equipe

Gabriel de Macedo Cavassani Montagna:   RA 242352

Gabriel Mattias Antunes:                RA 281199

Lucas Gomes Bussinger da Silva:         RA 247314

Lucas Lembo de Lara:                    RA 254467

Rafael Scalabrin Dosso:                 RA 205237

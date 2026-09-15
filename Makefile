PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin
DIST := dist

.PHONY: help venv install build verify lint format test coverage clean

help:
	@echo "Alvos disponíveis:"
	@echo "  make venv     - cria o ambiente virtual em $(VENV)"
	@echo "  make install  - instala o projeto em modo editável com as dependências de desenvolvimento"
	@echo "  make build    - gera os artefatos de distribuição (wheel e sdist) em $(DIST)/"
	@echo "  make verify   - instala o wheel gerado em um ambiente limpo e valida a importação"
	@echo "  make lint     - executa a análise estática (falha se houver violações)"
	@echo "  make format   - corrige automaticamente o que for corrigível e formata o código"
	@echo "  make test     - executa a suíte de testes automatizados"
	@echo "  make coverage - executa os testes medindo a cobertura e gera os relatórios"
	@echo "  make clean    - remove artefatos de build e caches"

$(BIN)/activate:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip

venv: $(BIN)/activate

install: venv
	$(BIN)/pip install -e ".[dev]"

lint: install
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

test: install
	$(BIN)/pytest

coverage: install
	$(BIN)/pytest --cov --cov-report=term-missing --cov-report=html --cov-report=xml
	@echo "Relatório HTML disponível em htmlcov/index.html"

format: install
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

build: install
	rm -rf $(DIST)
	$(BIN)/python -m build

verify: build
	rm -rf .verify-venv
	$(PYTHON) -m venv .verify-venv
	.verify-venv/bin/pip install --quiet $(DIST)/*.whl
	.verify-venv/bin/python -c "import votacao; print('votacao', votacao.__version__)"
	rm -rf .verify-venv

clean:
	rm -rf $(DIST) build .verify-venv
	rm -rf src/*.egg-info htmlcov coverage.xml .coverage .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

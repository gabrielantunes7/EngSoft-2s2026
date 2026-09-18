"""Testes unitários para o gerenciador de banco relacional SQL (SQLite)."""

import pytest

from votacao.dados.banco_sql import BancoDadosSQL
from votacao.dados.seeds import BancoDadosMock
from votacao.modelos import CasaLegislativa, TipoMateriaCongresso


@pytest.fixture
def banco_sql() -> BancoDadosSQL:
    """Fixture que cria banco em memória, carrega schema e seeds SQL."""
    db = BancoDadosSQL(database=":memory:")
    db.inicializar_schema()
    db.carregar_seeds()
    return db


def test_schema_e_seeds_tabelas_criadas(banco_sql: BancoDadosSQL):
    tabelas = [
        "discentes",
        "chapas",
        "chapa_integrantes",
        "acionistas",
        "procuracoes",
        "candidatos_conselho",
        "parlamentares",
        "materias_legislativas",
    ]
    for tabela in tabelas:
        rows = banco_sql.consultar(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabela,)
        )
        assert len(rows) == 1, f"Tabela {tabela} não foi criada pelo schema.sql."

    # Verifica se os dados foram inseridos
    qtd_discentes = banco_sql.consultar("SELECT COUNT(*) as total FROM discentes")[0]["total"]
    assert qtd_discentes >= 8

    qtd_acionistas = banco_sql.consultar("SELECT COUNT(*) as total FROM acionistas")[0]["total"]
    assert qtd_acionistas >= 6

    qtd_parlamentares = banco_sql.consultar("SELECT COUNT(*) as total FROM parlamentares")[0][
        "total"
    ]
    assert qtd_parlamentares >= 7


def test_obter_discente_sql(banco_sql: BancoDadosSQL):
    d = banco_sql.obter_discente("247314")
    assert d is not None
    assert d.ra == "247314"
    assert d.nome == "Lucas Bussinger"
    assert d.matricula_ativa is True
    assert d.formando_proximo_semestre is False
    assert d.suspenso is False

    # Discente formando
    d_formando = banco_sql.obter_discente("111222")
    assert d_formando is not None
    assert d_formando.formando_proximo_semestre is True

    # Inexistente
    assert banco_sql.obter_discente("000000") is None


def test_obter_chapa_sql(banco_sql: BancoDadosSQL):
    chapa = banco_sql.obter_chapa("chapa renova")
    assert chapa is not None
    assert chapa.nome == "Chapa Renova"
    assert "247314" in chapa.integrantes_ra
    assert len(chapa.integrantes_ra) == 3
    assert chapa.ativa is True

    # Inexistente
    assert banco_sql.obter_chapa("Chapa Inexistente") is None


def test_obter_acionista_sql(banco_sql: BancoDadosSQL):
    ac = banco_sql.obter_acionista("AC-001")
    assert ac is not None
    assert ac.id == "AC-001"
    assert ac.acoes_ordinarias == 500_000
    assert ac.bloqueado is False
    assert ac.ativo is True

    # Inexistente
    assert banco_sql.obter_acionista("AC-999") is None


def test_obter_procuracao_sql(banco_sql: BancoDadosSQL):
    proc = banco_sql.obter_procuracao("AC-001", "PROC-101")
    assert proc is not None
    assert proc.outorgante_id == "AC-001"
    assert proc.procurador_id == "PROC-101"
    assert proc.ativa is True
    assert proc.data_expiracao is not None

    # Inexistente
    assert banco_sql.obter_procuracao("AC-001", "PROC-FANTASMA") is None


def test_obter_parlamentar_sql(banco_sql: BancoDadosSQL):
    dep = banco_sql.obter_parlamentar("DEP-001")
    assert dep is not None
    assert dep.id == "DEP-001"
    assert dep.casa == CasaLegislativa.CAMARA
    assert dep.em_exercicio is True

    # Inexistente
    assert banco_sql.obter_parlamentar("DEP-999") is None


def test_obter_materia_sql(banco_sql: BancoDadosSQL):
    mat = banco_sql.obter_materia("PL-101/2026")
    assert mat is not None
    assert mat.tipo == TipoMateriaCongresso.LEI_ORDINARIA
    assert mat.casa_atual == CasaLegislativa.CAMARA
    assert mat.ativa is True

    # Inexistente
    assert banco_sql.obter_materia("PL-INEXISTENTE") is None


def test_banco_dados_mock_usar_sql():
    banco = BancoDadosMock(popular=True, usar_sql=True)
    # Verifica que os repositórios foram populados a partir das tabelas SQL
    assert len(banco.ca.listar_discentes()) >= 8
    assert len(banco.ca.listar_chapas()) >= 4
    assert len(banco.assembleia.listar_acionistas()) >= 6
    assert len(banco.congresso.listar_parlamentares()) >= 7

    # Testa busca nos repositórios carregados via SQL
    d = banco.ca.obter_discente("247314")
    assert d is not None
    assert d.nome == "Lucas Bussinger"

    # Testa executar query direta no banco_sql associado
    rows = banco.banco_sql.consultar(
        "SELECT COUNT(*) AS total FROM discentes WHERE matricula_ativa = 1"
    )
    assert rows[0]["total"] >= 6


def test_fechar_banco_sql(banco_sql: BancoDadosSQL):
    import sqlite3

    banco_sql.fechar()
    with pytest.raises(sqlite3.ProgrammingError):
        banco_sql.consultar("SELECT 1")


def test_executar_e_procuracao_sem_expiracao(banco_sql: BancoDadosSQL):
    # Testa método executar
    banco_sql.executar(
        "INSERT INTO procuracoes (outorgante_id, procurador_id, data_expiracao, ativa) "
        "VALUES (?, ?, NULL, 1)",
        ("AC-001", "PROC-SEMDATA"),
    )
    proc = banco_sql.obter_procuracao("AC-001", "PROC-SEMDATA")
    assert proc is not None
    assert proc.data_expiracao is None
    assert proc.ativa is True

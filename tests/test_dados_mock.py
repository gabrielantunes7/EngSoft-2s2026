"""Testes unitários para a camada de dados mockada e repositórios."""

from datetime import UTC, datetime, timedelta

import pytest

from votacao.dados import (
    Acionista,
    BancoDadosMock,
    CandidatoConselho,
    ChapaCA,
    Discente,
    MateriaLegislativa,
    Parlamentar,
    Procuracao,
    RepositorioAssembleia,
    RepositorioCA,
    RepositorioCongresso,
)
from votacao.modelos import CasaLegislativa, TipoMateriaCongresso


def test_discente_validacoes():
    d = Discente(ra="247314", nome="Lucas", curso="EngSoft")
    assert d.ra == "247314"
    assert d.nome == "Lucas"
    assert d.curso == "EngSoft"
    assert d.matricula_ativa is True

    with pytest.raises(ValueError, match="RA do discente não pode ser vazio"):
        Discente(ra="   ", nome="Lucas", curso="EngSoft")

    with pytest.raises(ValueError, match="nome do discente não pode ser vazio"):
        Discente(ra="247314", nome="  ", curso="EngSoft")


def test_chapa_ca_validacoes():
    chapa = ChapaCA(nome="Chapa Teste", integrantes_ra=("247314", "242352"))
    assert chapa.nome == "Chapa Teste"
    assert len(chapa.integrantes_ra) == 2

    with pytest.raises(ValueError, match="nome da chapa não pode ser vazio"):
        ChapaCA(nome="   ")


def test_repositorio_ca_operacoes():
    repo = RepositorioCA()
    d1 = Discente(ra="111", nome="Aluno 1", curso="EC")
    d2 = Discente(ra="222", nome="Aluno 2", curso="EC")
    repo.adicionar_discente(d1)
    repo.adicionar_discente(d2)

    assert repo.obter_discente("111") == d1
    assert repo.obter_discente("999") is None
    assert len(repo.listar_discentes()) == 2

    c1 = ChapaCA(nome="Chapa Alpha", integrantes_ra=("111",))
    repo.adicionar_chapa(c1)
    assert repo.obter_chapa("chapa alpha") == c1
    assert len(repo.listar_chapas()) == 1

    repo.limpar()
    assert repo.listar_discentes() == []
    assert repo.listar_chapas() == []


def test_acionista_validacoes():
    ac = Acionista(id="AC-1", nome="Alpha S.A.", acoes_ordinarias=1000)
    assert ac.id == "AC-1"
    assert ac.acoes_ordinarias == 1000

    with pytest.raises(ValueError, match="identificador do acionista não pode ser vazio"):
        Acionista(id="  ", nome="Alpha", acoes_ordinarias=10)

    with pytest.raises(ValueError, match="nome do acionista não pode ser vazio"):
        Acionista(id="AC-1", nome="  ", acoes_ordinarias=10)

    with pytest.raises(ValueError, match="ações ordinárias não pode ser negativa"):
        Acionista(id="AC-1", nome="Alpha", acoes_ordinarias=-1)

    with pytest.raises(ValueError, match="ações preferenciais não pode ser negativa"):
        Acionista(id="AC-1", nome="Alpha", acoes_ordinarias=10, acoes_preferenciais=-2)


def test_procuracao_vigencia_e_validacoes():
    agora = datetime.now(UTC)
    proc_valida = Procuracao(
        outorgante_id="AC-1",
        procurador_id="P-1",
        data_expiracao=agora + timedelta(days=1),
        ativa=True,
    )
    assert proc_valida.esta_vigente(agora) is True

    proc_expirada = Procuracao(
        outorgante_id="AC-1",
        procurador_id="P-2",
        data_expiracao=agora - timedelta(days=1),
        ativa=True,
    )
    assert proc_expirada.esta_vigente(agora) is False

    proc_revogada = Procuracao(
        outorgante_id="AC-1",
        procurador_id="P-3",
        data_expiracao=agora + timedelta(days=1),
        ativa=False,
    )
    assert proc_revogada.esta_vigente(agora) is False

    # Validação de campos obrigatórios
    with pytest.raises(ValueError, match="outorgante da procuração não pode ser vazio"):
        Procuracao(outorgante_id="  ", procurador_id="P-1")

    with pytest.raises(ValueError, match="procurador da procuração não pode ser vazio"):
        Procuracao(outorgante_id="AC-1", procurador_id="  ")

    # Comparação com datetime naive vs aware
    proc_naive = Procuracao(
        outorgante_id="AC-1",
        procurador_id="P-4",
        data_expiracao=datetime(2030, 1, 1),
        ativa=True,
    )
    assert proc_naive.esta_vigente(agora) is True

    proc_aware = Procuracao(
        outorgante_id="AC-1",
        procurador_id="P-5",
        data_expiracao=datetime(2030, 1, 1, tzinfo=UTC),
        ativa=True,
    )
    assert proc_aware.esta_vigente(datetime(2026, 1, 1)) is True


def test_candidato_conselho_validacoes():
    c = CandidatoConselho(id="C-1", nome="Dr. Roberto")
    assert c.id == "C-1"
    assert c.titular_acoes is True
    assert c.conflito_interesse is False

    with pytest.raises(ValueError, match="ID do candidato ao conselho não pode ser vazio"):
        CandidatoConselho(id="  ", nome="Roberto")

    with pytest.raises(ValueError, match="nome do candidato ao conselho não pode ser vazio"):
        CandidatoConselho(id="C-1", nome="  ")


def test_repositorio_assembleia_operacoes():
    repo = RepositorioAssembleia()
    a1 = Acionista(id="A1", nome="Holding 1", acoes_ordinarias=1000)
    a2 = Acionista(id="A2", nome="Holding 2", acoes_ordinarias=500, bloqueado=True)
    a3 = Acionista(id="A3", nome="Holding 3", acoes_ordinarias=200, ativo=False)
    repo.adicionar_acionista(a1)
    repo.adicionar_acionista(a2)
    repo.adicionar_acionista(a3)

    assert repo.obter_acionista("A1") == a1
    assert repo.obter_acionista("inexistente") is None
    assert len(repo.listar_acionistas()) == 3
    # Apenas A1 é ativo e não-bloqueado
    assert repo.total_capital_votante() == 1000

    p = Procuracao(outorgante_id="A1", procurador_id="PROC-1")
    repo.adicionar_procuracao(p)
    assert repo.obter_procuracao("A1", "PROC-1") == p
    assert repo.listar_procuracoes_do_outorgante("A1") == [p]

    cand = CandidatoConselho(id="CAND-1", nome="Silvia")
    repo.adicionar_candidato_conselho(cand)
    assert repo.obter_candidato_conselho("CAND-1") == cand
    assert len(repo.listar_candidatos_conselho()) == 1

    repo.limpar()
    assert repo.listar_acionistas() == []
    assert repo.listar_candidatos_conselho() == []


def test_parlamentar_e_materia_validacoes():
    p = Parlamentar(
        id="DEP-1",
        nome="Deputado A",
        casa=CasaLegislativa.CAMARA,
        partido="XYZ",
        uf="SP",
    )
    assert p.id == "DEP-1"
    assert p.em_exercicio is True

    with pytest.raises(ValueError, match="identificador do parlamentar não pode ser vazio"):
        Parlamentar(id="  ", nome="A", casa=CasaLegislativa.CAMARA, partido="X", uf="SP")

    with pytest.raises(ValueError, match="nome do parlamentar não pode ser vazio"):
        Parlamentar(id="DEP-1", nome="  ", casa=CasaLegislativa.CAMARA, partido="X", uf="SP")

    with pytest.raises(ValueError, match="partido do parlamentar não pode ser vazio"):
        Parlamentar(id="DEP-1", nome="A", casa=CasaLegislativa.CAMARA, partido="  ", uf="SP")

    with pytest.raises(ValueError, match="UF do parlamentar não pode ser vazia"):
        Parlamentar(id="DEP-1", nome="A", casa=CasaLegislativa.CAMARA, partido="X", uf="  ")

    mat = MateriaLegislativa(
        id="PL-1/2026",
        tipo=TipoMateriaCongresso.LEI_ORDINARIA,
        casa_atual=CasaLegislativa.CAMARA,
    )
    assert mat.id == "PL-1/2026"

    with pytest.raises(ValueError, match="identificador da matéria legislativa não pode ser vazio"):
        MateriaLegislativa(
            id="  ",
            tipo=TipoMateriaCongresso.LEI_ORDINARIA,
            casa_atual=CasaLegislativa.CAMARA,
        )


def test_repositorio_congresso_operacoes():
    repo = RepositorioCongresso()
    dep1 = Parlamentar(
        id="D1",
        nome="Dep 1",
        casa=CasaLegislativa.CAMARA,
        partido="P1",
        uf="SP",
        em_exercicio=True,
    )
    dep2 = Parlamentar(
        id="D2",
        nome="Dep 2",
        casa=CasaLegislativa.CAMARA,
        partido="P2",
        uf="RJ",
        em_exercicio=False,
        licenciado=True,
    )
    sen1 = Parlamentar(
        id="S1",
        nome="Sen 1",
        casa=CasaLegislativa.SENADO,
        partido="P3",
        uf="MG",
        em_exercicio=True,
    )
    repo.adicionar_parlamentar(dep1)
    repo.adicionar_parlamentar(dep2)
    repo.adicionar_parlamentar(sen1)

    assert repo.obter_parlamentar("D1") == dep1
    assert repo.obter_parlamentar("inexistente") is None
    assert len(repo.listar_parlamentares()) == 3
    assert len(repo.listar_parlamentares(CasaLegislativa.CAMARA)) == 2
    assert len(repo.listar_parlamentares(CasaLegislativa.SENADO)) == 1

    assert repo.total_em_exercicio(CasaLegislativa.CAMARA) == 1
    assert repo.total_em_exercicio(CasaLegislativa.SENADO) == 1

    m = MateriaLegislativa(
        id="PL-10/2026",
        tipo=TipoMateriaCongresso.LEI_ORDINARIA,
        casa_atual=CasaLegislativa.CAMARA,
    )
    repo.adicionar_materia(m)
    assert repo.obter_materia("pl-10/2026") == m
    assert len(repo.listar_materias(CasaLegislativa.CAMARA)) == 1
    assert len(repo.listar_materias(CasaLegislativa.SENADO)) == 0

    repo.limpar()
    assert repo.listar_parlamentares() == []
    assert repo.listar_materias() == []


def test_banco_dados_mock_seeds():
    banco = BancoDadosMock()
    assert len(banco.ca.listar_discentes()) >= 5
    assert len(banco.ca.listar_chapas()) >= 3

    assert len(banco.assembleia.listar_acionistas()) >= 5
    assert len(banco.assembleia.listar_candidatos_conselho()) >= 2

    assert len(banco.congresso.listar_parlamentares()) >= 5
    assert len(banco.congresso.listar_materias()) >= 3

    banco.limpar_todos()
    assert len(banco.ca.listar_discentes()) == 0
    assert len(banco.assembleia.listar_acionistas()) == 0
    assert len(banco.congresso.listar_parlamentares()) == 0

    banco.recarregar_dados_padrao()
    assert len(banco.ca.listar_discentes()) >= 5

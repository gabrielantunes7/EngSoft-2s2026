"""Testes unitários para as regras de Centro Acadêmico (RegraCA)."""

import pytest

from votacao.modelos import StatusResultado, Voto
from votacao.regras.ca import RegraCA


def test_regra_ca_parametros_invalidos():
    with pytest.raises(ValueError, match="não pode ser negativo"):
        RegraCA(quorum_minimo_votantes=-1)

    with pytest.raises(ValueError, match=r"deve estar entre 0\.0 e 1\.0"):
        RegraCA(percentual_quorum_minimo=1.5)


def test_regra_ca_vitoria_maioria_simples():
    regra = RegraCA(quorum_minimo_votantes=3)
    votos = [
        Voto(eleitor_id="aluno1", opcao="Chapa Renova"),
        Voto(eleitor_id="aluno2", opcao="Chapa Renova"),
        Voto(eleitor_id="aluno3", opcao="Chapa Avanca"),
        Voto(eleitor_id="aluno4", opcao="BRANCO"),
    ]

    resultado = regra.apurar(votos=votos, total_aptos=10)

    assert resultado.quorum_atingido is True
    assert resultado.status == StatusResultado.ELEITO
    assert resultado.vencedor_ou_decisao == "CHAPA RENOVA"
    assert resultado.total_votantes == 4
    assert resultado.total_peso_apurado == 4
    assert resultado.percentual_vencedor == pytest.approx(66.67, 0.01)
    assert resultado.detalhes["total_validos"] == 3
    assert resultado.detalhes["brancos"] == 1


def test_regra_ca_quorum_insuficiente_absoluto():
    regra = RegraCA(quorum_minimo_votantes=5)
    votos = [
        Voto(eleitor_id="aluno1", opcao="Chapa 1"),
        Voto(eleitor_id="aluno2", opcao="Chapa 1"),
    ]

    resultado = regra.apurar(votos=votos, total_aptos=50)

    assert resultado.quorum_atingido is False
    assert resultado.status == StatusResultado.QUORUM_INSUFICIENTE
    assert resultado.vencedor_ou_decisao is None


def test_regra_ca_quorum_percentual():
    regra = RegraCA(percentual_quorum_minimo=0.20)
    votos_insuficientes = [Voto(eleitor_id=f"a{i}", opcao="Chapa 1") for i in range(15)]
    votos_suficientes = [Voto(eleitor_id=f"a{i}", opcao="Chapa 1") for i in range(25)]

    res_insuficiente = regra.apurar(votos=votos_insuficientes, total_aptos=100)
    assert res_insuficiente.quorum_atingido is False
    assert res_insuficiente.status == StatusResultado.QUORUM_INSUFICIENTE

    assert regra.validar_quorum(total_aptos=0, votos=votos_suficientes) is False

    res_suficiente = regra.apurar(votos=votos_suficientes, total_aptos=100)
    assert res_suficiente.quorum_atingido is True
    assert res_suficiente.status == StatusResultado.ELEITO


def test_regra_ca_empate_entre_chapas():
    regra = RegraCA()
    votos = [
        Voto(eleitor_id="aluno1", opcao="Chapa A"),
        Voto(eleitor_id="aluno2", opcao="Chapa B"),
    ]

    resultado = regra.apurar(votos=votos)

    assert resultado.status == StatusResultado.EMPATE
    assert resultado.vencedor_ou_decisao is None
    assert resultado.percentual_vencedor == 50.0
    assert set(resultado.detalhes["chapas_empatadas"]) == {"CHAPA A", "CHAPA B"}


def test_regra_ca_apenas_brancos_e_nulos():
    regra = RegraCA()
    votos = [
        Voto(eleitor_id="aluno1", opcao="BRANCO"),
        Voto(eleitor_id="aluno2", opcao="NULO"),
    ]

    resultado = regra.apurar(votos=votos)

    assert resultado.status == StatusResultado.EMPATE
    assert resultado.vencedor_ou_decisao is None
    assert resultado.percentual_vencedor == 0.0


@pytest.mark.parametrize(
    ("id_caso", "quorum_minimo", "percentual_minimo", "deve_aceitar", "trecho_erro"),
    [
        ("quorum_minimo_negativo", -1, 0.0, False, "não pode ser negativo"),
        ("quorum_minimo_zero", 0, 0.0, True, ""),
        ("quorum_minimo_um", 1, 0.0, True, ""),
        (
            "percentual_abaixo_de_zero",
            0,
            -0.01,
            False,
            r"deve estar entre 0\.0 e 1\.0",
        ),
        ("percentual_zero_exato", 0, 0.0, True, ""),
        ("percentual_logo_acima_de_zero", 0, 0.01, True, ""),
        ("percentual_logo_abaixo_de_um", 0, 0.99, True, ""),
        ("percentual_um_exato", 0, 1.0, True, ""),
        (
            "percentual_acima_de_um",
            0,
            1.01,
            False,
            r"deve estar entre 0\.0 e 1\.0",
        ),
    ],
)
def test_regra_ca_construtor_fronteiras(
    id_caso: str,
    quorum_minimo: int,
    percentual_minimo: float,
    deve_aceitar: bool,
    trecho_erro: str,
):
    if deve_aceitar:
        regra = RegraCA(
            quorum_minimo_votantes=quorum_minimo,
            percentual_quorum_minimo=percentual_minimo,
        )
        assert regra.quorum_minimo_votantes == quorum_minimo, id_caso
        assert regra.percentual_quorum_minimo == percentual_minimo, id_caso
    else:
        with pytest.raises(ValueError, match=trecho_erro):
            RegraCA(
                quorum_minimo_votantes=quorum_minimo,
                percentual_quorum_minimo=percentual_minimo,
            )


@pytest.mark.parametrize(
    ("id_caso", "qtd_votantes", "esperado_quorum", "esperado_status"),
    [
        ("abaixo_quorum_4", 4, False, StatusResultado.QUORUM_INSUFICIENTE),
        ("no_limite_exato_5", 5, True, StatusResultado.ELEITO),
        ("acima_quorum_6", 6, True, StatusResultado.ELEITO),
    ],
)
def test_regra_ca_quorum_absoluto_fronteira(
    id_caso: str,
    qtd_votantes: int,
    esperado_quorum: bool,
    esperado_status: StatusResultado,
):
    regra = RegraCA(quorum_minimo_votantes=5)
    votos = [Voto(eleitor_id=f"aluno_{i}", opcao="Chapa Unica") for i in range(qtd_votantes)]

    assert regra.validar_quorum(total_aptos=50, votos=votos) is esperado_quorum, id_caso
    resultado = regra.apurar(votos=votos, total_aptos=50)
    assert resultado.quorum_atingido is esperado_quorum, id_caso
    assert resultado.status == esperado_status, id_caso


@pytest.mark.parametrize(
    ("id_caso", "total_aptos", "qtd_votantes", "esperado_quorum", "esperado_status"),
    [
        ("total_aptos_negativo", -1, 1, False, StatusResultado.QUORUM_INSUFICIENTE),
        ("total_aptos_zero", 0, 1, False, StatusResultado.QUORUM_INSUFICIENTE),
        ("total_aptos_um_com_um_voto", 1, 1, True, StatusResultado.ELEITO),
        ("abaixo_percentual_19", 100, 19, False, StatusResultado.QUORUM_INSUFICIENTE),
        ("no_limite_percentual_20", 100, 20, True, StatusResultado.ELEITO),
        ("acima_percentual_21", 100, 21, True, StatusResultado.ELEITO),
    ],
)
def test_regra_ca_quorum_percentual_fronteira(
    id_caso: str,
    total_aptos: int,
    qtd_votantes: int,
    esperado_quorum: bool,
    esperado_status: StatusResultado,
):
    regra = RegraCA(percentual_quorum_minimo=0.20)
    votos = [Voto(eleitor_id=f"aluno_{i}", opcao="Chapa Integracao") for i in range(qtd_votantes)]

    assert regra.validar_quorum(total_aptos=total_aptos, votos=votos) is esperado_quorum, id_caso
    resultado = regra.apurar(votos=votos, total_aptos=total_aptos)
    assert resultado.quorum_atingido is esperado_quorum, id_caso
    assert resultado.status == esperado_status, id_caso


def test_regra_ca_apuracao_detalhes_e_empate():
    regra = RegraCA()

    votos_lider = [
        Voto(eleitor_id="a1", opcao="  chapa alpha "),
        Voto(eleitor_id="a2", opcao="CHAPA ALPHA"),
        Voto(eleitor_id="a3", opcao="Chapa Beta"),
        Voto(eleitor_id="a4", opcao="branco"),
        Voto(eleitor_id="a5", opcao="nulo"),
    ]
    res_lider = regra.apurar(votos_lider, total_aptos=10)
    assert res_lider.status == StatusResultado.ELEITO
    assert res_lider.vencedor_ou_decisao == "CHAPA ALPHA"
    assert res_lider.detalhes == {"total_validos": 3, "brancos": 1, "nulos": 1}

    votos_empate = [
        Voto(eleitor_id="a1", opcao="Chapa 1"),
        Voto(eleitor_id="a2", opcao="Chapa 2"),
        Voto(eleitor_id="a3", opcao="Chapa 3"),
        Voto(eleitor_id="a4", opcao="NULO"),
    ]
    res_empate = regra.apurar(votos_empate, total_aptos=10)
    assert res_empate.status == StatusResultado.EMPATE
    assert res_empate.vencedor_ou_decisao is None
    assert res_empate.percentual_vencedor == pytest.approx(33.33, 0.01)
    assert res_empate.detalhes["votos_cada"] == 1
    assert set(res_empate.detalhes["chapas_empatadas"]) == {"CHAPA 1", "CHAPA 2", "CHAPA 3"}

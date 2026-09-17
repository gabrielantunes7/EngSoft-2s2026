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

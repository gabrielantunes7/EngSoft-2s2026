"""Testes unitários para as regras de Assembleias de Acionistas (RegraAssembleia)."""

import pytest

from votacao.modelos import (
    StatusResultado,
    TipoDecisaoAssembleia,
    Voto,
)
from votacao.regras.assembleia import RegraAssembleia


def test_regra_assembleia_parametros_invalidos():
    with pytest.raises(ValueError, match=r"deve estar entre 0\.0 e 1\.0"):
        RegraAssembleia(percentual_quorum_instalacao=1.2)


def test_regra_assembleia_voto_ponderado_maioria_simples():
    regra = RegraAssembleia(tipo_decisao=TipoDecisaoAssembleia.MAIORIA_SIMPLES)
    votos = [
        Voto(eleitor_id="investidor_majoritario", opcao="SIM", peso=7000),
        Voto(eleitor_id="investidor_minoritario_1", opcao="NAO", peso=2000),
        Voto(eleitor_id="investidor_minoritario_2", opcao="NAO", peso=1000),
    ]

    resultado = regra.apurar(votos=votos)

    assert resultado.status == StatusResultado.APROVADO
    assert resultado.vencedor_ou_decisao == "SIM"
    assert resultado.total_votantes == 3
    assert resultado.total_peso_apurado == 10000
    assert resultado.percentual_vencedor == 70.0


def test_regra_assembleia_quorum_instalacao_insuficiente():
    # Exige 50% de 100.000 ações = 50.000 ações presentes
    regra = RegraAssembleia(
        tipo_decisao=TipoDecisaoAssembleia.MAIORIA_SIMPLES,
        percentual_quorum_instalacao=0.50,
    )
    votos = [
        Voto(eleitor_id="acionista1", opcao="SIM", peso=30000),
    ]

    resultado = regra.apurar(votos=votos, total_aptos=100000)

    assert resultado.quorum_atingido is False
    assert resultado.status == StatusResultado.QUORUM_INSUFICIENTE
    assert resultado.vencedor_ou_decisao is None

    # Quando total_aptos <= 0 e percentual > 0
    assert regra.validar_quorum(total_aptos=0, votos=votos) is False


def test_regra_assembleia_maioria_absoluta():
    regra = RegraAssembleia(
        tipo_decisao=TipoDecisaoAssembleia.MAIORIA_ABSOLUTA,
        base_calculo_sobre_total_capital=True,
    )
    # Total capital = 10000. Precisa de > 5000 ações a favor.
    votos_aprovados = [
        Voto(eleitor_id="a1", opcao="SIM", peso=5001),
        Voto(eleitor_id="a2", opcao="NAO", peso=4999),
    ]
    votos_rejeitados = [
        Voto(eleitor_id="a1", opcao="SIM", peso=5000),
        Voto(eleitor_id="a2", opcao="NAO", peso=1000),
    ]

    res_ok = regra.apurar(votos=votos_aprovados, total_aptos=10000)
    assert res_ok.status == StatusResultado.APROVADO

    res_rejeitado = regra.apurar(votos=votos_rejeitados, total_aptos=10000)
    assert res_rejeitado.status == StatusResultado.REJEITADO


def test_regra_assembleia_qualificada_dois_tercos():
    regra = RegraAssembleia(tipo_decisao=TipoDecisaoAssembleia.QUALIFICADA_DOIS_TERCOS)
    # Total presente: 9000. 2/3 = 6000.
    votos_aprovados = [
        Voto(eleitor_id="a1", opcao="SIM", peso=6000),
        Voto(eleitor_id="a2", opcao="NAO", peso=3000),
    ]
    votos_rejeitados = [
        Voto(eleitor_id="a1", opcao="SIM", peso=5999),
        Voto(eleitor_id="a2", opcao="NAO", peso=3001),
    ]

    assert regra.apurar(votos=votos_aprovados).status == StatusResultado.APROVADO
    assert regra.apurar(votos=votos_rejeitados).status == StatusResultado.REJEITADO


def test_regra_assembleia_qualificada_tres_quintos():
    regra = RegraAssembleia(tipo_decisao=TipoDecisaoAssembleia.QUALIFICADA_TRES_QUINTOS)
    # Total presente: 10000. 3/5 = 6000.
    votos_aprovados = [
        Voto(eleitor_id="a1", opcao="SIM", peso=6000),
        Voto(eleitor_id="a2", opcao="NAO", peso=4000),
    ]
    votos_rejeitados = [
        Voto(eleitor_id="a1", opcao="SIM", peso=5999),
        Voto(eleitor_id="a2", opcao="NAO", peso=4001),
    ]

    assert regra.apurar(votos=votos_aprovados).status == StatusResultado.APROVADO
    assert regra.apurar(votos=votos_rejeitados).status == StatusResultado.REJEITADO


def test_regra_assembleia_sem_votos_deliberativos():
    regra = RegraAssembleia()
    votos = [Voto(eleitor_id="a1", opcao="ABSTENCAO", peso=1000)]

    res = regra.apurar(votos=votos)
    assert res.status == StatusResultado.REJEITADO
    assert res.vencedor_ou_decisao == "NAO"


def test_regra_assembleia_base_zero():
    regra = RegraAssembleia(
        tipo_decisao=TipoDecisaoAssembleia.QUALIFICADA_DOIS_TERCOS,
        base_calculo_sobre_total_capital=True,
    )
    voto_simples = [Voto(eleitor_id="a1", opcao="SIM", peso=100)]
    res = regra.apurar(votos=voto_simples, total_aptos=0)
    assert res.status == StatusResultado.REJEITADO

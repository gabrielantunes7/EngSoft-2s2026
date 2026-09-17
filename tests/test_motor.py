"""Testes de integração e regressão para o MotorApuracao."""

import pytest

from votacao.modelos import (
    CasaLegislativa,
    StatusResultado,
    TipoDecisaoAssembleia,
    TipoMateriaCongresso,
    Voto,
)
from votacao.motor import MotorApuracao
from votacao.regras import RegraAssembleia, RegraCA, RegraCongresso


def test_motor_tipo_regra_invalido():
    with pytest.raises(TypeError, match="deve implementar a interface RegraDeVotacao"):
        MotorApuracao.apurar(votos=[], regra="regra_invalida")  # type: ignore[arg-type]


@pytest.mark.regressao
def test_motor_apuracao_contexto_ca():
    votos = [
        Voto(eleitor_id="ra_01", opcao="Chapa Uniao"),
        Voto(eleitor_id="ra_02", opcao="Chapa Uniao"),
        Voto(eleitor_id="ra_03", opcao="Chapa Progresso"),
    ]
    resultado = MotorApuracao.apurar(
        votos=votos,
        regra=RegraCA(quorum_minimo_votantes=2),
        total_aptos_ou_capital=50,
    )

    assert resultado.quorum_atingido is True
    assert resultado.status == StatusResultado.ELEITO
    assert resultado.vencedor_ou_decisao == "CHAPA UNIAO"


@pytest.mark.regressao
def test_motor_apuracao_contexto_assembleia():
    votos = [
        Voto(eleitor_id="fundo_investimento", opcao="SIM", peso=80000),
        Voto(eleitor_id="acionistas_varejo", opcao="NAO", peso=20000),
    ]
    resultado = MotorApuracao.apurar(
        votos=votos,
        regra=RegraAssembleia(tipo_decisao=TipoDecisaoAssembleia.QUALIFICADA_DOIS_TERCOS),
        total_aptos_ou_capital=100000,
    )

    assert resultado.status == StatusResultado.APROVADO
    assert resultado.vencedor_ou_decisao == "SIM"
    assert resultado.percentual_vencedor == 80.0


@pytest.mark.regressao
def test_motor_apuracao_contexto_congresso():
    # Votação de PEC na Câmara: 310 deputados a favor, 40 contra
    votos = [Voto(eleitor_id=f"dep_{i}", opcao="SIM") for i in range(310)] + [
        Voto(eleitor_id=f"dep_{i}", opcao="NAO") for i in range(310, 350)
    ]
    resultado = MotorApuracao.apurar(
        votos=votos,
        regra=RegraCongresso(materia=TipoMateriaCongresso.PEC, casa=CasaLegislativa.CAMARA),
    )

    assert resultado.status == StatusResultado.APROVADO
    assert resultado.vencedor_ou_decisao == "SIM"
    assert resultado.detalhes["minimo_votos_sim_exigido"] == 308

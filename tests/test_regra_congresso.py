"""Testes unitários para as regras do Congresso Nacional (RegraCongresso)."""

from votacao.modelos import (
    CasaLegislativa,
    StatusResultado,
    TipoMateriaCongresso,
    Voto,
)
from votacao.regras.congresso import RegraCongresso


def test_congresso_quorum_insuficiente_camara():
    regra = RegraCongresso(materia=TipoMateriaCongresso.LEI_ORDINARIA, casa=CasaLegislativa.CAMARA)
    # Apenas 200 deputados presentes (mínimo exigido: 257)
    votos = [Voto(eleitor_id=f"dep_{i}", opcao="SIM") for i in range(200)]

    resultado = regra.apurar(votos=votos)

    assert resultado.quorum_atingido is False
    assert resultado.status == StatusResultado.QUORUM_INSUFICIENTE
    assert resultado.vencedor_ou_decisao is None


def test_congresso_lei_ordinaria_aprovacao_e_rejeicao():
    regra = RegraCongresso(materia=TipoMateriaCongresso.LEI_ORDINARIA, casa=CasaLegislativa.CAMARA)
    # 260 presentes
    votos_aprovados = [Voto(eleitor_id=f"dep_{i}", opcao="SIM") for i in range(140)] + [
        Voto(eleitor_id=f"dep_{i}", opcao="NAO") for i in range(140, 260)
    ]
    votos_rejeitados = [Voto(eleitor_id=f"dep_{i}", opcao="SIM") for i in range(120)] + [
        Voto(eleitor_id=f"dep_{i}", opcao="NAO") for i in range(120, 260)
    ]

    res_aprovado = regra.apurar(votos=votos_aprovados)
    assert res_aprovado.status == StatusResultado.APROVADO
    assert res_aprovado.vencedor_ou_decisao == "SIM"

    res_rejeitado = regra.apurar(votos=votos_rejeitados)
    assert res_rejeitado.status == StatusResultado.REJEITADO
    assert res_rejeitado.vencedor_ou_decisao == "NAO"


def test_congresso_lei_complementar():
    # Câmara: exige 257 votos SIM
    regra_camara = RegraCongresso(
        materia=TipoMateriaCongresso.LEI_COMPLEMENTAR,
        casa=CasaLegislativa.CAMARA,
    )
    votos_camara_ok = [Voto(eleitor_id=f"dep_{i}", opcao="SIM") for i in range(257)] + [
        Voto(eleitor_id=f"dep_{i}", opcao="NAO") for i in range(257, 300)
    ]
    votos_camara_falha = [Voto(eleitor_id=f"dep_{i}", opcao="SIM") for i in range(256)] + [
        Voto(eleitor_id=f"dep_{i}", opcao="NAO") for i in range(256, 300)
    ]

    assert regra_camara.apurar(votos=votos_camara_ok).status == StatusResultado.APROVADO
    assert regra_camara.apurar(votos=votos_camara_falha).status == StatusResultado.REJEITADO

    # Senado: exige 41 votos SIM
    regra_senado = RegraCongresso(
        materia=TipoMateriaCongresso.LEI_COMPLEMENTAR,
        casa=CasaLegislativa.SENADO,
    )
    votos_senado_ok = [Voto(eleitor_id=f"sen_{i}", opcao="SIM") for i in range(41)] + [
        Voto(eleitor_id=f"sen_{i}", opcao="NAO") for i in range(41, 50)
    ]
    votos_senado_falha = [Voto(eleitor_id=f"sen_{i}", opcao="SIM") for i in range(40)] + [
        Voto(eleitor_id=f"sen_{i}", opcao="NAO") for i in range(40, 50)
    ]

    assert regra_senado.apurar(votos=votos_senado_ok).status == StatusResultado.APROVADO
    assert regra_senado.apurar(votos=votos_senado_falha).status == StatusResultado.REJEITADO


def test_congresso_pec():
    # Câmara: exige 308 votos SIM
    regra_pec_camara = RegraCongresso(
        materia=TipoMateriaCongresso.PEC,
        casa=CasaLegislativa.CAMARA,
    )
    votos_pec_camara_ok = [Voto(eleitor_id=f"dep_{i}", opcao="SIM") for i in range(308)] + [
        Voto(eleitor_id=f"dep_{i}", opcao="NAO") for i in range(308, 350)
    ]
    votos_pec_camara_falha = [Voto(eleitor_id=f"dep_{i}", opcao="SIM") for i in range(307)] + [
        Voto(eleitor_id=f"dep_{i}", opcao="NAO") for i in range(307, 350)
    ]

    assert regra_pec_camara.apurar(votos=votos_pec_camara_ok).status == StatusResultado.APROVADO
    assert regra_pec_camara.apurar(votos=votos_pec_camara_falha).status == StatusResultado.REJEITADO

    # Senado: exige 49 votos SIM
    regra_pec_senado = RegraCongresso(
        materia=TipoMateriaCongresso.PEC,
        casa=CasaLegislativa.SENADO,
    )
    votos_pec_senado_ok = [Voto(eleitor_id=f"sen_{i}", opcao="SIM") for i in range(49)] + [
        Voto(eleitor_id=f"sen_{i}", opcao="NAO") for i in range(49, 60)
    ]
    votos_pec_senado_falha = [Voto(eleitor_id=f"sen_{i}", opcao="SIM") for i in range(48)] + [
        Voto(eleitor_id=f"sen_{i}", opcao="NAO") for i in range(48, 60)
    ]

    assert regra_pec_senado.apurar(votos=votos_pec_senado_ok).status == StatusResultado.APROVADO
    assert regra_pec_senado.apurar(votos=votos_pec_senado_falha).status == StatusResultado.REJEITADO

"""Testes unitários para as regras do Congresso Nacional (RegraCongresso)."""

import pytest

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


@pytest.mark.parametrize(
    ("id_caso", "casa", "presentes", "esperado_quorum", "esperado_status"),
    [
        (
            "camara_abaixo_256",
            CasaLegislativa.CAMARA,
            256,
            False,
            StatusResultado.QUORUM_INSUFICIENTE,
        ),
        (
            "camara_limite_exato_257",
            CasaLegislativa.CAMARA,
            257,
            True,
            StatusResultado.APROVADO,
        ),
        (
            "camara_acima_258",
            CasaLegislativa.CAMARA,
            258,
            True,
            StatusResultado.APROVADO,
        ),
        (
            "senado_abaixo_40",
            CasaLegislativa.SENADO,
            40,
            False,
            StatusResultado.QUORUM_INSUFICIENTE,
        ),
        (
            "senado_limite_exato_41",
            CasaLegislativa.SENADO,
            41,
            True,
            StatusResultado.APROVADO,
        ),
        (
            "senado_acima_42",
            CasaLegislativa.SENADO,
            42,
            True,
            StatusResultado.APROVADO,
        ),
    ],
)
def test_congresso_quorum_instalacao_fronteiras(
    id_caso: str,
    casa: CasaLegislativa,
    presentes: int,
    esperado_quorum: bool,
    esperado_status: StatusResultado,
):
    regra = RegraCongresso(materia=TipoMateriaCongresso.LEI_ORDINARIA, casa=casa)
    votos = [Voto(eleitor_id=f"parl_{i}", opcao="SIM") for i in range(presentes)]

    assert regra.validar_quorum(total_aptos=regra.total_membros, votos=votos) is esperado_quorum
    resultado = regra.apurar(votos=votos)
    assert resultado.quorum_atingido is esperado_quorum, id_caso
    assert resultado.status == esperado_status, id_caso


@pytest.mark.parametrize(
    (
        "id_caso",
        "qtd_sim",
        "qtd_nao",
        "qtd_abstencao",
        "qtd_branco",
        "esperado_status",
        "esperado_decisao",
    ),
    [
        (
            "abaixo_maioria_128_sim_129_nao",
            128,
            129,
            0,
            0,
            StatusResultado.REJEITADO,
            "NAO",
        ),
        (
            "empate_exato_128_sim_128_nao_1_abst",
            128,
            128,
            1,
            0,
            StatusResultado.REJEITADO,
            "NAO",
        ),
        (
            "acima_maioria_129_sim_128_nao",
            129,
            128,
            0,
            0,
            StatusResultado.APROVADO,
            "SIM",
        ),
        (
            "apenas_abstencoes_e_brancos",
            0,
            0,
            200,
            57,
            StatusResultado.REJEITADO,
            "NAO",
        ),
    ],
)
def test_congresso_lei_ordinaria_maioria_simples_e_abstencoes(
    id_caso: str,
    qtd_sim: int,
    qtd_nao: int,
    qtd_abstencao: int,
    qtd_branco: int,
    esperado_status: StatusResultado,
    esperado_decisao: str,
):
    regra = RegraCongresso(materia=TipoMateriaCongresso.LEI_ORDINARIA, casa=CasaLegislativa.CAMARA)
    votos = (
        [Voto(eleitor_id=f"sim_{i}", opcao="SIM") for i in range(qtd_sim)]
        + [Voto(eleitor_id=f"nao_{i}", opcao="NAO") for i in range(qtd_nao)]
        + [Voto(eleitor_id=f"abs_{i}", opcao="ABSTENCAO") for i in range(qtd_abstencao)]
        + [Voto(eleitor_id=f"bra_{i}", opcao="BRANCO") for i in range(qtd_branco)]
    )

    resultado = regra.apurar(votos=votos)
    assert resultado.quorum_atingido is True, id_caso
    assert resultado.status == esperado_status, id_caso
    assert resultado.vencedor_ou_decisao == esperado_decisao, id_caso
    assert resultado.detalhes["votos_sim"] == qtd_sim, id_caso
    assert resultado.detalhes["votos_nao"] == qtd_nao, id_caso
    assert resultado.detalhes["abstencoes"] == qtd_abstencao + qtd_branco, id_caso
    assert resultado.detalhes["minimo_votos_sim_exigido"] is None, id_caso


@pytest.mark.parametrize(
    ("id_caso", "materia", "casa", "qtd_sim", "total_presentes", "esperado_status", "min_exigido"),
    [
        (
            "lc_camara_256",
            TipoMateriaCongresso.LEI_COMPLEMENTAR,
            CasaLegislativa.CAMARA,
            256,
            300,
            StatusResultado.REJEITADO,
            257,
        ),
        (
            "lc_camara_257",
            TipoMateriaCongresso.LEI_COMPLEMENTAR,
            CasaLegislativa.CAMARA,
            257,
            300,
            StatusResultado.APROVADO,
            257,
        ),
        (
            "lc_camara_258",
            TipoMateriaCongresso.LEI_COMPLEMENTAR,
            CasaLegislativa.CAMARA,
            258,
            300,
            StatusResultado.APROVADO,
            257,
        ),
        (
            "lc_senado_40",
            TipoMateriaCongresso.LEI_COMPLEMENTAR,
            CasaLegislativa.SENADO,
            40,
            50,
            StatusResultado.REJEITADO,
            41,
        ),
        (
            "lc_senado_41",
            TipoMateriaCongresso.LEI_COMPLEMENTAR,
            CasaLegislativa.SENADO,
            41,
            50,
            StatusResultado.APROVADO,
            41,
        ),
        (
            "lc_senado_42",
            TipoMateriaCongresso.LEI_COMPLEMENTAR,
            CasaLegislativa.SENADO,
            42,
            50,
            StatusResultado.APROVADO,
            41,
        ),
        (
            "pec_camara_307",
            TipoMateriaCongresso.PEC,
            CasaLegislativa.CAMARA,
            307,
            350,
            StatusResultado.REJEITADO,
            308,
        ),
        (
            "pec_camara_308",
            TipoMateriaCongresso.PEC,
            CasaLegislativa.CAMARA,
            308,
            350,
            StatusResultado.APROVADO,
            308,
        ),
        (
            "pec_camara_309",
            TipoMateriaCongresso.PEC,
            CasaLegislativa.CAMARA,
            309,
            350,
            StatusResultado.APROVADO,
            308,
        ),
        (
            "pec_senado_48",
            TipoMateriaCongresso.PEC,
            CasaLegislativa.SENADO,
            48,
            60,
            StatusResultado.REJEITADO,
            49,
        ),
        (
            "pec_senado_49",
            TipoMateriaCongresso.PEC,
            CasaLegislativa.SENADO,
            49,
            60,
            StatusResultado.APROVADO,
            49,
        ),
        (
            "pec_senado_50",
            TipoMateriaCongresso.PEC,
            CasaLegislativa.SENADO,
            50,
            60,
            StatusResultado.APROVADO,
            49,
        ),
    ],
)
def test_congresso_maioria_absoluta_e_qualificada_fronteiras(
    id_caso: str,
    materia: TipoMateriaCongresso,
    casa: CasaLegislativa,
    qtd_sim: int,
    total_presentes: int,
    esperado_status: StatusResultado,
    min_exigido: int,
):
    regra = RegraCongresso(materia=materia, casa=casa)
    qtd_nao = total_presentes - qtd_sim
    votos = [Voto(eleitor_id=f"s_{i}", opcao="SIM") for i in range(qtd_sim)] + [
        Voto(eleitor_id=f"n_{i}", opcao="NAO") for i in range(qtd_nao)
    ]

    resultado = regra.apurar(votos=votos)
    assert resultado.status == esperado_status, id_caso
    assert resultado.detalhes["minimo_votos_sim_exigido"] == min_exigido, id_caso


def test_congresso_materia_desconhecida_levanta_value_error():
    regra = RegraCongresso(
        materia="MEDIDA_PROVISORIA_INVALIDA",  # type: ignore[arg-type]
        casa=CasaLegislativa.SENADO,
    )
    with pytest.raises(ValueError, match="Matéria desconhecida"):
        regra._avaliar_aprovacao(votos_sim=50, votos_nao=0, total_presentes=50)

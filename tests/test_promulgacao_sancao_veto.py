"""Testes da conclusão do rito por tipo de matéria: promulgação, sanção e veto (#34).

Antes da #34, PEC e projeto de lei terminavam idênticos, em APROVADA (evidência E1 /
D-RITO-02 da Atividade 3). A PEC é promulgada pelas Mesas (CF, art. 60, § 3º); o projeto
de lei vai à sanção, e o veto só é derrubado pela maioria absoluta dos Deputados e
Senadores, em votação aberta (art. 66, § 4º, com a redação da EC 76/2013).
"""

import pytest

from votacao.auditoria import LogDeAuditoria, TipoEvento
from votacao.dados.congresso import MateriaLegislativa, RepositorioCongresso
from votacao.modelos import CasaLegislativa, StatusResultado, TipoMateriaCongresso, Voto
from votacao.regras.congresso import RegraCongresso
from votacao.sessao import SessaoVotacao
from votacao.tramitacao import (
    FaseTramitacao,
    StatusTramitacao,
    TramitacaoInvalidaError,
    TramitacaoLegislativa,
)

CAMARA = CasaLegislativa.CAMARA
SENADO = CasaLegislativa.SENADO
MAIORIA_ABSOLUTA = {
    CAMARA: RegraCongresso.MINIMO_LEI_COMPLEMENTAR_CAMARA,  # 257
    SENADO: RegraCongresso.MINIMO_LEI_COMPLEMENTAR_SENADO,  # 41
}


def _sessao_apurada(tramitacao: TramitacaoLegislativa, sim: int, nao: int = 0) -> SessaoVotacao:
    sessao = tramitacao.nova_sessao()
    sessao.abrir()
    quorum = sessao.quorum_instalacao or 0
    sessao.registrar_presenca(*(f"P{i}" for i in range(quorum)))
    sessao.liberar_votacao()
    for i in range(sim):
        sessao.registrar_voto(Voto(eleitor_id=f"S{i}", opcao="SIM"))
    for i in range(nao):
        sessao.registrar_voto(Voto(eleitor_id=f"N{i}", opcao="NAO"))
    sessao.encerrar_votacao()
    sessao.apurar()
    return sessao


def _aprovar_turno(tramitacao: TramitacaoLegislativa) -> StatusTramitacao:
    sim = (
        RegraCongresso.MINIMO_PEC_CAMARA + 2
        if tramitacao.casa_atual == CAMARA
        else RegraCongresso.MINIMO_PEC_SENADO + 1
    )
    return tramitacao.registrar_resultado(_sessao_apurada(tramitacao, sim))


def _aprovar_nas_duas_casas(tramitacao: TramitacaoLegislativa) -> StatusTramitacao:
    status = tramitacao.status
    while status == StatusTramitacao.EM_TRAMITACAO:
        status = _aprovar_turno(tramitacao)
    return status


def _lei(tipo=TipoMateriaCongresso.LEI_ORDINARIA, **kwargs) -> TramitacaoLegislativa:
    return TramitacaoLegislativa("PL-8/2026", tipo, **kwargs)


def _vetada() -> TramitacaoLegislativa:
    tramitacao = _lei()
    _aprovar_nas_duas_casas(tramitacao)
    tramitacao.vetar("Contrário ao interesse público")
    return tramitacao


def _votar_veto(tramitacao: TramitacaoLegislativa, derrubar: int) -> StatusTramitacao:
    """Vota a derrubada na Casa corrente: `derrubar` votos SIM; o restante até o quórum NAO."""
    casa = tramitacao.casa_atual
    quorum = RegraCongresso.QUORUM_INSTALACAO_CAMARA
    if casa == SENADO:
        quorum = RegraCongresso.QUORUM_INSTALACAO_SENADO
    nao = max(0, quorum - derrubar)
    return tramitacao.registrar_resultado(_sessao_apurada(tramitacao, sim=derrubar, nao=nao))


# --- Conclusão por tipo de matéria -----------------------------------------------------


def test_pec_aprovada_nas_duas_casas_e_promulgada_sem_sancao():
    tramitacao = TramitacaoLegislativa("PEC-4/2026", TipoMateriaCongresso.PEC)

    assert _aprovar_nas_duas_casas(tramitacao) == StatusTramitacao.PROMULGADA
    assert tramitacao.status.concluida is True
    with pytest.raises(TramitacaoInvalidaError, match="não vai a sanção"):
        tramitacao.sancionar()
    with pytest.raises(TramitacaoInvalidaError, match="não vai a sanção"):
        tramitacao.vetar("Razões")


@pytest.mark.parametrize(
    "tipo",
    [TipoMateriaCongresso.LEI_ORDINARIA, TipoMateriaCongresso.LEI_COMPLEMENTAR],
    ids=["lei_ordinaria", "lei_complementar"],
)
def test_lei_aprovada_nas_duas_casas_e_enviada_a_sancao_sem_desfecho_final(tipo):
    tramitacao = _lei(tipo)

    assert _aprovar_nas_duas_casas(tramitacao) == StatusTramitacao.ENVIADA_A_SANCAO
    assert tramitacao.status.concluida is False


def test_sancao_conclui_como_aprovada():
    tramitacao = _lei()
    _aprovar_nas_duas_casas(tramitacao)

    assert tramitacao.sancionar() == StatusTramitacao.APROVADA
    assert tramitacao.status.concluida is True


def test_lei_emendada_tambem_vai_a_sancao_depois_da_apreciacao():
    tramitacao = _lei()
    _aprovar_turno(tramitacao)
    tramitacao.registrar_resultado(
        _sessao_apurada(tramitacao, RegraCongresso.MINIMO_PEC_SENADO + 1), com_emenda=True
    )

    assert _aprovar_turno(tramitacao) == StatusTramitacao.ENVIADA_A_SANCAO


# --- Recusas antes de vencer as duas Casas ---------------------------------------------


@pytest.mark.parametrize("operacao", ["sancionar", "vetar"])
def test_sancao_e_veto_recusados_antes_de_vencer_as_duas_casas(operacao: str):
    tramitacao = _lei()
    _aprovar_turno(tramitacao)  # só a Câmara

    with pytest.raises(TramitacaoInvalidaError, match="aprovada nas duas Casas"):
        if operacao == "sancionar":
            tramitacao.sancionar()
        else:
            tramitacao.vetar("Razões")
    assert tramitacao.status == StatusTramitacao.EM_TRAMITACAO


def test_pec_nao_e_promulgada_antes_de_vencer_as_duas_casas():
    tramitacao = TramitacaoLegislativa("PEC-4/2026", TipoMateriaCongresso.PEC)
    _aprovar_turno(tramitacao)
    _aprovar_turno(tramitacao)
    _aprovar_turno(tramitacao)  # falta o 2º turno do Senado

    assert tramitacao.status == StatusTramitacao.EM_TRAMITACAO


def test_sancao_nao_pode_ser_repetida():
    tramitacao = _lei()
    _aprovar_nas_duas_casas(tramitacao)
    tramitacao.sancionar()

    with pytest.raises(TramitacaoInvalidaError, match="APROVADA"):
        tramitacao.sancionar()


def test_veto_exige_razoes():
    tramitacao = _lei()
    _aprovar_nas_duas_casas(tramitacao)

    with pytest.raises(ValueError, match="razões do veto"):
        tramitacao.vetar("  ")
    assert tramitacao.status == StatusTramitacao.ENVIADA_A_SANCAO


# --- Apreciação do veto ----------------------------------------------------------------


def test_veto_abre_apreciacao_comecando_pela_camara():
    tramitacao = _vetada()

    assert tramitacao.status == StatusTramitacao.VETO_EM_APRECIACAO
    assert tramitacao.fase == FaseTramitacao.APRECIACAO_VETO
    assert tramitacao.casa_atual == CAMARA
    assert tramitacao.razoes_veto == "Contrário ao interesse público"
    assert tramitacao.id_proxima_sessao == "PL-8/2026-VETO-CAMARA"


@pytest.mark.parametrize(
    ("casa", "minimo"),
    [pytest.param(CAMARA, 257, id="camara"), pytest.param(SENADO, 41, id="senado")],
)
def test_sessao_do_veto_exige_maioria_absoluta_da_casa(casa: CasaLegislativa, minimo: int):
    tramitacao = _vetada()
    if casa == SENADO:
        _votar_veto(tramitacao, derrubar=MAIORIA_ABSOLUTA[CAMARA])

    sessao = tramitacao.nova_sessao()

    assert sessao.regra.casa == casa
    assert sessao.regra.materia == TipoMateriaCongresso.LEI_COMPLEMENTAR
    assert MAIORIA_ABSOLUTA[casa] == minimo


@pytest.mark.parametrize(
    ("derrubar", "status_esperado"),
    [
        pytest.param(256, StatusTramitacao.REJEITADA, id="camara_256_veto_mantido"),
        pytest.param(257, StatusTramitacao.VETO_EM_APRECIACAO, id="camara_257_segue_ao_senado"),
    ],
)
def test_fronteira_da_maioria_absoluta_na_camara(derrubar: int, status_esperado):
    tramitacao = _vetada()

    assert _votar_veto(tramitacao, derrubar=derrubar) == status_esperado


@pytest.mark.parametrize(
    ("derrubar", "status_esperado"),
    [
        pytest.param(40, StatusTramitacao.REJEITADA, id="senado_40_veto_mantido"),
        pytest.param(41, StatusTramitacao.APROVADA, id="senado_41_veto_derrubado"),
    ],
)
def test_fronteira_da_maioria_absoluta_no_senado(derrubar: int, status_esperado):
    tramitacao = _vetada()
    _votar_veto(tramitacao, derrubar=MAIORIA_ABSOLUTA[CAMARA])
    assert tramitacao.casa_atual == SENADO

    assert _votar_veto(tramitacao, derrubar=derrubar) == status_esperado


def test_veto_mantido_na_camara_nao_vai_ao_senado():
    tramitacao = _vetada()
    _votar_veto(tramitacao, derrubar=100)

    assert tramitacao.status == StatusTramitacao.REJEITADA
    with pytest.raises(TramitacaoInvalidaError):
        tramitacao.nova_sessao()


def test_apreciacao_do_veto_sem_quorum_mantem_a_etapa():
    tramitacao = _vetada()
    tramitacao.registrar_resultado(_sessao_apurada(tramitacao, sim=5))

    assert tramitacao.status == StatusTramitacao.VETO_EM_APRECIACAO
    assert tramitacao.historico[-1].valida is False
    assert tramitacao.historico[-1].resultado.status == StatusResultado.QUORUM_INSUFICIENTE


def test_emenda_na_apreciacao_do_veto_e_recusada():
    tramitacao = _vetada()
    sessao = _sessao_apurada(tramitacao, sim=MAIORIA_ABSOLUTA[CAMARA])

    with pytest.raises(TramitacaoInvalidaError, match="APRECIACAO_VETO"):
        tramitacao.registrar_resultado(sessao, com_emenda=True)


# --- Cadastro e log --------------------------------------------------------------------


def test_cadastro_acompanha_sancao_e_apreciacao_do_veto():
    repo = RepositorioCongresso()
    repo.adicionar_materia(
        MateriaLegislativa(
            id="PL-8/2026", tipo=TipoMateriaCongresso.LEI_ORDINARIA, casa_atual=CAMARA
        )
    )
    tramitacao = _lei(repo=repo)
    _aprovar_nas_duas_casas(tramitacao)
    assert repo.obter_materia("PL-8/2026").ativa is False  # saiu do Congresso

    tramitacao.vetar("Inconstitucionalidade")
    materia = repo.obter_materia("PL-8/2026")
    assert materia.ativa is True  # volta à pauta para apreciar o veto
    assert materia.casa_atual == CAMARA

    _votar_veto(tramitacao, derrubar=MAIORIA_ABSOLUTA[CAMARA])
    assert repo.obter_materia("PL-8/2026").casa_atual == SENADO
    _votar_veto(tramitacao, derrubar=MAIORIA_ABSOLUTA[SENADO])
    assert repo.obter_materia("PL-8/2026").ativa is False


def test_cada_transicao_de_conclusao_fica_no_log():
    log = LogDeAuditoria("PL-8/2026")
    tramitacao = _lei(log=log)
    _aprovar_nas_duas_casas(tramitacao)
    tramitacao.vetar("Contrário ao interesse público")
    _votar_veto(tramitacao, derrubar=MAIORIA_ABSOLUTA[CAMARA])
    _votar_veto(tramitacao, derrubar=MAIORIA_ABSOLUTA[SENADO])

    eventos = [r.evento for r in log.registros]
    assert eventos == [
        TipoEvento.TRAMITACAO_CASA_ALTERADA,  # Câmara -> Senado
        TipoEvento.TRAMITACAO_ENVIADA_A_SANCAO,
        TipoEvento.TRAMITACAO_VETO,
        TipoEvento.TRAMITACAO_CASA_ALTERADA,  # apreciação do veto: Câmara -> Senado
        TipoEvento.TRAMITACAO_CONCLUIDA,
    ]
    veto = log.registros[2].dados
    assert veto["razoes"] == "Contrário ao interesse público"
    assert "aberta" in veto["votacao"]
    assert "EC 76/2013" in veto["votacao"]
    assert log.registros[-1].dados == {
        "status": "APROVADA",
        "casa": "SENADO",
        "decisao": "VETO_DERRUBADO",
    }
    assert log.verificar_integridade().integro


@pytest.mark.parametrize(
    ("acao", "decisao", "status"),
    [
        pytest.param("sancionar", "SANCAO", "APROVADA", id="sancao"),
        pytest.param("manter_veto", "VETO_MANTIDO", "REJEITADA", id="veto_mantido"),
    ],
)
def test_conclusao_registra_a_decisao_no_log(acao: str, decisao: str, status: str):
    log = LogDeAuditoria("PL-8/2026")
    tramitacao = _lei(log=log)
    _aprovar_nas_duas_casas(tramitacao)
    if acao == "sancionar":
        tramitacao.sancionar()
    else:
        tramitacao.vetar("Razões")
        _votar_veto(tramitacao, derrubar=10)

    ultimo = log.registros[-1]
    assert ultimo.evento == TipoEvento.TRAMITACAO_CONCLUIDA
    assert ultimo.dados["decisao"] == decisao
    assert ultimo.dados["status"] == status


def test_pec_promulgada_fica_no_log_como_conclusao():
    log = LogDeAuditoria("PEC-4/2026")
    tramitacao = TramitacaoLegislativa("PEC-4/2026", TipoMateriaCongresso.PEC, log=log)
    _aprovar_nas_duas_casas(tramitacao)

    assert log.registros[-1].evento == TipoEvento.TRAMITACAO_CONCLUIDA
    assert log.registros[-1].dados["status"] == "PROMULGADA"

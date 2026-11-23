"""Testes do retorno à Casa iniciadora quando a revisora emenda a matéria (história #33).

Antes da #33 a aprovação na revisora concluía o rito, e uma PEC vencia os dois turnos
em cada Casa direto para APROVADA, sem etapa de emendas (evidência E1 / D-RITO-01 da
Atividade 3). "Sendo o projeto emendado, voltará à Casa iniciadora" (CF, art. 65, p.u.).
"""

import pytest

from votacao.auditoria import LogDeAuditoria, TipoEvento
from votacao.dados.congresso import MateriaLegislativa, RepositorioCongresso
from votacao.modelos import CasaLegislativa, TipoMateriaCongresso, Voto
from votacao.regras.congresso import RegraCongresso
from votacao.sessao import SessaoVotacao
from votacao.tramitacao import (
    FaseTramitacao,
    StatusTramitacao,
    TextoPrevalecente,
    TramitacaoInvalidaError,
    TramitacaoLegislativa,
)

CAMARA = CasaLegislativa.CAMARA
SENADO = CasaLegislativa.SENADO


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


def _aprovar(tramitacao: TramitacaoLegislativa, com_emenda: bool = False) -> StatusTramitacao:
    sim = (
        RegraCongresso.MINIMO_PEC_CAMARA + 2
        if tramitacao.casa_atual == CAMARA
        else RegraCongresso.MINIMO_PEC_SENADO + 1
    )
    return tramitacao.registrar_resultado(_sessao_apurada(tramitacao, sim), com_emenda=com_emenda)


def _rejeitar(tramitacao: TramitacaoLegislativa) -> StatusTramitacao:
    quorum = RegraCongresso.QUORUM_INSTALACAO_CAMARA
    if tramitacao.casa_atual == SENADO:
        quorum = RegraCongresso.QUORUM_INSTALACAO_SENADO
    return tramitacao.registrar_resultado(_sessao_apurada(tramitacao, sim=10, nao=quorum))


def _pl(**kwargs) -> TramitacaoLegislativa:
    return TramitacaoLegislativa("PL-7/2026", TipoMateriaCongresso.LEI_ORDINARIA, **kwargs)


# --- Retorno à iniciadora --------------------------------------------------------------


def test_aprovacao_com_emenda_na_revisora_volta_a_iniciadora():
    tramitacao = _pl()
    _aprovar(tramitacao)  # Câmara (iniciadora)

    status = _aprovar(tramitacao, com_emenda=True)  # Senado (revisora) emenda

    assert status == StatusTramitacao.EM_TRAMITACAO
    assert tramitacao.casa_atual == CAMARA
    assert tramitacao.fase == FaseTramitacao.APRECIACAO_EMENDAS
    assert tramitacao.historico[-1].com_emenda is True


def test_aprovacao_sem_emenda_na_revisora_conclui_como_hoje():
    tramitacao = _pl()
    _aprovar(tramitacao)

    assert _aprovar(tramitacao) == StatusTramitacao.ENVIADA_A_SANCAO
    assert tramitacao.texto_prevalecente is None
    assert tramitacao.casa_atual == SENADO


def test_iniciadora_no_senado_retorna_ao_senado():
    tramitacao = _pl(casa_iniciadora=SENADO)
    _aprovar(tramitacao)
    _aprovar(tramitacao, com_emenda=True)  # Câmara revisora emenda

    assert tramitacao.casa_atual == SENADO
    assert tramitacao.id_proxima_sessao == "PL-7/2026-SENADO-EMENDAS"


def test_pec_emendada_em_qualquer_turno_da_revisora_so_retorna_ao_fim_dos_turnos():
    tramitacao = TramitacaoLegislativa("PEC-3/2026", TipoMateriaCongresso.PEC)
    _aprovar(tramitacao)
    _aprovar(tramitacao)  # dois turnos na Câmara
    _aprovar(tramitacao, com_emenda=True)  # 1º turno no Senado, com emenda

    assert tramitacao.casa_atual == SENADO
    assert tramitacao.turno_atual == 2
    assert tramitacao.fase == FaseTramitacao.CASA_REVISORA

    _aprovar(tramitacao)  # 2º turno no Senado
    assert tramitacao.fase == FaseTramitacao.APRECIACAO_EMENDAS
    assert tramitacao.casa_atual == CAMARA


def test_identificador_da_sessao_de_emendas_nao_colide_com_o_do_turno_original():
    tramitacao = _pl()
    primeira = tramitacao.id_proxima_sessao
    _aprovar(tramitacao)
    _aprovar(tramitacao, com_emenda=True)

    assert primeira == "PL-7/2026-CAMARA-T1"
    assert tramitacao.id_proxima_sessao == "PL-7/2026-CAMARA-EMENDAS"
    sessao = tramitacao.nova_sessao(log=LogDeAuditoria(tramitacao.id_proxima_sessao))
    assert sessao.id_sessao == "PL-7/2026-CAMARA-EMENDAS"
    assert sessao.regra.casa == CAMARA


# --- Apreciação das emendas: terminal, dois desfechos ---------------------------------


@pytest.mark.parametrize(
    ("acolhe", "texto"),
    [
        pytest.param(True, TextoPrevalecente.REVISORA, id="emendas_acolhidas"),
        pytest.param(False, TextoPrevalecente.INICIADORA, id="emendas_rejeitadas"),
    ],
)
def test_apreciacao_das_emendas_aprova_a_materia_nos_dois_desfechos(
    acolhe: bool, texto: TextoPrevalecente
):
    tramitacao = _pl()
    _aprovar(tramitacao)
    _aprovar(tramitacao, com_emenda=True)

    status = _aprovar(tramitacao) if acolhe else _rejeitar(tramitacao)

    # Aprovada no Congresso: a lei segue para a sanção (#34)
    assert status == StatusTramitacao.ENVIADA_A_SANCAO
    assert tramitacao.texto_prevalecente == texto
    ultimo = tramitacao.historico[-1]
    assert ultimo.fase == FaseTramitacao.APRECIACAO_EMENDAS
    assert ultimo.texto_prevalecente == texto


def test_nao_ha_segundo_reenvio_a_revisora():
    tramitacao = _pl()
    _aprovar(tramitacao)
    _aprovar(tramitacao, com_emenda=True)
    _aprovar(tramitacao)

    with pytest.raises(TramitacaoInvalidaError, match="ENVIADA_A_SANCAO"):
        tramitacao.nova_sessao()


def test_apreciacao_sem_quorum_mantem_a_etapa_de_emendas():
    tramitacao = _pl()
    _aprovar(tramitacao)
    _aprovar(tramitacao, com_emenda=True)

    tramitacao.registrar_resultado(_sessao_apurada(tramitacao, sim=5))

    assert tramitacao.status == StatusTramitacao.EM_TRAMITACAO
    assert tramitacao.fase == FaseTramitacao.APRECIACAO_EMENDAS
    assert tramitacao.historico[-1].valida is False
    assert tramitacao.historico[-1].texto_prevalecente is None


# --- Emenda fora da revisora -----------------------------------------------------------


def test_emenda_na_casa_iniciadora_e_recusada_com_mensagem():
    tramitacao = _pl()
    sessao = _sessao_apurada(tramitacao, sim=RegraCongresso.QUORUM_INSTALACAO_CAMARA)

    with pytest.raises(TramitacaoInvalidaError, match="apenas a Casa revisora emenda"):
        tramitacao.registrar_resultado(sessao, com_emenda=True)

    assert tramitacao.historico == ()
    assert tramitacao.casa_atual == CAMARA


def test_emenda_na_apreciacao_das_emendas_e_recusada():
    tramitacao = _pl()
    _aprovar(tramitacao)
    _aprovar(tramitacao, com_emenda=True)

    with pytest.raises(TramitacaoInvalidaError, match="APRECIACAO_EMENDAS"):
        _aprovar(tramitacao, com_emenda=True)


def test_emenda_numa_sessao_que_rejeitou_e_recusada():
    tramitacao = _pl()
    _aprovar(tramitacao)
    sessao = _sessao_apurada(tramitacao, sim=5, nao=RegraCongresso.QUORUM_INSTALACAO_SENADO)

    with pytest.raises(TramitacaoInvalidaError, match="acompanha a aprovação"):
        tramitacao.registrar_resultado(sessao, com_emenda=True)
    assert tramitacao.status == StatusTramitacao.EM_TRAMITACAO


def test_aceita_emenda_so_na_revisora_em_tramitacao():
    tramitacao = _pl()
    assert tramitacao.aceita_emenda is False
    _aprovar(tramitacao)
    assert tramitacao.aceita_emenda is True
    _aprovar(tramitacao, com_emenda=True)
    assert tramitacao.aceita_emenda is False


# --- Cadastro e log --------------------------------------------------------------------


def test_retorno_sincroniza_a_casa_no_repositorio():
    repo = RepositorioCongresso()
    repo.adicionar_materia(
        MateriaLegislativa(
            id="PL-7/2026",
            tipo=TipoMateriaCongresso.LEI_ORDINARIA,
            titulo="Teste",
            casa_atual=CAMARA,
        )
    )
    tramitacao = _pl(repo=repo)
    _aprovar(tramitacao)
    assert repo.obter_materia("PL-7/2026").casa_atual == SENADO

    _aprovar(tramitacao, com_emenda=True)

    materia = repo.obter_materia("PL-7/2026")
    assert materia.casa_atual == CAMARA
    assert materia.ativa is True


def test_retorno_fica_no_log_com_casa_de_origem_e_destino():
    log = LogDeAuditoria("PL-7/2026")
    tramitacao = _pl(log=log)
    _aprovar(tramitacao)
    _aprovar(tramitacao, com_emenda=True)
    _rejeitar(tramitacao)

    eventos = [(r.evento, r.dados) for r in log.registros]
    assert eventos[0] == (
        TipoEvento.TRAMITACAO_CASA_ALTERADA,
        {"origem": "CAMARA", "destino": "SENADO", "fase": "CASA_REVISORA"},
    )
    assert eventos[1][0] == TipoEvento.TRAMITACAO_CASA_ALTERADA
    assert eventos[1][1]["origem"] == "SENADO"
    assert eventos[1][1]["destino"] == "CAMARA"
    assert eventos[1][1]["fase"] == "APRECIACAO_EMENDAS"
    assert "art. 65" in eventos[1][1]["motivo"]
    assert eventos[2] == (
        TipoEvento.TRAMITACAO_ENVIADA_A_SANCAO,
        {"casa": "CAMARA", "texto_prevalecente": "INICIADORA"},
    )
    assert log.verificar_integridade().integro


def test_log_de_outra_materia_e_recusado():
    with pytest.raises(ValueError, match="pertence a 'OUTRA'"):
        _pl(log=LogDeAuditoria("OUTRA"))

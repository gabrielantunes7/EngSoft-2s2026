"""Testes da anulação de sessão com motivo (história #39).

Antes da #39 uma sessão viciada terminava ENCERRADA, indistinguível de uma válida, e a
tramitação não tinha como saber a diferença (evidência E5 / D-RITO-04 da Atividade 3).
"""

from collections.abc import Callable

import pytest

from votacao.auditoria import LogDeAuditoria, TipoEvento
from votacao.modelos import TipoMateriaCongresso, Voto
from votacao.regras.ca import RegraCA
from votacao.sessao import (
    EstadoSessao,
    SessaoVotacao,
    TransicaoInvalidaError,
    VotoRecusadoError,
)
from votacao.tramitacao import StatusTramitacao, TramitacaoInvalidaError, TramitacaoLegislativa


def _sessao(log: LogDeAuditoria | None = None) -> SessaoVotacao:
    return SessaoVotacao("CA-2026", RegraCA(quorum_minimo_votantes=1), total_aptos=10, log=log)


def _ate(sessao: SessaoVotacao, estado: EstadoSessao) -> SessaoVotacao:
    passos: dict[EstadoSessao, list[Callable[[], object]]] = {
        EstadoSessao.CRIADA: [],
        EstadoSessao.ABERTA: [sessao.abrir],
        EstadoSessao.EM_VOTACAO: [sessao.abrir, sessao.liberar_votacao],
        EstadoSessao.SUSPENSA: [
            sessao.abrir,
            sessao.liberar_votacao,
            lambda: sessao.suspender("Questão de ordem"),
        ],
        EstadoSessao.EM_APURACAO: [sessao.abrir, sessao.liberar_votacao, sessao.encerrar_votacao],
        EstadoSessao.ENCERRADA: [
            sessao.abrir,
            sessao.liberar_votacao,
            lambda: sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A")),
            sessao.encerrar_votacao,
            sessao.apurar,
        ],
    }
    for passo in passos[estado]:
        passo()
    return sessao


# --- Estados de origem ----------------------------------------------------------------


@pytest.mark.parametrize(
    "estado",
    [
        EstadoSessao.ABERTA,
        EstadoSessao.EM_VOTACAO,
        EstadoSessao.SUSPENSA,
        EstadoSessao.EM_APURACAO,
        EstadoSessao.ENCERRADA,
    ],
    ids=lambda e: e.value,
)
def test_anular_a_partir_de_qualquer_estado_posterior_a_abertura(estado: EstadoSessao):
    sessao = _ate(_sessao(), estado)

    sessao.anular("Fraude no credenciamento")

    assert sessao.estado == EstadoSessao.ANULADA
    assert sessao.motivo_anulacao == "Fraude no credenciamento"


def test_anular_sessao_ainda_nao_aberta_e_recusado():
    sessao = _sessao()

    with pytest.raises(TransicaoInvalidaError, match="a partir da abertura"):
        sessao.anular("Motivo")
    assert sessao.estado == EstadoSessao.CRIADA


def test_anulada_e_terminal_e_nao_pode_ser_anulada_de_novo():
    sessao = _ate(_sessao(), EstadoSessao.EM_VOTACAO)
    sessao.anular("Vício de convocação")

    with pytest.raises(TransicaoInvalidaError, match="ANULADA"):
        sessao.anular("Outro motivo")
    for operacao in (sessao.encerrar_votacao, sessao.retomar, sessao.liberar_votacao):
        with pytest.raises(TransicaoInvalidaError):
            operacao()
    assert sessao.motivo_anulacao == "Vício de convocação"


@pytest.mark.parametrize("motivo", ["", "   "], ids=["vazio", "so_espacos"])
def test_anular_exige_motivo(motivo: str):
    sessao = _ate(_sessao(), EstadoSessao.EM_VOTACAO)

    with pytest.raises(ValueError, match="motivo"):
        sessao.anular(motivo)
    assert sessao.estado == EstadoSessao.EM_VOTACAO


# --- Sessão anulada não produz resultado ----------------------------------------------


def test_sessao_anulada_nao_aceita_votos_nem_presenca():
    sessao = _ate(_sessao(), EstadoSessao.EM_VOTACAO)
    sessao.anular("Vício")

    with pytest.raises(TransicaoInvalidaError):
        sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))
    with pytest.raises(TransicaoInvalidaError, match="ANULADA"):
        sessao.registrar_presenca("101")


def test_sessao_anulada_nao_e_apurada_e_resultado_fica_indisponivel():
    sessao = _ate(_sessao(), EstadoSessao.EM_APURACAO)
    sessao.anular("Urna adulterada")

    with pytest.raises(TransicaoInvalidaError, match="ANULADA"):
        sessao.apurar()
    assert sessao.resultado is None


def test_anular_sessao_ja_apurada_descarta_o_resultado():
    sessao = _ate(_sessao(), EstadoSessao.ENCERRADA)
    assert sessao.resultado is not None

    sessao.anular("Eleitor inapto votou")

    assert sessao.resultado is None
    assert len(sessao.votos) == 1  # os votos continuam registrados para auditoria


def test_anular_sessao_suspensa_limpa_o_motivo_da_suspensao():
    sessao = _ate(_sessao(), EstadoSessao.SUSPENSA)

    sessao.anular("Quórum não recomposto")

    assert sessao.motivo_suspensao is None


def test_voto_em_sessao_suspensa_e_anulada_nao_cai_na_mensagem_de_suspensao():
    sessao = _ate(_sessao(), EstadoSessao.SUSPENSA)
    sessao.anular("Vício")

    with pytest.raises(TransicaoInvalidaError) as erro:
        sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))
    assert not isinstance(erro.value, VotoRecusadoError)


# --- Log de auditoria (RNF-RITO-01) ---------------------------------------------------


def test_anulacao_fica_no_log_com_motivo_e_estado_anterior():
    log = LogDeAuditoria("CA-2026")
    sessao = _ate(_sessao(log=log), EstadoSessao.ENCERRADA)

    sessao.anular("Eleitor inapto votou")

    ultimo = log.registros[-1]
    assert ultimo.evento == TipoEvento.SESSAO_ANULADA
    assert ultimo.dados == {
        "motivo": "Eleitor inapto votou",
        "estado_anterior": "ENCERRADA",
        "total_votos": 1,
        "resultado_descartado": True,
    }
    assert log.verificar_integridade().integro


def test_anulacao_recusada_nao_grava_no_log():
    log = LogDeAuditoria("CA-2026")
    sessao = _ate(_sessao(log=log), EstadoSessao.EM_VOTACAO)

    with pytest.raises(ValueError):
        sessao.anular(" ")

    assert TipoEvento.SESSAO_ANULADA not in [r.evento for r in log.registros]


# --- Tramitação -----------------------------------------------------------------------


def _sessao_da_tramitacao_votada(tramitacao: TramitacaoLegislativa) -> SessaoVotacao:
    sessao = tramitacao.nova_sessao()
    sessao.abrir()
    quorum = sessao.quorum_instalacao or 0
    sessao.registrar_presenca(*(f"DEP-{i:03d}" for i in range(quorum)))
    sessao.liberar_votacao()
    for i in range(quorum):
        sessao.registrar_voto(Voto(eleitor_id=f"DEP-{i:03d}", opcao="SIM"))
    return sessao


def test_tramitacao_recusa_sessao_anulada_com_mensagem_explicativa():
    tramitacao = TramitacaoLegislativa("PL-9/2026", TipoMateriaCongresso.LEI_ORDINARIA)
    sessao = _sessao_da_tramitacao_votada(tramitacao)
    sessao.anular("Votação nominal com painel defeituoso")

    with pytest.raises(TramitacaoInvalidaError) as erro:
        tramitacao.registrar_resultado(sessao)

    mensagem = str(erro.value)
    assert "foi anulada (Votação nominal com painel defeituoso)" in mensagem
    assert "convoque uma nova sessão" in mensagem


def test_anulada_a_sessao_a_etapa_se_mantem_e_outra_e_convocada():
    tramitacao = TramitacaoLegislativa("PL-9/2026", TipoMateriaCongresso.LEI_ORDINARIA)
    anulada = _sessao_da_tramitacao_votada(tramitacao)
    anulada.encerrar_votacao()
    anulada.apurar()
    anulada.anular("Vício apurado após a votação")
    with pytest.raises(TramitacaoInvalidaError):
        tramitacao.registrar_resultado(anulada)

    assert tramitacao.status == StatusTramitacao.EM_TRAMITACAO
    assert tramitacao.turno_atual == 1
    assert tramitacao.historico == ()

    nova = _sessao_da_tramitacao_votada(tramitacao)
    assert nova.id_sessao == anulada.id_sessao
    nova.encerrar_votacao()
    nova.apurar()
    tramitacao.registrar_resultado(nova)

    assert tramitacao.casa_atual.value == "SENADO"
    assert [r.id_sessao for r in tramitacao.historico] == [nova.id_sessao]

"""Testes da suspensão e retomada da sessão de votação (história #38).

Antes da #38 a máquina de estados era estritamente progressiva: uma interrupção obrigava
a abandonar a sessão e convocar outra (evidência E5 / D-RITO-04 da Atividade 3).
"""

from datetime import UTC, datetime, timedelta

import pytest

from votacao.auditoria import LogDeAuditoria, TipoEvento
from votacao.modelos import CasaLegislativa, StatusResultado, TipoMateriaCongresso, Voto
from votacao.regras.ca import RegraCA
from votacao.regras.congresso import RegraCongresso
from votacao.sessao import (
    EstadoSessao,
    SessaoVotacao,
    TransicaoInvalidaError,
    VotoRecusadoError,
)

INICIO = datetime(2026, 11, 21, 14, 0, tzinfo=UTC)
FIM = INICIO + timedelta(hours=2)


class Relogio:
    def __init__(self, agora: datetime) -> None:
        self.agora = agora

    def __call__(self) -> datetime:
        return self.agora


def _sessao_em_votacao(
    log: LogDeAuditoria | None = None, relogio: Relogio | None = None
) -> SessaoVotacao:
    sessao = SessaoVotacao(
        "CA-2026", RegraCA(quorum_minimo_votantes=2), total_aptos=10, log=log, relogio=relogio
    )
    sessao.abrir()
    if relogio is not None:
        sessao.liberar_votacao(inicio=INICIO, fim=FIM)
    else:
        sessao.liberar_votacao()
    return sessao


def _votar(sessao: SessaoVotacao, eleitor: str, opcao: str = "Chapa A") -> str | None:
    return sessao.registrar_voto(Voto(eleitor_id=eleitor, opcao=opcao))


# --- Suspensão ------------------------------------------------------------------------


def test_suspender_a_partir_da_votacao_leva_a_suspensa_com_motivo():
    sessao = _sessao_em_votacao()

    sessao.suspender("Questão de ordem")

    assert sessao.estado == EstadoSessao.SUSPENSA
    assert sessao.motivo_suspensao == "Questão de ordem"
    assert sessao.total_suspensoes == 1


@pytest.mark.parametrize("motivo", ["", "   "], ids=["vazio", "so_espacos"])
def test_suspender_exige_motivo(motivo: str):
    sessao = _sessao_em_votacao()

    with pytest.raises(ValueError, match="motivo"):
        sessao.suspender(motivo)
    assert sessao.estado == EstadoSessao.EM_VOTACAO


@pytest.mark.parametrize(
    "estado",
    [EstadoSessao.CRIADA, EstadoSessao.ABERTA, EstadoSessao.EM_APURACAO, EstadoSessao.ENCERRADA],
    ids=lambda e: e.value,
)
def test_suspender_fora_da_votacao_e_recusado(estado: EstadoSessao):
    sessao = SessaoVotacao("CA-2026", RegraCA(), total_aptos=10)
    caminho = {
        EstadoSessao.CRIADA: [],
        EstadoSessao.ABERTA: [sessao.abrir],
        EstadoSessao.EM_APURACAO: [sessao.abrir, sessao.liberar_votacao, sessao.encerrar_votacao],
        EstadoSessao.ENCERRADA: [
            sessao.abrir,
            sessao.liberar_votacao,
            sessao.encerrar_votacao,
            sessao.apurar,
        ],
    }
    for passo in caminho[estado]:
        passo()

    with pytest.raises(TransicaoInvalidaError, match="suspender"):
        sessao.suspender("Motivo")


def test_suspender_sessao_ja_suspensa_e_recusado():
    sessao = _sessao_em_votacao()
    sessao.suspender("Primeira")

    with pytest.raises(TransicaoInvalidaError):
        sessao.suspender("Segunda")


# --- Votos durante e depois da suspensão ----------------------------------------------


def test_voto_e_recusado_durante_a_suspensao_com_mensagem_explicativa():
    sessao = _sessao_em_votacao()
    sessao.suspender("Queda de quórum")

    with pytest.raises(VotoRecusadoError) as erro:
        _votar(sessao, "101")

    assert "está suspensa (Queda de quórum)" in str(erro.value)
    assert "aguarde a retomada" in str(erro.value)
    assert sessao.votos == ()


def test_votos_anteriores_sao_preservados_e_quem_votou_continua_impedido():
    sessao = _sessao_em_votacao()
    _votar(sessao, "101", "Chapa A")
    _votar(sessao, "102", "Chapa B")

    sessao.suspender("Questão de ordem")
    sessao.retomar()

    assert [v.eleitor_id for v in sessao.votos] == ["101", "102"]
    with pytest.raises(VotoRecusadoError, match="já votou"):
        _votar(sessao, "101")


def test_retomar_devolve_a_votacao_e_ela_prossegue_ate_a_apuracao():
    sessao = _sessao_em_votacao()
    _votar(sessao, "101", "Chapa A")
    sessao.suspender("Intervalo regimental")

    sessao.retomar()
    _votar(sessao, "102", "Chapa A")
    sessao.encerrar_votacao()
    resultado = sessao.apurar()

    assert sessao.estado == EstadoSessao.ENCERRADA
    assert sessao.motivo_suspensao is None
    assert resultado.status == StatusResultado.ELEITO
    assert resultado.total_votantes == 2


def test_encerrar_ou_apurar_sessao_suspensa_e_recusado():
    sessao = _sessao_em_votacao()
    sessao.suspender("Obstrução")

    with pytest.raises(TransicaoInvalidaError, match="SUSPENSA"):
        sessao.encerrar_votacao()
    with pytest.raises(TransicaoInvalidaError, match="SUSPENSA"):
        sessao.apurar()
    assert sessao.estado == EstadoSessao.SUSPENSA


def test_retomar_sessao_nao_suspensa_e_recusado():
    sessao = _sessao_em_votacao()

    with pytest.raises(TransicaoInvalidaError, match="retomar"):
        sessao.retomar()


def test_sessao_pode_ser_suspensa_e_retomada_varias_vezes():
    sessao = _sessao_em_votacao()
    for i, eleitor in enumerate(["101", "102", "103"], start=1):
        _votar(sessao, eleitor)
        sessao.suspender(f"Interrupção {i}")
        sessao.retomar()

    assert sessao.total_suspensoes == 3
    assert len(sessao.votos) == 3
    assert sessao.estado == EstadoSessao.EM_VOTACAO


# --- Janela de votação ----------------------------------------------------------------


def test_retomada_nao_estende_a_janela_de_votacao():
    relogio = Relogio(INICIO + timedelta(minutes=30))
    sessao = _sessao_em_votacao(relogio=relogio)
    _votar(sessao, "101")
    sessao.suspender("Falta de tempo regimental")

    relogio.agora = FIM + timedelta(minutes=1)
    sessao.retomar()

    assert sessao.fim_votacao == FIM
    with pytest.raises(VotoRecusadoError, match="terminou"):
        _votar(sessao, "102")


def test_retomada_dentro_da_janela_aceita_votos_ate_o_fim_original():
    relogio = Relogio(INICIO + timedelta(minutes=30))
    sessao = _sessao_em_votacao(relogio=relogio)
    sessao.suspender("Questão de ordem")

    relogio.agora = FIM
    sessao.retomar()
    _votar(sessao, "101")

    assert len(sessao.votos) == 1


# --- Log de auditoria (RNF-RITO-01) ---------------------------------------------------


def test_suspensao_e_retomada_ficam_no_log_com_o_motivo():
    log = LogDeAuditoria("CA-2026")
    sessao = _sessao_em_votacao(log=log)
    _votar(sessao, "101")

    sessao.suspender("Queda de quórum")
    sessao.retomar()

    eventos = [r.evento for r in log.registros]
    assert eventos == [
        TipoEvento.VOTACAO_ABERTA,
        TipoEvento.VOTO_REGISTRADO,
        TipoEvento.VOTACAO_SUSPENSA,
        TipoEvento.VOTACAO_RETOMADA,
    ]
    suspensao, retomada = log.registros[2], log.registros[3]
    assert suspensao.dados == {"motivo": "Queda de quórum", "total_votos": 1}
    assert retomada.dados == {"motivo_da_suspensao": "Queda de quórum", "total_votos": 1}
    assert log.verificar_integridade().integro


def test_suspensao_recusada_nao_grava_no_log():
    log = LogDeAuditoria("CA-2026")
    sessao = _sessao_em_votacao(log=log)

    with pytest.raises(ValueError):
        sessao.suspender("")

    assert [r.evento for r in log.registros] == [TipoEvento.VOTACAO_ABERTA]


# --- Integração com o quórum de instalação (#37) --------------------------------------


def _sessao_camara_em_votacao() -> SessaoVotacao:
    quorum = RegraCongresso.QUORUM_INSTALACAO_CAMARA
    sessao = SessaoVotacao(
        "PL-1-CAMARA-T1",
        RegraCongresso(TipoMateriaCongresso.LEI_ORDINARIA, CasaLegislativa.CAMARA),
        total_aptos=RegraCongresso.TOTAL_MEMBROS_CAMARA,
        quorum_instalacao=quorum,
    )
    sessao.abrir()
    sessao.registrar_presenca(*(f"DEP-{i:03d}" for i in range(quorum)))
    sessao.liberar_votacao()
    return sessao


def test_presenca_pode_ser_registrada_durante_a_suspensao():
    sessao = _sessao_camara_em_votacao()
    sessao.suspender("Aguardando parlamentares")

    sessao.registrar_presenca("DEP-CHEGOU")

    assert "DEP-CHEGOU" in sessao.presentes


def test_retomada_reafere_o_quorum_de_instalacao():
    sessao = _sessao_camara_em_votacao()
    sessao.suspender("Questão de ordem")

    sessao.retomar()

    assert sessao.estado == EstadoSessao.EM_VOTACAO

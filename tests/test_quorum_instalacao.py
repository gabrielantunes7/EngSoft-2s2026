"""Testes do quórum de instalação aferido na abertura da sessão (história #37).

Antes da #37, uma sessão da Câmara aceitava votos sem quórum e só descobria o
impedimento na apuração, já ENCERRADA (evidência E4 da Atividade 3). Agora a presença é
registrada à parte do voto e a votação só é liberada com a maioria absoluta presente
(CF, art. 47).
"""

import pytest

from votacao.auditoria import LogDeAuditoria, TipoEvento
from votacao.fabricas import FabricaAssembleia, FabricaCA, FabricaCongresso
from votacao.modelos import CasaLegislativa, StatusResultado, TipoMateriaCongresso, Voto
from votacao.regras.ca import RegraCA
from votacao.regras.congresso import RegraCongresso
from votacao.sessao import (
    EstadoSessao,
    QuorumInstalacaoError,
    SessaoVotacao,
    TransicaoInvalidaError,
)
from votacao.tramitacao import TramitacaoLegislativa

QUORUM_CAMARA = RegraCongresso.QUORUM_INSTALACAO_CAMARA  # 257
QUORUM_SENADO = RegraCongresso.QUORUM_INSTALACAO_SENADO  # 41


def _sessao_camara(log: LogDeAuditoria | None = None) -> SessaoVotacao:
    return SessaoVotacao(
        id_sessao="PL-1-CAMARA-T1",
        regra=RegraCongresso(TipoMateriaCongresso.LEI_ORDINARIA, CasaLegislativa.CAMARA),
        total_aptos=RegraCongresso.TOTAL_MEMBROS_CAMARA,
        log=log,
        quorum_instalacao=QUORUM_CAMARA,
    )


def _presentes(n: int, prefixo: str = "DEP") -> list[str]:
    return [f"{prefixo}-{i:03d}" for i in range(n)]


# --- Presença como operação distinta do voto -------------------------------------------


def test_presenca_e_registrada_sem_votar():
    sessao = _sessao_camara()
    sessao.abrir()

    total = sessao.registrar_presenca("DEP-001", "DEP-002")

    assert total == 2
    assert sessao.presentes == frozenset({"DEP-001", "DEP-002"})
    assert sessao.votos == ()


def test_presenca_repetida_nao_conta_duas_vezes():
    sessao = _sessao_camara()
    sessao.registrar_presenca("DEP-001")

    assert sessao.registrar_presenca("DEP-001", "DEP-001") == 1


def test_presenca_com_identificador_vazio_e_recusada_sem_registrar_os_demais():
    sessao = _sessao_camara()

    with pytest.raises(ValueError, match="vazio"):
        sessao.registrar_presenca("DEP-001", "  ")
    assert sessao.total_presentes == 0


def test_presenca_e_recusada_depois_de_fechada_a_urna():
    sessao = _sessao_camara()
    sessao.abrir()
    sessao.registrar_presenca(*_presentes(QUORUM_CAMARA))
    sessao.liberar_votacao()
    sessao.encerrar_votacao()

    with pytest.raises(TransicaoInvalidaError, match="já foi encerrada"):
        sessao.registrar_presenca("DEP-999")


def test_quem_vota_passa_a_constar_como_presente():
    sessao = _sessao_camara()
    sessao.abrir()
    sessao.registrar_presenca(*_presentes(QUORUM_CAMARA))
    sessao.liberar_votacao()

    sessao.registrar_voto(Voto(eleitor_id="DEP-RETARDATARIO", opcao="SIM"))

    assert "DEP-RETARDATARIO" in sessao.presentes
    assert sessao.total_presentes == QUORUM_CAMARA + 1


def test_quorum_de_instalacao_negativo_e_recusado():
    with pytest.raises(ValueError, match="quórum de instalação"):
        SessaoVotacao("S", RegraCA(), quorum_instalacao=-1)


# --- Aferição na abertura -------------------------------------------------------------


def test_reproducao_e4_sessao_sem_quorum_nao_colhe_votos():
    """E4: dez parlamentares não podem mais votar numa sessão que exige 257 presentes."""
    sessao = _sessao_camara()
    sessao.abrir()
    sessao.registrar_presenca(*_presentes(10))

    with pytest.raises(QuorumInstalacaoError) as erro:
        sessao.liberar_votacao()

    assert "há 10 presentes e são exigidos 257" in str(erro.value)
    assert "art. 47" in str(erro.value)
    assert sessao.estado == EstadoSessao.ABERTA
    with pytest.raises(TransicaoInvalidaError):
        sessao.registrar_voto(Voto(eleitor_id="DEP-000", opcao="SIM"))


def test_recusa_por_quorum_e_conflito_de_estado():
    # Subclasse de TransicaoInvalidaError: a API da interface responde 409.
    assert issubclass(QuorumInstalacaoError, TransicaoInvalidaError)


@pytest.mark.parametrize(
    ("presentes", "libera"),
    [
        pytest.param(QUORUM_CAMARA - 1, False, id="camara_256_abaixo"),
        pytest.param(QUORUM_CAMARA, True, id="camara_257_limite_exato"),
        pytest.param(QUORUM_CAMARA + 1, True, id="camara_258_acima"),
    ],
)
def test_fronteira_do_quorum_de_instalacao_na_camara(presentes: int, libera: bool):
    sessao = _sessao_camara()
    sessao.abrir()
    sessao.registrar_presenca(*_presentes(presentes))

    if libera:
        sessao.liberar_votacao()
        assert sessao.estado == EstadoSessao.EM_VOTACAO
    else:
        with pytest.raises(QuorumInstalacaoError):
            sessao.liberar_votacao()
        assert sessao.estado == EstadoSessao.ABERTA


def test_presenca_completada_depois_da_recusa_libera_a_votacao():
    sessao = _sessao_camara()
    sessao.abrir()
    sessao.registrar_presenca(*_presentes(QUORUM_CAMARA - 1))
    with pytest.raises(QuorumInstalacaoError):
        sessao.liberar_votacao()

    sessao.registrar_presenca("DEP-CHEGOU")
    sessao.liberar_votacao()

    assert sessao.estado == EstadoSessao.EM_VOTACAO


def test_instalacao_registra_presentes_no_log():
    log = LogDeAuditoria("PL-1-CAMARA-T1")
    sessao = _sessao_camara(log=log)
    sessao.abrir()
    sessao.registrar_presenca(*_presentes(300))

    sessao.liberar_votacao()

    abertura = log.registros[0]
    assert abertura.evento == TipoEvento.VOTACAO_ABERTA
    assert abertura.dados["total_presentes"] == 300
    assert abertura.dados["quorum_instalacao"] == QUORUM_CAMARA
    assert log.verificar_integridade().integro


def test_recusa_por_quorum_nao_grava_abertura_no_log():
    log = LogDeAuditoria("PL-1-CAMARA-T1")
    sessao = _sessao_camara(log=log)
    sessao.abrir()

    with pytest.raises(QuorumInstalacaoError):
        sessao.liberar_votacao()

    assert log.registros == ()


# --- Presente que não vota ------------------------------------------------------------


def test_presente_pode_nao_votar_sem_invalidar_a_sessao():
    sessao = _sessao_camara()
    sessao.abrir()
    sessao.registrar_presenca(*_presentes(300))
    sessao.liberar_votacao()
    for i in range(260):
        sessao.registrar_voto(Voto(eleitor_id=f"DEP-{i:03d}", opcao="SIM"))
    sessao.encerrar_votacao()

    resultado = sessao.apurar()

    assert sessao.total_presentes == 300
    assert sessao.total_presentes >= len(sessao.votos)
    assert resultado.quorum_atingido is True
    assert resultado.status == StatusResultado.APROVADO


def test_votos_abaixo_do_quorum_continuam_sem_deliberacao_na_apuracao():
    # Instalada com quórum, a votação ainda exige o mínimo de votos registrados
    # (inclusive abstenções) na apuração: é a "falta de quórum" da votação nominal.
    sessao = _sessao_camara()
    sessao.abrir()
    sessao.registrar_presenca(*_presentes(300))
    sessao.liberar_votacao()
    for i in range(QUORUM_CAMARA - 1):
        sessao.registrar_voto(Voto(eleitor_id=f"DEP-{i:03d}", opcao="SIM"))
    sessao.encerrar_votacao()

    assert sessao.apurar().status == StatusResultado.QUORUM_INSUFICIENTE


# --- Sem quórum de instalação: comportamento anterior ----------------------------------


def test_sem_quorum_de_instalacao_a_votacao_abre_sem_presenca():
    log = LogDeAuditoria("CA")
    sessao = SessaoVotacao("CA", RegraCA(), total_aptos=10, log=log)
    sessao.abrir()

    sessao.liberar_votacao()

    assert sessao.quorum_instalacao is None
    assert sessao.estado == EstadoSessao.EM_VOTACAO
    assert log.registros[0].dados == {"inicio": None, "fim": None, "total_aptos": 10}


def test_ca_e_assembleia_nao_tem_quorum_de_instalacao_na_abertura():
    assert FabricaCA().criar_sessao("CA").quorum_instalacao is None
    assert FabricaAssembleia().criar_sessao("AGE").quorum_instalacao is None


def test_fabrica_do_congresso_so_exige_quorum_quando_informado():
    fabrica = FabricaCongresso()

    assert fabrica.criar_sessao("S").quorum_instalacao is None
    assert fabrica.criar_sessao("S", quorum_instalacao=41).quorum_instalacao == 41


# --- Tramitação -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("casa", "quorum"),
    [
        pytest.param(CasaLegislativa.CAMARA, QUORUM_CAMARA, id="camara_257"),
        pytest.param(CasaLegislativa.SENADO, QUORUM_SENADO, id="senado_41"),
    ],
)
def test_tramitacao_convoca_sessao_com_quorum_da_casa(casa: CasaLegislativa, quorum: int):
    tramitacao = TramitacaoLegislativa(
        "PL-9/2026", TipoMateriaCongresso.LEI_ORDINARIA, casa_iniciadora=casa
    )

    sessao = tramitacao.nova_sessao()

    assert sessao.quorum_instalacao == quorum
    assert sessao.quorum_instalacao == sessao.regra.quorum_instalacao


def test_tramitacao_nao_libera_turno_sem_quorum_de_presenca():
    tramitacao = TramitacaoLegislativa("PL-9/2026", TipoMateriaCongresso.LEI_ORDINARIA)
    sessao = tramitacao.nova_sessao()
    sessao.abrir()
    sessao.registrar_presenca(*_presentes(10))

    with pytest.raises(QuorumInstalacaoError):
        sessao.liberar_votacao()
    assert tramitacao.historico == ()

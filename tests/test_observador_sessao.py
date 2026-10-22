"""Testes da aplicação do padrão Observer no ciclo de vida da Sessão de Votação."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from votacao.auditoria import LogDeAuditoria, TipoEvento
from votacao.modelos import StatusResultado, Voto
from votacao.observadores import (
    ObservadorAuditoria,
    ObservadorSessao,
)
from votacao.regras.ca import RegraCA
from votacao.sessao import EstadoSessao, SessaoVotacao, TransicaoInvalidaError


class ObservadorRegistroMemoria(ObservadorSessao):
    """Observador espião em memória para testes de ciclo de vida e notificações."""

    def __init__(self) -> None:
        self.eventos: list[dict[str, Any]] = []
        self.votos: list[Voto] = []

    def ao_mudar_estado(
        self,
        sessao: SessaoVotacao,
        estado_anterior: EstadoSessao,
        novo_estado: EstadoSessao,
        evento: TipoEvento | None = None,
        dados: Mapping[str, Any] | None = None,
    ) -> None:
        self.eventos.append(
            {
                "sessao_id": sessao.id_sessao,
                "estado_anterior": estado_anterior,
                "novo_estado": novo_estado,
                "evento": evento,
                "dados": dict(dados or {}),
            }
        )

    def ao_registrar_voto(
        self,
        sessao: SessaoVotacao,
        voto: Voto,
    ) -> str | None:
        self.votos.append(voto)
        return None


def test_observador_auditoria_valida_tipo():
    with pytest.raises(TypeError, match="LogDeAuditoria"):
        ObservadorAuditoria(object())  # type: ignore[arg-type]


def test_sessao_adicionar_observador_invalido():
    sessao = SessaoVotacao("CA-2026", RegraCA())
    with pytest.raises(TypeError, match="ObservadorSessao"):
        sessao.adicionar_observador(object())  # type: ignore[arg-type]


def test_sessao_construtor_rejeita_log_com_id_divergente():
    log_outro = LogDeAuditoria("SESSAO-2")
    with pytest.raises(ValueError, match="pertence à votação 'SESSAO-2'"):
        SessaoVotacao("SESSAO-1", RegraCA(), log=log_outro)


def test_liberar_votacao_estado_invalido_nao_corrompe_janela():
    sessao = SessaoVotacao("S1", RegraCA())
    inicio = datetime(2030, 1, 1, tzinfo=UTC)
    fim = datetime(2030, 1, 2, tzinfo=UTC)

    with pytest.raises(TransicaoInvalidaError):
        sessao.liberar_votacao(inicio=inicio, fim=fim)

    assert sessao.inicio_votacao is None
    assert sessao.fim_votacao is None


def test_sessao_adicionar_e_remover_observadores():
    sessao = SessaoVotacao("CA-2026", RegraCA())
    obs1 = ObservadorRegistroMemoria()
    obs2 = ObservadorRegistroMemoria()

    assert sessao.observadores == ()

    sessao.adicionar_observador(obs1)
    assert sessao.observadores == (obs1,)

    # Adicionar o mesmo observador não duplica
    sessao.adicionar_observador(obs1)
    assert sessao.observadores == (obs1,)

    sessao.adicionar_observador(obs2)
    assert sessao.observadores == (obs1, obs2)

    # Remoção com sucesso
    assert sessao.remover_observador(obs1) is True
    assert sessao.observadores == (obs2,)

    # Remoção de observador não presente
    assert sessao.remover_observador(obs1) is False
    assert sessao.observadores == (obs2,)


def test_sessao_retrocompatibilidade_parametro_log():
    log = LogDeAuditoria("CA-2026")
    sessao = SessaoVotacao("CA-2026", RegraCA(), log=log)

    assert sessao.log is log
    assert len(sessao.observadores) == 1
    assert isinstance(sessao.observadores[0], ObservadorAuditoria)
    assert sessao.observadores[0].log is log

    # Remoção do observador de auditoria reflete na property .log
    sessao.remover_observador(sessao.observadores[0])
    assert sessao.log is None


def test_sessao_notifica_observador_memoria_ao_longo_do_ciclo():
    inicio = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    fim = datetime(2026, 10, 1, 17, 0, tzinfo=UTC)
    meio = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)

    sessao = SessaoVotacao("CA-2026", RegraCA(), total_aptos=10, relogio=lambda: meio)
    espiao = ObservadorRegistroMemoria()
    sessao.adicionar_observador(espiao)

    sessao.abrir()
    sessao.liberar_votacao(inicio=inicio, fim=fim)

    voto = Voto(eleitor_id="aluno-1", opcao="Chapa A")
    sessao.registrar_voto(voto)

    sessao.encerrar_votacao()
    resultado = sessao.apurar()

    # Confere votos recebidos pelo observador
    assert espiao.votos == [voto]

    # Confere transições registradas
    transicoes = [(e["estado_anterior"], e["novo_estado"], e["evento"]) for e in espiao.eventos]
    esperadas = [
        (EstadoSessao.CRIADA, EstadoSessao.ABERTA, None),
        (EstadoSessao.ABERTA, EstadoSessao.EM_VOTACAO, TipoEvento.VOTACAO_ABERTA),
        (EstadoSessao.EM_VOTACAO, EstadoSessao.EM_APURACAO, TipoEvento.VOTACAO_ENCERRADA),
        (EstadoSessao.EM_APURACAO, EstadoSessao.ENCERRADA, TipoEvento.RESULTADO_PROCLAMADO),
    ]
    assert transicoes == esperadas

    # Confere dados dos eventos
    dados_abertura = espiao.eventos[1]["dados"]
    assert dados_abertura["total_aptos"] == 10
    assert dados_abertura["inicio"] == inicio.isoformat()
    assert dados_abertura["fim"] == fim.isoformat()

    dados_encerramento = espiao.eventos[2]["dados"]
    assert dados_encerramento["total_votos"] == 1

    dados_proclamacao = espiao.eventos[3]["dados"]
    assert dados_proclamacao["status"] == StatusResultado.ELEITO.value
    assert dados_proclamacao["vencedor_ou_decisao"] == "CHAPA A"
    assert resultado.vencedor_ou_decisao == "CHAPA A"


def test_sessao_multiplos_observadores_incluindo_auditoria():
    log = LogDeAuditoria("CA-2026")
    obs_auditoria = ObservadorAuditoria(log)
    obs_memoria = ObservadorRegistroMemoria()

    sessao = SessaoVotacao(
        "CA-2026",
        RegraCA(),
        total_aptos=5,
        observadores=[obs_auditoria, obs_memoria],
    )

    sessao.abrir()
    sessao.liberar_votacao()

    voto = Voto(eleitor_id="101", opcao="Chapa A")
    protocolo = sessao.registrar_voto(voto)

    sessao.encerrar_votacao()
    sessao.apurar()

    # O protocolo devolvido é o hash gerado pelo ObservadorAuditoria
    assert isinstance(protocolo, str)
    assert len(protocolo) == 64
    assert log.contem_protocolo(protocolo)

    # Observador em memória registrou o voto e todos os 4 eventos
    assert len(obs_memoria.votos) == 1
    assert len(obs_memoria.eventos) == 4

    # A cadeia de auditoria está íntegra
    verificacao = log.verificar_integridade()
    assert verificacao.integro is True

"""Testes da aplicação do padrão Observer no ciclo de vida da Sessão de Votação."""

from datetime import UTC, datetime
from typing import Any

import pytest

from votacao.auditoria import LogDeAuditoria, TipoEvento
from votacao.modelos import StatusResultado, Voto
from votacao.observadores import (
    ObservadorAuditoria,
    ObservadorCallback,
    ObservadorRegistroMemoria,
)
from votacao.regras.ca import RegraCA
from votacao.sessao import EstadoSessao, SessaoVotacao


def test_observador_auditoria_valida_tipo():
    with pytest.raises(TypeError, match="LogDeAuditoria"):
        ObservadorAuditoria(object())  # type: ignore[arg-type]


def test_sessao_adicionar_observador_invalido():
    sessao = SessaoVotacao("CA-2026", RegraCA())
    with pytest.raises(TypeError, match="ObservadorSessao"):
        sessao.adicionar_observador(object())  # type: ignore[arg-type]


def test_sessao_adicionar_observador_auditoria_sessao_divergente():
    sessao = SessaoVotacao("SESSAO-1", RegraCA())
    log_outro = LogDeAuditoria("SESSAO-2")
    obs_invalido = ObservadorAuditoria(log_outro)

    with pytest.raises(ValueError, match="pertence à votação 'SESSAO-2'"):
        sessao.adicionar_observador(obs_invalido)


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
    espião = ObservadorRegistroMemoria()
    sessao.adicionar_observador(espião)

    sessao.abrir()
    sessao.liberar_votacao(inicio=inicio, fim=fim)

    voto = Voto(eleitor_id="aluno-1", opcao="Chapa A")
    sessao.registrar_voto(voto)

    sessao.encerrar_votacao()
    resultado = sessao.apurar()

    # Confere votos recebidos pelo observador
    assert espião.votos == [voto]

    # Confere transições registradas
    transicoes = [(e["estado_anterior"], e["novo_estado"], e["evento"]) for e in espião.eventos]
    esperadas = [
        (EstadoSessao.CRIADA, EstadoSessao.ABERTA, None),
        (EstadoSessao.ABERTA, EstadoSessao.EM_VOTACAO, TipoEvento.VOTACAO_ABERTA),
        (EstadoSessao.EM_VOTACAO, EstadoSessao.EM_APURACAO, TipoEvento.VOTACAO_ENCERRADA),
        (EstadoSessao.EM_APURACAO, EstadoSessao.ENCERRADA, TipoEvento.RESULTADO_PROCLAMADO),
    ]
    assert transicoes == esperadas

    # Confere dados dos eventos
    dados_abertura = espião.eventos[1]["dados"]
    assert dados_abertura["total_aptos"] == 10
    assert dados_abertura["inicio"] == inicio.isoformat()
    assert dados_abertura["fim"] == fim.isoformat()

    dados_encerramento = espião.eventos[2]["dados"]
    assert dados_encerramento["total_votos"] == 1

    dados_proclamacao = espião.eventos[3]["dados"]
    assert dados_proclamacao["status"] == StatusResultado.ELEITO.value
    assert dados_proclamacao["vencedor_ou_decisao"] == "CHAPA A"
    assert resultado.vencedor_ou_decisao == "CHAPA A"


def test_sessao_multiplos_observadores_incluindo_auditoria_e_callback():
    log = LogDeAuditoria("CA-2026")
    obs_auditoria = ObservadorAuditoria(log)
    obs_memoria = ObservadorRegistroMemoria()

    chamadas_callback_voto: list[Voto] = []
    chamadas_callback_estado: list[dict[str, Any]] = []

    obs_callback = ObservadorCallback(
        quando_mudar_estado=lambda **kwargs: chamadas_callback_estado.append(kwargs),
        quando_registrar_voto=lambda v: chamadas_callback_voto.append(v),
    )

    sessao = SessaoVotacao(
        "CA-2026",
        RegraCA(),
        total_aptos=5,
        observadores=[obs_auditoria, obs_memoria, obs_callback],
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

    # Observador callback disparou em todas as etapas
    assert len(chamadas_callback_voto) == 1
    assert chamadas_callback_voto[0] == voto
    assert len(chamadas_callback_estado) == 4

    # A cadeia de auditoria está íntegra
    verificacao = log.verificar_integridade()
    assert verificacao.integro is True


def test_observador_callback_sem_handlers_no_op():
    obs_vazio = ObservadorCallback()
    sessao = SessaoVotacao("CA-2026", RegraCA(), observadores=[obs_vazio])

    sessao.abrir()
    sessao.liberar_votacao()
    protocolo = sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))

    assert protocolo is None

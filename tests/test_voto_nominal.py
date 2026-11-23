"""Testes do registro nominal e aberto de votos no log para assembleias (história #44).

As histórias #27 e #28 aplicaram sigilo e embaralhamento a todos os votos. Na assembleia
societária, porém, o voto é aberto: a Lei das S/A (art. 130) e a CVM exigem o mapa de
votação identificado na ata (D-AUD-04).
"""

import random
from dataclasses import replace

import pytest

from votacao.auditoria import LogDeAuditoria, PoliticaIdentificacao, TipoEvento
from votacao.fabricas import FabricaAssembleia, FabricaCA
from votacao.modelos import TipoDecisaoAssembleia, Voto
from votacao.recontagem import recontar
from votacao.regras.assembleia import RegraAssembleia
from votacao.sessao import VotoRecusadoError

VOTOS = [
    Voto(eleitor_id="AC-001", opcao="SIM", peso=500_000),
    Voto(eleitor_id="AC-002", opcao="NAO", peso=300_000),
    Voto(eleitor_id="PROC-101", opcao="SIM", peso=150_000, representados=("AC-004", "AC-005")),
]


def _log_nominal(**kwargs) -> LogDeAuditoria:
    return LogDeAuditoria("AGE-2026", politica=PoliticaIdentificacao.NOMINAL, **kwargs)


def _assembleia(log: LogDeAuditoria):
    sessao = FabricaAssembleia().criar_sessao(
        log.id_votacao,
        total_aptos=1_000_000,
        tipo_decisao=TipoDecisaoAssembleia.MAIORIA_SIMPLES,
        log=log,
    )
    sessao.abrir()
    sessao.liberar_votacao()
    return sessao


# --- Política configurável -------------------------------------------------------------


def test_politica_padrao_continua_sigilosa():
    assert LogDeAuditoria("CA-2026").politica == PoliticaIdentificacao.SIGILOSA


def test_log_nominal_grava_titular_opcao_e_peso_em_claro():
    log = _log_nominal()

    registro = log.registrar_voto(VOTOS[0])

    assert registro.evento == TipoEvento.VOTO_REGISTRADO
    assert registro.dados == {"eleitor_id": "AC-001", "opcao": "SIM", "peso": 500_000}


def test_voto_consolidado_registra_os_representados():
    log = _log_nominal()

    registro = log.registrar_voto(VOTOS[2])

    assert registro.dados["representados"] == ["AC-004", "AC-005"]


# --- Cédulas sem embaralhamento no modo aberto -----------------------------------------


def test_modo_nominal_publica_as_cedulas_na_ordem_de_registro():
    # A mesma semente que embaralha no modo sigiloso não altera a ordem no nominal.
    log = _log_nominal(aleatorio=random.Random(2026))
    for voto in VOTOS:
        log.registrar_voto(voto)

    encerramento = log.registrar(TipoEvento.VOTACAO_ENCERRADA)

    assert encerramento.dados["cedulas"] == [[v.opcao, v.peso] for v in VOTOS]


def test_modo_sigiloso_continua_embaralhando():
    log = LogDeAuditoria("CA-2026", aleatorio=random.Random(2026))
    votos = [Voto(eleitor_id=str(i), opcao=f"Chapa {i}") for i in range(8)]
    for voto in votos:
        log.registrar_voto(voto)

    encerramento = log.registrar(TipoEvento.VOTACAO_ENCERRADA)

    assert encerramento.dados["cedulas"] != [[v.opcao, v.peso] for v in votos]


# --- Mapa nominal para a ata -----------------------------------------------------------


def test_mapa_nominal_associa_cada_acionista_ao_seu_voto():
    log = _log_nominal()
    for voto in VOTOS:
        log.registrar_voto(voto)

    mapa = log.mapa_nominal()

    assert mapa == [
        {"eleitor_id": "AC-001", "opcao": "SIM", "peso": 500_000},
        {"eleitor_id": "AC-002", "opcao": "NAO", "peso": 300_000},
        {
            "eleitor_id": "PROC-101",
            "opcao": "SIM",
            "peso": 150_000,
            "representados": ["AC-004", "AC-005"],
        },
    ]


def test_mapa_nominal_e_uma_copia_que_nao_altera_o_log():
    log = _log_nominal()
    log.registrar_voto(VOTOS[0])

    log.mapa_nominal()[0]["opcao"] = "NAO"

    assert log.mapa_nominal()[0]["opcao"] == "SIM"
    assert log.verificar_integridade().integro


def test_log_sigiloso_nao_tem_mapa_nominal():
    log = LogDeAuditoria("CA-2026")
    log.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))

    with pytest.raises(ValueError, match="sigiloso"):
        log.mapa_nominal()


# --- Rejeição de voto sigiloso em assembleia -------------------------------------------


def test_assembleia_recusa_voto_com_log_sigiloso():
    sessao = _assembleia(LogDeAuditoria("AGE-2026"))

    with pytest.raises(VotoRecusadoError, match="exige voto aberto e nominal"):
        sessao.registrar_voto(VOTOS[0])
    assert sessao.votos == ()


def test_assembleia_aceita_voto_com_log_nominal():
    log = _log_nominal()
    sessao = _assembleia(log)

    sessao.registrar_voto(VOTOS[0])

    assert len(sessao.votos) == 1
    assert log.mapa_nominal()[0]["eleitor_id"] == "AC-001"


def test_sessao_de_assembleia_exige_voto_nominal_e_a_de_ca_nao():
    assert FabricaAssembleia().criar_sessao("AGE").exige_voto_nominal is True
    assert FabricaCA().criar_sessao("CA").exige_voto_nominal is False


# --- Integridade e recontagem no modo aberto -------------------------------------------


def test_verificacao_contra_a_ancora_funciona_no_modo_nominal():
    log = _log_nominal()
    sessao = _assembleia(log)
    for voto in VOTOS:
        sessao.registrar_voto(voto)
    sessao.encerrar_votacao()
    sessao.apurar()
    ancora = log.resumo_encerramento()

    assert log.verificar_integridade(ancora=ancora).integro is True
    assert ancora.total_votos == len(VOTOS)

    # Trocar a opção de um acionista é detectado, como no modo sigiloso
    registros = list(log.registros)
    indice = next(i for i, r in enumerate(registros) if r.evento == TipoEvento.VOTO_REGISTRADO)
    log._registros[indice] = replace(
        registros[indice], dados={**registros[indice].dados, "opcao": "NAO"}
    )
    assert log.verificar_integridade(ancora=ancora).integro is False


def test_recontagem_funciona_no_modo_nominal():
    log = _log_nominal()
    sessao = _assembleia(log)
    for voto in VOTOS:
        sessao.registrar_voto(voto)
    sessao.encerrar_votacao()
    sessao.apurar()

    recontagem = recontar(
        log,
        RegraAssembleia(tipo_decisao=TipoDecisaoAssembleia.MAIORIA_SIMPLES),
        ancora=log.resumo_encerramento(),
    )

    assert recontagem.confere is True
    assert recontagem.resultado.contagem_por_opcao == {"SIM": 650_000, "NAO": 300_000}


# --- Regressão: CA continua com sigilo estrito -----------------------------------------


@pytest.mark.regressao
def test_eleicao_de_ca_continua_com_sigilo_estrito():
    log = LogDeAuditoria("CA-2026", aleatorio=random.Random(1))
    sessao = FabricaCA().criar_sessao("CA-2026", total_aptos=10, log=log)
    sessao.abrir()
    sessao.liberar_votacao()
    for ra, chapa in (("101", "Chapa A"), ("102", "Chapa B"), ("103", "Chapa A")):
        sessao.registrar_voto(Voto(eleitor_id=ra, opcao=chapa))
    sessao.encerrar_votacao()

    votos = [r for r in log.registros if r.evento == TipoEvento.VOTO_REGISTRADO]
    assert all(r.dados == {} for r in votos)
    assert all(ra not in str([r.dados for r in log.registros]) for ra in ("101", "102", "103"))
    assert sorted(log.registros[-1].dados["cedulas"]) == [
        ["Chapa A", 1],
        ["Chapa A", 1],
        ["Chapa B", 1],
    ]

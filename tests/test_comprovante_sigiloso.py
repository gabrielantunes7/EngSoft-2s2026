"""Testes do comprovante que não revela a opção e das cédulas embaralhadas (história #28).

Antes da #28, cada VOTO_REGISTRADO guardava opção e peso em ordem de chegada: quem tinha
o protocolo lia o voto (D-AUD-02), e quem anotou a ordem de quem votou ligava cada voto
a um eleitor (D-AUD-03). Agora a inclusão e o conteúdo do voto entram na cadeia em
momentos separados.
"""

import json
import random
from collections import Counter
from dataclasses import asdict, replace

import pytest

from votacao.auditoria import (
    INSTRUCAO_COMPROVANTE,
    LogDeAuditoria,
    SituacaoComprovante,
    TipoEvento,
)
from votacao.modelos import Voto

VOTOS = [
    Voto(eleitor_id="RA-101", opcao="Chapa A"),
    Voto(eleitor_id="RA-102", opcao="Chapa B"),
    Voto(eleitor_id="RA-103", opcao="Chapa A"),
    Voto(eleitor_id="RA-104", opcao="Chapa C"),
    Voto(eleitor_id="RA-105", opcao="Chapa B"),
    Voto(eleitor_id="RA-106", opcao="Chapa A"),
]


def _log(aleatorio: random.Random | None = None) -> tuple[LogDeAuditoria, list[str]]:
    log = LogDeAuditoria("CA-2026", aleatorio=aleatorio)
    log.registrar(TipoEvento.VOTACAO_ABERTA)
    protocolos = [log.registrar_voto(v).hash for v in VOTOS]
    return log, protocolos


def _encerrado(aleatorio: random.Random | None = None):
    log, protocolos = _log(aleatorio)
    log.registrar(TipoEvento.VOTACAO_ENCERRADA, {"total_votos": len(VOTOS)})
    return log, protocolos, log.resumo_encerramento()


# --- Registro do voto sem conteúdo -----------------------------------------------------


def test_voto_registrado_nao_tem_opcao_peso_nem_eleitor():
    log, protocolos = _log()

    for protocolo in protocolos:
        registro = next(r for r in log.registros if r.hash == protocolo)
        assert registro.evento == TipoEvento.VOTO_REGISTRADO
        assert registro.dados == {}


def test_protocolos_sao_distintos_mesmo_sem_conteudo():
    _, protocolos = _log()

    assert len(set(protocolos)) == len(protocolos)


# --- Cédulas publicadas no encerramento -----------------------------------------------


def test_encerramento_publica_as_cedulas_com_opcao_e_peso():
    log, _, _ = _encerrado()

    encerramento = log.registros[-1]
    assert encerramento.evento == TipoEvento.VOTACAO_ENCERRADA
    assert encerramento.dados["total_votos"] == len(VOTOS)
    assert all(len(cedula) == 2 for cedula in encerramento.dados["cedulas"])


def test_multiconjunto_das_cedulas_e_igual_ao_dos_votos():
    log, _, _ = _encerrado()

    cedulas = log.registros[-1].dados["cedulas"]
    votos_registrados = [r for r in log.registros if r.evento == TipoEvento.VOTO_REGISTRADO]

    assert Counter(tuple(c) for c in cedulas) == Counter((v.opcao, v.peso) for v in VOTOS)
    assert len(cedulas) == len(votos_registrados)


def test_cedulas_nao_tem_horario_individual():
    log, _, _ = _encerrado()

    for cedula in log.registros[-1].dados["cedulas"]:
        assert cedula[0] in {"Chapa A", "Chapa B", "Chapa C"}
        assert isinstance(cedula[1], int)


def test_ordem_publicada_difere_da_ordem_de_chegada_com_fonte_deterministica():
    # RNF-AUD-02: com semente fixa, o embaralhamento é reprodutível e não é a identidade.
    log, _, _ = _encerrado(aleatorio=random.Random(2026))

    publicada = [tuple(c) for c in log.registros[-1].dados["cedulas"]]
    chegada = [(v.opcao, v.peso) for v in VOTOS]

    assert publicada != chegada
    assert sorted(publicada) == sorted(chegada)


def test_mesma_semente_produz_a_mesma_ordem():
    a, _, _ = _encerrado(aleatorio=random.Random(7))
    b, _, _ = _encerrado(aleatorio=random.Random(7))

    assert a.registros[-1].dados["cedulas"] == b.registros[-1].dados["cedulas"]


def test_fonte_padrao_e_o_gerador_do_sistema_operacional():
    import secrets

    log = LogDeAuditoria("CA-2026")

    assert isinstance(log._aleatorio, secrets.SystemRandom)


def test_cedulas_entram_no_hash_ancorado():
    log, _, ancora = _encerrado()
    assert log.verificar_integridade(ancora=ancora).integro

    # Trocar uma cédula muda o hash do encerramento: a âncora denuncia.
    encerramento = log.registros[-1]
    cedulas = [list(c) for c in encerramento.dados["cedulas"]]
    cedulas[0][0] = "Chapa X"
    adulterado = replace(encerramento, dados={**encerramento.dados, "cedulas": cedulas})
    log._registros[-1] = adulterado

    assert log.verificar_integridade(ancora=ancora).integro is False


def test_votacao_sem_votos_publica_lista_vazia():
    log = LogDeAuditoria("CA-2026")
    log.registrar(TipoEvento.VOTACAO_ABERTA)

    encerramento = log.registrar(TipoEvento.VOTACAO_ENCERRADA)

    assert encerramento.dados == {"cedulas": []}


# --- Consulta do comprovante -----------------------------------------------------------


def test_consulta_confirma_inclusao_na_urna_encerrada():
    log, protocolos, ancora = _encerrado()

    consulta = log.consultar_comprovante(protocolos[2], ancora=ancora)

    assert consulta.situacao == SituacaoComprovante.INCLUIDO
    assert consulta.incluido is True
    assert consulta.mensagem == "Registrado e incluído na urna encerrada."


def test_consulta_antes_do_encerramento_informa_que_a_urna_esta_aberta():
    log, protocolos = _log()

    consulta = log.consultar_comprovante(protocolos[0])

    assert consulta.situacao == SituacaoComprovante.REGISTRADO_URNA_ABERTA
    assert consulta.incluido is False


def test_protocolo_inexistente_orienta_a_procurar_a_comissao():
    log, _, ancora = _encerrado()

    consulta = log.consultar_comprovante("f" * 64, ancora=ancora)

    assert consulta.situacao == SituacaoComprovante.NAO_ENCONTRADO
    assert "comissão eleitoral" in consulta.mensagem


def test_hash_de_evento_que_nao_e_voto_nao_e_confirmado_como_voto():
    log, _, ancora = _encerrado()

    consulta = log.consultar_comprovante(log.registros[0].hash, ancora=ancora)

    assert consulta.situacao == SituacaoComprovante.NAO_ENCONTRADO


def test_cadeia_reprovada_nao_confirma_a_inclusao():
    log, protocolos, ancora = _encerrado()
    abertura = log.registros[0]
    log._registros[0] = replace(abertura, dados={"adulterado": True})

    consulta = log.consultar_comprovante(protocolos[0], ancora=ancora)

    assert consulta.situacao == SituacaoComprovante.CADEIA_REPROVADA
    assert consulta.incluido is False


def test_consulta_traz_instrucao_nao_tecnica():
    log, protocolos, ancora = _encerrado()

    consulta = log.consultar_comprovante(protocolos[0], ancora=ancora)

    # RNF-AUD-05: diz o que o comprovante prova e o que não revela, sem jargão.
    assert consulta.instrucao == INSTRUCAO_COMPROVANTE
    assert "foi registrado" in consulta.instrucao
    assert "não mostra em quem você votou" in consulta.instrucao
    for jargao in ("hash", "SHA", "cadeia", "âncora"):
        assert jargao not in consulta.instrucao


# --- RNF-AUD-01: varredura completa ----------------------------------------------------


def test_nenhum_registro_nem_retorno_de_consulta_expoe_eleitor_ou_voto():
    log, protocolos, ancora = _encerrado()
    log.registrar(TipoEvento.RESULTADO_PROCLAMADO, {"vencedor": "CHAPA A"})

    # Nenhum registro da cadeia contém identificação de eleitor.
    cadeia = json.dumps([asdict(r) for r in log.registros], default=str, ensure_ascii=False)
    for voto in VOTOS:
        assert voto.eleitor_id not in cadeia

    # O registro localizado por um comprovante não contém opção nem peso.
    for protocolo in protocolos:
        registro = next(r for r in log.registros if r.hash == protocolo)
        assert "opcao" not in registro.dados
        assert "peso" not in registro.dados

        consulta = log.consultar_comprovante(protocolo, ancora=ancora)
        retorno = json.dumps(asdict(consulta), ensure_ascii=False)
        for valor in ("Chapa A", "Chapa B", "Chapa C", "opcao", "peso", "RA-1"):
            assert valor not in retorno
        assert registro.timestamp.isoformat() not in retorno


@pytest.mark.parametrize("peso", [1, 80000], ids=["voto_unitario", "voto_ponderado"])
def test_voto_ponderado_entra_nas_cedulas_com_o_peso(peso: int):
    log = LogDeAuditoria("AGE-2026")
    registro = log.registrar_voto(Voto(eleitor_id="AC-001", opcao="SIM", peso=peso))
    encerramento = log.registrar(TipoEvento.VOTACAO_ENCERRADA)

    assert registro.dados == {}
    assert encerramento.dados["cedulas"] == [["SIM", peso]]

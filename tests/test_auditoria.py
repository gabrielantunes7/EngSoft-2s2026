"""Testes unitários para o log de auditoria encadeado (LogDeAuditoria).

Os testes de adulteração acessam `_registros` diretamente de propósito: simulam um
fraudador com acesso ao armazenamento, que altera os registros sem passar pela API do
log. É exatamente esse cenário que o encadeamento por hash existe para denunciar.
"""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from itertools import pairwise

import pytest

from votacao.auditoria import HASH_GENESE, LogDeAuditoria, TipoEvento
from votacao.modelos import Voto
from votacao.motor import MotorApuracao
from votacao.regras import RegraCA

VOTOS_DA_ELEICAO = (
    Voto(eleitor_id="ra_281199", opcao="Chapa Renova"),
    Voto(eleitor_id="ra_242352", opcao="Chapa Avanca"),
    Voto(eleitor_id="ra_247314", opcao="Chapa Renova"),
    Voto(eleitor_id="ra_254467", opcao="BRANCO"),
)


def relogio_sequencial() -> Callable[[], datetime]:
    """Devolve um relógio determinístico que avança um segundo a cada chamada."""
    instantes = (datetime(2026, 9, 17, 12, 0, segundo, tzinfo=UTC) for segundo in range(60))
    return lambda: next(instantes)


def criar_log(id_votacao: str = "eleicao-ca-2026") -> LogDeAuditoria:
    """Cria um log vazio com relógio determinístico."""
    return LogDeAuditoria(id_votacao, relogio=relogio_sequencial())


def criar_log_de_eleicao() -> LogDeAuditoria:
    """Cria um log completo: abertura, quatro votos e encerramento."""
    log = criar_log()
    log.registrar(TipoEvento.VOTACAO_ABERTA, {"cargos": "diretoria"})
    for voto in VOTOS_DA_ELEICAO:
        log.registrar_voto(voto)
    log.registrar(TipoEvento.VOTACAO_ENCERRADA)
    return log


def test_auditoria_id_de_votacao_invalido():
    with pytest.raises(ValueError, match="não pode ser vazio"):
        LogDeAuditoria("   ")


def test_auditoria_primeiro_registro_parte_do_hash_de_genese():
    log = criar_log()

    registro = log.registrar(TipoEvento.VOTACAO_ABERTA)

    assert registro.indice == 0
    assert registro.hash_anterior == HASH_GENESE
    assert registro.id_votacao == "eleicao-ca-2026"
    assert registro.evento == TipoEvento.VOTACAO_ABERTA


def test_auditoria_encadeia_cada_registro_ao_hash_do_anterior():
    log = criar_log_de_eleicao()

    registros = log.registros

    assert len(registros) == 6
    assert log.ultimo_hash == registros[-1].hash
    for anterior, seguinte in pairwise(registros):
        assert seguinte.indice == anterior.indice + 1
        assert seguinte.hash_anterior == anterior.hash


def test_auditoria_log_vazio_tem_hash_de_genese_e_e_integro():
    log = criar_log()

    resultado = log.verificar_integridade()

    assert log.registros == ()
    assert log.ultimo_hash == HASH_GENESE
    assert resultado.integro is True


def test_auditoria_cadeia_intacta_nao_aponta_divergencia():
    log = criar_log_de_eleicao()

    resultado = log.verificar_integridade()

    assert resultado.integro is True
    assert resultado.indice_divergente is None
    assert resultado.motivo is None


def test_auditoria_detecta_adulteracao_de_conteudo():
    log = criar_log_de_eleicao()

    log.registros[2].dados["opcao"] = "Chapa Renova"
    resultado = log.verificar_integridade()

    assert resultado.integro is False
    assert resultado.indice_divergente == 2
    assert resultado.motivo is not None
    assert "hash gravado" in resultado.motivo


def test_auditoria_detecta_adulteracao_com_hash_recalculado():
    log = criar_log_de_eleicao()

    # Fraudador que reescreve o registro e recalcula seu hash para encobrir a troca:
    # o próprio registro fica coerente, mas o elo do registro seguinte não fecha mais.
    forjado = replace(log.registros[2], dados={"opcao": "Chapa Renova", "peso": 1})
    log._registros[2] = replace(forjado, hash=forjado.calcular_hash())
    resultado = log.verificar_integridade()

    assert resultado.integro is False
    assert resultado.indice_divergente == 3
    assert resultado.motivo is not None
    assert "elo" in resultado.motivo


def test_auditoria_detecta_remocao_de_registro():
    log = criar_log_de_eleicao()

    del log._registros[2]
    resultado = log.verificar_integridade()

    assert resultado.integro is False
    assert resultado.indice_divergente == 2
    assert resultado.motivo is not None
    assert "posição na cadeia" in resultado.motivo


def test_auditoria_detecta_reordenacao_de_registros():
    log = criar_log_de_eleicao()

    log._registros[1], log._registros[2] = log._registros[2], log._registros[1]
    resultado = log.verificar_integridade()

    assert resultado.integro is False
    assert resultado.indice_divergente == 1


def test_auditoria_comprovantes_sao_distintos_para_votos_identicos():
    log = criar_log()
    voto = Voto(eleitor_id="ra_281199", opcao="Chapa Renova")

    primeiro = log.registrar_voto(voto)
    segundo = log.registrar_voto(voto)

    assert primeiro.dados == segundo.dados
    assert primeiro.hash != segundo.hash
    assert log.comprovante(0) == primeiro.hash
    assert log.comprovante(1) == segundo.hash


def test_auditoria_registro_de_voto_nao_expoe_o_eleitor():
    log = criar_log_de_eleicao()

    conteudo = [(registro.dados, registro.hash) for registro in log.registros]

    assert all("eleitor_id" not in dados for dados, _ in conteudo)
    for voto in VOTOS_DA_ELEICAO:
        assert not any(voto.eleitor_id in str(item) for item in conteudo)


def test_auditoria_registra_o_peso_do_voto_ponderado():
    log = criar_log("assembleia-2026")

    registro = log.registrar_voto(Voto(eleitor_id="fundo_investimento", opcao="SIM", peso=80000))

    assert registro.evento == TipoEvento.VOTO_REGISTRADO
    assert registro.dados == {"opcao": "SIM", "peso": 80000}
    assert log.verificar_integridade().integro is True


def test_auditoria_copia_os_dados_recebidos():
    log = criar_log()
    dados = {"cargos": "diretoria"}

    registro = log.registrar(TipoEvento.VOTACAO_ABERTA, dados)
    dados["cargos"] = "conselho fiscal"

    assert registro.dados == {"cargos": "diretoria"}
    assert log.verificar_integridade().integro is True


def test_auditoria_evento_sem_dados_registra_conteudo_vazio():
    log = criar_log()

    registro = log.registrar(TipoEvento.VOTACAO_ENCERRADA)

    assert registro.dados == {}


def test_auditoria_usa_o_relogio_do_sistema_em_utc_por_padrao():
    log = LogDeAuditoria("eleicao-ca-2026")

    registro = log.registrar(TipoEvento.VOTACAO_ABERTA)

    assert registro.timestamp.tzinfo is not None
    assert registro.timestamp.utcoffset() == datetime.now(UTC).utcoffset()


def test_auditoria_comprovante_de_indice_inexistente():
    log = criar_log_de_eleicao()

    with pytest.raises(ValueError, match="índice 99"):
        log.comprovante(99)

    with pytest.raises(ValueError, match="índice -1"):
        log.comprovante(-1)


def test_auditoria_permite_reconferir_a_contagem_apurada():
    log = criar_log_de_eleicao()
    regra = RegraCA(quorum_minimo_votantes=3)

    resultado = MotorApuracao.apurar(votos=VOTOS_DA_ELEICAO, regra=regra, total_aptos_ou_capital=10)
    contagem_do_log: dict[str, int] = {}
    for registro in log.registros:
        if registro.evento is TipoEvento.VOTO_REGISTRADO:
            opcao = str(registro.dados["opcao"]).strip().upper()
            contagem_do_log[opcao] = contagem_do_log.get(opcao, 0) + 1

    assert log.verificar_integridade().integro is True
    assert contagem_do_log == resultado.contagem_por_opcao
    assert resultado.vencedor_ou_decisao == "CHAPA RENOVA"

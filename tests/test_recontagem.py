"""Testes da recontagem do resultado a partir do log de auditoria (história #29).

O fiscal reapura a votação usando só o que o log publica (cédulas do encerramento e total
de aptos da abertura) e compara com o RESULTADO_PROCLAMADO (D-AUD-05, D-AUD-09).
"""

import time
from dataclasses import replace

import pytest

from votacao.auditoria import HASH_GENESE, LogDeAuditoria, RegistroAuditoria, TipoEvento
from votacao.modelos import (
    CasaLegislativa,
    StatusResultado,
    TipoDecisaoAssembleia,
    TipoMateriaCongresso,
    Voto,
)
from votacao.recontagem import RecontagemRecusadaError, recontar
from votacao.regras.assembleia import RegraAssembleia
from votacao.regras.base import RegraDeVotacao
from votacao.regras.ca import RegraCA
from votacao.regras.congresso import RegraCongresso
from votacao.sessao import SessaoVotacao


def _votacao_completa(
    regra: RegraDeVotacao, total_aptos: int, votos: list[Voto], id_votacao: str = "V-2026"
) -> LogDeAuditoria:
    log = LogDeAuditoria(id_votacao)
    sessao = SessaoVotacao(id_votacao, regra, total_aptos=total_aptos, log=log)
    sessao.abrir()
    sessao.liberar_votacao()
    for voto in votos:
        sessao.registrar_voto(voto)
    sessao.encerrar_votacao()
    sessao.apurar()
    return log


def _reescrever_a_partir_de(log: LogDeAuditoria, indice: int, dados: dict) -> None:
    """Fraudador que troca um registro e recalcula os hashes dali em diante."""
    registros = list(log.registros)
    registros[indice] = replace(registros[indice], dados=dados)
    hash_anterior = registros[indice - 1].hash if indice > 0 else HASH_GENESE
    for posicao in range(indice, len(registros)):
        original = registros[posicao]
        refeito = RegistroAuditoria.criar(
            indice=posicao,
            evento=original.evento,
            id_votacao=original.id_votacao,
            timestamp=original.timestamp,
            dados=original.dados,
            hash_anterior=hash_anterior,
        )
        registros[posicao] = refeito
        hash_anterior = refeito.hash
    log._registros = registros


# --- Recontagem nos três contextos -----------------------------------------------------


def test_recontagem_de_eleicao_de_ca_confere():
    regra = RegraCA(quorum_minimo_votantes=3)
    votos = [
        Voto(eleitor_id="101", opcao="Chapa Renova"),
        Voto(eleitor_id="102", opcao="Chapa Futuro"),
        Voto(eleitor_id="103", opcao="Chapa Renova"),
        Voto(eleitor_id="104", opcao="BRANCO"),
    ]
    log = _votacao_completa(regra, total_aptos=10, votos=votos)

    recontagem = recontar(log, RegraCA(quorum_minimo_votantes=3), ancora=log.resumo_encerramento())

    assert recontagem.confere is True
    assert recontagem.resultado.vencedor_ou_decisao == "CHAPA RENOVA"
    assert recontagem.opcoes_divergentes == {}


def test_recontagem_de_assembleia_respeita_os_pesos():
    def regra() -> RegraAssembleia:
        return RegraAssembleia(
            tipo_decisao=TipoDecisaoAssembleia.MAIORIA_SIMPLES, percentual_quorum_instalacao=0.25
        )

    votos = [
        Voto(eleitor_id="AC-001", opcao="SIM", peso=500_000),
        Voto(eleitor_id="AC-002", opcao="NAO", peso=300_000),
        Voto(eleitor_id="AC-003", opcao="NAO", peso=150_000),
    ]
    log = _votacao_completa(regra(), total_aptos=1_000_000, votos=votos)

    recontagem = recontar(log, regra(), ancora=log.resumo_encerramento())

    assert recontagem.confere is True
    assert recontagem.resultado.contagem_por_opcao == {"SIM": 500_000, "NAO": 450_000}
    assert recontagem.resultado.vencedor_ou_decisao == "SIM"


@pytest.mark.parametrize(
    ("presentes", "status"),
    [
        pytest.param(256, StatusResultado.QUORUM_INSUFICIENTE, id="sem_quorum_256"),
        pytest.param(257, StatusResultado.APROVADO, id="com_quorum_257"),
    ],
)
def test_recontagem_do_congresso_reaplica_o_quorum(presentes: int, status: StatusResultado):
    def regra() -> RegraCongresso:
        return RegraCongresso(TipoMateriaCongresso.LEI_ORDINARIA, CasaLegislativa.CAMARA)

    votos = [Voto(eleitor_id=f"DEP-{i}", opcao="SIM") for i in range(presentes)]
    log = _votacao_completa(regra(), total_aptos=513, votos=votos)

    recontagem = recontar(log, regra(), ancora=log.resumo_encerramento())

    assert recontagem.confere is True
    assert recontagem.resultado.status == status


def test_recontagem_usa_so_o_log():
    # O total de aptos vem da abertura e os votos, das cédulas: nada da sessão.
    log = _votacao_completa(
        RegraCA(percentual_quorum_minimo=0.5),
        total_aptos=4,
        votos=[Voto(eleitor_id="1", opcao="Chapa A"), Voto(eleitor_id="2", opcao="Chapa A")],
    )

    recontagem = recontar(log, RegraCA(percentual_quorum_minimo=0.5))

    assert recontagem.resultado.quorum_atingido is True  # 2 de 4 aptos = 50%
    assert recontagem.resultado.total_votantes == 2


# --- Comparação com o resultado proclamado ---------------------------------------------


def test_proclamacao_adulterada_depois_do_encerramento_e_detectada():
    regra = RegraCA(quorum_minimo_votantes=1)
    votos = [
        Voto(eleitor_id="101", opcao="Chapa A"),
        Voto(eleitor_id="102", opcao="Chapa A"),
        Voto(eleitor_id="103", opcao="Chapa B"),
    ]
    log = _votacao_completa(regra, total_aptos=10, votos=votos)
    ancora = log.resumo_encerramento()

    proclamacao = log.registros[-1]
    assert proclamacao.evento == TipoEvento.RESULTADO_PROCLAMADO
    fraude = {
        **proclamacao.dados,
        "vencedor_ou_decisao": "CHAPA B",
        "contagem_por_opcao": {"CHAPA A": 1, "CHAPA B": 2},
    }
    _reescrever_a_partir_de(log, len(log.registros) - 1, fraude)

    # A cadeia recalculada continua aprovada, inclusive contra a âncora...
    assert log.verificar_integridade(ancora=ancora).integro is True
    # ...mas a recontagem a partir das cédulas denuncia a proclamação falsa.
    recontagem = recontar(log, regra, ancora=ancora)
    assert recontagem.confere is False
    assert recontagem.opcoes_divergentes == {"CHAPA A": (2, 1), "CHAPA B": (1, 2)}
    assert recontagem.campos_divergentes["vencedor_ou_decisao"] == ("CHAPA A", "CHAPA B")


def test_divergencia_de_opcao_ausente_na_proclamacao_e_informada():
    regra = RegraCA(quorum_minimo_votantes=1)
    log = _votacao_completa(
        regra,
        total_aptos=10,
        votos=[Voto(eleitor_id="1", opcao="Chapa A"), Voto(eleitor_id="2", opcao="Chapa B")],
    )
    proclamacao = log.registros[-1]
    _reescrever_a_partir_de(
        log,
        len(log.registros) - 1,
        {**proclamacao.dados, "contagem_por_opcao": {"CHAPA A": 1}},
    )

    recontagem = recontar(log, regra)

    assert recontagem.opcoes_divergentes == {"CHAPA B": (1, 0)}


def test_sem_resultado_proclamado_a_comparacao_fica_em_aberto():
    log = LogDeAuditoria("V-2026")
    sessao = SessaoVotacao("V-2026", RegraCA(), total_aptos=3, log=log)
    sessao.abrir()
    sessao.liberar_votacao()
    sessao.registrar_voto(Voto(eleitor_id="1", opcao="Chapa A"))
    sessao.encerrar_votacao()

    recontagem = recontar(log, RegraCA())

    assert recontagem.confere is None
    assert recontagem.resultado.contagem_por_opcao == {"CHAPA A": 1}


# --- Recusa sobre log adulterado ou incompleto ----------------------------------------


def test_recontagem_recusada_se_a_cadeia_for_reprovada_sem_ancora():
    log = _votacao_completa(RegraCA(), 5, [Voto(eleitor_id="1", opcao="Chapa A")])
    encerramento_idx = next(
        r.indice for r in log.registros if r.evento == TipoEvento.VOTACAO_ENCERRADA
    )
    original = log.registros[encerramento_idx]
    log._registros[encerramento_idx] = replace(
        original, dados={**original.dados, "cedulas": [["Chapa B", 1]]}
    )

    with pytest.raises(RecontagemRecusadaError, match="reprovada"):
        recontar(log, RegraCA())


def test_recontagem_recusada_se_a_cadeia_for_reprovada_contra_a_ancora():
    # Reescrita completa que troca as cédulas: coerente por dentro, mas não bate com a âncora.
    log = _votacao_completa(RegraCA(), 5, [Voto(eleitor_id="1", opcao="Chapa A")])
    ancora = log.resumo_encerramento()
    encerramento_idx = ancora.total_registros - 1
    original = log.registros[encerramento_idx]
    _reescrever_a_partir_de(log, encerramento_idx, {**original.dados, "cedulas": [["Chapa B", 1]]})
    assert log.verificar_integridade().integro is True

    with pytest.raises(RecontagemRecusadaError, match="âncora"):
        recontar(log, RegraCA(), ancora=ancora)


def test_recontagem_recusada_sem_encerramento():
    log = LogDeAuditoria("V-2026")
    log.registrar(TipoEvento.VOTACAO_ABERTA, {"total_aptos": 3})
    log.registrar_voto(Voto(eleitor_id="1", opcao="Chapa A"))

    with pytest.raises(RecontagemRecusadaError, match="encerramento com as cédulas"):
        recontar(log, RegraCA())


# --- RNF-AUD-04: desempenho ------------------------------------------------------------


def test_verificar_e_recontar_dez_mil_votos_em_ate_dois_segundos():
    regra = RegraCA(quorum_minimo_votantes=1)
    votos = [Voto(eleitor_id=str(i), opcao=f"Chapa {i % 3}") for i in range(10_000)]
    log = _votacao_completa(regra, total_aptos=20_000, votos=votos)
    ancora = log.resumo_encerramento()

    inicio = time.perf_counter()
    recontagem = recontar(log, regra, ancora=ancora)
    duracao = time.perf_counter() - inicio

    assert recontagem.confere is True
    assert recontagem.resultado.total_votantes == 10_000
    assert duracao <= 2.0

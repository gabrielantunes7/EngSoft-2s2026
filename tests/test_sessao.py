"""Testes da máquina de estados da sessão de votação."""

from datetime import UTC, datetime, timedelta

import pytest

from votacao.auditoria import LogDeAuditoria, TipoEvento
from votacao.modelos import StatusResultado, Voto
from votacao.regras.ca import RegraCA
from votacao.sessao import (
    EstadoSessao,
    SessaoVotacao,
    TransicaoInvalidaError,
    VotoRecusadoError,
)

CICLO = (
    EstadoSessao.CRIADA,
    EstadoSessao.ABERTA,
    EstadoSessao.EM_VOTACAO,
    EstadoSessao.EM_APURACAO,
    EstadoSessao.ENCERRADA,
)

OPERACOES = ("abrir", "liberar_votacao", "registrar_voto", "encerrar_votacao", "apurar")

# Operações válidas em cada estado. Tudo que não está aqui deve ser recusado.
TRANSICOES_VALIDAS = {
    EstadoSessao.CRIADA: {"abrir"},
    EstadoSessao.ABERTA: {"liberar_votacao"},
    EstadoSessao.EM_VOTACAO: {"registrar_voto", "encerrar_votacao"},
    EstadoSessao.EM_APURACAO: {"apurar"},
    EstadoSessao.ENCERRADA: set(),
}


INICIO = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
FIM = datetime(2026, 10, 1, 17, 0, tzinfo=UTC)


class RelogioControlado:
    """Relógio injetável cujo instante os testes ajustam livremente."""

    def __init__(self, agora: datetime) -> None:
        self.agora = agora

    def __call__(self) -> datetime:
        return self.agora


def _nova_sessao(
    regra: RegraCA | None = None,
    total_aptos: int = 0,
    log: LogDeAuditoria | None = None,
    relogio: RelogioControlado | None = None,
) -> SessaoVotacao:
    return SessaoVotacao(
        "CA-2026",
        regra if regra is not None else RegraCA(),
        total_aptos,
        log=log,
        relogio=relogio,
    )


def _avancar_ate(sessao: SessaoVotacao, estado: EstadoSessao) -> None:
    passos = {
        EstadoSessao.ABERTA: sessao.abrir,
        EstadoSessao.EM_VOTACAO: sessao.liberar_votacao,
        EstadoSessao.EM_APURACAO: sessao.encerrar_votacao,
        EstadoSessao.ENCERRADA: sessao.apurar,
    }
    for alvo in CICLO[1 : CICLO.index(estado) + 1]:
        passos[alvo]()


def _executar(sessao: SessaoVotacao, operacao: str) -> None:
    if operacao == "registrar_voto":
        sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))
    else:
        getattr(sessao, operacao)()


def test_sessao_parametros_invalidos():
    with pytest.raises(ValueError, match="identificador"):
        SessaoVotacao("   ", RegraCA())
    with pytest.raises(TypeError, match="RegraDeVotacao"):
        SessaoVotacao("CA-2026", object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="negativo"):
        SessaoVotacao("CA-2026", RegraCA(), total_aptos=-1)


def test_sessao_nasce_criada_sem_votos_nem_resultado():
    sessao = _nova_sessao()

    assert sessao.estado == EstadoSessao.CRIADA
    assert sessao.votos == ()
    assert sessao.resultado is None


def test_sessao_percorre_o_ciclo_na_ordem():
    sessao = _nova_sessao()

    sessao.abrir()
    assert sessao.estado == EstadoSessao.ABERTA

    sessao.liberar_votacao()
    assert sessao.estado == EstadoSessao.EM_VOTACAO

    sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))
    assert sessao.estado == EstadoSessao.EM_VOTACAO

    sessao.encerrar_votacao()
    assert sessao.estado == EstadoSessao.EM_APURACAO

    sessao.apurar()
    assert sessao.estado == EstadoSessao.ENCERRADA


@pytest.mark.parametrize(
    ("estado", "operacao"),
    [
        pytest.param(estado, operacao, id=f"{estado.value}-{operacao}")
        for estado in CICLO
        for operacao in OPERACOES
        if operacao not in TRANSICOES_VALIDAS[estado]
    ],
)
def test_sessao_recusa_operacao_fora_de_ordem(estado: EstadoSessao, operacao: str):
    sessao = _nova_sessao()
    _avancar_ate(sessao, estado)
    votos_antes = sessao.votos

    with pytest.raises(TransicaoInvalidaError, match=estado.value):
        _executar(sessao, operacao)

    assert sessao.estado == estado
    assert sessao.votos == votos_antes


def test_sessao_guarda_os_votos_na_ordem_recebida():
    sessao = _nova_sessao()
    _avancar_ate(sessao, EstadoSessao.EM_VOTACAO)
    voto_a = Voto(eleitor_id="101", opcao="Chapa A")
    voto_b = Voto(eleitor_id="102", opcao="Chapa B")

    sessao.registrar_voto(voto_a)
    sessao.registrar_voto(voto_b)

    assert sessao.votos == (voto_a, voto_b)


def test_sessao_apura_com_a_regra_configurada():
    sessao = _nova_sessao(regra=RegraCA(quorum_minimo_votantes=3), total_aptos=10)
    _avancar_ate(sessao, EstadoSessao.EM_VOTACAO)
    sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))
    sessao.registrar_voto(Voto(eleitor_id="102", opcao="Chapa A"))
    sessao.registrar_voto(Voto(eleitor_id="103", opcao="Chapa B"))
    sessao.encerrar_votacao()

    resultado = sessao.apurar()

    assert resultado.status == StatusResultado.ELEITO
    assert resultado.vencedor_ou_decisao == "CHAPA A"
    assert resultado.contagem_por_opcao == {"CHAPA A": 2, "CHAPA B": 1}
    assert sessao.resultado is resultado
    assert sessao.estado == EstadoSessao.ENCERRADA


def test_sessao_sem_votos_apura_quorum_insuficiente():
    sessao = _nova_sessao(regra=RegraCA(quorum_minimo_votantes=1))
    _avancar_ate(sessao, EstadoSessao.EM_APURACAO)

    resultado = sessao.apurar()

    assert resultado.status == StatusResultado.QUORUM_INSUFICIENTE
    assert resultado.quorum_atingido is False


def test_sessao_recusa_segundo_voto_do_mesmo_eleitor():
    sessao = _nova_sessao()
    _avancar_ate(sessao, EstadoSessao.EM_VOTACAO)
    sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))

    with pytest.raises(VotoRecusadoError, match="já votou"):
        sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa B"))

    assert len(sessao.votos) == 1
    assert sessao.votos[0].opcao == "Chapa A"


@pytest.mark.parametrize(
    ("primeiro", "segundo"),
    [
        pytest.param("AC-001", "AC-001#rep:PROC-101", id="titular-depois-procurador"),
        pytest.param("AC-001#rep:PROC-101", "AC-001", id="procurador-depois-titular"),
        pytest.param("AC-001#rep:PROC-101", "AC-001#rep:PROC-102", id="dois-procuradores"),
    ],
)
def test_sessao_recusa_voto_repetido_pelo_mesmo_outorgante(primeiro: str, segundo: str):
    sessao = _nova_sessao()
    _avancar_ate(sessao, EstadoSessao.EM_VOTACAO)
    sessao.registrar_voto(Voto(eleitor_id=primeiro, opcao="SIM", peso=500))

    with pytest.raises(VotoRecusadoError, match="'AC-001' já votou"):
        sessao.registrar_voto(Voto(eleitor_id=segundo, opcao="NAO", peso=500))

    assert len(sessao.votos) == 1


def test_sessao_aceita_o_mesmo_procurador_para_outorgantes_distintos():
    sessao = _nova_sessao()
    _avancar_ate(sessao, EstadoSessao.EM_VOTACAO)

    sessao.registrar_voto(Voto(eleitor_id="AC-001#rep:PROC-101", opcao="SIM", peso=500))
    sessao.registrar_voto(Voto(eleitor_id="AC-002#rep:PROC-101", opcao="NAO", peso=300))

    assert len(sessao.votos) == 2


def test_sessao_recusa_janela_com_inicio_apos_o_fim():
    sessao = _nova_sessao()
    sessao.abrir()

    with pytest.raises(ValueError, match="posterior ao fim"):
        sessao.liberar_votacao(inicio=FIM, fim=INICIO)

    assert sessao.estado == EstadoSessao.ABERTA


def test_sessao_sem_janela_aceita_voto_a_qualquer_momento():
    relogio = RelogioControlado(datetime(1999, 1, 1, tzinfo=UTC))
    sessao = _nova_sessao(relogio=relogio)
    _avancar_ate(sessao, EstadoSessao.EM_VOTACAO)

    sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))

    assert sessao.inicio_votacao is None
    assert sessao.fim_votacao is None
    assert len(sessao.votos) == 1


def test_sessao_recusa_voto_fora_da_janela_e_aceita_dentro():
    relogio = RelogioControlado(INICIO - timedelta(minutes=1))
    sessao = _nova_sessao(relogio=relogio)
    sessao.abrir()
    sessao.liberar_votacao(inicio=INICIO, fim=FIM)

    with pytest.raises(VotoRecusadoError, match="só começa"):
        sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))

    relogio.agora = INICIO
    sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))

    relogio.agora = FIM + timedelta(minutes=1)
    with pytest.raises(VotoRecusadoError, match="terminou"):
        sessao.registrar_voto(Voto(eleitor_id="102", opcao="Chapa A"))

    assert len(sessao.votos) == 1
    assert sessao.estado == EstadoSessao.EM_VOTACAO


def test_sessao_janela_apenas_com_inicio():
    relogio = RelogioControlado(INICIO - timedelta(seconds=1))
    sessao = _nova_sessao(relogio=relogio)
    sessao.abrir()
    sessao.liberar_votacao(inicio=INICIO)

    with pytest.raises(VotoRecusadoError, match="só começa"):
        sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))

    relogio.agora = INICIO + timedelta(days=365)
    sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))

    assert len(sessao.votos) == 1


def test_sessao_janela_apenas_com_fim_usa_relogio_utc_por_padrao():
    sessao = _nova_sessao()
    sessao.abrir()
    sessao.liberar_votacao(fim=datetime(2000, 1, 1, tzinfo=UTC))

    with pytest.raises(VotoRecusadoError, match="terminou"):
        sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))

    assert sessao.votos == ()


def test_sessao_recusa_log_de_outra_votacao():
    with pytest.raises(ValueError, match="pertence à votação 'OUTRA'"):
        _nova_sessao(log=LogDeAuditoria("OUTRA"))


def test_sessao_sem_log_nao_emite_comprovante():
    sessao = _nova_sessao()
    _avancar_ate(sessao, EstadoSessao.EM_VOTACAO)

    assert sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A")) is None


def test_sessao_emite_comprovante_verificavel_sem_expor_o_eleitor():
    log = LogDeAuditoria("CA-2026")
    sessao = _nova_sessao(log=log)
    _avancar_ate(sessao, EstadoSessao.EM_VOTACAO)

    protocolo = sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))

    assert protocolo is not None
    assert log.contem_protocolo(protocolo)
    registro = next(r for r in log.registros if r.hash == protocolo)
    assert registro.evento == TipoEvento.VOTO_REGISTRADO
    assert registro.dados == {"opcao": "Chapa A", "peso": 1}
    assert "101" not in str(registro.dados)


def test_sessao_voto_recusado_nao_entra_no_log():
    log = LogDeAuditoria("CA-2026")
    sessao = _nova_sessao(log=log)
    _avancar_ate(sessao, EstadoSessao.EM_VOTACAO)
    sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))
    registros_antes = len(log.registros)

    with pytest.raises(VotoRecusadoError):
        sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa B"))

    assert len(log.registros) == registros_antes


def test_sessao_registra_a_janela_na_abertura_da_urna():
    log = LogDeAuditoria("CA-2026")
    sessao = _nova_sessao(log=log, total_aptos=10)
    sessao.abrir()

    sessao.liberar_votacao(inicio=INICIO, fim=FIM)

    abertura = log.registros[-1]
    assert abertura.evento == TipoEvento.VOTACAO_ABERTA
    assert abertura.dados == {
        "inicio": INICIO.isoformat(),
        "fim": FIM.isoformat(),
        "total_aptos": 10,
    }


def test_sessao_registra_o_ciclo_completo_no_log():
    log = LogDeAuditoria("CA-2026")
    sessao = _nova_sessao(regra=RegraCA(quorum_minimo_votantes=2), log=log, total_aptos=5)
    sessao.abrir()
    sessao.liberar_votacao()
    sessao.registrar_voto(Voto(eleitor_id="101", opcao="Chapa A"))
    sessao.registrar_voto(Voto(eleitor_id="102", opcao="Chapa A"))
    sessao.registrar_voto(Voto(eleitor_id="103", opcao="Chapa B"))
    sessao.encerrar_votacao()
    resultado = sessao.apurar()

    eventos = [registro.evento for registro in log.registros]
    assert eventos == [
        TipoEvento.VOTACAO_ABERTA,
        TipoEvento.VOTO_REGISTRADO,
        TipoEvento.VOTO_REGISTRADO,
        TipoEvento.VOTO_REGISTRADO,
        TipoEvento.VOTACAO_ENCERRADA,
        TipoEvento.RESULTADO_PROCLAMADO,
    ]

    encerramento = log.registros[-2]
    assert encerramento.dados == {"total_votos": 3}

    proclamacao = log.registros[-1]
    assert proclamacao.dados["status"] == StatusResultado.ELEITO.value
    assert proclamacao.dados["vencedor_ou_decisao"] == "CHAPA A"
    assert proclamacao.dados["contagem_por_opcao"] == resultado.contagem_por_opcao

    assert log.verificar_integridade().integro


def _voto_consolidado(eleitor_id: str = "PROC-101") -> Voto:
    return Voto(eleitor_id=eleitor_id, opcao="SIM", peso=800, representados=("AC-001", "AC-002"))


@pytest.mark.parametrize(
    "segundo",
    [
        pytest.param("AC-001", id="representado-vota-direto"),
        pytest.param("AC-002", id="outro-representado-vota-direto"),
        pytest.param("AC-001#rep:PROC-102", id="representado-por-outro-procurador"),
        pytest.param("PROC-101", id="procurador-vota-de-novo"),
    ],
)
def test_sessao_recusa_novo_voto_de_quem_ja_esta_no_voto_consolidado(segundo: str):
    sessao = _nova_sessao()
    _avancar_ate(sessao, EstadoSessao.EM_VOTACAO)
    sessao.registrar_voto(_voto_consolidado())

    with pytest.raises(VotoRecusadoError, match="já votou"):
        sessao.registrar_voto(Voto(eleitor_id=segundo, opcao="NAO", peso=10))

    assert len(sessao.votos) == 1


@pytest.mark.parametrize("ja_votou", ["AC-002", "AC-002#rep:PROC-102", "PROC-101"])
def test_sessao_recusa_voto_consolidado_que_inclui_quem_ja_votou_sem_registro_parcial(
    ja_votou: str,
):
    sessao = _nova_sessao()
    _avancar_ate(sessao, EstadoSessao.EM_VOTACAO)
    sessao.registrar_voto(Voto(eleitor_id=ja_votou, opcao="NAO", peso=300))

    with pytest.raises(VotoRecusadoError, match="já votou"):
        sessao.registrar_voto(_voto_consolidado())

    assert len(sessao.votos) == 1
    # AC-001 não foi marcado como votado pela tentativa recusada.
    sessao.registrar_voto(Voto(eleitor_id="AC-001", opcao="SIM", peso=500))
    assert len(sessao.votos) == 2


def test_sessao_aceita_consolidados_de_procuradores_com_outorgantes_distintos():
    sessao = _nova_sessao()
    _avancar_ate(sessao, EstadoSessao.EM_VOTACAO)

    sessao.registrar_voto(_voto_consolidado("PROC-101"))
    sessao.registrar_voto(
        Voto(eleitor_id="PROC-102", opcao="NAO", peso=90, representados=("AC-003",))
    )

    assert len(sessao.votos) == 2


def test_sessao_audita_o_voto_consolidado_uma_vez_com_o_peso_somado_e_sem_identificar_ninguem():
    log = LogDeAuditoria("CA-2026")
    sessao = _nova_sessao(log=log)
    _avancar_ate(sessao, EstadoSessao.EM_VOTACAO)

    protocolo = sessao.registrar_voto(_voto_consolidado())

    assert protocolo is not None
    votos_no_log = [r for r in log.registros if r.evento == TipoEvento.VOTO_REGISTRADO]
    assert len(votos_no_log) == 1
    assert votos_no_log[0].dados == {"opcao": "SIM", "peso": 800}
    assert "AC-001" not in str(votos_no_log[0].dados)
    assert "PROC-101" not in str(votos_no_log[0].dados)

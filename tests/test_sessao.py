"""Testes da máquina de estados da sessão de votação."""

import pytest

from votacao.modelos import StatusResultado, Voto
from votacao.regras.ca import RegraCA
from votacao.sessao import EstadoSessao, SessaoVotacao, TransicaoInvalidaError

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


def _nova_sessao(regra: RegraCA | None = None, total_aptos: int = 0) -> SessaoVotacao:
    return SessaoVotacao("CA-2026", regra if regra is not None else RegraCA(), total_aptos)


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

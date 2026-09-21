"""Testes de ponta a ponta da delegação de voto: procuração, voto consolidado e apuração."""

import pytest

from votacao.dados import Acionista, BancoDadosMock, Procurador
from votacao.modelos import StatusResultado, TipoDecisaoAssembleia
from votacao.regras.assembleia import RegraAssembleia
from votacao.servicos import ServicoElegibilidade
from votacao.sessao import SessaoVotacao, VotoRecusadoError


def _assembleia() -> tuple[ServicoElegibilidade, int]:
    """Assembleia com três acionistas (500, 300 e 150 ações) e o procurador P-1."""
    banco = BancoDadosMock(popular=False)
    banco.assembleia.adicionar_acionista(Acionista(id="AC-1", nome="Alpha", acoes_ordinarias=500))
    banco.assembleia.adicionar_acionista(Acionista(id="AC-2", nome="Beta", acoes_ordinarias=300))
    banco.assembleia.adicionar_acionista(Acionista(id="AC-3", nome="Gama", acoes_ordinarias=150))
    banco.assembleia.adicionar_procurador(Procurador(id="P-1", nome="Advocacia Um"))
    return ServicoElegibilidade(banco=banco), banco.assembleia.total_capital_votante()


def _sessao_aberta(capital: int, regra: RegraAssembleia | None = None) -> SessaoVotacao:
    sessao = SessaoVotacao("AGO-2026", regra or RegraAssembleia(), capital)
    sessao.abrir()
    sessao.liberar_votacao()
    return sessao


def test_fluxo_completo_da_delegacao_ate_a_apuracao():
    servico, capital = _assembleia()
    regra = RegraAssembleia(
        tipo_decisao=TipoDecisaoAssembleia.MAIORIA_ABSOLUTA,
        percentual_quorum_instalacao=0.5,
        base_calculo_sobre_total_capital=True,
    )

    # AC-1 e AC-2 delegam ao procurador P-1 e deixam de poder votar diretamente.
    servico.procuracoes.cadastrar("AC-1", "P-1")
    servico.procuracoes.cadastrar("AC-2", "P-1")
    with pytest.raises(PermissionError, match="delegou o voto ao procurador 'P-1'"):
        servico.autorizar_voto("AC-1", "NAO", "ASSEMBLEIA")

    # O procurador vota uma única vez com o poder consolidado dos dois; AC-3 vota direto.
    sessao = _sessao_aberta(capital, regra)
    sessao.registrar_voto(servico.autorizar_voto_do_procurador("P-1", "SIM"))
    sessao.registrar_voto(servico.autorizar_voto("AC-3", "NAO", "ASSEMBLEIA"))
    sessao.encerrar_votacao()
    resultado = sessao.apurar()

    assert len(sessao.votos) == 2
    assert sessao.votos[0].peso == 800
    assert resultado.status == StatusResultado.APROVADO
    assert resultado.contagem_por_opcao == {"SIM": 800, "NAO": 150}
    assert resultado.total_peso_apurado == capital == 950


def test_revogar_libera_o_voto_direto_mas_a_sessao_nao_conta_o_mesmo_capital_duas_vezes():
    servico, capital = _assembleia()
    servico.procuracoes.cadastrar("AC-1", "P-1")
    sessao = _sessao_aberta(capital)
    sessao.registrar_voto(servico.autorizar_voto_do_procurador("P-1", "SIM"))

    servico.procuracoes.revogar("AC-1", "P-1")
    voto_direto = servico.autorizar_voto("AC-1", "NAO", "ASSEMBLEIA")

    assert voto_direto.peso == 500
    with pytest.raises(VotoRecusadoError, match="'AC-1' já votou"):
        sessao.registrar_voto(voto_direto)
    assert len(sessao.votos) == 1


def test_revogar_antes_do_voto_devolve_o_poder_ao_titular():
    servico, capital = _assembleia()
    servico.procuracoes.cadastrar("AC-1", "P-1")
    servico.procuracoes.revogar("AC-1", "P-1")
    sessao = _sessao_aberta(capital)

    with pytest.raises(PermissionError, match="sem poder de voto"):
        servico.autorizar_voto_do_procurador("P-1", "SIM")
    sessao.registrar_voto(servico.autorizar_voto("AC-1", "SIM", "ASSEMBLEIA"))

    assert sessao.votos[0].peso == 500


@pytest.mark.regressao
def test_regressao_voto_consolidado_apura_igual_aos_votos_por_outorgante():
    """Na mesma opção, o voto consolidado apura como um voto por outorgante (fluxo da A1)."""
    regra = RegraAssembleia(percentual_quorum_instalacao=0.5)

    servico, capital = _assembleia()
    servico.procuracoes.cadastrar("AC-1", "P-1")
    servico.procuracoes.cadastrar("AC-2", "P-1")
    consolidado = _sessao_aberta(capital, regra)
    consolidado.registrar_voto(servico.autorizar_voto_do_procurador("P-1", "SIM"))
    consolidado.registrar_voto(servico.autorizar_voto("AC-3", "NAO", "ASSEMBLEIA"))
    consolidado.encerrar_votacao()
    apuracao_consolidada = consolidado.apurar()

    legado_servico, legado_capital = _assembleia()
    legado_servico.procuracoes.cadastrar("AC-1", "P-1")
    legado_servico.procuracoes.cadastrar("AC-2", "P-1")
    por_outorgante = _sessao_aberta(legado_capital, regra)
    for outorgante in ("AC-1", "AC-2"):
        por_outorgante.registrar_voto(
            legado_servico.autorizar_voto(outorgante, "SIM", "ASSEMBLEIA", procurador_id="P-1")
        )
    por_outorgante.registrar_voto(legado_servico.autorizar_voto("AC-3", "NAO", "ASSEMBLEIA"))
    por_outorgante.encerrar_votacao()
    apuracao_legada = por_outorgante.apurar()

    assert apuracao_consolidada.status == apuracao_legada.status
    assert apuracao_consolidada.vencedor_ou_decisao == apuracao_legada.vencedor_ou_decisao
    assert apuracao_consolidada.contagem_por_opcao == apuracao_legada.contagem_por_opcao
    assert apuracao_consolidada.total_peso_apurado == apuracao_legada.total_peso_apurado
    assert apuracao_consolidada.percentual_vencedor == apuracao_legada.percentual_vencedor
    # O procurador é um votante só; no fluxo antigo cada procuração contava um votante.
    assert apuracao_consolidada.total_votantes == 2
    assert apuracao_legada.total_votantes == 3


@pytest.mark.regressao
def test_regressao_assembleia_sem_procuracoes_vota_direto_como_antes():
    servico, capital = _assembleia()
    sessao = _sessao_aberta(capital)

    for acionista, opcao in (("AC-1", "SIM"), ("AC-2", "NAO"), ("AC-3", "SIM")):
        voto = servico.autorizar_voto(acionista, opcao, "ASSEMBLEIA")
        assert voto.eleitor_id == acionista
        assert voto.representados == ()
        sessao.registrar_voto(voto)
    sessao.encerrar_votacao()
    resultado = sessao.apurar()

    assert resultado.status == StatusResultado.APROVADO
    assert resultado.contagem_por_opcao == {"SIM": 650, "NAO": 300}

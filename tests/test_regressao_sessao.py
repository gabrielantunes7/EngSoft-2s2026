"""Testes de regressão: a sessão não altera a apuração dos contextos já entregues."""

import pytest

from votacao.auditoria import LogDeAuditoria
from votacao.dados import Acionista, BancoDadosMock, ChapaCA, Discente, Procuracao
from votacao.modelos import StatusResultado, TipoDecisaoAssembleia
from votacao.motor import MotorApuracao
from votacao.regras.assembleia import RegraAssembleia
from votacao.regras.ca import RegraCA
from votacao.servicos import ServicoElegibilidade
from votacao.sessao import EstadoSessao, SessaoVotacao


@pytest.mark.regressao
def test_regressao_sessao_ca_reproduz_apuracao_do_motor():
    """CA: autenticação -> elegibilidade -> sessão -> apuração == motor direto."""
    banco = BancoDadosMock(popular=False)
    for ra in ("101", "102", "103", "104"):
        banco.ca.adicionar_discente(Discente(ra=ra, nome=f"Aluno {ra}", curso="EngSoft"))
    banco.ca.adicionar_chapa(ChapaCA(nome="Chapa Inovacao", integrantes_ra=("101",)))
    banco.ca.adicionar_chapa(ChapaCA(nome="Chapa Tradicao", integrantes_ra=("102",)))
    servico = ServicoElegibilidade(banco=banco)

    regra = RegraCA(quorum_minimo_votantes=3, percentual_quorum_minimo=0.5)
    total_aptos = len(banco.ca.listar_discentes())
    log = LogDeAuditoria("CA-2026")
    sessao = SessaoVotacao("CA-2026", regra, total_aptos, log=log)
    sessao.abrir()
    sessao.liberar_votacao()

    comprovantes = [
        sessao.registrar_voto(servico.autorizar_voto("101", "Chapa Inovacao", "CA")),
        sessao.registrar_voto(servico.autorizar_voto("102", "Chapa Inovacao", "CA")),
        sessao.registrar_voto(servico.autorizar_voto("103", "Chapa Tradicao", "CA")),
        sessao.registrar_voto(servico.autorizar_voto("104", "BRANCO", "CA")),
    ]
    sessao.encerrar_votacao()
    resultado = sessao.apurar()

    esperado = MotorApuracao.apurar(
        votos=sessao.votos, regra=regra, total_aptos_ou_capital=total_aptos
    )
    assert resultado == esperado
    assert resultado.status == StatusResultado.ELEITO
    assert resultado.vencedor_ou_decisao == "CHAPA INOVACAO"
    assert resultado.contagem_por_opcao == {"CHAPA INOVACAO": 2, "CHAPA TRADICAO": 1, "BRANCO": 1}
    assert resultado.detalhes["brancos"] == 1

    assert sessao.estado == EstadoSessao.ENCERRADA
    assert all(log.contem_protocolo(c) for c in comprovantes)
    assert log.verificar_integridade().integro


@pytest.mark.regressao
def test_regressao_sessao_assembleia_reproduz_apuracao_ponderada_do_motor():
    """Assembleia: voto ponderado, com procuração, via sessão == motor direto."""
    banco = BancoDadosMock(popular=False)
    banco.assembleia.adicionar_acionista(Acionista(id="AC-1", nome="Alpha", acoes_ordinarias=500))
    banco.assembleia.adicionar_acionista(Acionista(id="AC-2", nome="Beta", acoes_ordinarias=300))
    banco.assembleia.adicionar_acionista(Acionista(id="AC-3", nome="Gama", acoes_ordinarias=150))
    banco.assembleia.adicionar_acionista(
        Acionista(id="AC-4", nome="Sem Voto", acoes_ordinarias=0, acoes_preferenciais=80)
    )
    banco.assembleia.adicionar_procuracao(Procuracao(outorgante_id="AC-1", procurador_id="P-1"))
    servico = ServicoElegibilidade(banco=banco)

    regra = RegraAssembleia(
        tipo_decisao=TipoDecisaoAssembleia.MAIORIA_ABSOLUTA,
        percentual_quorum_instalacao=0.5,
        base_calculo_sobre_total_capital=True,
    )
    capital_total = banco.assembleia.total_capital_votante()
    sessao = SessaoVotacao("AGO-2026", regra, capital_total)
    sessao.abrir()
    sessao.liberar_votacao()

    sessao.registrar_voto(servico.autorizar_voto("AC-1", "SIM", "ASSEMBLEIA", procurador_id="P-1"))
    sessao.registrar_voto(servico.autorizar_voto("AC-2", "NAO", "ASSEMBLEIA"))
    sessao.registrar_voto(servico.autorizar_voto("AC-3", "SIM", "ASSEMBLEIA"))
    sessao.encerrar_votacao()
    resultado = sessao.apurar()

    esperado = MotorApuracao.apurar(
        votos=sessao.votos, regra=regra, total_aptos_ou_capital=capital_total
    )
    assert resultado == esperado
    assert capital_total == 950
    assert resultado.status == StatusResultado.APROVADO
    assert resultado.total_peso_apurado == 950
    assert resultado.contagem_por_opcao == {"SIM": 650, "NAO": 300}
    assert resultado.detalhes["votos_sim_peso"] == 650
    assert resultado.detalhes["base_calculo"] == 950.0
    assert sessao.votos[0].eleitor_id == "AC-1#rep:P-1"
    assert sessao.votos[0].peso == 500

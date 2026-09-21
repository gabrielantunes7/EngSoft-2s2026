"""Testes de regressão e integração ponta a ponta com o motor de apuração."""

import pytest

from votacao import (
    CasaLegislativa,
    MotorApuracao,
    RegraAssembleia,
    RegraCA,
    RegraCongresso,
    ServicoElegibilidade,
    StatusResultado,
    TipoDecisaoAssembleia,
    TipoMateriaCongresso,
)
from votacao.dados import (
    Acionista,
    BancoDadosMock,
    ChapaCA,
    Discente,
    Parlamentar,
    Procuracao,
)


@pytest.mark.regressao
def test_regressao_integracao_ca_fluxo_completo():
    """Valida fluxo de ponta a ponta no CA: autenticação -> elegibilidade -> voto -> apuração."""
    banco = BancoDadosMock(popular=False)
    # Cadastra eleitores
    banco.ca.adicionar_discente(Discente(ra="101", nome="Aluno A", curso="EngSoft"))
    banco.ca.adicionar_discente(Discente(ra="102", nome="Aluno B", curso="EngSoft"))
    banco.ca.adicionar_discente(Discente(ra="103", nome="Aluno C", curso="EngSoft"))
    banco.ca.adicionar_discente(
        Discente(ra="104", nome="Aluno Jubilando", curso="EngSoft", matricula_ativa=False)
    )

    # Cadastra chapas
    banco.ca.adicionar_chapa(ChapaCA(nome="Chapa Inovacao", integrantes_ra=("101",), ativa=True))
    banco.ca.adicionar_chapa(ChapaCA(nome="Chapa Tradicao", integrantes_ra=("102",), ativa=True))

    servico = ServicoElegibilidade(banco=banco)

    # Autenticação
    assert servico.autenticar("101", "CA") is not None
    assert servico.autenticar("104", "CA").ativo is False

    # Aluno inativo não consegue emitir voto
    with pytest.raises(PermissionError):
        servico.autorizar_voto("104", "Chapa Inovacao", "CA")

    # Emissão de votos autorizados
    voto1 = servico.autorizar_voto("101", "Chapa Inovacao", "CA")
    voto2 = servico.autorizar_voto("102", "Chapa Inovacao", "CA")
    voto3 = servico.autorizar_voto("103", "Chapa Tradicao", "CA")

    # Apuração com a regra oficial de CA
    votos = [voto1, voto2, voto3]
    resultado = MotorApuracao.apurar(
        votos=votos,
        regra=RegraCA(quorum_minimo_votantes=3),
        total_aptos_ou_capital=3,
    )

    assert resultado.status == StatusResultado.ELEITO
    assert resultado.vencedor_ou_decisao == "CHAPA INOVACAO"
    assert resultado.total_votantes == 3
    assert resultado.contagem_por_opcao["CHAPA INOVACAO"] == 2
    assert resultado.contagem_por_opcao["CHAPA TRADICAO"] == 1


@pytest.mark.regressao
def test_regressao_integracao_assembleia_voto_ponderado():
    """Valida fluxo na Assembleia: titularidade acionária -> procurações -> apuração ponderada."""
    banco = BancoDadosMock(popular=False)
    banco.assembleia.adicionar_acionista(
        Acionista(id="AC-ALPHA", nome="Alpha Corp", acoes_ordinarias=600_000)
    )
    banco.assembleia.adicionar_acionista(
        Acionista(id="AC-BETA", nome="Beta Fund", acoes_ordinarias=300_000)
    )
    banco.assembleia.adicionar_acionista(
        Acionista(id="AC-GAMA", nome="Gama Bloqueado", acoes_ordinarias=100_000, bloqueado=True)
    )
    banco.assembleia.adicionar_procuracao(
        Procuracao(outorgante_id="AC-BETA", procurador_id="PROC-ADVOGADO", ativa=True)
    )

    servico = ServicoElegibilidade(banco=banco)

    # Acionista bloqueado é barrado
    with pytest.raises(PermissionError):
        servico.autorizar_voto("AC-GAMA", "SIM", "ASSEMBLEIA")

    # Alpha vota SIM diretamente
    voto_alpha = servico.autorizar_voto("AC-ALPHA", "SIM", "ASSEMBLEIA")
    assert voto_alpha.peso == 600_000

    # Beta vota NAO via procurador
    voto_beta = servico.autorizar_voto(
        eleitor_id="AC-BETA",
        opcao="NAO",
        contexto="ASSEMBLEIA",
        procurador_id="PROC-ADVOGADO",
    )
    assert voto_beta.peso == 300_000

    votos = [voto_alpha, voto_beta]
    total_capital = 1_000_000

    # Apura por maioria absoluta do capital total
    regra = RegraAssembleia(
        tipo_decisao=TipoDecisaoAssembleia.MAIORIA_ABSOLUTA,
        percentual_quorum_instalacao=0.5,
        base_calculo_sobre_total_capital=True,
    )
    resultado = MotorApuracao.apurar(votos=votos, regra=regra, total_aptos_ou_capital=total_capital)

    assert resultado.status == StatusResultado.APROVADO
    assert resultado.vencedor_ou_decisao == "SIM"
    assert resultado.total_peso_apurado == 900_000
    assert resultado.contagem_por_opcao["SIM"] == 600_000
    assert resultado.contagem_por_opcao["NAO"] == 300_000


@pytest.mark.regressao
def test_regressao_integracao_congresso_pec():
    """Valida fluxo no Congresso: deputados ativos -> matérias -> apuração bicameral."""
    banco = BancoDadosMock(popular=False)
    # Cadastra deputados
    for i in range(1, 310):
        banco.congresso.adicionar_parlamentar(
            Parlamentar(
                id=f"DEP-{i}",
                nome=f"Deputado {i}",
                casa=CasaLegislativa.CAMARA,
                partido="ABC",
                uf="SP",
                em_exercicio=True,
            )
        )

    # Deputado licenciado (não pode votar)
    banco.congresso.adicionar_parlamentar(
        Parlamentar(
            id="DEP-LICENCIADO",
            nome="Deputado Licenciado",
            casa=CasaLegislativa.CAMARA,
            partido="ABC",
            uf="RJ",
            em_exercicio=False,
            licenciado=True,
        )
    )

    servico = ServicoElegibilidade(banco=banco)

    with pytest.raises(PermissionError):
        servico.autorizar_voto("DEP-LICENCIADO", "SIM", "CONGRESSO", casa=CasaLegislativa.CAMARA)

    # 309 deputados votam SIM (mínimo para PEC na Câmara é 308)
    votos_deputados = [
        servico.autorizar_voto(
            eleitor_id=f"DEP-{i}",
            opcao="SIM",
            contexto="CONGRESSO",
            casa=CasaLegislativa.CAMARA,
        )
        for i in range(1, 310)
    ]

    regra_pec_camara = RegraCongresso(
        materia=TipoMateriaCongresso.PEC,
        casa=CasaLegislativa.CAMARA,
    )
    resultado = MotorApuracao.apurar(votos=votos_deputados, regra=regra_pec_camara)

    assert resultado.status == StatusResultado.APROVADO
    assert resultado.vencedor_ou_decisao == "SIM"
    assert resultado.total_votantes == 309
    assert resultado.contagem_por_opcao["SIM"] == 309

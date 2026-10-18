"""Testes do padrão Abstract Factory para criação de famílias de componentes eleitorais."""

from typing import Any

import pytest

from votacao.dados.assembleia import RepositorioAssembleia
from votacao.dados.ca import RepositorioCA
from votacao.dados.congresso import RepositorioCongresso
from votacao.elegibilidade.validador_assembleia import (
    ValidadorElegibilidadeAssembleia,
)
from votacao.elegibilidade.validador_ca import ValidadorElegibilidadeCA
from votacao.elegibilidade.validador_congresso import (
    ValidadorElegibilidadeCongresso,
)
from votacao.fabricas import (
    FabricaAssembleia,
    FabricaCA,
    FabricaCongresso,
    FabricaContextoVotacao,
    obter_fabrica_contexto,
    registrar_fabrica_contexto,
)
from votacao.modelos import (
    CasaLegislativa,
    StatusResultado,
    TipoDecisaoAssembleia,
    TipoMateriaCongresso,
    Voto,
)
from votacao.regras.assembleia import RegraAssembleia
from votacao.regras.ca import RegraCA
from votacao.regras.congresso import RegraCongresso
from votacao.sessao import EstadoSessao, SessaoVotacao


def test_fabrica_ca_cria_familia_coesa():
    fabrica = FabricaCA()
    assert fabrica.contexto == "CA"

    regra = fabrica.criar_regra(quorum_minimo_votantes=2, percentual_quorum_minimo=0.2)
    assert isinstance(regra, RegraCA)
    assert regra.quorum_minimo_votantes == 2
    assert regra.percentual_quorum_minimo == 0.2

    validador = fabrica.criar_validador()
    assert isinstance(validador, ValidadorElegibilidadeCA)

    repo_vazio = fabrica.criar_repositorio(popular=False)
    assert isinstance(repo_vazio, RepositorioCA)
    assert len(repo_vazio.listar_discentes()) == 0

    repo_populado = fabrica.criar_repositorio(popular=True)
    assert isinstance(repo_populado, RepositorioCA)
    assert len(repo_populado.listar_discentes()) > 0

    sessao = fabrica.criar_sessao("CA-TESTE", total_aptos=10, quorum_minimo_votantes=1)
    assert isinstance(sessao, SessaoVotacao)
    assert isinstance(sessao.regra, RegraCA)
    assert sessao.total_aptos == 10

    # Ciclo de apuração funcional na sessão gerada pela fábrica
    sessao.abrir()
    sessao.liberar_votacao()
    sessao.registrar_voto(Voto(eleitor_id="ra-1", opcao="Chapa 1"))
    sessao.encerrar_votacao()
    resultado = sessao.apurar()
    assert resultado.status == StatusResultado.ELEITO
    assert resultado.vencedor_ou_decisao == "CHAPA 1"


def test_fabrica_ca_sessao_com_regra_previa():
    fabrica = FabricaCA()
    regra_costumizada = RegraCA(quorum_minimo_votantes=5)
    sessao = fabrica.criar_sessao("CA-CUSTOM", total_aptos=20, regra=regra_costumizada)
    assert sessao.regra is regra_costumizada


def test_fabrica_assembleia_cria_familia_coesa():
    fabrica = FabricaAssembleia()
    assert fabrica.contexto == "ASSEMBLEIA"

    regra = fabrica.criar_regra(
        tipo_decisao=TipoDecisaoAssembleia.MAIORIA_ABSOLUTA,
        percentual_quorum_instalacao=0.5,
        base_calculo_sobre_total_capital=True,
    )
    assert isinstance(regra, RegraAssembleia)
    assert regra.tipo_decisao == TipoDecisaoAssembleia.MAIORIA_ABSOLUTA
    assert regra.percentual_quorum_instalacao == 0.5
    assert regra.base_calculo_sobre_total_capital is True

    validador = fabrica.criar_validador()
    assert isinstance(validador, ValidadorElegibilidadeAssembleia)

    repo_vazio = fabrica.criar_repositorio(popular=False)
    assert isinstance(repo_vazio, RepositorioAssembleia)
    assert len(repo_vazio.listar_acionistas()) == 0

    repo_populado = fabrica.criar_repositorio(popular=True)
    assert isinstance(repo_populado, RepositorioAssembleia)
    assert len(repo_populado.listar_acionistas()) > 0

    sessao = fabrica.criar_sessao(
        "AGO-TESTE",
        total_aptos=1000,
        tipo_decisao=TipoDecisaoAssembleia.MAIORIA_SIMPLES,
    )
    assert isinstance(sessao, SessaoVotacao)
    assert isinstance(sessao.regra, RegraAssembleia)
    assert sessao.total_aptos == 1000

    sessao.abrir()
    sessao.liberar_votacao()
    sessao.registrar_voto(Voto(eleitor_id="investidor-1", opcao="SIM", peso=600))
    sessao.registrar_voto(Voto(eleitor_id="investidor-2", opcao="NAO", peso=400))
    sessao.encerrar_votacao()
    resultado = sessao.apurar()
    assert resultado.status == StatusResultado.APROVADO
    assert resultado.vencedor_ou_decisao == "SIM"


def test_fabrica_assembleia_sessao_com_regra_previa():
    fabrica = FabricaAssembleia()
    regra_costumizada = RegraAssembleia(tipo_decisao=TipoDecisaoAssembleia.QUALIFICADA_DOIS_TERCOS)
    sessao = fabrica.criar_sessao("AGO-CUSTOM", total_aptos=500, regra=regra_costumizada)
    assert sessao.regra is regra_costumizada


def test_fabrica_congresso_cria_familia_coesa():
    fabrica = FabricaCongresso()
    assert fabrica.contexto == "CONGRESSO"

    regra = fabrica.criar_regra(
        materia=TipoMateriaCongresso.PEC,
        casa=CasaLegislativa.SENADO,
    )
    assert isinstance(regra, RegraCongresso)
    assert regra.materia == TipoMateriaCongresso.PEC
    assert regra.casa == CasaLegislativa.SENADO
    assert regra.total_membros == 81

    validador = fabrica.criar_validador()
    assert isinstance(validador, ValidadorElegibilidadeCongresso)

    repo_vazio = fabrica.criar_repositorio(popular=False)
    assert isinstance(repo_vazio, RepositorioCongresso)
    assert len(repo_vazio.listar_parlamentares()) == 0

    repo_populado = fabrica.criar_repositorio(popular=True)
    assert isinstance(repo_populado, RepositorioCongresso)
    assert len(repo_populado.listar_parlamentares()) > 0

    # Sessão usa automaticamente total constitucional de membros quando total_aptos=0
    sessao = fabrica.criar_sessao(
        "PL-TESTE",
        materia=TipoMateriaCongresso.LEI_ORDINARIA,
        casa=CasaLegislativa.CAMARA,
    )
    assert isinstance(sessao, SessaoVotacao)
    assert isinstance(sessao.regra, RegraCongresso)
    assert sessao.total_aptos == 513
    assert sessao.estado == EstadoSessao.CRIADA


def test_fabrica_congresso_sessao_com_regra_previa():
    fabrica = FabricaCongresso()
    regra_costumizada = RegraCongresso(materia=TipoMateriaCongresso.LEI_COMPLEMENTAR)
    sessao = fabrica.criar_sessao("PLC-CUSTOM", regra=regra_costumizada)
    assert sessao.regra is regra_costumizada


def test_obter_fabrica_contexto():
    f_ca = obter_fabrica_contexto("ca")
    assert isinstance(f_ca, FabricaCA)

    f_ass = obter_fabrica_contexto(" Assembleia ")
    assert isinstance(f_ass, FabricaAssembleia)

    f_cong = obter_fabrica_contexto("CONGRESSO")
    assert isinstance(f_cong, FabricaCongresso)

    with pytest.raises(ValueError, match="não reconhecido"):
        obter_fabrica_contexto("DOMINIO_INVALIDO")


def test_registrar_fabrica_contexto_estende_sistema():
    class FabricaCustomizada(FabricaContextoVotacao):
        @property
        def contexto(self) -> str:
            return "NOVO_CONTEXTO"

        def criar_regra(self, **kwargs: Any) -> RegraCA:
            return RegraCA()

        def criar_validador(self, **kwargs: Any) -> ValidadorElegibilidadeCA:
            return ValidadorElegibilidadeCA()

        def criar_repositorio(self, popular: bool = True, **kwargs: Any) -> RepositorioCA:
            return RepositorioCA()

        def criar_sessao(
            self,
            id_sessao: str,
            total_aptos: int = 0,
            **kwargs: Any,
        ) -> SessaoVotacao:
            return SessaoVotacao(id_sessao, RegraCA(), total_aptos=total_aptos)

    fabrica_custom = FabricaCustomizada()
    registrar_fabrica_contexto("NOVO_CONTEXTO", fabrica_custom)

    obtida = obter_fabrica_contexto("novo_contexto")
    assert obtida is fabrica_custom
    assert obtida.contexto == "NOVO_CONTEXTO"


def test_registrar_fabrica_contexto_validacoes():
    with pytest.raises(ValueError, match="vazio"):
        registrar_fabrica_contexto("   ", FabricaCA())

    with pytest.raises(TypeError, match="FabricaContextoVotacao"):
        registrar_fabrica_contexto("TESTE", object())  # type: ignore[arg-type]

"""Fábrica concreta para o contexto de Assembleia de Acionistas."""

from typing import Any

from votacao.dados.assembleia import RepositorioAssembleia
from votacao.dados.seeds import carregar_dados_padrao_assembleia
from votacao.elegibilidade.validador_assembleia import (
    ValidadorElegibilidadeAssembleia,
)
from votacao.fabricas.base import FabricaContextoVotacao
from votacao.modelos import TipoDecisaoAssembleia
from votacao.regras.assembleia import RegraAssembleia
from votacao.sessao import SessaoVotacao


class FabricaAssembleia(FabricaContextoVotacao):
    """Fábrica concreta para família de componentes de Assembleia de Acionistas."""

    @property
    def contexto(self) -> str:
        return "ASSEMBLEIA"

    def criar_regra(
        self,
        tipo_decisao: TipoDecisaoAssembleia = TipoDecisaoAssembleia.MAIORIA_SIMPLES,
        percentual_quorum_instalacao: float = 0.0,
        base_calculo_sobre_total_capital: bool = False,
        **kwargs: Any,
    ) -> RegraAssembleia:
        """Cria uma RegraAssembleia configurada."""
        return RegraAssembleia(
            tipo_decisao=tipo_decisao,
            percentual_quorum_instalacao=percentual_quorum_instalacao,
            base_calculo_sobre_total_capital=base_calculo_sobre_total_capital,
        )

    def criar_validador(self, **kwargs: Any) -> ValidadorElegibilidadeAssembleia:
        """Cria o ValidadorElegibilidadeAssembleia."""
        return ValidadorElegibilidadeAssembleia()

    def criar_repositorio(self, popular: bool = True, **kwargs: Any) -> RepositorioAssembleia:
        """Cria o RepositorioAssembleia, opcionalmente populado com dados padrão."""
        repo = RepositorioAssembleia()
        if popular:
            carregar_dados_padrao_assembleia(repo)
        return repo

    def criar_sessao(
        self,
        id_sessao: str,
        total_aptos: int = 0,
        tipo_decisao: TipoDecisaoAssembleia = TipoDecisaoAssembleia.MAIORIA_SIMPLES,
        percentual_quorum_instalacao: float = 0.0,
        base_calculo_sobre_total_capital: bool = False,
        **kwargs: Any,
    ) -> SessaoVotacao:
        """Cria uma SessaoVotacao com RegraAssembleia associada."""
        regra = kwargs.get("regra")
        if regra is None:
            regra = self.criar_regra(
                tipo_decisao=tipo_decisao,
                percentual_quorum_instalacao=percentual_quorum_instalacao,
                base_calculo_sobre_total_capital=base_calculo_sobre_total_capital,
            )
        return SessaoVotacao(
            id_sessao=id_sessao,
            regra=regra,
            total_aptos=total_aptos,
            log=kwargs.get("log"),
            relogio=kwargs.get("relogio"),
        )

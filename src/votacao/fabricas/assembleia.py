"""Fábrica concreta para o contexto de Assembleia de Acionistas."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any

from votacao.auditoria import LogDeAuditoria
from votacao.dados.assembleia import RepositorioAssembleia
from votacao.dados.seeds import carregar_dados_padrao_assembleia
from votacao.elegibilidade.validador_assembleia import (
    ValidadorElegibilidadeAssembleia,
)
from votacao.fabricas.base import FabricaContextoVotacao
from votacao.modelos import TipoDecisaoAssembleia
from votacao.regras.assembleia import RegraAssembleia
from votacao.sessao import SessaoVotacao

if TYPE_CHECKING:
    from votacao.observadores import ObservadorSessao


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
    ) -> RegraAssembleia:
        """Cria uma RegraAssembleia configurada."""
        return RegraAssembleia(
            tipo_decisao=tipo_decisao,
            percentual_quorum_instalacao=percentual_quorum_instalacao,
            base_calculo_sobre_total_capital=base_calculo_sobre_total_capital,
        )

    def criar_validador(self) -> ValidadorElegibilidadeAssembleia:
        """Cria o ValidadorElegibilidadeAssembleia."""
        return ValidadorElegibilidadeAssembleia()

    def criar_repositorio(self, popular: bool = True) -> RepositorioAssembleia:
        """Cria o RepositorioAssembleia, opcionalmente populado com dados padrão."""
        repo = RepositorioAssembleia()
        if popular:
            carregar_dados_padrao_assembleia(repo)
        return repo

    def obter_repositorio(self, banco: Any | None = None) -> RepositorioAssembleia:
        """Obtém o repositório Assembleia a partir do banco unificado ou cria um novo."""
        if banco is not None and hasattr(banco, "assembleia"):
            return banco.assembleia
        return self.criar_repositorio(popular=True)

    def criar_sessao(
        self,
        id_sessao: str,
        total_aptos: int = 0,
        tipo_decisao: TipoDecisaoAssembleia = TipoDecisaoAssembleia.MAIORIA_SIMPLES,
        percentual_quorum_instalacao: float = 0.0,
        base_calculo_sobre_total_capital: bool = False,
        log: LogDeAuditoria | None = None,
        observadores: Sequence[ObservadorSessao] | None = None,
        relogio: Callable[[], datetime] | None = None,
        regra: RegraAssembleia | None = None,
    ) -> SessaoVotacao:
        """Cria uma SessaoVotacao com RegraAssembleia associada."""
        if regra is None:
            regra = self.criar_regra(
                tipo_decisao=tipo_decisao,
                percentual_quorum_instalacao=percentual_quorum_instalacao,
                base_calculo_sobre_total_capital=base_calculo_sobre_total_capital,
            )
        kwargs_sessao: dict[str, Any] = {
            "id_sessao": id_sessao,
            "regra": regra,
            "total_aptos": total_aptos,
            "log": log,
            "relogio": relogio,
        }
        if observadores is not None:
            kwargs_sessao["observadores"] = observadores
        return SessaoVotacao(**kwargs_sessao)

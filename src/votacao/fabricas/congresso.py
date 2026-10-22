"""Fábrica concreta para o contexto de Congresso Nacional."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any

from votacao.auditoria import LogDeAuditoria
from votacao.dados.congresso import RepositorioCongresso
from votacao.dados.seeds import carregar_dados_padrao_congresso
from votacao.elegibilidade.validador_congresso import (
    ValidadorElegibilidadeCongresso,
)
from votacao.fabricas.base import FabricaContextoVotacao
from votacao.modelos import CasaLegislativa, TipoMateriaCongresso
from votacao.regras.congresso import RegraCongresso
from votacao.sessao import SessaoVotacao

if TYPE_CHECKING:
    from votacao.observadores import ObservadorSessao


class FabricaCongresso(FabricaContextoVotacao):
    """Fábrica concreta para família de componentes do Congresso Nacional."""

    @property
    def contexto(self) -> str:
        return "CONGRESSO"

    def criar_regra(
        self,
        materia: TipoMateriaCongresso = TipoMateriaCongresso.LEI_ORDINARIA,
        casa: CasaLegislativa = CasaLegislativa.CAMARA,
    ) -> RegraCongresso:
        """Cria uma RegraCongresso configurada."""
        return RegraCongresso(materia=materia, casa=casa)

    def criar_validador(self) -> ValidadorElegibilidadeCongresso:
        """Cria o ValidadorElegibilidadeCongresso."""
        return ValidadorElegibilidadeCongresso()

    def criar_repositorio(self, popular: bool = True) -> RepositorioCongresso:
        """Cria o RepositorioCongresso, opcionalmente populado com dados padrão."""
        repo = RepositorioCongresso()
        if popular:
            carregar_dados_padrao_congresso(repo)
        return repo

    def obter_repositorio(self, banco: Any | None = None) -> RepositorioCongresso:
        """Obtém o repositório Congresso a partir do banco unificado ou cria um novo."""
        if banco is not None and hasattr(banco, "congresso"):
            return banco.congresso
        return self.criar_repositorio(popular=True)

    def criar_sessao(
        self,
        id_sessao: str,
        total_aptos: int = 0,
        materia: TipoMateriaCongresso = TipoMateriaCongresso.LEI_ORDINARIA,
        casa: CasaLegislativa = CasaLegislativa.CAMARA,
        log: LogDeAuditoria | None = None,
        observadores: Sequence[ObservadorSessao] | None = None,
        relogio: Callable[[], datetime] | None = None,
        regra: RegraCongresso | None = None,
    ) -> SessaoVotacao:
        """Cria uma SessaoVotacao com RegraCongresso associada."""
        if regra is None:
            regra = self.criar_regra(materia=materia, casa=casa)
        aptos = total_aptos if total_aptos > 0 else regra.total_membros
        kwargs_sessao: dict[str, Any] = {
            "id_sessao": id_sessao,
            "regra": regra,
            "total_aptos": aptos,
            "log": log,
            "relogio": relogio,
        }
        if observadores is not None:
            kwargs_sessao["observadores"] = observadores
        return SessaoVotacao(**kwargs_sessao)

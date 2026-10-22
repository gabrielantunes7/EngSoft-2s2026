"""Fábrica concreta para o contexto de Centro Acadêmico (CA)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any

from votacao.auditoria import LogDeAuditoria
from votacao.dados.ca import RepositorioCA
from votacao.dados.seeds import carregar_dados_padrao_ca
from votacao.elegibilidade.validador_ca import ValidadorElegibilidadeCA
from votacao.fabricas.base import FabricaContextoVotacao
from votacao.regras.ca import RegraCA
from votacao.sessao import SessaoVotacao

if TYPE_CHECKING:
    from votacao.observadores import ObservadorSessao


class FabricaCA(FabricaContextoVotacao):
    """Fábrica concreta para família de componentes de eleição de Centro Acadêmico."""

    @property
    def contexto(self) -> str:
        return "CA"

    def criar_regra(
        self,
        quorum_minimo_votantes: int = 0,
        percentual_quorum_minimo: float = 0.0,
    ) -> RegraCA:
        """Cria uma RegraCA configurada."""
        return RegraCA(
            quorum_minimo_votantes=quorum_minimo_votantes,
            percentual_quorum_minimo=percentual_quorum_minimo,
        )

    def criar_validador(self) -> ValidadorElegibilidadeCA:
        """Cria o ValidadorElegibilidadeCA."""
        return ValidadorElegibilidadeCA()

    def criar_repositorio(self, popular: bool = True) -> RepositorioCA:
        """Cria o RepositorioCA, opcionalmente populado com dados padrão."""
        repo = RepositorioCA()
        if popular:
            carregar_dados_padrao_ca(repo)
        return repo

    def obter_repositorio(self, banco: Any | None = None) -> RepositorioCA:
        """Obtém o repositório CA a partir do banco unificado ou cria um novo."""
        if banco is not None and hasattr(banco, "ca"):
            return banco.ca
        return self.criar_repositorio(popular=True)

    def criar_sessao(
        self,
        id_sessao: str,
        total_aptos: int = 0,
        quorum_minimo_votantes: int = 0,
        percentual_quorum_minimo: float = 0.0,
        log: LogDeAuditoria | None = None,
        observadores: Sequence[ObservadorSessao] | None = None,
        relogio: Callable[[], datetime] | None = None,
        regra: RegraCA | None = None,
    ) -> SessaoVotacao:
        """Cria uma SessaoVotacao com RegraCA associada."""
        if regra is None:
            regra = self.criar_regra(
                quorum_minimo_votantes=quorum_minimo_votantes,
                percentual_quorum_minimo=percentual_quorum_minimo,
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

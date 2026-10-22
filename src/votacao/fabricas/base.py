"""Interface abstrata (Abstract Factory) para famílias de componentes de votação."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any

from votacao.elegibilidade.base import ValidadorContexto
from votacao.regras.base import RegraDeVotacao
from votacao.sessao import SessaoVotacao

if TYPE_CHECKING:
    from votacao.auditoria import LogDeAuditoria
    from votacao.observadores import ObservadorSessao


class FabricaContextoVotacao(ABC):
    """Fábrica abstrata que define a criação da família de componentes de um domínio.

    Garante que regras de apuração, validadores de elegibilidade, repositórios de dados
    e sessões de votação instanciados pertençam ao mesmo contexto e sejam mutuamente
    compatíveis.
    """

    @property
    @abstractmethod
    def contexto(self) -> str:
        """Nome identificador do contexto eleitoral (ex.: 'CA', 'ASSEMBLEIA', 'CONGRESSO')."""
        raise NotImplementedError

    @abstractmethod
    def criar_regra(self, **kwargs: Any) -> RegraDeVotacao:
        """Instancia a regra de apuração correspondente ao contexto."""
        raise NotImplementedError

    @abstractmethod
    def criar_validador(self) -> ValidadorContexto:
        """Instancia o validador de elegibilidade correspondente ao contexto."""
        raise NotImplementedError

    @abstractmethod
    def criar_repositorio(self, popular: bool = True) -> Any:
        """Instancia o repositório de dados correspondente ao contexto."""
        raise NotImplementedError

    @abstractmethod
    def obter_repositorio(self, banco: Any | None = None) -> Any:
        """Obtém o repositório deste contexto a partir do banco unificado ou cria um novo."""
        raise NotImplementedError

    @abstractmethod
    def criar_sessao(
        self,
        id_sessao: str,
        total_aptos: int = 0,
        log: LogDeAuditoria | None = None,
        observadores: Sequence[ObservadorSessao] | None = None,
        relogio: Callable[[], datetime] | None = None,
        regra: RegraDeVotacao | None = None,
        **kwargs: Any,
    ) -> SessaoVotacao:
        """Instancia uma SessaoVotacao pré-configurada com a regra do contexto."""
        raise NotImplementedError


__all__ = ["FabricaContextoVotacao", "ValidadorContexto"]

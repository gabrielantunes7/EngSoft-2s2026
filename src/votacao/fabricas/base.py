"""Interface abstrata (Abstract Factory) para famílias de componentes de votação."""

from abc import ABC, abstractmethod
from typing import Any

from votacao.regras.base import RegraDeVotacao
from votacao.sessao import SessaoVotacao


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
    def criar_validador(self, **kwargs: Any) -> Any:
        """Instancia o validador de elegibilidade correspondente ao contexto."""
        raise NotImplementedError

    @abstractmethod
    def criar_repositorio(self, popular: bool = True, **kwargs: Any) -> Any:
        """Instancia o repositório de dados correspondente ao contexto."""
        raise NotImplementedError

    @abstractmethod
    def criar_sessao(
        self,
        id_sessao: str,
        total_aptos: int = 0,
        **kwargs: Any,
    ) -> SessaoVotacao:
        """Instancia uma SessaoVotacao pré-configurada com a regra do contexto."""
        raise NotImplementedError

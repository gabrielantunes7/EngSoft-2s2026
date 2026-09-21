"""Contratos base para repositórios de dados mockados."""

from abc import ABC, abstractmethod


class RepositorioBase(ABC):
    """Interface abstrata base para repositórios de dados mockados."""

    @abstractmethod
    def limpar(self) -> None:
        """Remove todos os registros armazenados no repositório."""
        raise NotImplementedError

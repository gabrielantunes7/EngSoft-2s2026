"""Interface base polimórfica para validadores de elegibilidade por contexto."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from votacao.modelos import AptidaoVoto, CasaLegislativa, ElegibilidadeCandidato, Usuario


class ValidadorContexto(ABC):
    """Interface polimórfica comum para a família de validadores de cada contexto."""

    @abstractmethod
    def autenticar(self, identificador: str, repo: Any) -> Usuario | None:
        """Autentica o participante no repositório correspondente."""
        raise NotImplementedError

    @abstractmethod
    def consultar_aptidao(
        self,
        eleitor_id: str,
        repo: Any,
        *,
        casa: CasaLegislativa | None = None,
        procurador_id: str | None = None,
        momento: datetime | None = None,
    ) -> AptidaoVoto:
        """Verifica a aptidão ao voto do eleitor/participante no contexto."""
        raise NotImplementedError

    @abstractmethod
    def validar_opcao(
        self,
        opcao_ou_candidato: str,
        repo: Any,
        *,
        casa: CasaLegislativa | None = None,
    ) -> ElegibilidadeCandidato:
        """Valida a opção de voto ou candidatura no contexto."""
        raise NotImplementedError

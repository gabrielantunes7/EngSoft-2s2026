"""Interface base (Strategy) para regras de votação e apuração."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from votacao.modelos import ResultadoApuracao, Voto


class RegraDeVotacao(ABC):
    """Interface abstrata que define o contrato para estratégias de votação."""

    @abstractmethod
    def validar_quorum(self, total_aptos: int, votos: Sequence[Voto]) -> bool:
        """Verifica se o quórum mínimo de participação ou instalação foi atingido.

        Args:
            total_aptos: Total de eleitores aptos ou total de capital social votante.
            votos: Sequência de votos computados.

        Returns:
            True se o quórum foi atingido, False caso contrário.
        """
        raise NotImplementedError

    @abstractmethod
    def apurar(self, votos: Sequence[Voto], total_aptos: int = 0) -> ResultadoApuracao:
        """Executa a contagem, ponderação e apuração do resultado da votação.

        Args:
            votos: Sequência de votos computados.
            total_aptos: Total de eleitores aptos ou total de capital social votante.

        Returns:
            Instância de ResultadoApuracao com o veredito final.
        """
        raise NotImplementedError

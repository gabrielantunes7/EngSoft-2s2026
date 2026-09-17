"""Motor de apuração e orquestração de votações."""

from collections.abc import Sequence

from votacao.modelos import ResultadoApuracao, Voto
from votacao.regras.base import RegraDeVotacao


class MotorApuracao:
    """Motor central responsável por delegar a apuração à estratégia configurada."""

    @staticmethod
    def apurar(
        votos: Sequence[Voto],
        regra: RegraDeVotacao,
        total_aptos_ou_capital: int = 0,
    ) -> ResultadoApuracao:
        """Executa a apuração dos votos utilizando a regra especificada.

        Args:
            votos: Sequência de votos computados.
            regra: Estratégia de votação que implementa RegraDeVotacao.
            total_aptos_ou_capital: Total de aptos (CA/Congresso) ou capital social (Assembleia).

        Returns:
            ResultadoApuracao consolidado.
        """
        if not isinstance(regra, RegraDeVotacao):
            msg = "A regra de votação fornecida deve implementar a interface RegraDeVotacao."
            raise TypeError(msg)

        return regra.apurar(votos=votos, total_aptos=total_aptos_ou_capital)

"""Regra de votação e apuração para eleições de Centro Acadêmico (CA)."""

from collections import Counter
from collections.abc import Sequence
from typing import ClassVar

from votacao.modelos import ResultadoApuracao, StatusResultado, Voto
from votacao.regras.base import RegraDeVotacao


class RegraCA(RegraDeVotacao):
    """Regra de eleição de Centro Acadêmico baseada em maioria simples e voto unitário.

    Attributes:
        quorum_minimo_votantes: Quantidade mínima absoluta de votos necessários.
        percentual_quorum_minimo: Fração mínima (0.0 a 1.0) do total de alunos aptos exigida.
    """

    OPCOES_NAO_VALIDAS: ClassVar[set[str]] = {"BRANCO", "NULO"}

    def __init__(
        self,
        quorum_minimo_votantes: int = 0,
        percentual_quorum_minimo: float = 0.0,
    ) -> None:
        if quorum_minimo_votantes < 0:
            msg = "O quórum mínimo de votantes não pode ser negativo."
            raise ValueError(msg)
        if not (0.0 <= percentual_quorum_minimo <= 1.0):
            msg = "O percentual de quórum mínimo deve estar entre 0.0 e 1.0."
            raise ValueError(msg)

        self.quorum_minimo_votantes = quorum_minimo_votantes
        self.percentual_quorum_minimo = percentual_quorum_minimo

    def validar_quorum(self, total_aptos: int, votos: Sequence[Voto]) -> bool:
        """Verifica se o número de votantes atinge o quórum absoluto e percentual."""
        total_votantes = len(votos)
        if total_votantes < self.quorum_minimo_votantes:
            return False

        if self.percentual_quorum_minimo > 0.0:
            if total_aptos <= 0:
                return False
            minimo_exigido = total_aptos * self.percentual_quorum_minimo
            if total_votantes < minimo_exigido:
                return False

        return True

    def apurar(self, votos: Sequence[Voto], total_aptos: int = 0) -> ResultadoApuracao:
        """Apura a eleição do Centro Acadêmico por maioria simples de votos válidos."""
        total_votantes = len(votos)
        quorum_ok = self.validar_quorum(total_aptos, votos)

        # Contagem de votos (voto unitário para CA: peso 1)
        contagem: Counter[str] = Counter()
        for voto in votos:
            opcao_normalizada = voto.opcao.strip().upper()
            contagem[opcao_normalizada] += 1

        contagem_dict = dict(contagem)
        total_peso = total_votantes

        if not quorum_ok:
            return ResultadoApuracao(
                status=StatusResultado.QUORUM_INSUFICIENTE,
                vencedor_ou_decisao=None,
                quorum_atingido=False,
                total_votantes=total_votantes,
                total_peso_apurado=total_peso,
                contagem_por_opcao=contagem_dict,
                percentual_vencedor=None,
                detalhes={"motivo": "Quórum mínimo de participação não atingido."},
            )

        # Votos válidos são aqueles que não são BRANCO nem NULO
        votos_validos = {
            op: qtd for op, qtd in contagem.items() if op not in self.OPCOES_NAO_VALIDAS
        }
        total_validos = sum(votos_validos.values())

        if total_validos == 0:
            return ResultadoApuracao(
                status=StatusResultado.EMPATE,
                vencedor_ou_decisao=None,
                quorum_atingido=True,
                total_votantes=total_votantes,
                total_peso_apurado=total_peso,
                contagem_por_opcao=contagem_dict,
                percentual_vencedor=0.0,
                detalhes={"motivo": "Nenhum voto válido computado para as chapas concorrentes."},
            )

        # Determina a chapa mais votada
        ordenados = sorted(votos_validos.items(), key=lambda item: item[1], reverse=True)
        chapa_lider, max_votos = ordenados[0]

        # Verifica se houve empate entre duas ou mais chapas no topo
        chapas_com_max_votos = [op for op, qtd in ordenados if qtd == max_votos]
        if len(chapas_com_max_votos) > 1:
            return ResultadoApuracao(
                status=StatusResultado.EMPATE,
                vencedor_ou_decisao=None,
                quorum_atingido=True,
                total_votantes=total_votantes,
                total_peso_apurado=total_peso,
                contagem_por_opcao=contagem_dict,
                percentual_vencedor=round((max_votos / total_validos) * 100, 2),
                detalhes={"chapas_empatadas": chapas_com_max_votos, "votos_cada": max_votos},
            )

        percentual = round((max_votos / total_validos) * 100, 2)
        return ResultadoApuracao(
            status=StatusResultado.ELEITO,
            vencedor_ou_decisao=chapa_lider,
            quorum_atingido=True,
            total_votantes=total_votantes,
            total_peso_apurado=total_peso,
            contagem_por_opcao=contagem_dict,
            percentual_vencedor=percentual,
            detalhes={
                "total_validos": total_validos,
                "brancos": contagem.get("BRANCO", 0),
                "nulos": contagem.get("NULO", 0),
            },
        )

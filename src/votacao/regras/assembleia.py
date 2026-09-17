"""Regra de votação e apuração para assembleias corporativas de acionistas."""

from collections import Counter
from collections.abc import Sequence
from typing import ClassVar

from votacao.modelos import (
    ResultadoApuracao,
    StatusResultado,
    TipoDecisaoAssembleia,
    Voto,
)
from votacao.regras.base import RegraDeVotacao


class RegraAssembleia(RegraDeVotacao):
    """Regra de deliberação para Assembleias com votos ponderados por ações/cotas.

    Attributes:
        tipo_decisao: Critério de aprovação (Maioria Simples, Absoluta ou Qualificada).
        percentual_quorum_instalacao: Fração mínima (0.0 a 1.0) do capital social total
            necessária para instalar e validar a assembleia.
        base_calculo_sobre_total_capital: Se True, maiorias qualificadas/absolutas são
            calculadas sobre o total de capital existente, e não apenas sobre os presentes.
    """

    OPCOES_ABSTENCAO: ClassVar[set[str]] = {"ABSTENCAO", "BRANCO", "NULO"}

    def __init__(
        self,
        tipo_decisao: TipoDecisaoAssembleia = TipoDecisaoAssembleia.MAIORIA_SIMPLES,
        percentual_quorum_instalacao: float = 0.0,
        base_calculo_sobre_total_capital: bool = False,
    ) -> None:
        if not (0.0 <= percentual_quorum_instalacao <= 1.0):
            msg = "O percentual de quórum de instalação deve estar entre 0.0 e 1.0."
            raise ValueError(msg)

        self.tipo_decisao = tipo_decisao
        self.percentual_quorum_instalacao = percentual_quorum_instalacao
        self.base_calculo_sobre_total_capital = base_calculo_sobre_total_capital

    def validar_quorum(self, total_aptos: int, votos: Sequence[Voto]) -> bool:
        """Verifica se o capital social presente atinge o quórum mínimo de instalação.

        No contexto de Assembleia, total_aptos representa o total de capital social votante.
        """
        if self.percentual_quorum_instalacao == 0.0:
            return True

        if total_aptos <= 0:
            return False

        capital_presente = sum(voto.peso for voto in votos)
        capital_minimo = total_aptos * self.percentual_quorum_instalacao
        return capital_presente >= capital_minimo

    def apurar(self, votos: Sequence[Voto], total_aptos: int = 0) -> ResultadoApuracao:
        """Apura a deliberação da assembleia ponderando os votos pelo peso das ações."""
        total_votantes = len(votos)
        quorum_ok = self.validar_quorum(total_aptos, votos)

        # Contagem ponderada por opção de voto
        contagem_ponderada: Counter[str] = Counter()
        for voto in votos:
            opcao_normalizada = voto.opcao.strip().upper()
            contagem_ponderada[opcao_normalizada] += voto.peso

        total_peso_presente = sum(contagem_ponderada.values())
        contagem_dict = dict(contagem_ponderada)

        if not quorum_ok:
            return ResultadoApuracao(
                status=StatusResultado.QUORUM_INSUFICIENTE,
                vencedor_ou_decisao=None,
                quorum_atingido=False,
                total_votantes=total_votantes,
                total_peso_apurado=total_peso_presente,
                contagem_por_opcao=contagem_dict,
                percentual_vencedor=None,
                detalhes={
                    "motivo": "Quórum de instalação da assembleia não foi atingido.",
                    "capital_presente": total_peso_presente,
                    "capital_total": total_aptos,
                },
            )

        votos_sim = contagem_ponderada.get("SIM", 0)
        votos_nao = contagem_ponderada.get("NAO", 0)
        votos_deliberativos = votos_sim + votos_nao

        if votos_deliberativos == 0:
            return ResultadoApuracao(
                status=StatusResultado.REJEITADO,
                vencedor_ou_decisao="NAO",
                quorum_atingido=True,
                total_votantes=total_votantes,
                total_peso_apurado=total_peso_presente,
                contagem_por_opcao=contagem_dict,
                percentual_vencedor=0.0,
                detalhes={"motivo": "Nenhum voto SIM ou NAO computado na assembleia."},
            )

        aprovado, percentual_sim, detalhes_criterio = self._avaliar_criterio(
            votos_sim=votos_sim,
            votos_nao=votos_nao,
            votos_deliberativos=votos_deliberativos,
            total_peso_presente=total_peso_presente,
            total_capital_votante=total_aptos,
        )

        status = StatusResultado.APROVADO if aprovado else StatusResultado.REJEITADO
        decisao = "SIM" if aprovado else "NAO"

        return ResultadoApuracao(
            status=status,
            vencedor_ou_decisao=decisao,
            quorum_atingido=True,
            total_votantes=total_votantes,
            total_peso_apurado=total_peso_presente,
            contagem_por_opcao=contagem_dict,
            percentual_vencedor=percentual_sim,
            detalhes={
                "tipo_decisao": self.tipo_decisao.value,
                "votos_sim_peso": votos_sim,
                "votos_nao_peso": votos_nao,
                "abstencoes_peso": sum(
                    contagem_ponderada.get(op, 0) for op in self.OPCOES_ABSTENCAO
                ),
                **detalhes_criterio,
            },
        )

    def _avaliar_criterio(
        self,
        votos_sim: int,
        votos_nao: int,
        votos_deliberativos: int,
        total_peso_presente: int,
        total_capital_votante: int,
    ) -> tuple[bool, float, dict[str, float]]:
        """Aplica o critério de maioria correspondente ao tipo de deliberação."""
        detalhes: dict[str, float] = {}

        if self.tipo_decisao == TipoDecisaoAssembleia.MAIORIA_SIMPLES:
            percentual_sim = round((votos_sim / votos_deliberativos) * 100, 2)
            aprovado = votos_sim > votos_nao
            return aprovado, percentual_sim, detalhes

        base = (
            total_capital_votante if self.base_calculo_sobre_total_capital else total_peso_presente
        )

        if self.tipo_decisao == TipoDecisaoAssembleia.MAIORIA_ABSOLUTA:
            if base <= 0:
                return False, 0.0, detalhes
            percentual_sim = round((votos_sim / base) * 100, 2)
            aprovado = votos_sim > (base / 2)
            detalhes["base_calculo"] = float(base)
            return aprovado, percentual_sim, detalhes

        if self.tipo_decisao == TipoDecisaoAssembleia.QUALIFICADA_DOIS_TERCOS:
            if base <= 0:
                return False, 0.0, detalhes
            percentual_sim = round((votos_sim / base) * 100, 2)
            fracao_exigida = 2.0 / 3.0
            aprovado = (votos_sim / base) >= fracao_exigida
            detalhes["percentual_minimo_exigido"] = round(fracao_exigida * 100, 2)
            return aprovado, percentual_sim, detalhes

        if self.tipo_decisao == TipoDecisaoAssembleia.QUALIFICADA_TRES_QUINTOS:
            if base <= 0:
                return False, 0.0, detalhes
            percentual_sim = round((votos_sim / base) * 100, 2)
            fracao_exigida = 3.0 / 5.0
            aprovado = (votos_sim / base) >= fracao_exigida
            detalhes["percentual_minimo_exigido"] = round(fracao_exigida * 100, 2)
            return aprovado, percentual_sim, detalhes

        msg = f"Tipo de decisão desconhecido: {self.tipo_decisao}"
        raise ValueError(msg)

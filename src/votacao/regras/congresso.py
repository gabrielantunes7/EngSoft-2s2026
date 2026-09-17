"""Regra de votação e apuração para o Congresso Nacional."""

from collections import Counter
from collections.abc import Sequence

from votacao.modelos import (
    CasaLegislativa,
    ResultadoApuracao,
    StatusResultado,
    TipoMateriaCongresso,
    Voto,
)
from votacao.regras.base import RegraDeVotacao


class RegraCongresso(RegraDeVotacao):
    """Regra de deliberação parlamentar para Câmara dos Deputados e Senado Federal.

    Attributes:
        materia: Tipo de matéria legislativa (Lei Ordinária, Complementar ou PEC).
        casa: Casa legislativa onde a votação ocorre (Câmara ou Senado).
    """

    TOTAL_MEMBROS_CAMARA = 513
    TOTAL_MEMBROS_SENADO = 81

    # Quórum mínimo de instalação de sessão (maioria absoluta de membros presentes)
    QUORUM_INSTALACAO_CAMARA = 257  # 513 // 2 + 1
    QUORUM_INSTALACAO_SENADO = 41  # 81 // 2 + 1

    # Votos SIM mínimos para aprovação de Lei Complementar (maioria absoluta do total de membros)
    MINIMO_LEI_COMPLEMENTAR_CAMARA = 257
    MINIMO_LEI_COMPLEMENTAR_SENADO = 41

    # Votos SIM mínimos para aprovação de PEC (três quintos do total de membros: 3/5)
    MINIMO_PEC_CAMARA = 308  # ceil(513 * 3 / 5)
    MINIMO_PEC_SENADO = 49  # ceil(81 * 3 / 5)

    def __init__(
        self,
        materia: TipoMateriaCongresso = TipoMateriaCongresso.LEI_ORDINARIA,
        casa: CasaLegislativa = CasaLegislativa.CAMARA,
    ) -> None:
        self.materia = materia
        self.casa = casa

    @property
    def total_membros(self) -> int:
        """Retorna o número total constitucional de membros da Casa."""
        if self.casa == CasaLegislativa.CAMARA:
            return self.TOTAL_MEMBROS_CAMARA
        return self.TOTAL_MEMBROS_SENADO

    @property
    def quorum_instalacao(self) -> int:
        """Retorna o número mínimo de parlamentares presentes para abrir a votação."""
        if self.casa == CasaLegislativa.CAMARA:
            return self.QUORUM_INSTALACAO_CAMARA
        return self.QUORUM_INSTALACAO_SENADO

    def validar_quorum(self, total_aptos: int, votos: Sequence[Voto]) -> bool:
        """Verifica se há quórum mínimo de presentes para deliberação em plenário."""
        return len(votos) >= self.quorum_instalacao

    def apurar(self, votos: Sequence[Voto], total_aptos: int = 0) -> ResultadoApuracao:
        """Apura a votação parlamentar conforme o tipo de matéria e Casa Legislativa."""
        total_presentes = len(votos)
        quorum_ok = self.validar_quorum(total_aptos, votos)

        contagem: Counter[str] = Counter()
        for voto in votos:
            opcao_normalizada = voto.opcao.strip().upper()
            contagem[opcao_normalizada] += 1

        votos_sim = contagem.get("SIM", 0)
        votos_nao = contagem.get("NAO", 0)
        abstencoes = contagem.get("ABSTENCAO", 0) + contagem.get("BRANCO", 0)

        contagem_dict = dict(contagem)

        if not quorum_ok:
            return ResultadoApuracao(
                status=StatusResultado.QUORUM_INSUFICIENTE,
                vencedor_ou_decisao=None,
                quorum_atingido=False,
                total_votantes=total_presentes,
                total_peso_apurado=total_presentes,
                contagem_por_opcao=contagem_dict,
                percentual_vencedor=None,
                detalhes={
                    "motivo": "Quórum mínimo de instalação de sessão não atingido.",
                    "presentes": total_presentes,
                    "minimo_exigido": self.quorum_instalacao,
                    "casa": self.casa.value,
                },
            )

        aprovado, min_exigido = self._avaliar_aprovacao(votos_sim, votos_nao, total_presentes)
        percentual_sim = (
            round((votos_sim / total_presentes) * 100, 2) if total_presentes > 0 else 0.0
        )
        status = StatusResultado.APROVADO if aprovado else StatusResultado.REJEITADO
        decisao = "SIM" if aprovado else "NAO"

        return ResultadoApuracao(
            status=status,
            vencedor_ou_decisao=decisao,
            quorum_atingido=True,
            total_votantes=total_presentes,
            total_peso_apurado=total_presentes,
            contagem_por_opcao=contagem_dict,
            percentual_vencedor=percentual_sim,
            detalhes={
                "materia": self.materia.value,
                "casa": self.casa.value,
                "votos_sim": votos_sim,
                "votos_nao": votos_nao,
                "abstencoes": abstencoes,
                "total_membros_casa": self.total_membros,
                "minimo_votos_sim_exigido": min_exigido,
            },
        )

    def _avaliar_aprovacao(
        self, votos_sim: int, votos_nao: int, total_presentes: int
    ) -> tuple[bool, int | None]:
        """Avalia se os votos SIM atingem o patamar exigido pela Constituição."""
        if self.materia == TipoMateriaCongresso.LEI_ORDINARIA:
            aprovado = votos_sim > votos_nao
            return aprovado, None

        if self.materia == TipoMateriaCongresso.LEI_COMPLEMENTAR:
            minimo = (
                self.MINIMO_LEI_COMPLEMENTAR_CAMARA
                if self.casa == CasaLegislativa.CAMARA
                else self.MINIMO_LEI_COMPLEMENTAR_SENADO
            )
            aprovado = votos_sim >= minimo
            return aprovado, minimo

        if self.materia == TipoMateriaCongresso.PEC:
            minimo = (
                self.MINIMO_PEC_CAMARA
                if self.casa == CasaLegislativa.CAMARA
                else self.MINIMO_PEC_SENADO
            )
            aprovado = votos_sim >= minimo
            return aprovado, minimo

        msg = f"Matéria desconhecida: {self.materia}"
        raise ValueError(msg)

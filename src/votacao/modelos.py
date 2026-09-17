"""Modelos de dados para o sistema de votação e apuração."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class StatusResultado(StrEnum):
    """Status consolidado do resultado de uma votação."""

    APROVADO = "APROVADO"
    REJEITADO = "REJEITADO"
    ELEITO = "ELEITO"
    EMPATE = "EMPATE"
    QUORUM_INSUFICIENTE = "QUORUM_INSUFICIENTE"


class TipoDecisaoAssembleia(StrEnum):
    """Tipos de critério de deliberação em assembleias de acionistas."""

    MAIORIA_SIMPLES = "MAIORIA_SIMPLES"
    MAIORIA_ABSOLUTA = "MAIORIA_ABSOLUTA"
    QUALIFICADA_DOIS_TERCOS = "QUALIFICADA_DOIS_TERCOS"
    QUALIFICADA_TRES_QUINTOS = "QUALIFICADA_TRES_QUINTOS"


class TipoMateriaCongresso(StrEnum):
    """Tipos de matérias legislativas com ritos e quóruns distintos."""

    LEI_ORDINARIA = "LEI_ORDINARIA"
    LEI_COMPLEMENTAR = "LEI_COMPLEMENTAR"
    PEC = "PEC"


class CasaLegislativa(StrEnum):
    """Casas do Congresso Nacional."""

    CAMARA = "CAMARA"
    SENADO = "SENADO"


@dataclass(frozen=True)
class Voto:
    """Representa um voto individual registrado no sistema.

    Attributes:
        eleitor_id: Identificador único do votante (anônimo ou nominal).
        opcao: Opção escolhida (nome da chapa, 'SIM', 'NAO', 'BRANCO', 'NULO').
        peso: Peso decisório do voto (1 para CA/Congresso; quantidade de ações para Assembleia).
        timestamp: Data e hora do registro do voto.
    """

    eleitor_id: str
    opcao: str
    peso: int = 1
    timestamp: datetime | None = None

    def __post_init__(self) -> None:
        if self.peso <= 0:
            msg = "O peso do voto deve ser um número inteiro positivo."
            raise ValueError(msg)
        if not self.eleitor_id.strip():
            msg = "O identificador do eleitor não pode ser vazio."
            raise ValueError(msg)
        if not self.opcao.strip():
            msg = "A opção de voto não pode ser vazia."
            raise ValueError(msg)


@dataclass(frozen=True)
class ResultadoApuracao:
    """Resultado consolidado da apuração de uma votação.

    Attributes:
        status: Status final do processo deliberativo ou eleitoral.
        vencedor_ou_decisao: Nome da chapa vencedora ou decisão ('SIM'/'NAO'/None).
        quorum_atingido: Indica se os requisitos mínimos de quórum foram satisfeitos.
        total_votantes: Quantidade absoluta de eleitores que registraram voto.
        total_peso_apurado: Soma dos pesos dos votos computados.
        contagem_por_opcao: Dicionário mapeando cada opção à soma de seus pesos apurados.
        percentual_vencedor: Percentual obtido pela opção vencedora/aprovada (0.0 a 100.0).
        detalhes: Informações complementares específicas do contexto.
    """

    status: StatusResultado
    vencedor_ou_decisao: str | None
    quorum_atingido: bool
    total_votantes: int
    total_peso_apurado: int
    contagem_por_opcao: dict[str, int] = field(default_factory=dict)
    percentual_vencedor: float | None = None
    detalhes: dict[str, Any] = field(default_factory=dict)

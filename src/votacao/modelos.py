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
        representados: Identificadores dos acionistas cujo capital foi consolidado neste voto
            por procuração (Assembleia), inclusive o do próprio emissor quando as suas
            ações entram no voto. Vazio nos votos individuais.
    """

    eleitor_id: str
    opcao: str
    peso: int = 1
    timestamp: datetime | None = None
    representados: tuple[str, ...] = ()

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
        if any(not representado.strip() for representado in self.representados):
            msg = "Os identificadores dos representados não podem ser vazios."
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


@dataclass(frozen=True)
class Usuario:
    """Representa um usuário autenticável no sistema.

    Attributes:
        id: Identificador único (RA, CPF/CNPJ, ID parlamentar).
        nome: Nome completo do usuário.
        email: E-mail para notificações e comprovantes.
        ativo: Indica se o cadastro do usuário está ativo no sistema.
    """

    id: str
    nome: str
    email: str = ""
    ativo: bool = True

    def __post_init__(self) -> None:
        if not self.id.strip():
            msg = "O identificador do usuário não pode ser vazio."
            raise ValueError(msg)
        if not self.nome.strip():
            msg = "O nome do usuário não pode ser vazio."
            raise ValueError(msg)


@dataclass(frozen=True)
class AptidaoVoto:
    """Resultado da verificação de aptidão de um eleitor para votar.

    Attributes:
        apto: Indica se o eleitor cumpre todos os requisitos para votar.
        peso_voto: Peso unitário (CA/Congresso) ou ponderado por ações (Assembleia).
        motivo_inaptidao: Descrição da razão caso o eleitor não esteja apto.
        dados_eleitor: Metadados contextuais adicionais do eleitor.
    """

    apto: bool
    peso_voto: int = 1
    motivo_inaptidao: str | None = None
    dados_eleitor: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.peso_voto < 0:
            msg = "O peso do voto não pode ser negativo."
            raise ValueError(msg)


@dataclass(frozen=True)
class ElegibilidadeCandidato:
    """Resultado da verificação de elegibilidade de um candidato ou chapa.

    Attributes:
        elegivel: Indica se o candidato ou chapa atende a todos os critérios.
        motivo_inelegibilidade: Descrição da causa de inelegibilidade, se houver.
        detalhes: Informações complementares da validação de requisitos.
    """

    elegivel: bool
    motivo_inelegibilidade: str | None = None
    detalhes: dict[str, Any] = field(default_factory=dict)

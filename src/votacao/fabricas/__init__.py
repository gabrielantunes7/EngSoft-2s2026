"""Padrão Abstract Factory para famílias de componentes por contexto de votação."""

from votacao.fabricas.assembleia import FabricaAssembleia
from votacao.fabricas.base import FabricaContextoVotacao
from votacao.fabricas.ca import FabricaCA
from votacao.fabricas.congresso import FabricaCongresso

_CATALOGO_FABRICAS: dict[str, FabricaContextoVotacao] = {
    "CA": FabricaCA(),
    "ASSEMBLEIA": FabricaAssembleia(),
    "CONGRESSO": FabricaCongresso(),
}


def obter_fabrica_contexto(contexto: str) -> FabricaContextoVotacao:
    """Retorna a fábrica abstrata concreta vinculada ao contexto informado.

    Args:
        contexto: Nome do contexto ('CA', 'ASSEMBLEIA', 'CONGRESSO' ou registrado dinamicamente).

    Returns:
        Instância correspondente de FabricaContextoVotacao.

    Raises:
        ValueError: Se o contexto não estiver catalogado.
    """
    ctx_normalizado = contexto.strip().upper()
    if ctx_normalizado not in _CATALOGO_FABRICAS:
        validos = ", ".join(sorted(_CATALOGO_FABRICAS.keys()))
        msg = f"Contexto '{contexto}' não reconhecido. Contextos válidos: {validos}."
        raise ValueError(msg)
    return _CATALOGO_FABRICAS[ctx_normalizado]


def registrar_fabrica_contexto(contexto: str, fabrica: FabricaContextoVotacao) -> None:
    """Registra dinamicamente uma nova fábrica para estender o sistema a novos domínios.

    Args:
        contexto: Identificador do novo contexto eleitoral.
        fabrica: Instância de FabricaContextoVotacao.

    Raises:
        ValueError: Se o nome do contexto for vazio.
        TypeError: Se a fábrica não implementar FabricaContextoVotacao.
    """
    nome = contexto.strip().upper()
    if not nome:
        msg = "O identificador do contexto não pode ser vazio."
        raise ValueError(msg)
    if not isinstance(fabrica, FabricaContextoVotacao):
        msg = "A fábrica fornecida deve implementar a interface FabricaContextoVotacao."
        raise TypeError(msg)
    _CATALOGO_FABRICAS[nome] = fabrica


__all__ = [
    "FabricaAssembleia",
    "FabricaCA",
    "FabricaCongresso",
    "FabricaContextoVotacao",
    "obter_fabrica_contexto",
    "registrar_fabrica_contexto",
]

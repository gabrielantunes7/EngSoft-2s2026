"""Módulo de regras de votação e estratégias de decisão."""

from votacao.regras.assembleia import RegraAssembleia
from votacao.regras.base import RegraDeVotacao
from votacao.regras.ca import RegraCA
from votacao.regras.congresso import RegraCongresso

__all__ = [
    "RegraAssembleia",
    "RegraCA",
    "RegraCongresso",
    "RegraDeVotacao",
]

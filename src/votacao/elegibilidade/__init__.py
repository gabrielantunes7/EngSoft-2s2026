"""Módulo de validação de elegibilidade e regras de aptidão ao voto."""

from votacao.elegibilidade.validador_assembleia import (
    ValidadorElegibilidadeAssembleia,
)
from votacao.elegibilidade.validador_ca import ValidadorElegibilidadeCA
from votacao.elegibilidade.validador_congresso import (
    ValidadorElegibilidadeCongresso,
)

__all__ = [
    "ValidadorElegibilidadeAssembleia",
    "ValidadorElegibilidadeCA",
    "ValidadorElegibilidadeCongresso",
]

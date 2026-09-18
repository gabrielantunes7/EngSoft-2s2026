"""Sistema de votação digital com motor de regras extensível."""

from votacao.dados.seeds import BancoDadosMock
from votacao.elegibilidade.validador_assembleia import (
    ValidadorElegibilidadeAssembleia,
)
from votacao.elegibilidade.validador_ca import ValidadorElegibilidadeCA
from votacao.elegibilidade.validador_congresso import (
    ValidadorElegibilidadeCongresso,
)
from votacao.modelos import (
    AptidaoVoto,
    CasaLegislativa,
    ElegibilidadeCandidato,
    ResultadoApuracao,
    StatusResultado,
    TipoDecisaoAssembleia,
    TipoMateriaCongresso,
    Usuario,
    Voto,
)
from votacao.motor import MotorApuracao
from votacao.regras.assembleia import RegraAssembleia
from votacao.regras.base import RegraDeVotacao
from votacao.regras.ca import RegraCA
from votacao.regras.congresso import RegraCongresso
from votacao.servicos import ServicoElegibilidade

__version__ = "0.1.0"

__all__ = [
    "AptidaoVoto",
    "BancoDadosMock",
    "CasaLegislativa",
    "ElegibilidadeCandidato",
    "MotorApuracao",
    "RegraAssembleia",
    "RegraCA",
    "RegraCongresso",
    "RegraDeVotacao",
    "ResultadoApuracao",
    "ServicoElegibilidade",
    "StatusResultado",
    "TipoDecisaoAssembleia",
    "TipoMateriaCongresso",
    "Usuario",
    "ValidadorElegibilidadeAssembleia",
    "ValidadorElegibilidadeCA",
    "ValidadorElegibilidadeCongresso",
    "Voto",
    "__version__",
]

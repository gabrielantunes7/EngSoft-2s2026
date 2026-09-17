"""Sistema de votação digital com motor de regras extensível."""

from votacao.auditoria import (
    HASH_GENESE,
    LogDeAuditoria,
    RegistroAuditoria,
    ResultadoVerificacao,
    TipoEvento,
)
from votacao.modelos import (
    CasaLegislativa,
    ResultadoApuracao,
    StatusResultado,
    TipoDecisaoAssembleia,
    TipoMateriaCongresso,
    Voto,
)
from votacao.motor import MotorApuracao
from votacao.regras.assembleia import RegraAssembleia
from votacao.regras.base import RegraDeVotacao
from votacao.regras.ca import RegraCA
from votacao.regras.congresso import RegraCongresso

__version__ = "0.1.0"

__all__ = [
    "HASH_GENESE",
    "CasaLegislativa",
    "LogDeAuditoria",
    "MotorApuracao",
    "RegistroAuditoria",
    "RegraAssembleia",
    "RegraCA",
    "RegraCongresso",
    "RegraDeVotacao",
    "ResultadoApuracao",
    "ResultadoVerificacao",
    "StatusResultado",
    "TipoDecisaoAssembleia",
    "TipoEvento",
    "TipoMateriaCongresso",
    "Voto",
    "__version__",
]

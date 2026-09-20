"""Sistema de votação digital com motor de regras extensível."""

from votacao.auditoria import (
    HASH_GENESE,
    LogDeAuditoria,
    RegistroAuditoria,
    ResultadoVerificacao,
    TipoEvento,
)
from votacao.dados.banco_sql import BancoDadosSQL
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
from votacao.sessao import (
    EstadoSessao,
    SessaoVotacao,
    TransicaoInvalidaError,
    VotoRecusadoError,
)
from votacao.tramitacao import (
    RegistroTramitacao,
    StatusTramitacao,
    TramitacaoInvalidaError,
    TramitacaoLegislativa,
)

__version__ = "0.1.0"

__all__ = [
    "HASH_GENESE",
    "AptidaoVoto",
    "BancoDadosMock",
    "BancoDadosSQL",
    "CasaLegislativa",
    "ElegibilidadeCandidato",
    "EstadoSessao",
    "LogDeAuditoria",
    "MotorApuracao",
    "RegistroAuditoria",
    "RegistroTramitacao",
    "RegraAssembleia",
    "RegraCA",
    "RegraCongresso",
    "RegraDeVotacao",
    "ResultadoApuracao",
    "ResultadoVerificacao",
    "ServicoElegibilidade",
    "SessaoVotacao",
    "StatusResultado",
    "StatusTramitacao",
    "TipoDecisaoAssembleia",
    "TipoEvento",
    "TipoMateriaCongresso",
    "TramitacaoInvalidaError",
    "TramitacaoLegislativa",
    "TransicaoInvalidaError",
    "Usuario",
    "ValidadorElegibilidadeAssembleia",
    "ValidadorElegibilidadeCA",
    "ValidadorElegibilidadeCongresso",
    "Voto",
    "VotoRecusadoError",
    "__version__",
]

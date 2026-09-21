"""Módulo de dados mockados e repositórios para o sistema de votação."""

from votacao.dados.assembleia import (
    Acionista,
    CandidatoConselho,
    Procuracao,
    Procurador,
    RepositorioAssembleia,
)
from votacao.dados.banco_sql import BancoDadosSQL
from votacao.dados.base import RepositorioBase
from votacao.dados.ca import ChapaCA, Discente, RepositorioCA
from votacao.dados.congresso import (
    MateriaLegislativa,
    Parlamentar,
    RepositorioCongresso,
)
from votacao.dados.seeds import (
    BancoDadosMock,
    carregar_dados_padrao_assembleia,
    carregar_dados_padrao_ca,
    carregar_dados_padrao_congresso,
)

__all__ = [
    "Acionista",
    "BancoDadosMock",
    "BancoDadosSQL",
    "CandidatoConselho",
    "ChapaCA",
    "Discente",
    "MateriaLegislativa",
    "Parlamentar",
    "Procuracao",
    "Procurador",
    "RepositorioAssembleia",
    "RepositorioBase",
    "RepositorioCA",
    "RepositorioCongresso",
    "carregar_dados_padrao_assembleia",
    "carregar_dados_padrao_ca",
    "carregar_dados_padrao_congresso",
]

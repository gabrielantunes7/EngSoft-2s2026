"""Módulo de dados mockados e repositórios para o sistema de votação."""

from votacao.dados.assembleia import (
    Acionista,
    CandidatoConselho,
    Procuracao,
    RepositorioAssembleia,
)
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
    "CandidatoConselho",
    "ChapaCA",
    "Discente",
    "MateriaLegislativa",
    "Parlamentar",
    "Procuracao",
    "RepositorioAssembleia",
    "RepositorioBase",
    "RepositorioCA",
    "RepositorioCongresso",
    "carregar_dados_padrao_assembleia",
    "carregar_dados_padrao_ca",
    "carregar_dados_padrao_congresso",
]

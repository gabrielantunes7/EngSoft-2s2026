"""Fábrica concreta para o contexto de Congresso Nacional."""

from typing import Any

from votacao.dados.congresso import RepositorioCongresso
from votacao.dados.seeds import carregar_dados_padrao_congresso
from votacao.elegibilidade.validador_congresso import (
    ValidadorElegibilidadeCongresso,
)
from votacao.fabricas.base import FabricaContextoVotacao
from votacao.modelos import CasaLegislativa, TipoMateriaCongresso
from votacao.regras.congresso import RegraCongresso
from votacao.sessao import SessaoVotacao


class FabricaCongresso(FabricaContextoVotacao):
    """Fábrica concreta para família de componentes do Congresso Nacional."""

    @property
    def contexto(self) -> str:
        return "CONGRESSO"

    def criar_regra(
        self,
        materia: TipoMateriaCongresso = TipoMateriaCongresso.LEI_ORDINARIA,
        casa: CasaLegislativa = CasaLegislativa.CAMARA,
        **kwargs: Any,
    ) -> RegraCongresso:
        """Cria uma RegraCongresso configurada."""
        return RegraCongresso(materia=materia, casa=casa)

    def criar_validador(self, **kwargs: Any) -> ValidadorElegibilidadeCongresso:
        """Cria o ValidadorElegibilidadeCongresso."""
        return ValidadorElegibilidadeCongresso()

    def criar_repositorio(self, popular: bool = True, **kwargs: Any) -> RepositorioCongresso:
        """Cria o RepositorioCongresso, opcionalmente populado com dados padrão."""
        repo = RepositorioCongresso()
        if popular:
            carregar_dados_padrao_congresso(repo)
        return repo

    def criar_sessao(
        self,
        id_sessao: str,
        total_aptos: int = 0,
        materia: TipoMateriaCongresso = TipoMateriaCongresso.LEI_ORDINARIA,
        casa: CasaLegislativa = CasaLegislativa.CAMARA,
        **kwargs: Any,
    ) -> SessaoVotacao:
        """Cria uma SessaoVotacao com RegraCongresso associada."""
        regra = kwargs.get("regra")
        if regra is None:
            regra = self.criar_regra(materia=materia, casa=casa)
        aptos = total_aptos if total_aptos > 0 else regra.total_membros
        return SessaoVotacao(
            id_sessao=id_sessao,
            regra=regra,
            total_aptos=aptos,
            log=kwargs.get("log"),
            relogio=kwargs.get("relogio"),
        )

"""Fábrica concreta para o contexto de Centro Acadêmico (CA)."""

from typing import Any

from votacao.dados.ca import RepositorioCA
from votacao.dados.seeds import carregar_dados_padrao_ca
from votacao.elegibilidade.validador_ca import ValidadorElegibilidadeCA
from votacao.fabricas.base import FabricaContextoVotacao
from votacao.regras.ca import RegraCA
from votacao.sessao import SessaoVotacao


class FabricaCA(FabricaContextoVotacao):
    """Fábrica concreta para família de componentes de eleição de Centro Acadêmico."""

    @property
    def contexto(self) -> str:
        return "CA"

    def criar_regra(
        self,
        quorum_minimo_votantes: int = 0,
        percentual_quorum_minimo: float = 0.0,
        **kwargs: Any,
    ) -> RegraCA:
        """Cria uma RegraCA configurada."""
        return RegraCA(
            quorum_minimo_votantes=quorum_minimo_votantes,
            percentual_quorum_minimo=percentual_quorum_minimo,
        )

    def criar_validador(self, **kwargs: Any) -> ValidadorElegibilidadeCA:
        """Cria o ValidadorElegibilidadeCA."""
        return ValidadorElegibilidadeCA()

    def criar_repositorio(self, popular: bool = True, **kwargs: Any) -> RepositorioCA:
        """Cria o RepositorioCA, opcionalmente populado com dados padrão."""
        repo = RepositorioCA()
        if popular:
            carregar_dados_padrao_ca(repo)
        return repo

    def criar_sessao(
        self,
        id_sessao: str,
        total_aptos: int = 0,
        quorum_minimo_votantes: int = 0,
        percentual_quorum_minimo: float = 0.0,
        **kwargs: Any,
    ) -> SessaoVotacao:
        """Cria uma SessaoVotacao com RegraCA associada."""
        regra = kwargs.get("regra")
        if regra is None:
            regra = self.criar_regra(
                quorum_minimo_votantes=quorum_minimo_votantes,
                percentual_quorum_minimo=percentual_quorum_minimo,
            )
        return SessaoVotacao(
            id_sessao=id_sessao,
            regra=regra,
            total_aptos=total_aptos,
            log=kwargs.get("log"),
            relogio=kwargs.get("relogio"),
        )

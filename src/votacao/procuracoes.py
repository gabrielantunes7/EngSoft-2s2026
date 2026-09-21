"""Gestão de procurações de voto em assembleias de acionistas."""

from dataclasses import replace
from datetime import UTC, datetime

from votacao.dados.assembleia import Acionista, Procuracao, Procurador, RepositorioAssembleia


class ProcuracaoInvalidaError(ValueError):
    """Procuração que não pode ser cadastrada ou revogada."""


class ServicoProcuracao:
    """Cadastro e revogação de procurações, com as travas de validade do instrumento.

    Um outorgante tem no máximo uma procuração vigente por vez: para constituir um novo
    procurador, a procuração anterior precisa ser revogada (ou ter expirado).

    Attributes:
        repo: Repositório da assembleia onde acionistas, procuradores e procurações vivem.
    """

    def __init__(self, repo: RepositorioAssembleia) -> None:
        self.repo = repo

    def cadastrar(
        self,
        outorgante_id: str,
        procurador_id: str,
        data_expiracao: datetime | None = None,
        momento: datetime | None = None,
    ) -> Procuracao:
        """Constitui uma procuração do acionista outorgante ao procurador credenciado.

        Args:
            outorgante_id: Acionista que transfere o poder de voto.
            procurador_id: Procurador que passa a exercê-lo.
            data_expiracao: Limite de validade do instrumento; None não impõe limite.
            momento: Instante de referência do cadastro (padrão: agora, em UTC).

        Returns:
            A procuração registrada, vigente a partir de agora.

        Raises:
            ProcuracaoInvalidaError: Se o outorgante não puder delegar, o procurador não
                estiver credenciado, ambos forem a mesma pessoa, a expiração não estiver
                no futuro ou o outorgante já tiver uma procuração vigente.
        """
        outorgante_id = outorgante_id.strip()
        procurador_id = procurador_id.strip()
        referencia = momento or datetime.now(UTC)

        if outorgante_id == procurador_id:
            msg = f"O acionista '{outorgante_id}' não pode outorgar procuração a si mesmo."
            raise ProcuracaoInvalidaError(msg)

        self._exigir_outorgante_habilitado(outorgante_id)
        self._exigir_procurador_credenciado(procurador_id)

        procuracao = Procuracao(
            outorgante_id=outorgante_id,
            procurador_id=procurador_id,
            data_expiracao=data_expiracao,
        )
        if not procuracao.esta_vigente(referencia):
            msg = (
                f"A expiração da procuração ({data_expiracao.isoformat()}) precisa estar "
                f"no futuro em relação a {referencia.isoformat()}."
            )
            raise ProcuracaoInvalidaError(msg)

        vigente = self.obter_vigente(outorgante_id, referencia)
        if vigente is not None:
            msg = (
                f"O acionista '{outorgante_id}' já possui procuração vigente outorgada ao "
                f"procurador '{vigente.procurador_id}'; revogue-a antes de constituir outra."
            )
            raise ProcuracaoInvalidaError(msg)

        self.repo.adicionar_procuracao(procuracao)
        return procuracao

    def revogar(self, outorgante_id: str, procurador_id: str) -> Procuracao:
        """Revoga a procuração, devolvendo ao outorgante o direito de votar diretamente.

        Raises:
            ProcuracaoInvalidaError: Se a procuração não existir ou já estiver revogada.
        """
        procuracao = self.repo.obter_procuracao(outorgante_id, procurador_id)
        if procuracao is None:
            msg = (
                f"Não há procuração do acionista '{outorgante_id.strip()}' "
                f"ao procurador '{procurador_id.strip()}'."
            )
            raise ProcuracaoInvalidaError(msg)
        if not procuracao.ativa:
            msg = (
                f"A procuração do acionista '{outorgante_id.strip()}' "
                f"ao procurador '{procurador_id.strip()}' já foi revogada."
            )
            raise ProcuracaoInvalidaError(msg)

        revogada = replace(procuracao, ativa=False)
        self.repo.adicionar_procuracao(revogada)
        return revogada

    def obter_vigente(
        self, outorgante_id: str, momento: datetime | None = None
    ) -> Procuracao | None:
        """Devolve a procuração vigente do outorgante no instante dado, se houver."""
        return self.repo.obter_procuracao_vigente(outorgante_id, momento)

    def _exigir_outorgante_habilitado(self, outorgante_id: str) -> Acionista:
        acionista = self.repo.obter_acionista(outorgante_id)
        if acionista is None:
            msg = f"Acionista '{outorgante_id}' não encontrado no livro societário."
            raise ProcuracaoInvalidaError(msg)
        if not acionista.ativo:
            msg = f"Acionista '{acionista.nome}' (ID {outorgante_id}) está com cadastro inativo."
            raise ProcuracaoInvalidaError(msg)
        if acionista.bloqueado:
            msg = (
                f"Acionista '{acionista.nome}' (ID {outorgante_id}) possui bloqueio "
                "no exercício do voto e não pode delegá-lo."
            )
            raise ProcuracaoInvalidaError(msg)
        if acionista.acoes_ordinarias <= 0:
            msg = (
                f"Acionista '{acionista.nome}' (ID {outorgante_id}) não possui ações "
                "ordinárias com direito a voto para delegar."
            )
            raise ProcuracaoInvalidaError(msg)
        return acionista

    def _exigir_procurador_credenciado(self, procurador_id: str) -> Procurador:
        procurador = self.repo.obter_procurador(procurador_id)
        if procurador is None:
            msg = f"Procurador '{procurador_id}' não está cadastrado."
            raise ProcuracaoInvalidaError(msg)
        if not procurador.credenciado:
            msg = f"Procurador '{procurador.nome}' (ID {procurador_id}) não está credenciado."
            raise ProcuracaoInvalidaError(msg)
        if not procurador.ativo:
            msg = f"Procurador '{procurador.nome}' (ID {procurador_id}) está com cadastro inativo."
            raise ProcuracaoInvalidaError(msg)
        return procurador

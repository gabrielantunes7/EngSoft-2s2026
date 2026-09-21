"""Gestão de procurações de voto em assembleias de acionistas."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from votacao.dados.assembleia import Acionista, Procuracao, Procurador, RepositorioAssembleia
from votacao.elegibilidade.validador_assembleia import ValidadorElegibilidadeAssembleia


class ProcuracaoInvalidaError(ValueError):
    """Procuração que não pode ser cadastrada ou revogada."""


@dataclass(frozen=True)
class PoderDeVoto:
    """Poder de voto que um procurador exerce em uma única emissão de voto.

    Attributes:
        procurador_id: Procurador que emite o voto.
        peso_proprio: Ações ordinárias do próprio procurador, quando ele é acionista apto
            e não delegou o seu voto a outra pessoa.
        peso_delegado: Soma das ações dos outorgantes aptos com procuração vigente.
        outorgantes: Acionistas representados, em ordem alfabética.
    """

    procurador_id: str
    peso_proprio: int = 0
    peso_delegado: int = 0
    outorgantes: tuple[str, ...] = ()

    @property
    def peso_total(self) -> int:
        """Peso consolidado do voto: o próprio mais o delegado."""
        return self.peso_proprio + self.peso_delegado


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

    def calcular_poder_de_voto(
        self, procurador_id: str, momento: datetime | None = None
    ) -> PoderDeVoto:
        """Consolida o poder de voto que o procurador exerce no instante dado.

        Soma as ações do próprio procurador (se for acionista apto e não tiver delegado o
        seu voto) às de cada outorgante com procuração vigente que ainda esteja apto a
        votar. Outorgantes que ficaram bloqueados ou inativos depois do cadastro não
        entram na soma.
        """
        procurador_id = procurador_id.strip()

        como_titular = ValidadorElegibilidadeAssembleia.validar_eleitor(
            procurador_id, self.repo, momento=momento
        )
        peso_proprio = como_titular.peso_voto if como_titular.apto else 0

        peso_delegado = 0
        outorgantes: list[str] = []
        for procuracao in self.repo.listar_procuracoes_do_procurador(procurador_id):
            aptidao = ValidadorElegibilidadeAssembleia.validar_eleitor(
                procuracao.outorgante_id,
                self.repo,
                procurador_id=procurador_id,
                momento=momento,
            )
            if aptidao.apto:
                peso_delegado += aptidao.peso_voto
                outorgantes.append(procuracao.outorgante_id)

        return PoderDeVoto(
            procurador_id=procurador_id,
            peso_proprio=peso_proprio,
            peso_delegado=peso_delegado,
            outorgantes=tuple(sorted(outorgantes)),
        )

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

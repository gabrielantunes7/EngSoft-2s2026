"""Ciclo de vida de uma sessão de votação."""

from enum import StrEnum

from votacao.modelos import ResultadoApuracao, Voto
from votacao.motor import MotorApuracao
from votacao.regras.base import RegraDeVotacao


class EstadoSessao(StrEnum):
    """Etapas do ciclo de vida de uma sessão, na ordem em que ocorrem."""

    CRIADA = "CRIADA"
    ABERTA = "ABERTA"
    EM_VOTACAO = "EM_VOTACAO"
    EM_APURACAO = "EM_APURACAO"
    ENCERRADA = "ENCERRADA"


class TransicaoInvalidaError(Exception):
    """Operação incompatível com o estado atual da sessão."""


class SessaoVotacao:
    """Sessão de votação controlada por uma máquina de estados.

    A sessão percorre CRIADA → ABERTA → EM_VOTACAO → EM_APURACAO → ENCERRADA, sempre
    nessa ordem e sem retorno. Votos só são aceitos em EM_VOTACAO, e a apuração só
    acontece depois que a urna foi fechada.

    Attributes:
        id_sessao: Identificador da sessão.
        regra: Estratégia de quórum e apuração aplicada aos votos.
        total_aptos: Total de eleitores aptos ou de capital social votante.
    """

    def __init__(self, id_sessao: str, regra: RegraDeVotacao, total_aptos: int = 0) -> None:
        """Cria a sessão no estado CRIADA.

        Args:
            id_sessao: Identificador da sessão.
            regra: Estratégia de votação que implementa RegraDeVotacao.
            total_aptos: Total de aptos (CA/Congresso) ou capital social (Assembleia).

        Raises:
            ValueError: Se o identificador for vazio ou o total de aptos for negativo.
            TypeError: Se a regra não implementar RegraDeVotacao.
        """
        if not id_sessao.strip():
            msg = "O identificador da sessão não pode ser vazio."
            raise ValueError(msg)
        if not isinstance(regra, RegraDeVotacao):
            msg = "A regra da sessão deve implementar a interface RegraDeVotacao."
            raise TypeError(msg)
        if total_aptos < 0:
            msg = "O total de aptos não pode ser negativo."
            raise ValueError(msg)

        self.id_sessao = id_sessao
        self.regra = regra
        self.total_aptos = total_aptos
        self._estado = EstadoSessao.CRIADA
        self._votos: list[Voto] = []
        self._resultado: ResultadoApuracao | None = None

    @property
    def estado(self) -> EstadoSessao:
        """Etapa atual da sessão."""
        return self._estado

    @property
    def votos(self) -> tuple[Voto, ...]:
        """Votos aceitos, na ordem em que foram registrados."""
        return tuple(self._votos)

    @property
    def resultado(self) -> ResultadoApuracao | None:
        """Resultado da apuração, ou None enquanto a sessão não for apurada."""
        return self._resultado

    def abrir(self) -> None:
        """Instala a sessão (CRIADA → ABERTA)."""
        self._transitar(de=EstadoSessao.CRIADA, para=EstadoSessao.ABERTA)

    def liberar_votacao(self) -> None:
        """Abre a urna para receber votos (ABERTA → EM_VOTACAO)."""
        self._transitar(de=EstadoSessao.ABERTA, para=EstadoSessao.EM_VOTACAO)

    def encerrar_votacao(self) -> None:
        """Fecha a urna (EM_VOTACAO → EM_APURACAO)."""
        self._transitar(de=EstadoSessao.EM_VOTACAO, para=EstadoSessao.EM_APURACAO)

    def registrar_voto(self, voto: Voto) -> None:
        """Aceita um voto, somente enquanto a urna estiver aberta.

        Args:
            voto: Voto já autorizado pelo serviço de elegibilidade.

        Raises:
            TransicaoInvalidaError: Se a sessão não estiver em EM_VOTACAO.
        """
        self._exigir_estado(EstadoSessao.EM_VOTACAO, operacao="registrar voto")
        self._votos.append(voto)

    def apurar(self) -> ResultadoApuracao:
        """Apura os votos com a regra da sessão (EM_APURACAO → ENCERRADA).

        Returns:
            Resultado consolidado, que também fica disponível em `resultado`.

        Raises:
            TransicaoInvalidaError: Se a urna ainda não foi fechada ou a sessão já foi apurada.
        """
        self._exigir_estado(EstadoSessao.EM_APURACAO, operacao="apurar")
        self._resultado = MotorApuracao.apurar(
            votos=self._votos,
            regra=self.regra,
            total_aptos_ou_capital=self.total_aptos,
        )
        self._estado = EstadoSessao.ENCERRADA
        return self._resultado

    def _transitar(self, de: EstadoSessao, para: EstadoSessao) -> None:
        self._exigir_estado(de, operacao=f"passar a {para.value}")
        self._estado = para

    def _exigir_estado(self, esperado: EstadoSessao, operacao: str) -> None:
        if self._estado != esperado:
            msg = (
                f"Não é possível {operacao} na sessão '{self.id_sessao}': "
                f"estado atual é {self._estado.value}, esperado {esperado.value}."
            )
            raise TransicaoInvalidaError(msg)

"""Ciclo de vida de uma sessão de votação."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from votacao.auditoria import LogDeAuditoria, TipoEvento
from votacao.modelos import ResultadoApuracao, Voto
from votacao.motor import MotorApuracao
from votacao.observadores import ObservadorAuditoria, ObservadorSessao
from votacao.regras.base import RegraDeVotacao

# Separador que o ServicoElegibilidade usa para marcar voto por procuração:
# "<outorgante>#rep:<procurador>". Para fins de duplicata, a identidade do
# voto é a do outorgante, votando ele próprio ou por procurador. Já o voto consolidado
# de um procurador lista em `Voto.representados` todos os acionistas cujo capital ele
# carrega (inclusive o próprio procurador, se as suas ações entram no voto): a
# identidade é esse conjunto, e não o `eleitor_id` de quem emite o voto.
SEPARADOR_PROCURACAO = "#rep:"


class EstadoSessao(StrEnum):
    """Etapas do ciclo de vida de uma sessão, na ordem em que ocorrem."""

    CRIADA = "CRIADA"
    ABERTA = "ABERTA"
    EM_VOTACAO = "EM_VOTACAO"
    EM_APURACAO = "EM_APURACAO"
    ENCERRADA = "ENCERRADA"


class TransicaoInvalidaError(Exception):
    """Operação incompatível com o estado atual da sessão."""


class VotoRecusadoError(Exception):
    """Voto inadmissível: o eleitor já votou ou a janela de votação não está aberta."""


class SessaoVotacao:
    """Sessão de votação controlada por uma máquina de estados e padrão Observer.

    A sessão percorre CRIADA → ABERTA → EM_VOTACAO → EM_APURACAO → ENCERRADA, sempre
    nessa ordem e sem retorno. Votos só são aceitos em EM_VOTACAO, dentro da janela
    de votação quando ela é definida, e no máximo um por eleitor. A apuração só
    acontece depois que a urna foi fechada.

    A sessão atua como publicador (Subject) no padrão Observer: sempre que transita de
    estado ou admite um voto, notifica os observadores registrados (como o
    `ObservadorAuditoria`), permitindo desacoplar a auditoria, notificações e métricas.

    Attributes:
        id_sessao: Identificador da sessão.
        regra: Estratégia de quórum e apuração aplicada aos votos.
        total_aptos: Total de eleitores aptos ou de capital social votante.
    """

    def __init__(
        self,
        id_sessao: str,
        regra: RegraDeVotacao,
        total_aptos: int = 0,
        log: LogDeAuditoria | None = None,
        observadores: Sequence[ObservadorSessao] | None = None,
        relogio: Callable[[], datetime] | None = None,
    ) -> None:
        """Cria a sessão no estado CRIADA.

        Args:
            id_sessao: Identificador da sessão.
            regra: Estratégia de votação que implementa RegraDeVotacao.
            total_aptos: Total de aptos (CA/Congresso) ou capital social (Assembleia).
            log: Log de auditoria opcional. Quando informado, registra automaticamente um
                ObservadorAuditoria para manter a retrocompatibilidade.
            observadores: Lista opcional de observadores que acompanharão a sessão.
            relogio: Função que devolve o instante corrente, usada para aplicar a
                janela de votação. O padrão é a hora corrente em UTC; injetar outra
                torna a trava temporal determinística nos testes.

        Raises:
            ValueError: Se o identificador for vazio, o total de aptos for negativo ou
                o log pertencer a outra votação.
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
        if log is not None and log.id_votacao != id_sessao:
            msg = (
                f"O log de auditoria pertence à votação '{log.id_votacao}', "
                f"não à sessão '{id_sessao}'."
            )
            raise ValueError(msg)

        self.id_sessao = id_sessao
        self.regra = regra
        self.total_aptos = total_aptos
        self._observadores: list[ObservadorSessao] = []
        self._log = log

        if log is not None:
            self.adicionar_observador(ObservadorAuditoria(log))

        if observadores is not None:
            for obs in observadores:
                self.adicionar_observador(obs)

        self._relogio = relogio if relogio is not None else lambda: datetime.now(UTC)
        self._estado = EstadoSessao.CRIADA
        self._inicio_votacao: datetime | None = None
        self._fim_votacao: datetime | None = None
        self._eleitores: set[str] = set()
        self._votos: list[Voto] = []
        self._resultado: ResultadoApuracao | None = None

    @property
    def log(self) -> LogDeAuditoria | None:
        """Log de auditoria configurado na sessão, se houver."""
        return self._log

    @property
    def observadores(self) -> tuple[ObservadorSessao, ...]:
        """Observadores atualmente registrados na sessão."""
        return tuple(self._observadores)

    def adicionar_observador(self, observador: ObservadorSessao) -> None:
        """Registra um observador para acompanhar eventos e votos da sessão.

        Args:
            observador: Instância de ObservadorSessao.

        Raises:
            TypeError: Se o objeto não implementar ObservadorSessao.
        """
        if not isinstance(observador, ObservadorSessao):
            msg = "O observador deve implementar a interface ObservadorSessao."
            raise TypeError(msg)

        if observador not in self._observadores:
            self._observadores.append(observador)

    def remover_observador(self, observador: ObservadorSessao) -> bool:
        """Remove um observador registrado da sessão.

        Returns:
            True se o observador foi removido, False caso não estivesse presente.
        """
        if observador in self._observadores:
            self._observadores.remove(observador)
            if (
                self._log is not None
                and isinstance(observador, ObservadorAuditoria)
                and observador.log is self._log
            ):
                self._log = None
            return True
        return False

    @property
    def estado(self) -> EstadoSessao:
        """Etapa atual da sessão."""
        return self._estado

    @property
    def inicio_votacao(self) -> datetime | None:
        """Instante a partir do qual a urna aceita votos, ou None se não houver limite."""
        return self._inicio_votacao

    @property
    def fim_votacao(self) -> datetime | None:
        """Instante até o qual a urna aceita votos, ou None se não houver limite."""
        return self._fim_votacao

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

    def liberar_votacao(
        self,
        inicio: datetime | None = None,
        fim: datetime | None = None,
    ) -> None:
        """Abre a urna para receber votos (ABERTA → EM_VOTACAO).

        Args:
            inicio: Instante a partir do qual votos são aceitos. None libera de imediato.
            fim: Instante até o qual votos são aceitos. None não impõe limite.

        Raises:
            ValueError: Se o início for posterior ao fim.
            TransicaoInvalidaError: Se a sessão não estiver em ABERTA.
        """
        self._exigir_estado(EstadoSessao.ABERTA, operacao="passar a EM_VOTACAO")
        if inicio is not None and fim is not None and inicio > fim:
            msg = "O início da janela de votação não pode ser posterior ao fim."
            raise ValueError(msg)

        self._inicio_votacao = inicio
        self._fim_votacao = fim
        self._transitar(
            de=EstadoSessao.ABERTA,
            para=EstadoSessao.EM_VOTACAO,
            evento=TipoEvento.VOTACAO_ABERTA,
            dados={
                "inicio": inicio.isoformat() if inicio is not None else None,
                "fim": fim.isoformat() if fim is not None else None,
                "total_aptos": self.total_aptos,
            },
        )

    def encerrar_votacao(self) -> None:
        """Fecha a urna (EM_VOTACAO → EM_APURACAO)."""
        self._transitar(
            de=EstadoSessao.EM_VOTACAO,
            para=EstadoSessao.EM_APURACAO,
            evento=TipoEvento.VOTACAO_ENCERRADA,
            dados={"total_votos": len(self._votos)},
        )

    def registrar_voto(self, voto: Voto) -> str | None:
        """Aceita um voto, somente com a urna aberta, dentro da janela e uma vez por eleitor.

        Args:
            voto: Voto já autorizado pelo serviço de elegibilidade.

        Returns:
            O protocolo do registro de auditoria gerado pelo observador de auditoria,
            ou None se a sessão não possui observador de auditoria.

        Raises:
            TransicaoInvalidaError: Se a sessão não estiver em EM_VOTACAO.
            VotoRecusadoError: Se o relógio estiver fora da janela de votação ou se o
                eleitor — diretamente, por procurador ou representado em voto consolidado —
                já tiver votado nesta sessão.
        """
        self._exigir_estado(EstadoSessao.EM_VOTACAO, operacao="registrar voto")
        self._exigir_dentro_da_janela()

        identidades = self._identidades(voto)
        ja_votaram = sorted(identidades & self._eleitores)
        if ja_votaram:
            msg = f"O eleitor '{ja_votaram[0]}' já votou na sessão '{self.id_sessao}'."
            raise VotoRecusadoError(msg)

        self._eleitores.update(identidades)
        self._votos.append(voto)

        protocolo: str | None = None
        for obs in self._observadores:
            comprovante = obs.ao_registrar_voto(self, voto)
            if comprovante is not None and protocolo is None:
                protocolo = comprovante

        return protocolo

    def apurar(self) -> ResultadoApuracao:
        """Apura os votos com a regra da sessão (EM_APURACAO → ENCERRADA).

        Returns:
            Resultado consolidado, que também fica disponível em `resultado`.

        Raises:
            TransicaoInvalidaError: Se a urna ainda não foi fechada ou a sessão já foi apurada.
        """
        self._exigir_estado(EstadoSessao.EM_APURACAO, operacao="apurar")
        resultado = MotorApuracao.apurar(
            votos=self._votos,
            regra=self.regra,
            total_aptos_ou_capital=self.total_aptos,
        )
        self._resultado = resultado
        self._transitar(
            de=EstadoSessao.EM_APURACAO,
            para=EstadoSessao.ENCERRADA,
            evento=TipoEvento.RESULTADO_PROCLAMADO,
            dados={
                "status": resultado.status.value,
                "vencedor_ou_decisao": resultado.vencedor_ou_decisao,
                "quorum_atingido": resultado.quorum_atingido,
                "total_votantes": resultado.total_votantes,
                "total_peso_apurado": resultado.total_peso_apurado,
                "contagem_por_opcao": dict(resultado.contagem_por_opcao),
            },
        )
        return resultado

    def _transitar(
        self,
        de: EstadoSessao,
        para: EstadoSessao,
        evento: TipoEvento | None = None,
        dados: dict[str, Any] | None = None,
    ) -> None:
        self._exigir_estado(de, operacao=f"passar a {para.value}")
        self._estado = para
        for obs in self._observadores:
            obs.ao_mudar_estado(
                sessao=self,
                estado_anterior=de,
                novo_estado=para,
                evento=evento,
                dados=dados or {},
            )

    def _exigir_estado(self, esperado: EstadoSessao, operacao: str) -> None:
        if self._estado != esperado:
            msg = (
                f"Não é possível {operacao} na sessão '{self.id_sessao}': "
                f"estado atual é {self._estado.value}, esperado {esperado.value}."
            )
            raise TransicaoInvalidaError(msg)

    def _exigir_dentro_da_janela(self) -> None:
        if self._inicio_votacao is None and self._fim_votacao is None:
            return

        agora = self._relogio()
        if self._inicio_votacao is not None and agora < self._inicio_votacao:
            msg = (
                f"A votação da sessão '{self.id_sessao}' só começa em "
                f"{self._inicio_votacao.isoformat()}."
            )
            raise VotoRecusadoError(msg)
        if self._fim_votacao is not None and agora > self._fim_votacao:
            msg = (
                f"A votação da sessão '{self.id_sessao}' terminou em "
                f"{self._fim_votacao.isoformat()}."
            )
            raise VotoRecusadoError(msg)

    @staticmethod
    def _identidades(voto: Voto) -> set[str]:
        """Eleitores cujo capital o voto consome: os representados ou, sem eles, o titular."""
        if voto.representados:
            return set(voto.representados)
        return {voto.eleitor_id.split(SEPARADOR_PROCURACAO, 1)[0]}

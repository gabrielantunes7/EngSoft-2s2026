"""Padrão Observer para o ciclo de vida e eventos de sessões de votação."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from votacao.auditoria import LogDeAuditoria, TipoEvento
from votacao.modelos import Voto

if TYPE_CHECKING:
    from votacao.sessao import EstadoSessao, SessaoVotacao


class ObservadorSessao(ABC):
    """Interface abstrata (Observer) para acompanhamento dos eventos de uma sessão."""

    @abstractmethod
    def ao_mudar_estado(
        self,
        sessao: "SessaoVotacao",
        estado_anterior: "EstadoSessao",
        novo_estado: "EstadoSessao",
        evento: TipoEvento | None = None,
        dados: Mapping[str, Any] | None = None,
    ) -> None:
        """Notificado quando a sessão transita de estado ou registra um evento de ciclo.

        Args:
            sessao: Instância da sessão de votação que disparou a notificação.
            estado_anterior: Estado em que a sessão se encontrava antes da transição.
            novo_estado: Novo estado da sessão após a transição.
            evento: Tipo do evento do ciclo de vida associado, se houver.
            dados: Informações complementares e metadados contextuais do evento.
        """
        raise NotImplementedError

    @abstractmethod
    def ao_registrar_voto(
        self,
        sessao: "SessaoVotacao",
        voto: Voto,
    ) -> str | None:
        """Notificado quando um voto válido é admitido na urna da sessão.

        Args:
            sessao: Instância da sessão onde o voto foi registrado.
            voto: Voto computado.

        Returns:
            Opcionalmente, uma chave, protocolo ou hash (ex.: pelo observador de auditoria).
        """
        raise NotImplementedError


class ObservadorAuditoria(ObservadorSessao):
    """Observador que sincroniza eventos e votos com a cadeia imutável de auditoria.

    Attributes:
        log: Instância de LogDeAuditoria que recebe os registros criptográficos.
    """

    def __init__(self, log: LogDeAuditoria) -> None:
        if not isinstance(log, LogDeAuditoria):
            msg = "O log de auditoria deve ser uma instância de LogDeAuditoria."
            raise TypeError(msg)
        self.log = log

    def ao_mudar_estado(
        self,
        sessao: "SessaoVotacao",
        estado_anterior: "EstadoSessao",
        novo_estado: "EstadoSessao",
        evento: TipoEvento | None = None,
        dados: Mapping[str, Any] | None = None,
    ) -> None:
        """Grava na cadeia de auditoria os eventos com TipoEvento definido."""
        if evento is not None:
            self.log.registrar(evento, dict(dados or {}))

    def ao_registrar_voto(
        self,
        sessao: "SessaoVotacao",
        voto: Voto,
    ) -> str:
        """Registra o voto na cadeia e devolve o hash resultante como comprovante."""
        registro = self.log.registrar_voto(voto)
        return registro.hash


class ObservadorRegistroMemoria(ObservadorSessao):
    """Observador espião em memória para testes, monitoramento e telemetria.

    Attributes:
        eventos: Lista cronológica de transições e eventos recebidos.
        votos: Lista cronológica de votos registrados.
    """

    def __init__(self) -> None:
        self.eventos: list[dict[str, Any]] = []
        self.votos: list[Voto] = []

    def ao_mudar_estado(
        self,
        sessao: "SessaoVotacao",
        estado_anterior: "EstadoSessao",
        novo_estado: "EstadoSessao",
        evento: TipoEvento | None = None,
        dados: Mapping[str, Any] | None = None,
    ) -> None:
        """Acumula o evento de estado em memória."""
        self.eventos.append(
            {
                "sessao_id": sessao.id_sessao,
                "estado_anterior": estado_anterior,
                "novo_estado": novo_estado,
                "evento": evento,
                "dados": dict(dados or {}),
            }
        )

    def ao_registrar_voto(
        self,
        sessao: "SessaoVotacao",
        voto: Voto,
    ) -> str | None:
        """Acumula o voto em memória."""
        self.votos.append(voto)
        return None


class ObservadorCallback(ObservadorSessao):
    """Observador flexível que executa callbacks funcionais injetados.

    Útil para integrações pontuais, emissão de métricas ou envio de notificações externas.
    """

    def __init__(
        self,
        quando_mudar_estado: Callable[..., Any] | None = None,
        quando_registrar_voto: Callable[[Voto], Any] | None = None,
    ) -> None:
        self.quando_mudar_estado = quando_mudar_estado
        self.quando_registrar_voto = quando_registrar_voto

    def ao_mudar_estado(
        self,
        sessao: "SessaoVotacao",
        estado_anterior: "EstadoSessao",
        novo_estado: "EstadoSessao",
        evento: TipoEvento | None = None,
        dados: Mapping[str, Any] | None = None,
    ) -> None:
        if self.quando_mudar_estado is not None:
            self.quando_mudar_estado(
                sessao=sessao,
                estado_anterior=estado_anterior,
                novo_estado=novo_estado,
                evento=evento,
                dados=dados or {},
            )

    def ao_registrar_voto(
        self,
        sessao: "SessaoVotacao",
        voto: Voto,
    ) -> str | None:
        if self.quando_registrar_voto is not None:
            self.quando_registrar_voto(voto)
        return None

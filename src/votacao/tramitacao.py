"""Tramitação de matérias legislativas entre as Casas do Congresso Nacional."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import ClassVar

from votacao.auditoria import LogDeAuditoria
from votacao.modelos import (
    CasaLegislativa,
    ResultadoApuracao,
    StatusResultado,
    TipoMateriaCongresso,
)
from votacao.regras.congresso import RegraCongresso
from votacao.sessao import EstadoSessao, SessaoVotacao


class StatusTramitacao(StrEnum):
    """Situação de uma matéria ao longo do rito legislativo."""

    EM_TRAMITACAO = "EM_TRAMITACAO"
    APROVADA = "APROVADA"
    REJEITADA = "REJEITADA"


class TramitacaoInvalidaError(Exception):
    """Operação incompatível com a situação da tramitação ou com a etapa corrente."""


@dataclass(frozen=True)
class RegistroTramitacao:
    """Resultado de uma sessão de votação no histórico da tramitação.

    Attributes:
        id_sessao: Identificador da sessão apurada.
        casa: Casa em que a sessão ocorreu.
        turno: Turno de votação a que a sessão correspondeu.
        resultado: Resultado apurado pela sessão.
        valida: False quando a sessão não atingiu o quórum de instalação e, por isso,
            não produziu decisão de mérito.
    """

    id_sessao: str
    casa: CasaLegislativa
    turno: int
    resultado: ResultadoApuracao
    valida: bool


class TramitacaoLegislativa:
    """Conduz uma matéria pela Casa iniciadora e pela Casa revisora, turno a turno.

    Cada turno é uma `SessaoVotacao` convocada por `nova_sessao`, já configurada com
    a `RegraCongresso` da matéria e da Casa corrente. Ao registrar o resultado de uma
    sessão encerrada, a tramitação avança para o próximo turno, para a Casa revisora
    ou para a conclusão, conforme o rito exigido pelo tipo de matéria.

    Attributes:
        materia_id: Identificador oficial da matéria (ex.: 'PEC-50/2026').
        tipo: Tipo da matéria, que determina o número de turnos por Casa.
        casa_iniciadora: Casa em que a matéria começa a tramitar.
    """

    TURNOS_POR_MATERIA: ClassVar[dict[TipoMateriaCongresso, int]] = {
        TipoMateriaCongresso.LEI_ORDINARIA: 1,
        TipoMateriaCongresso.LEI_COMPLEMENTAR: 1,
        TipoMateriaCongresso.PEC: 2,
    }

    def __init__(
        self,
        materia_id: str,
        tipo: TipoMateriaCongresso,
        casa_iniciadora: CasaLegislativa = CasaLegislativa.CAMARA,
    ) -> None:
        """Inicia a tramitação no primeiro turno da Casa iniciadora.

        Args:
            materia_id: Identificador oficial da matéria.
            tipo: Tipo da matéria legislativa.
            casa_iniciadora: Casa em que a matéria começa a tramitar.

        Raises:
            ValueError: Se o identificador da matéria for vazio.
        """
        if not materia_id.strip():
            msg = "O identificador da matéria não pode ser vazio."
            raise ValueError(msg)

        self.materia_id = materia_id
        self.tipo = tipo
        self.casa_iniciadora = casa_iniciadora
        self._casa_atual = casa_iniciadora
        self._turno_atual = 1
        self._status = StatusTramitacao.EM_TRAMITACAO
        self._historico: list[RegistroTramitacao] = []
        self._sessao_convocada: SessaoVotacao | None = None

    @property
    def status(self) -> StatusTramitacao:
        """Situação corrente da matéria."""
        return self._status

    @property
    def casa_atual(self) -> CasaLegislativa:
        """Casa em que a matéria se encontra."""
        return self._casa_atual

    @property
    def casa_revisora(self) -> CasaLegislativa:
        """Casa que revisa a matéria após a iniciadora."""
        if self.casa_iniciadora == CasaLegislativa.CAMARA:
            return CasaLegislativa.SENADO
        return CasaLegislativa.CAMARA

    @property
    def turno_atual(self) -> int:
        """Turno de votação corrente na Casa atual, a partir de 1."""
        return self._turno_atual

    @property
    def turnos_por_casa(self) -> int:
        """Quantidade de turnos que a matéria precisa vencer em cada Casa."""
        return self.TURNOS_POR_MATERIA[self.tipo]

    @property
    def historico(self) -> tuple[RegistroTramitacao, ...]:
        """Resultados registrados, na ordem em que as sessões foram apuradas."""
        return tuple(self._historico)

    @property
    def id_proxima_sessao(self) -> str:
        """Identificador que `nova_sessao` atribuirá à sessão da etapa corrente."""
        return f"{self.materia_id}-{self._casa_atual.value}-T{self._turno_atual}"

    def nova_sessao(
        self,
        log: LogDeAuditoria | None = None,
        relogio: Callable[[], datetime] | None = None,
    ) -> SessaoVotacao:
        """Convoca a sessão de votação da etapa corrente.

        Args:
            log: Log de auditoria da sessão. Precisa ter sido criado com
                `id_proxima_sessao` como identificador.
            relogio: Relógio injetável repassado à sessão.

        Returns:
            Sessão em CRIADA, com `RegraCongresso` da matéria e da Casa corrente e
            total de aptos igual ao número constitucional de membros da Casa.

        Raises:
            TramitacaoInvalidaError: Se a tramitação já foi concluída.
        """
        self._exigir_em_tramitacao(operacao="convocar sessão")

        regra = RegraCongresso(materia=self.tipo, casa=self._casa_atual)
        sessao = SessaoVotacao(
            self.id_proxima_sessao,
            regra,
            total_aptos=regra.total_membros,
            log=log,
            relogio=relogio,
        )
        self._sessao_convocada = sessao
        return sessao

    def registrar_resultado(self, sessao: SessaoVotacao) -> StatusTramitacao:
        """Incorpora o resultado da sessão da etapa corrente e avança o rito.

        Aprovação avança o turno; vencidos os turnos da Casa, passa à revisora;
        vencidas as duas Casas, a matéria fica APROVADA. Rejeição em qualquer etapa
        encerra a tramitação como REJEITADA. Quórum insuficiente não é decisão de
        mérito: a sessão entra no histórico como inválida e a etapa se mantém, de modo
        que uma nova sessão possa ser convocada.

        Args:
            sessao: Sessão convocada por `nova_sessao` para a etapa corrente, já
                apurada.

        Returns:
            Situação da matéria após o registro.

        Raises:
            TramitacaoInvalidaError: Se a tramitação já foi concluída, se a sessão não
                foi convocada por esta tramitação para a etapa corrente, se já foi
                registrada ou se ainda não foi apurada.
        """
        self._exigir_em_tramitacao(operacao="registrar resultado")

        if sessao is not self._sessao_convocada:
            msg = (
                f"A sessão '{sessao.id_sessao}' não é a sessão convocada para a etapa "
                f"corrente da matéria '{self.materia_id}' ({self.id_proxima_sessao}), "
                "ou já teve seu resultado registrado."
            )
            raise TramitacaoInvalidaError(msg)
        if sessao.estado != EstadoSessao.ENCERRADA or sessao.resultado is None:
            msg = (
                f"A sessão '{sessao.id_sessao}' ainda não foi apurada "
                f"(estado atual: {sessao.estado.value})."
            )
            raise TramitacaoInvalidaError(msg)

        resultado = sessao.resultado
        valida = resultado.status != StatusResultado.QUORUM_INSUFICIENTE
        self._historico.append(
            RegistroTramitacao(
                id_sessao=sessao.id_sessao,
                casa=self._casa_atual,
                turno=self._turno_atual,
                resultado=resultado,
                valida=valida,
            )
        )
        self._sessao_convocada = None

        if not valida:
            return self._status
        if resultado.status == StatusResultado.REJEITADO:
            self._status = StatusTramitacao.REJEITADA
            return self._status

        self._avancar()
        return self._status

    def _avancar(self) -> None:
        if self._turno_atual < self.turnos_por_casa:
            self._turno_atual += 1
        elif self._casa_atual == self.casa_iniciadora:
            self._casa_atual = self.casa_revisora
            self._turno_atual = 1
        else:
            self._status = StatusTramitacao.APROVADA

    def _exigir_em_tramitacao(self, operacao: str) -> None:
        if self._status != StatusTramitacao.EM_TRAMITACAO:
            msg = (
                f"Não é possível {operacao}: a matéria '{self.materia_id}' "
                f"já foi concluída com situação {self._status.value}."
            )
            raise TramitacaoInvalidaError(msg)

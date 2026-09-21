"""Ciclo de vida de uma sessão de votação."""

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from votacao.auditoria import LogDeAuditoria, TipoEvento
from votacao.modelos import ResultadoApuracao, Voto
from votacao.motor import MotorApuracao
from votacao.regras.base import RegraDeVotacao

# Separador que o ServicoElegibilidade usa para marcar voto por procuração:
# "<outorgante>#rep:<procurador>". Para fins de duplicata, a identidade do
# voto é a do outorgante, votando ele próprio ou por procurador.
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
    """Sessão de votação controlada por uma máquina de estados.

    A sessão percorre CRIADA → ABERTA → EM_VOTACAO → EM_APURACAO → ENCERRADA, sempre
    nessa ordem e sem retorno. Votos só são aceitos em EM_VOTACAO, dentro da janela
    de votação quando ela é definida, e no máximo um por eleitor. A apuração só
    acontece depois que a urna foi fechada.

    Quando a sessão recebe um `LogDeAuditoria`, cada transição e cada voto aceito
    geram um registro na cadeia, e o eleitor recebe o hash do seu registro como
    comprovante.

    Attributes:
        id_sessao: Identificador da sessão.
        regra: Estratégia de quórum e apuração aplicada aos votos.
        total_aptos: Total de eleitores aptos ou de capital social votante.
        log: Log de auditoria da sessão, ou None para uma sessão sem auditoria.
    """

    def __init__(
        self,
        id_sessao: str,
        regra: RegraDeVotacao,
        total_aptos: int = 0,
        log: LogDeAuditoria | None = None,
        relogio: Callable[[], datetime] | None = None,
    ) -> None:
        """Cria a sessão no estado CRIADA.

        Args:
            id_sessao: Identificador da sessão.
            regra: Estratégia de votação que implementa RegraDeVotacao.
            total_aptos: Total de aptos (CA/Congresso) ou capital social (Assembleia).
            log: Log de auditoria no qual o ciclo da sessão é registrado. Precisa ter
                sido criado para esta mesma votação.
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
        self.log = log
        self._relogio = relogio if relogio is not None else lambda: datetime.now(UTC)
        self._estado = EstadoSessao.CRIADA
        self._inicio_votacao: datetime | None = None
        self._fim_votacao: datetime | None = None
        self._eleitores: set[str] = set()
        self._votos: list[Voto] = []
        self._resultado: ResultadoApuracao | None = None

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
        if inicio is not None and fim is not None and inicio > fim:
            msg = "O início da janela de votação não pode ser posterior ao fim."
            raise ValueError(msg)

        self._transitar(de=EstadoSessao.ABERTA, para=EstadoSessao.EM_VOTACAO)
        self._inicio_votacao = inicio
        self._fim_votacao = fim
        self._auditar(
            TipoEvento.VOTACAO_ABERTA,
            {
                "inicio": inicio.isoformat() if inicio is not None else None,
                "fim": fim.isoformat() if fim is not None else None,
                "total_aptos": self.total_aptos,
            },
        )

    def encerrar_votacao(self) -> None:
        """Fecha a urna (EM_VOTACAO → EM_APURACAO)."""
        self._transitar(de=EstadoSessao.EM_VOTACAO, para=EstadoSessao.EM_APURACAO)
        self._auditar(TipoEvento.VOTACAO_ENCERRADA, {"total_votos": len(self._votos)})

    def registrar_voto(self, voto: Voto) -> str | None:
        """Aceita um voto, somente com a urna aberta, dentro da janela e uma vez por eleitor.

        Args:
            voto: Voto já autorizado pelo serviço de elegibilidade.

        Returns:
            O protocolo do registro de auditoria, que serve de comprovante ao eleitor,
            ou None se a sessão não tem log.

        Raises:
            TransicaoInvalidaError: Se a sessão não estiver em EM_VOTACAO.
            VotoRecusadoError: Se o relógio estiver fora da janela de votação ou se o
                eleitor — diretamente ou por procurador — já tiver votado nesta sessão.
        """
        self._exigir_estado(EstadoSessao.EM_VOTACAO, operacao="registrar voto")
        self._exigir_dentro_da_janela()

        identidade = self._identidade(voto)
        if identidade in self._eleitores:
            msg = f"O eleitor '{identidade}' já votou na sessão '{self.id_sessao}'."
            raise VotoRecusadoError(msg)

        self._eleitores.add(identidade)
        self._votos.append(voto)

        if self.log is None:
            return None
        return self.log.registrar_voto(voto).hash

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
        self._estado = EstadoSessao.ENCERRADA
        self._auditar(
            TipoEvento.RESULTADO_PROCLAMADO,
            {
                "status": resultado.status.value,
                "vencedor_ou_decisao": resultado.vencedor_ou_decisao,
                "quorum_atingido": resultado.quorum_atingido,
                "total_votantes": resultado.total_votantes,
                "total_peso_apurado": resultado.total_peso_apurado,
                "contagem_por_opcao": dict(resultado.contagem_por_opcao),
            },
        )
        return resultado

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

    def _auditar(self, evento: TipoEvento, dados: dict[str, Any]) -> None:
        if self.log is not None:
            self.log.registrar(evento, dados)

    @staticmethod
    def _identidade(voto: Voto) -> str:
        return voto.eleitor_id.split(SEPARADOR_PROCURACAO, 1)[0]

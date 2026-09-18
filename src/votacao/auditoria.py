"""Log de auditoria encadeado para registro verificável de eventos de votação."""

import hashlib
import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from votacao.modelos import Voto

# Hash atribuído ao antecessor do primeiro registro, que não possui um.
HASH_GENESE = "0" * 64


class TipoEvento(StrEnum):
    """Eventos do ciclo de vida de uma votação que são registrados no log."""

    VOTACAO_ABERTA = "VOTACAO_ABERTA"
    VOTO_REGISTRADO = "VOTO_REGISTRADO"
    VOTACAO_ENCERRADA = "VOTACAO_ENCERRADA"


@dataclass(frozen=True)
class RegistroAuditoria:
    """Evento registrado no log, encadeado ao anterior pelo hash.

    Attributes:
        indice: Posição do registro na cadeia, começando em 0.
        evento: Tipo do evento registrado.
        id_votacao: Identificador da votação à qual o evento pertence.
        timestamp: Data e hora em que o evento foi registrado.
        dados: Conteúdo específico do evento, serializável em JSON. Nunca contém
            identificação do eleitor.
        hash_anterior: Hash do registro imediatamente anterior na cadeia.
        hash: Hash do próprio registro, usado como protocolo e elo do próximo.
    """

    indice: int
    evento: TipoEvento
    id_votacao: str
    timestamp: datetime
    dados: dict[str, Any]
    hash_anterior: str
    hash: str

    @classmethod
    def criar(
        cls,
        indice: int,
        evento: TipoEvento,
        id_votacao: str,
        timestamp: datetime,
        dados: dict[str, Any],
        hash_anterior: str,
    ) -> "RegistroAuditoria":
        """Monta um registro já com o hash calculado a partir do próprio conteúdo.

        Args:
            indice: Posição do registro na cadeia.
            evento: Tipo do evento registrado.
            id_votacao: Identificador da votação.
            timestamp: Data e hora do registro.
            dados: Conteúdo específico do evento.
            hash_anterior: Hash do registro anterior, ou HASH_GENESE para o primeiro.

        Returns:
            Registro imutável pronto para ser anexado à cadeia.
        """
        registro = cls(
            indice=indice,
            evento=evento,
            id_votacao=id_votacao,
            timestamp=timestamp,
            dados=dados,
            hash_anterior=hash_anterior,
            hash="",
        )
        return replace(registro, hash=registro.calcular_hash())

    def calcular_hash(self) -> str:
        """Recalcula o hash a partir do conteúdo atual do registro.

        A serialização é canônica (chaves ordenadas) para que o mesmo conteúdo produza
        sempre o mesmo hash. É a comparação entre este valor e o campo `hash` gravado
        que permite detectar adulteração posterior de um registro.

        Tipos fora do JSON são recusados de propósito, em vez de convertidos para texto:
        a representação padrão de um objeto inclui seu endereço de memória, o que faria
        o mesmo registro produzir hashes diferentes a cada execução e a cadeia acusar
        uma adulteração que nunca houve.

        Returns:
            Hash SHA-256 hexadecimal do conteúdo do registro.

        Raises:
            TypeError: Se `dados` contiver valor não serializável em JSON.
        """
        conteudo = json.dumps(
            {
                "indice": self.indice,
                "evento": self.evento,
                "id_votacao": self.id_votacao,
                "timestamp": self.timestamp.isoformat(),
                "dados": self.dados,
                "hash_anterior": self.hash_anterior,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResultadoVerificacao:
    """Veredito da conferência de integridade de uma cadeia de registros.

    Attributes:
        integro: Indica se a cadeia inteira resistiu à conferência.
        indice_divergente: Índice do primeiro registro com problema, ou None se íntegra.
        motivo: Descrição do problema encontrado, ou None se íntegra.
    """

    integro: bool
    indice_divergente: int | None = None
    motivo: str | None = None


class LogDeAuditoria:
    """Cadeia de registros de auditoria de uma votação.

    Cada evento registrado carrega o hash do evento anterior, de modo que alterar ou
    remover um registro quebra a cadeia a partir dele.

    Attributes:
        id_votacao: Identificador da votação auditada.
    """

    def __init__(self, id_votacao: str, relogio: Callable[[], datetime] | None = None) -> None:
        """Inicializa um log vazio.

        Args:
            id_votacao: Identificador da votação auditada.
            relogio: Função que devolve o instante do registro. O padrão é a hora
                corrente em UTC; injetar outra torna o registro determinístico nos testes.

        Raises:
            ValueError: Se o identificador da votação for vazio.
        """
        if not id_votacao.strip():
            msg = "O identificador da votação não pode ser vazio."
            raise ValueError(msg)

        self.id_votacao = id_votacao
        self._relogio = relogio if relogio is not None else lambda: datetime.now(UTC)
        self._registros: list[RegistroAuditoria] = []

    @property
    def registros(self) -> tuple[RegistroAuditoria, ...]:
        """Registros da cadeia, na ordem em que foram criados."""
        return tuple(self._registros)

    @property
    def ultimo_hash(self) -> str:
        """Hash do último registro, ou o hash de gênese se a cadeia estiver vazia."""
        return self._registros[-1].hash if self._registros else HASH_GENESE

    def registrar(
        self,
        evento: TipoEvento,
        dados: Mapping[str, Any] | None = None,
    ) -> RegistroAuditoria:
        """Anexa um evento ao final da cadeia.

        Args:
            evento: Tipo do evento a registrar.
            dados: Conteúdo específico do evento, serializável em JSON. É copiado em
                profundidade, para que alterações posteriores no dicionário de origem —
                inclusive em estruturas aninhadas — não corrompam o registro.

        Returns:
            O registro criado, cujo hash serve de protocolo.

        Raises:
            TypeError: Se `dados` contiver valor não serializável em JSON.
        """
        try:
            registro = RegistroAuditoria.criar(
                indice=len(self._registros),
                evento=evento,
                id_votacao=self.id_votacao,
                timestamp=self._relogio(),
                dados=deepcopy(dict(dados)) if dados is not None else {},
                hash_anterior=self.ultimo_hash,
            )
        except TypeError as erro:
            msg = (
                "Os dados do evento devem ser serializáveis em JSON para que o hash "
                "do registro seja reprodutível."
            )
            raise TypeError(msg) from erro

        self._registros.append(registro)
        return registro

    def registrar_voto(self, voto: Voto) -> RegistroAuditoria:
        """Registra um voto preservando o sigilo de quem votou.

        Apenas a opção escolhida e o peso aplicado são gravados. O `eleitor_id` entra
        neste método e não é persistido em lugar nenhum da cadeia: é essa ausência que
        garante o anonimato do voto, sem abrir mão da auditabilidade da contagem.

        Args:
            voto: Voto já validado e aceito pela votação.

        Returns:
            O registro criado, cujo hash é o comprovante entregue ao eleitor.
        """
        return self.registrar(
            TipoEvento.VOTO_REGISTRADO,
            {"opcao": voto.opcao, "peso": voto.peso},
        )

    def verificar_integridade(self) -> ResultadoVerificacao:
        """Percorre a cadeia conferindo a posição, o elo e o conteúdo de cada registro.

        A conferência para no primeiro problema encontrado: uma vez quebrada, a cadeia
        já não sustenta os registros seguintes, e o que interessa à auditoria é onde a
        quebra começou.

        Returns:
            Resultado íntegro, ou o índice e o motivo da primeira divergência.
        """
        hash_esperado = HASH_GENESE

        for posicao, registro in enumerate(self._registros):
            if registro.indice != posicao:
                return ResultadoVerificacao(
                    integro=False,
                    indice_divergente=posicao,
                    motivo="O índice do registro não corresponde à sua posição na cadeia.",
                )

            if registro.hash_anterior != hash_esperado:
                return ResultadoVerificacao(
                    integro=False,
                    indice_divergente=posicao,
                    motivo="O elo com o registro anterior foi rompido.",
                )

            if registro.calcular_hash() != registro.hash:
                return ResultadoVerificacao(
                    integro=False,
                    indice_divergente=posicao,
                    motivo="O conteúdo do registro não corresponde ao hash gravado.",
                )

            hash_esperado = registro.hash

        return ResultadoVerificacao(integro=True)

    def comprovante(self, indice: int) -> str:
        """Devolve o protocolo de um registro, entregue a quem votou.

        Args:
            indice: Índice do registro na cadeia.

        Returns:
            Hash do registro, que comprova sua presença na cadeia sem revelar o eleitor.

        Raises:
            ValueError: Se não houver registro no índice informado.
        """
        if not 0 <= indice < len(self._registros):
            msg = f"Não há registro de auditoria no índice {indice}."
            raise ValueError(msg)

        return self._registros[indice].hash

    def contem_protocolo(self, protocolo: str) -> bool:
        """Informa se um protocolo corresponde a algum registro da cadeia.

        É o que permite ao eleitor confirmar que seu voto foi contabilizado: ele guarda
        apenas o hash devolvido no momento do voto e, com ele, verifica sua presença sem
        precisar saber a posição do próprio registro — posição que o anonimato não lhe dá.

        Args:
            protocolo: Hash entregue no momento do registro.

        Returns:
            True se algum registro da cadeia tem esse hash, False caso contrário.
        """
        return any(registro.hash == protocolo for registro in self._registros)

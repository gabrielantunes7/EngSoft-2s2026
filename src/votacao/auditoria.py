"""Log de auditoria encadeado para registro verificável de eventos de votação."""

import hashlib
import json
import random
import secrets
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
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
    VOTACAO_SUSPENSA = "VOTACAO_SUSPENSA"
    VOTACAO_RETOMADA = "VOTACAO_RETOMADA"
    VOTACAO_ENCERRADA = "VOTACAO_ENCERRADA"
    RESULTADO_PROCLAMADO = "RESULTADO_PROCLAMADO"
    SESSAO_ANULADA = "SESSAO_ANULADA"
    TRAMITACAO_CASA_ALTERADA = "TRAMITACAO_CASA_ALTERADA"
    TRAMITACAO_CONCLUIDA = "TRAMITACAO_CONCLUIDA"
    TRAMITACAO_ENVIADA_A_SANCAO = "TRAMITACAO_ENVIADA_A_SANCAO"
    TRAMITACAO_VETO = "TRAMITACAO_VETO"


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


class SituacaoComprovante(StrEnum):
    """Resposta da consulta de um comprovante de voto."""

    INCLUIDO = "INCLUIDO"
    REGISTRADO_URNA_ABERTA = "REGISTRADO_URNA_ABERTA"
    NAO_ENCONTRADO = "NAO_ENCONTRADO"
    CADEIA_REPROVADA = "CADEIA_REPROVADA"


# Instrução entregue em toda consulta, sem jargão técnico (RNF-AUD-05).
INSTRUCAO_COMPROVANTE = (
    "Este comprovante serve para você conferir que o seu voto foi registrado e entrou na "
    "urna. Ele não mostra em quem você votou: ninguém consegue descobrir o seu voto a "
    "partir dele, e por isso ele também não serve para provar a outra pessoa como você "
    "votou."
)


@dataclass(frozen=True)
class ConsultaComprovante:
    """Resultado da consulta de um comprovante, sem opção, peso nem horário do voto.

    Attributes:
        situacao: Situação do voto ligado ao protocolo.
        mensagem: Explicação da situação, em linguagem não técnica.
        instrucao: O que o comprovante prova e o que não revela.
    """

    situacao: SituacaoComprovante
    mensagem: str
    instrucao: str = INSTRUCAO_COMPROVANTE

    @property
    def incluido(self) -> bool:
        """Se o voto consta da urna encerrada e a cadeia foi aprovada contra a âncora."""
        return self.situacao == SituacaoComprovante.INCLUIDO


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


@dataclass(frozen=True)
class ResumoEncerramento:
    """Âncora de integridade emitida no encerramento de uma votação.

    É o valor que a comissão eleitoral guarda fora do sistema — impresso ou entregue aos
    fiscais, como o boletim de urna. Sozinha, a cadeia não resiste a quem a reescreve
    inteira recalculando todos os hashes; conferida contra esta âncora, resiste, porque o
    fraudador não alcança as cópias que já saíram do sistema.

    Attributes:
        id_votacao: Identificador da votação encerrada.
        total_registros: Quantidade de registros da cadeia até o encerramento, inclusive.
        hash_encerramento: Hash do registro VOTACAO_ENCERRADA.
        total_votos: Quantidade de votos registrados até o encerramento.
    """

    id_votacao: str
    total_registros: int
    hash_encerramento: str
    total_votos: int

    def para_json(self) -> str:
        """Serializa o resumo para ser impresso ou distribuído aos fiscais.

        Returns:
            Texto JSON com as chaves ordenadas, estável entre execuções.
        """
        return json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)

    @classmethod
    def de_json(cls, texto: str) -> "ResumoEncerramento":
        """Reconstrói o resumo guardado por um fiscal para conferir o log.

        Args:
            texto: JSON produzido por `para_json`.

        Returns:
            O resumo de encerramento correspondente.

        Raises:
            ValueError: Se o texto não for JSON ou não tiver exatamente os campos do resumo.
        """
        try:
            return cls(**json.loads(texto))
        except (json.JSONDecodeError, TypeError) as erro:
            msg = "O texto informado não é um resumo de encerramento válido."
            raise ValueError(msg) from erro


class LogDeAuditoria:
    """Cadeia de registros de auditoria de uma votação.

    Cada evento registrado carrega o hash do evento anterior, de modo que alterar ou
    remover um registro quebra a cadeia a partir dele.

    O voto entra na cadeia em dois momentos separados, para que o comprovante prove a
    inclusão sem revelar o conteúdo (#28): no voto, um VOTO_REGISTRADO sem opção, peso
    ou eleitor, cujo hash é o protocolo; no encerramento, as cédulas (opção e peso) de
    todos os votos, em ordem aleatória e sem horário, que permitem recontar o resultado
    sem ligar nenhuma cédula a quem votou, nem pela ordem de chegada.

    Attributes:
        id_votacao: Identificador da votação auditada.
    """

    def __init__(
        self,
        id_votacao: str,
        relogio: Callable[[], datetime] | None = None,
        aleatorio: random.Random | None = None,
    ) -> None:
        """Inicializa um log vazio.

        Args:
            id_votacao: Identificador da votação auditada.
            relogio: Função que devolve o instante do registro. O padrão é a hora
                corrente em UTC; injetar outra torna o registro determinístico nos testes.
            aleatorio: Fonte aleatória usada para embaralhar as cédulas no encerramento.
                O padrão é `secrets.SystemRandom`, imprevisível; injetar uma fonte com
                semente torna o embaralhamento reprodutível nos testes.

        Raises:
            ValueError: Se o identificador da votação for vazio.
        """
        if not id_votacao.strip():
            msg = "O identificador da votação não pode ser vazio."
            raise ValueError(msg)

        self.id_votacao = id_votacao
        self._relogio = relogio if relogio is not None else lambda: datetime.now(UTC)
        self._aleatorio = aleatorio if aleatorio is not None else secrets.SystemRandom()
        self._registros: list[RegistroAuditoria] = []
        # Cédulas guardadas fora da cadeia até o encerramento, quando são publicadas
        # embaralhadas. Nunca contêm o eleitor nem a ordem de chegada depois de publicadas.
        self._cedulas_pendentes: list[list[Any]] = []

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

        Ao registrar VOTACAO_ENCERRADA, o log acrescenta aos dados a lista `cedulas` com
        os pares [opção, peso] de todos os votos registrados até ali, embaralhados.

        Raises:
            TypeError: Se `dados` contiver valor não serializável em JSON.
        """
        if evento == TipoEvento.VOTACAO_ENCERRADA:
            dados = {**(dados or {}), "cedulas": self._publicar_cedulas()}
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
        """Registra a inclusão de um voto sem gravar o seu conteúdo nem o eleitor.

        O VOTO_REGISTRADO não contém opção, peso nem `eleitor_id`: o hash dele é o
        comprovante, que prova a inclusão do voto mas não revela em quem se votou
        (D-AUD-02). A opção e o peso ficam guardados fora da cadeia e só entram nela no
        encerramento, entre as cédulas embaralhadas (D-AUD-03).

        Args:
            voto: Voto já validado e aceito pela votação.

        Returns:
            O registro criado, cujo hash é o comprovante entregue ao eleitor.
        """
        registro = self.registrar(TipoEvento.VOTO_REGISTRADO, {})
        self._cedulas_pendentes.append([voto.opcao, voto.peso])
        return registro

    def _publicar_cedulas(self) -> list[list[Any]]:
        """Embaralha e entrega as cédulas guardadas desde o último encerramento."""
        cedulas = list(self._cedulas_pendentes)
        self._aleatorio.shuffle(cedulas)
        self._cedulas_pendentes = []
        return cedulas

    def consultar_comprovante(
        self, protocolo: str, ancora: ResumoEncerramento | None = None
    ) -> ConsultaComprovante:
        """Responde ao eleitor se o voto do comprovante está na urna encerrada.

        Com a âncora do encerramento (#27), confirma a inclusão quando o protocolo
        existe, o registro é anterior ao VOTACAO_ENCERRADA e a cadeia é aprovada contra a
        âncora. A resposta nunca contém a opção, o peso nem o horário do voto.

        Args:
            protocolo: Comprovante entregue no momento do voto.
            ancora: Resumo guardado pela comissão no encerramento, ou None se a votação
                ainda não foi encerrada.

        Returns:
            Situação, explicação e instrução em linguagem não técnica.
        """
        registro = next(
            (
                r
                for r in self._registros
                if r.hash == protocolo.strip() and r.evento == TipoEvento.VOTO_REGISTRADO
            ),
            None,
        )
        if registro is None:
            return ConsultaComprovante(
                situacao=SituacaoComprovante.NAO_ENCONTRADO,
                mensagem=(
                    "Não encontramos um voto com este comprovante. Confira se ele foi "
                    "copiado por inteiro e, se o problema continuar, procure a comissão "
                    "eleitoral levando o comprovante."
                ),
            )

        verificacao = self.verificar_integridade(ancora=ancora)
        if not verificacao.integro:
            return ConsultaComprovante(
                situacao=SituacaoComprovante.CADEIA_REPROVADA,
                mensagem=(
                    "O registro da votação não passou na conferência de integridade, então "
                    "não é possível confirmar a inclusão do seu voto. Procure a comissão "
                    "eleitoral: o registro pode ter sido alterado."
                ),
            )

        if ancora is None:
            return ConsultaComprovante(
                situacao=SituacaoComprovante.REGISTRADO_URNA_ABERTA,
                mensagem=(
                    "O seu voto foi registrado. A votação ainda não foi encerrada; depois "
                    "do encerramento será possível confirmar que ele entrou na urna fechada."
                ),
            )

        if registro.indice >= ancora.total_registros - 1:
            # Voto posterior ao encerramento: a própria conferência contra a âncora já o
            # reprova; mantido como salvaguarda explícita.
            return ConsultaComprovante(  # pragma: no cover
                situacao=SituacaoComprovante.CADEIA_REPROVADA,
                mensagem="Este voto foi registrado depois do encerramento da urna.",
            )

        return ConsultaComprovante(
            situacao=SituacaoComprovante.INCLUIDO,
            mensagem="Registrado e incluído na urna encerrada.",
        )

    def verificar_integridade(
        self, ancora: ResumoEncerramento | None = None
    ) -> ResultadoVerificacao:
        """Percorre a cadeia conferindo a posição, o elo e o conteúdo de cada registro.

        A conferência para no primeiro problema encontrado: uma vez quebrada, a cadeia
        já não sustenta os registros seguintes, e o que interessa à auditoria é onde a
        quebra começou.

        Sem âncora, a conferência só prova que a cadeia é coerente consigo mesma — o que
        uma reescrita completa, com todos os hashes recalculados, também é. Com a âncora
        guardada no encerramento, a cadeia precisa ainda reproduzir o hash ancorado.

        Args:
            ancora: Resumo emitido no encerramento e guardado fora do sistema, ou None
                para conferir apenas a coerência interna.

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

        if ancora is not None:
            return self._conferir_ancora(ancora)
        return ResultadoVerificacao(integro=True)

    def _conferir_ancora(self, ancora: ResumoEncerramento) -> ResultadoVerificacao:
        """Confere uma cadeia já coerente contra a âncora guardada no encerramento.

        Basta comparar o hash na posição ancorada: como cada hash incorpora o anterior,
        ele resume todos os registros até ali. Alterar, remover ou inserir qualquer um
        deles — mesmo recalculando a cadeia — muda esse hash.

        Depois da âncora a cadeia pode continuar, com a proclamação do resultado, mas não
        pode receber votos: um voto ali entrou numa urna que a comissão já fechou.
        """
        if ancora.id_votacao != self.id_votacao:
            return ResultadoVerificacao(
                integro=False,
                motivo="A âncora pertence a outra votação.",
            )

        posicao = ancora.total_registros - 1
        if posicao >= len(self._registros):
            return ResultadoVerificacao(
                integro=False,
                indice_divergente=len(self._registros),
                motivo="O log tem menos registros do que os ancorados no encerramento.",
            )

        if posicao < 0 or self._registros[posicao].hash != ancora.hash_encerramento:
            return ResultadoVerificacao(
                integro=False,
                indice_divergente=max(posicao, 0),
                motivo="O registro de encerramento não corresponde à âncora.",
            )

        for indice, registro in enumerate(
            self._registros[ancora.total_registros :], start=ancora.total_registros
        ):
            if registro.evento == TipoEvento.VOTO_REGISTRADO:
                return ResultadoVerificacao(
                    integro=False,
                    indice_divergente=indice,
                    motivo="Há voto registrado depois do encerramento ancorado.",
                )

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

    def resumo_encerramento(self) -> ResumoEncerramento:
        """Emite a âncora a ser guardada fora do sistema quando a votação é encerrada.

        O resumo aponta para o primeiro registro VOTACAO_ENCERRADA. Registros posteriores,
        como a proclamação do resultado, não alteram a âncora.

        Returns:
            Resumo com o hash do encerramento e os totais até ele.

        Raises:
            ValueError: Se a votação ainda não tiver sido encerrada no log.
        """
        for posicao, registro in enumerate(self._registros):
            if registro.evento == TipoEvento.VOTACAO_ENCERRADA:
                total_votos = sum(
                    1
                    for anterior in self._registros[:posicao]
                    if anterior.evento == TipoEvento.VOTO_REGISTRADO
                )
                return ResumoEncerramento(
                    id_votacao=self.id_votacao,
                    total_registros=posicao + 1,
                    hash_encerramento=registro.hash,
                    total_votos=total_votos,
                )

        msg = "A votação ainda não foi encerrada: não há resumo de encerramento a emitir."
        raise ValueError(msg)

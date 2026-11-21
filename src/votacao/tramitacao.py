"""Tramitação de matérias legislativas entre as Casas do Congresso Nacional."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import ClassVar

from votacao.auditoria import LogDeAuditoria, TipoEvento
from votacao.dados.congresso import RepositorioCongresso
from votacao.fabricas.congresso import FabricaCongresso
from votacao.modelos import (
    CasaLegislativa,
    ResultadoApuracao,
    StatusResultado,
    TipoMateriaCongresso,
)
from votacao.sessao import EstadoSessao, SessaoVotacao


class StatusTramitacao(StrEnum):
    """Situação de uma matéria ao longo do rito legislativo.

    EM_TRAMITACAO, ENVIADA_A_SANCAO e VETO_EM_APRECIACAO são situações intermediárias;
    APROVADA, PROMULGADA e REJEITADA são desfechos finais.
    """

    EM_TRAMITACAO = "EM_TRAMITACAO"
    ENVIADA_A_SANCAO = "ENVIADA_A_SANCAO"
    VETO_EM_APRECIACAO = "VETO_EM_APRECIACAO"
    APROVADA = "APROVADA"
    PROMULGADA = "PROMULGADA"
    REJEITADA = "REJEITADA"

    @property
    def concluida(self) -> bool:
        """Se a situação é um desfecho final da tramitação."""
        return self in (
            StatusTramitacao.APROVADA,
            StatusTramitacao.PROMULGADA,
            StatusTramitacao.REJEITADA,
        )


class FaseTramitacao(StrEnum):
    """Etapa do rito bicameral em que a matéria se encontra."""

    CASA_INICIADORA = "CASA_INICIADORA"
    CASA_REVISORA = "CASA_REVISORA"
    APRECIACAO_EMENDAS = "APRECIACAO_EMENDAS"
    APRECIACAO_VETO = "APRECIACAO_VETO"


class TextoPrevalecente(StrEnum):
    """Texto que prevalece ao fim da apreciação das emendas da revisora (art. 65)."""

    REVISORA = "REVISORA"
    INICIADORA = "INICIADORA"


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
        fase: Etapa do rito em que a sessão ocorreu.
        com_emenda: True quando a aprovação na Casa revisora veio com emendas.
        texto_prevalecente: Na apreciação das emendas, qual texto prevaleceu; None nas
            demais etapas.
    """

    id_sessao: str
    casa: CasaLegislativa
    turno: int
    resultado: ResultadoApuracao
    valida: bool
    fase: FaseTramitacao = FaseTramitacao.CASA_INICIADORA
    com_emenda: bool = False
    texto_prevalecente: TextoPrevalecente | None = None


class TramitacaoLegislativa:
    """Conduz uma matéria pela Casa iniciadora e pela Casa revisora, turno a turno.

    Cada turno é uma `SessaoVotacao` convocada por `nova_sessao`, já configurada com
    a `RegraCongresso` da matéria e da Casa corrente. Ao registrar o resultado de uma
    sessão encerrada, a tramitação avança para o próximo turno, para a Casa revisora
    ou para a conclusão, conforme o rito exigido pelo tipo de matéria.

    Se a Casa revisora aprova a matéria com emendas, ela volta à Casa iniciadora, que
    aprecia apenas as emendas (CF, art. 65, parágrafo único). A apreciação é terminal:
    acolhidas as emendas prevalece o texto da revisora; rejeitadas, o da iniciadora. Nos
    dois casos a matéria está aprovada, e não há novo envio à revisora.

    A conclusão depende do tipo da matéria. A PEC aprovada nas duas Casas é promulgada
    pelas Mesas, sem sanção (CF, art. 60, § 3º). O projeto de lei vai à sanção
    presidencial (art. 66): sancionado, está aprovado; vetado, o veto é apreciado e só é
    derrubado pela maioria absoluta dos Deputados e Senadores (art. 66, § 4º), em
    votação aberta desde a EC 76/2013. Derrubado o veto, a matéria está aprovada; mantido,
    rejeitada.

    Quando recebe um `RepositorioCongresso`, mantém a `MateriaLegislativa` cadastrada
    coerente com o rito: `casa_atual` acompanha a Casa em que a matéria se encontra e
    `ativa` passa a False na conclusão. É o que permite ao validador de elegibilidade
    aceitar os parlamentares da Casa revisora e recusar votos em matéria concluída.

    Attributes:
        materia_id: Identificador oficial da matéria (ex.: 'PEC-50/2026').
        tipo: Tipo da matéria, que determina o número de turnos por Casa.
        casa_iniciadora: Casa em que a matéria começa a tramitar.
        repo: Repositório em que a matéria está cadastrada, ou None.
        log: Log de auditoria do rito, em que ficam a troca de Casa (inclusive o retorno
            por emenda) e a conclusão, ou None.
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
        repo: RepositorioCongresso | None = None,
        log: LogDeAuditoria | None = None,
    ) -> None:
        """Inicia a tramitação no primeiro turno da Casa iniciadora.

        Args:
            materia_id: Identificador oficial da matéria.
            tipo: Tipo da matéria legislativa.
            casa_iniciadora: Casa em que a matéria começa a tramitar.
            repo: Repositório com o cadastro da matéria. Quando informado, a matéria
                precisa existir, estar ativa, ter o mesmo tipo e estar pautada na
                Casa iniciadora.
            log: Log de auditoria do rito. Precisa ter sido criado com o identificador
                da matéria.

        Raises:
            ValueError: Se o identificador da matéria for vazio, se o cadastro no
                repositório divergir dos parâmetros informados ou se o log pertencer a
                outra matéria.
        """
        if not materia_id.strip():
            msg = "O identificador da matéria não pode ser vazio."
            raise ValueError(msg)
        if log is not None and log.id_votacao != materia_id:
            msg = f"O log de auditoria pertence a '{log.id_votacao}', não à matéria '{materia_id}'."
            raise ValueError(msg)

        self.materia_id = materia_id
        self.tipo = tipo
        self.casa_iniciadora = casa_iniciadora
        self.repo = repo
        self._casa_atual = casa_iniciadora
        self._turno_atual = 1
        self._status = StatusTramitacao.EM_TRAMITACAO
        self._historico: list[RegistroTramitacao] = []
        self._sessao_convocada: SessaoVotacao | None = None
        self._fase = FaseTramitacao.CASA_INICIADORA
        self._revisora_emendou = False
        self._texto_prevalecente: TextoPrevalecente | None = None
        self._razoes_veto: str | None = None
        self.log = log

        if repo is not None:
            self._conferir_cadastro(repo)

    @property
    def status(self) -> StatusTramitacao:
        """Situação corrente da matéria."""
        return self._status

    @property
    def fase(self) -> FaseTramitacao:
        """Etapa do rito em que a matéria se encontra."""
        return self._fase

    @property
    def aceita_emenda(self) -> bool:
        """Se uma aprovação na etapa corrente pode vir com emendas (só na revisora)."""
        return (
            self._status == StatusTramitacao.EM_TRAMITACAO
            and self._fase == FaseTramitacao.CASA_REVISORA
        )

    @property
    def razoes_veto(self) -> str | None:
        """Razões do veto presidencial, ou None se a matéria não foi vetada."""
        return self._razoes_veto

    @property
    def texto_prevalecente(self) -> TextoPrevalecente | None:
        """Texto que prevaleceu na apreciação das emendas, ou None se não houve."""
        return self._texto_prevalecente

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
        """Identificador que `nova_sessao` atribuirá à sessão da etapa corrente.

        A apreciação de emendas ocorre na mesma Casa do 1º turno da iniciadora; o
        sufixo EMENDAS evita que os dois logs de auditoria colidam no mesmo id.
        """
        if self._fase == FaseTramitacao.APRECIACAO_EMENDAS:
            return f"{self.materia_id}-{self._casa_atual.value}-EMENDAS"
        if self._fase == FaseTramitacao.APRECIACAO_VETO:
            return f"{self.materia_id}-VETO-{self._casa_atual.value}"
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
            Sessão em CRIADA, com `RegraCongresso` da matéria e da Casa corrente, total
            de aptos igual ao número constitucional de membros da Casa e quórum de
            instalação igual à maioria absoluta desses membros: a votação só é liberada
            depois de registrada a presença desse número de parlamentares (CF, art. 47).

        Raises:
            TramitacaoInvalidaError: Se a tramitação já foi concluída.
        """
        self._exigir_deliberacao_aberta(operacao="convocar sessão")

        fabrica = FabricaCongresso()
        # A derrubada do veto exige maioria absoluta dos membros de cada Casa
        # (art. 66, § 4º): o mesmo patamar da lei complementar (257 e 41 votos SIM).
        materia_da_regra = (
            TipoMateriaCongresso.LEI_COMPLEMENTAR
            if self._fase == FaseTramitacao.APRECIACAO_VETO
            else self.tipo
        )
        regra = fabrica.criar_regra(materia=materia_da_regra, casa=self._casa_atual)
        sessao = fabrica.criar_sessao(
            id_sessao=self.id_proxima_sessao,
            materia=materia_da_regra,
            casa=self._casa_atual,
            log=log,
            relogio=relogio,
            regra=regra,
            quorum_instalacao=regra.quorum_instalacao,
        )
        self._sessao_convocada = sessao
        return sessao

    def registrar_resultado(
        self, sessao: SessaoVotacao, com_emenda: bool = False
    ) -> StatusTramitacao:
        """Incorpora o resultado da sessão da etapa corrente e avança o rito.

        Aprovação avança o turno; vencidos os turnos da Casa, passa à revisora;
        vencidas as duas Casas, a matéria fica APROVADA. Rejeição em qualquer etapa
        encerra a tramitação como REJEITADA. Quórum insuficiente não é decisão de
        mérito: a sessão entra no histórico como inválida e a etapa se mantém, de modo
        que uma nova sessão possa ser convocada. Sessão anulada é recusada com o mesmo
        efeito sobre a etapa: ela se mantém e outra sessão pode ser convocada.

        Aprovação com emendas na Casa revisora não conclui o rito: vencidos os turnos
        da revisora, a matéria volta à iniciadora para apreciar as emendas (CF, art. 65,
        parágrafo único). Na apreciação, aprovar acolhe as emendas (prevalece o texto
        da revisora) e rejeitar as recusa (prevalece o da iniciadora); nos dois casos a
        matéria fica APROVADA.

        Args:
            sessao: Sessão convocada por `nova_sessao` para a etapa corrente, já
                apurada.
            com_emenda: Indica que a aprovação na Casa revisora veio com emendas.

        Returns:
            Situação da matéria após o registro.

        Raises:
            TramitacaoInvalidaError: Se a tramitação já foi concluída, se a sessão não
                foi convocada por esta tramitação para a etapa corrente, se já foi
                registrada, se foi anulada, se ainda não foi apurada, ou se houver
                emenda fora da Casa revisora ou em sessão que não aprovou a matéria.
        """
        self._exigir_deliberacao_aberta(operacao="registrar resultado")

        if sessao is not self._sessao_convocada:
            msg = (
                f"A sessão '{sessao.id_sessao}' não é a sessão convocada para a etapa "
                f"corrente da matéria '{self.materia_id}' ({self.id_proxima_sessao}), "
                "ou já teve seu resultado registrado."
            )
            raise TramitacaoInvalidaError(msg)
        if sessao.estado == EstadoSessao.ANULADA:
            msg = (
                f"A sessão '{sessao.id_sessao}' foi anulada ({sessao.motivo_anulacao}) e não "
                "produz resultado. A etapa se mantém: convoque uma nova sessão com "
                "nova_sessao()."
            )
            raise TramitacaoInvalidaError(msg)
        if sessao.estado != EstadoSessao.ENCERRADA or sessao.resultado is None:
            msg = (
                f"A sessão '{sessao.id_sessao}' ainda não foi apurada "
                f"(estado atual: {sessao.estado.value})."
            )
            raise TramitacaoInvalidaError(msg)

        resultado = sessao.resultado
        if com_emenda:
            self._exigir_emenda_admissivel(resultado)

        valida = resultado.status != StatusResultado.QUORUM_INSUFICIENTE
        fase = self._fase
        texto: TextoPrevalecente | None = None
        if fase == FaseTramitacao.APRECIACAO_EMENDAS and valida:
            texto = (
                TextoPrevalecente.REVISORA
                if resultado.status == StatusResultado.APROVADO
                else TextoPrevalecente.INICIADORA
            )
        self._historico.append(
            RegistroTramitacao(
                id_sessao=sessao.id_sessao,
                casa=self._casa_atual,
                turno=self._turno_atual,
                resultado=resultado,
                valida=valida,
                fase=fase,
                com_emenda=com_emenda,
                texto_prevalecente=texto,
            )
        )
        self._sessao_convocada = None

        if not valida:
            return self._status
        if fase == FaseTramitacao.APRECIACAO_VETO:
            self._registrar_apreciacao_do_veto(resultado)
            return self._status
        if texto is not None:
            # Apreciação de emendas é terminal: os dois desfechos aprovam a matéria.
            self._texto_prevalecente = texto
            self._concluir_aprovacao_no_congresso()
            return self._status
        if resultado.status == StatusResultado.REJEITADO:
            self._concluir(StatusTramitacao.REJEITADA)
            return self._status

        if com_emenda:
            self._revisora_emendou = True
        self._avancar()
        return self._status

    def _exigir_emenda_admissivel(self, resultado: ResultadoApuracao) -> None:
        """Só a Casa revisora emenda (CF, art. 65), e só ao aprovar a matéria."""
        if self._fase != FaseTramitacao.CASA_REVISORA:
            msg = (
                f"Emenda indicada na fase {self._fase.value} da matéria "
                f"'{self.materia_id}': apenas a Casa revisora emenda o projeto "
                "(CF, art. 65), e a apreciação das emendas não admite novas emendas."
            )
            raise TramitacaoInvalidaError(msg)
        if resultado.status != StatusResultado.APROVADO:
            msg = (
                "Emenda indicada numa sessão que não aprovou a matéria "
                f"(resultado {resultado.status.value}): a emenda acompanha a aprovação."
            )
            raise TramitacaoInvalidaError(msg)

    def _avancar(self) -> None:
        if self._turno_atual < self.turnos_por_casa:
            self._turno_atual += 1
        elif self._casa_atual == self.casa_iniciadora:
            self._mudar_de_casa(self.casa_revisora, FaseTramitacao.CASA_REVISORA)
        elif self._revisora_emendou:
            self._retornar_para_apreciar_emendas()
        else:
            self._concluir_aprovacao_no_congresso()

    def _concluir_aprovacao_no_congresso(self) -> None:
        """Encerra a fase legislativa: promulgação da PEC ou envio da lei à sanção.

        A PEC é promulgada pelas Mesas da Câmara e do Senado, com o respectivo número de
        ordem, e não vai à sanção (CF, art. 60, § 3º). O projeto de lei aprovado é
        enviado ao Presidente da República para sanção ou veto (art. 66).
        """
        if self.tipo == TipoMateriaCongresso.PEC:
            self._concluir(StatusTramitacao.PROMULGADA)
            return
        self._status = StatusTramitacao.ENVIADA_A_SANCAO
        self._sincronizar_cadastro(ativa=False)
        dados: dict[str, str] = {"casa": self._casa_atual.value}
        if self._texto_prevalecente is not None:
            dados["texto_prevalecente"] = self._texto_prevalecente.value
        self._registrar_no_log(TipoEvento.TRAMITACAO_ENVIADA_A_SANCAO, dados)

    def sancionar(self) -> StatusTramitacao:
        """Registra a sanção presidencial, que conclui a tramitação como aprovada (art. 66).

        Raises:
            TramitacaoInvalidaError: Se a matéria não estiver aguardando sanção, o que
                inclui a PEC (que não vai a sanção) e a matéria que ainda não venceu as
                duas Casas.
        """
        self._exigir_aguardando_sancao(operacao="sancionar")
        self._concluir(StatusTramitacao.APROVADA, decisao="SANCAO")
        return self._status

    def vetar(self, razoes: str) -> StatusTramitacao:
        """Registra o veto presidencial e abre a sua apreciação pelo Congresso.

        "O veto será apreciado em sessão conjunta (...) só podendo ser rejeitado pelo voto
        da maioria absoluta dos Deputados e Senadores" (CF, art. 66, § 4º). A apreciação
        é apurada separadamente em cada Casa, Câmara e depois Senado; votar SIM é votar
        pela derrubada. Desde a EC 76/2013 a votação é aberta.

        Args:
            razoes: Razões do veto comunicadas ao Presidente do Senado (art. 66, § 1º).

        Raises:
            ValueError: Se as razões forem vazias.
            TramitacaoInvalidaError: Se a matéria não estiver aguardando sanção.
        """
        self._exigir_aguardando_sancao(operacao="vetar")
        razoes_limpas = razoes.strip()
        if not razoes_limpas:
            msg = "Informe as razões do veto (CF, art. 66, § 1º)."
            raise ValueError(msg)

        self._razoes_veto = razoes_limpas
        self._status = StatusTramitacao.VETO_EM_APRECIACAO
        self._fase = FaseTramitacao.APRECIACAO_VETO
        self._casa_atual = CasaLegislativa.CAMARA
        self._turno_atual = 1
        self._sincronizar_cadastro(casa_atual=self._casa_atual, ativa=True)
        self._registrar_no_log(
            TipoEvento.TRAMITACAO_VETO,
            {
                "decisao": "VETO",
                "razoes": razoes_limpas,
                "votacao": "aberta (CF, art. 66, § 4º, redação da EC 76/2013)",
            },
        )
        return self._status

    def _registrar_apreciacao_do_veto(self, resultado: ResultadoApuracao) -> None:
        """Maioria absoluta pela derrubada em cada Casa derruba o veto; senão, é mantido."""
        if resultado.status != StatusResultado.APROVADO:
            self._concluir(StatusTramitacao.REJEITADA, decisao="VETO_MANTIDO")
            return
        if self._casa_atual == CasaLegislativa.CAMARA:
            self._mudar_de_casa(
                CasaLegislativa.SENADO,
                FaseTramitacao.APRECIACAO_VETO,
                motivo="Apreciação do veto: apuração no Senado (CF, art. 66, § 4º)",
            )
            return
        self._concluir(StatusTramitacao.APROVADA, decisao="VETO_DERRUBADO")

    def _exigir_aguardando_sancao(self, operacao: str) -> None:
        if self._status != StatusTramitacao.ENVIADA_A_SANCAO:
            if self.tipo == TipoMateriaCongresso.PEC:
                motivo = "PEC é promulgada pelas Mesas e não vai a sanção (CF, art. 60, § 3º)"
            else:
                motivo = (
                    "só a matéria aprovada nas duas Casas e enviada à sanção pode ser "
                    "sancionada ou vetada (CF, art. 66)"
                )
            msg = (
                f"Não é possível {operacao} a matéria '{self.materia_id}' "
                f"(situação {self._status.value}): {motivo}."
            )
            raise TramitacaoInvalidaError(msg)

    def _retornar_para_apreciar_emendas(self) -> None:
        """Devolve à iniciadora a matéria emendada pela revisora.

        "Sendo o projeto emendado, voltará à Casa iniciadora" (CF, art. 65, parágrafo
        único). A iniciadora delibera apenas sobre as emendas, em sessão única.
        """
        self._mudar_de_casa(
            self.casa_iniciadora,
            FaseTramitacao.APRECIACAO_EMENDAS,
            motivo="Retorno à Casa iniciadora para apreciar as emendas (CF, art. 65, p.u.)",
        )

    def _mudar_de_casa(
        self,
        destino: CasaLegislativa,
        fase: FaseTramitacao,
        motivo: str | None = None,
    ) -> None:
        origem = self._casa_atual
        self._casa_atual = destino
        self._turno_atual = 1
        self._fase = fase
        self._sincronizar_cadastro(casa_atual=destino)
        dados: dict[str, str] = {"origem": origem.value, "destino": destino.value}
        dados["fase"] = fase.value
        if motivo is not None:
            dados["motivo"] = motivo
        self._registrar_no_log(TipoEvento.TRAMITACAO_CASA_ALTERADA, dados)

    def _concluir(self, status: StatusTramitacao, decisao: str | None = None) -> None:
        self._status = status
        self._sincronizar_cadastro(ativa=False)
        dados: dict[str, str] = {"status": status.value, "casa": self._casa_atual.value}
        if decisao is not None:
            dados["decisao"] = decisao
        if self._texto_prevalecente is not None:
            dados["texto_prevalecente"] = self._texto_prevalecente.value
        self._registrar_no_log(TipoEvento.TRAMITACAO_CONCLUIDA, dados)

    def _registrar_no_log(self, evento: TipoEvento, dados: dict[str, str]) -> None:
        if self.log is not None:
            self.log.registrar(evento, dados)

    def _exigir_deliberacao_aberta(self, operacao: str) -> None:
        """Há votação a fazer no Congresso: em tramitação ou com veto em apreciação."""
        if self._status not in (
            StatusTramitacao.EM_TRAMITACAO,
            StatusTramitacao.VETO_EM_APRECIACAO,
        ):
            msg = (
                f"Não é possível {operacao}: a matéria '{self.materia_id}' "
                f"não está em deliberação no Congresso (situação {self._status.value})."
            )
            raise TramitacaoInvalidaError(msg)

    def _conferir_cadastro(self, repo: RepositorioCongresso) -> None:
        materia = repo.obter_materia(self.materia_id)
        if materia is None:
            msg = f"A matéria '{self.materia_id}' não está cadastrada no repositório."
            raise ValueError(msg)
        if not materia.ativa:
            msg = f"A matéria '{self.materia_id}' está arquivada e não pode tramitar."
            raise ValueError(msg)
        if materia.tipo != self.tipo:
            msg = (
                f"A matéria '{self.materia_id}' está cadastrada como {materia.tipo.value}, "
                f"não como {self.tipo.value}."
            )
            raise ValueError(msg)
        if materia.casa_atual != self.casa_iniciadora:
            msg = (
                f"A matéria '{self.materia_id}' está pautada na {materia.casa_atual.value}, "
                f"não na Casa iniciadora informada ({self.casa_iniciadora.value})."
            )
            raise ValueError(msg)

    def _sincronizar_cadastro(
        self,
        casa_atual: CasaLegislativa | None = None,
        ativa: bool | None = None,
    ) -> None:
        if self.repo is None:
            return
        materia = self.repo.obter_materia(self.materia_id)
        if materia is None:
            return
        alteracoes: dict[str, CasaLegislativa | bool] = {}
        if casa_atual is not None:
            alteracoes["casa_atual"] = casa_atual
        if ativa is not None:
            alteracoes["ativa"] = ativa
        self.repo.adicionar_materia(replace(materia, **alteracoes))

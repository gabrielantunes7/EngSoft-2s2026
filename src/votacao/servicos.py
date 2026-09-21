"""Serviço interno de autenticação, consulta de aptidão ao voto e elegibilidade."""

from datetime import UTC, datetime
from typing import ClassVar

from votacao.dados.seeds import BancoDadosMock
from votacao.elegibilidade.validador_assembleia import (
    ValidadorElegibilidadeAssembleia,
)
from votacao.elegibilidade.validador_ca import ValidadorElegibilidadeCA
from votacao.elegibilidade.validador_congresso import (
    ValidadorElegibilidadeCongresso,
)
from votacao.modelos import (
    AptidaoVoto,
    CasaLegislativa,
    ElegibilidadeCandidato,
    Usuario,
    Voto,
)
from votacao.procuracoes import ServicoProcuracao


class ServicoElegibilidade:
    """API interna para autenticação de participantes e verificação de aptidão ao voto.

    Centraliza a orquestração entre a camada de dados mockada e os validadores de
    elegibilidade de cada domínio (CA, Assembleia de Acionistas e Congresso Nacional).
    """

    CONTEXTOS_VALIDOS: ClassVar[set[str]] = {"CA", "ASSEMBLEIA", "CONGRESSO"}
    OPCOES_PADRAO_ASSEMBLEIA: ClassVar[set[str]] = {"SIM", "NAO", "ABSTENCAO", "BRANCO", "NULO"}
    OPCOES_PADRAO_CONGRESSO: ClassVar[set[str]] = {"SIM", "NAO", "ABSTENCAO", "BRANCO"}

    def __init__(self, banco: BancoDadosMock | None = None) -> None:
        self.banco = banco if banco is not None else BancoDadosMock()
        self.validador_ca = ValidadorElegibilidadeCA()
        self.validador_assembleia = ValidadorElegibilidadeAssembleia()
        self.validador_congresso = ValidadorElegibilidadeCongresso()
        self.procuracoes = ServicoProcuracao(self.banco.assembleia)

    def autenticar(self, identificador: str, contexto: str) -> Usuario | None:
        """Autentica o usuário na base correspondente ao contexto do processo de escolha.

        Args:
            identificador: RA (CA), CPF/ID de acionista (Assembleia) ou ID funcional (Congresso).
            contexto: 'CA', 'ASSEMBLEIA' ou 'CONGRESSO'.

        Returns:
            Instância de Usuario caso o registro exista e esteja habilitado; None caso contrário.
        """
        ctx = self._normalizar_contexto(contexto)
        identificador_limpo = identificador.strip()

        if ctx == "CA":
            discente = self.banco.ca.obter_discente(identificador_limpo)
            if discente is None:
                return None
            ativo = discente.matricula_ativa and not discente.suspenso
            return Usuario(
                id=discente.ra,
                nome=discente.nome,
                email=f"{discente.ra}@dac.unicamp.br",
                ativo=ativo,
            )

        if ctx == "ASSEMBLEIA":
            acionista = self.banco.assembleia.obter_acionista(identificador_limpo)
            if acionista is None:
                return None
            ativo = acionista.ativo and not acionista.bloqueado
            return Usuario(
                id=acionista.id,
                nome=acionista.nome,
                email=f"{acionista.id.lower()}@investidores.com.br",
                ativo=ativo,
            )

        # Contexto CONGRESSO
        parlamentar = self.banco.congresso.obter_parlamentar(identificador_limpo)
        if parlamentar is None:
            return None
        ativo = parlamentar.em_exercicio and not parlamentar.licenciado and not parlamentar.suspenso
        casa_sigla = "camara" if parlamentar.casa == CasaLegislativa.CAMARA else "senado"
        return Usuario(
            id=parlamentar.id,
            nome=parlamentar.nome,
            email=f"{parlamentar.id.lower()}@{casa_sigla}.leg.br",
            ativo=ativo,
        )

    def consultar_aptidao(
        self,
        eleitor_id: str,
        contexto: str,
        casa: CasaLegislativa | None = None,
        procurador_id: str | None = None,
        momento: datetime | None = None,
    ) -> AptidaoVoto:
        """Consulta centralizada da aptidão ao voto para qualquer um dos três contextos."""
        ctx = self._normalizar_contexto(contexto)

        if ctx == "CA":
            return self.validador_ca.validar_eleitor(eleitor_id, self.banco.ca)

        if ctx == "ASSEMBLEIA":
            return self.validador_assembleia.validar_eleitor(
                acionista_id=eleitor_id,
                repo=self.banco.assembleia,
                procurador_id=procurador_id,
                momento=momento,
            )

        # Contexto CONGRESSO
        if casa is None:
            msg = "Para consulta no contexto CONGRESSO, a CasaLegislativa deve ser informada."
            raise ValueError(msg)
        return self.validador_congresso.validar_eleitor(
            parlamentar_id=eleitor_id,
            casa_votacao=casa,
            repo=self.banco.congresso,
        )

    def validar_candidato_ou_opcao(
        self,
        opcao_ou_candidato: str,
        contexto: str,
        casa: CasaLegislativa | None = None,
    ) -> ElegibilidadeCandidato:
        """Valida se a opção ou candidatura é elegível e admissível para votação."""
        ctx = self._normalizar_contexto(contexto)
        opcao_norm = opcao_ou_candidato.strip().upper()

        if ctx == "CA":
            if opcao_norm in {"BRANCO", "NULO"}:
                return ElegibilidadeCandidato(elegivel=True, detalhes={"tipo": "voto_neutro"})
            return self.validador_ca.validar_candidato_chapa(opcao_ou_candidato, self.banco.ca)

        if ctx == "ASSEMBLEIA":
            if opcao_norm in self.OPCOES_PADRAO_ASSEMBLEIA:
                return ElegibilidadeCandidato(elegivel=True, detalhes={"tipo": "deliberacao"})
            return self.validador_assembleia.validar_candidato_conselho(
                candidato_id=opcao_ou_candidato,
                repo=self.banco.assembleia,
            )

        # Contexto CONGRESSO
        if casa is None:
            msg = "Para validação no contexto CONGRESSO, a CasaLegislativa deve ser informada."
            raise ValueError(msg)

        if opcao_norm in self.OPCOES_PADRAO_CONGRESSO:
            return ElegibilidadeCandidato(elegivel=True, detalhes={"tipo": "voto_parlamentar"})

        return self.validador_congresso.validar_materia(
            materia_id=opcao_ou_candidato,
            casa_votacao=casa,
            repo=self.banco.congresso,
        )

    def autorizar_voto(
        self,
        eleitor_id: str,
        opcao: str,
        contexto: str,
        casa: CasaLegislativa | None = None,
        procurador_id: str | None = None,
        momento: datetime | None = None,
        validar_opcao: bool = True,
    ) -> Voto:
        """Valida a aptidão do eleitor e integridade da opção, emitindo o objeto Voto.

        Args:
            eleitor_id: Identificador do eleitor titular ou do acionista outorgante.
            opcao: Chapa escolhida, deliberação ('SIM'/'NAO') ou opção de voto.
            contexto: 'CA', 'ASSEMBLEIA' ou 'CONGRESSO'.
            casa: Casa Legislativa (obrigatório se contexto == 'CONGRESSO').
            procurador_id: ID do procurador caso o voto seja delegado em assembleia.
            momento: Timestamp do registro (padrão: agora UTC).
            validar_opcao: Se True, verifica também a elegibilidade da chapa ou matéria.

        Returns:
            Instância autorizada de Voto com o peso estritamente calculado pelas regras.

        Raises:
            PermissionError: Caso o eleitor não esteja apto a votar.
            ValueError: Caso a opção de voto seja inválida ou inelegível.
        """
        aptidao = self.consultar_aptidao(
            eleitor_id=eleitor_id,
            contexto=contexto,
            casa=casa,
            procurador_id=procurador_id,
            momento=momento,
        )
        if not aptidao.apto:
            msg = (
                f"Eleitor '{eleitor_id}' inapto para votar no contexto "
                f"{contexto}: {aptidao.motivo_inaptidao}"
            )
            raise PermissionError(msg)

        if validar_opcao:
            eleg = self.validar_candidato_ou_opcao(
                opcao_ou_candidato=opcao,
                contexto=contexto,
                casa=casa,
            )
            if not eleg.elegivel:
                msg = (
                    f"Opção ou candidatura '{opcao}' inelegível para votação no contexto "
                    f"{contexto}: {eleg.motivo_inelegibilidade}"
                )
                raise ValueError(msg)

        identificador_registro = (
            f"{eleitor_id}#rep:{procurador_id}" if procurador_id else eleitor_id
        )
        timestamp_voto = momento or datetime.now(UTC)

        return Voto(
            eleitor_id=identificador_registro,
            opcao=opcao.strip().upper(),
            peso=aptidao.peso_voto,
            timestamp=timestamp_voto,
        )

    def autorizar_voto_do_procurador(
        self,
        procurador_id: str,
        opcao: str,
        momento: datetime | None = None,
        validar_opcao: bool = True,
    ) -> Voto:
        """Emite um único voto com todo o poder de voto que o procurador exerce.

        O peso do voto consolida, no momento da emissão, as ações do próprio procurador
        (se for acionista apto) e as de cada outorgante com procuração vigente e apto.
        Todos votam na mesma opção; para votar de forma diferente por algum outorgante,
        use `autorizar_voto` com `procurador_id`.

        Args:
            procurador_id: Procurador que emite o voto.
            opcao: Deliberação ('SIM'/'NAO'/...) ou candidato ao conselho.
            momento: Timestamp do registro (padrão: agora UTC).
            validar_opcao: Se True, verifica também a elegibilidade da opção.

        Returns:
            Voto único com o peso consolidado e os outorgantes em `representados`.

        Raises:
            PermissionError: Caso o procurador não tenha nenhum poder de voto a exercer.
            ValueError: Caso a opção de voto seja inválida ou inelegível.
        """
        poder = self.procuracoes.calcular_poder_de_voto(procurador_id, momento)
        if poder.peso_total == 0:
            msg = (
                f"Procurador '{procurador_id}' sem poder de voto: não possui ações aptas "
                "próprias nem procurações vigentes de acionistas aptos."
            )
            raise PermissionError(msg)

        if validar_opcao:
            eleg = self.validar_candidato_ou_opcao(opcao_ou_candidato=opcao, contexto="ASSEMBLEIA")
            if not eleg.elegivel:
                msg = (
                    f"Opção ou candidatura '{opcao}' inelegível para votação no contexto "
                    f"ASSEMBLEIA: {eleg.motivo_inelegibilidade}"
                )
                raise ValueError(msg)

        return Voto(
            eleitor_id=poder.procurador_id,
            opcao=opcao.strip().upper(),
            peso=poder.peso_total,
            timestamp=momento or datetime.now(UTC),
            representados=poder.outorgantes,
        )

    def _normalizar_contexto(self, contexto: str) -> str:
        ctx = contexto.strip().upper()
        if ctx not in self.CONTEXTOS_VALIDOS:
            msg = (
                f"Contexto de votação desconhecido: '{contexto}'. "
                f"Valores suportados: {', '.join(sorted(self.CONTEXTOS_VALIDOS))}."
            )
            raise ValueError(msg)
        return ctx

"""Validador de elegibilidade para deliberações em Assembleia de Acionistas."""

from datetime import datetime

from votacao.dados.assembleia import RepositorioAssembleia
from votacao.modelos import AptidaoVoto, ElegibilidadeCandidato


class ValidadorElegibilidadeAssembleia:
    """Valida aptidão de acionistas e procuradores, e elegibilidade ao conselho."""

    @staticmethod
    def validar_eleitor(
        acionista_id: str,
        repo: RepositorioAssembleia,
        procurador_id: str | None = None,
        momento: datetime | None = None,
    ) -> AptidaoVoto:
        """Verifica se o acionista (ou seu procurador constituído) está apto a votar.

        Requisitos:
            - Acionista titular cadastrado e com status ativo;
            - Ausência de bloqueio no exercício do direito de voto;
            - Titularidade de ações ordinárias (com direito a voto) > 0;
            - Se exercido via procuração: instrumento formal ativo, cadastrado e dentro do prazo;
            - Se exercido diretamente: ausência de procuração vigente, pois quem delegou o
              voto só volta a votar por conta própria depois de revogar a procuração.

        Retorna:
            AptidaoVoto com peso_voto igual à quantidade de ações ordinárias do titular.
        """
        # Se for votação via representação por procuração
        if procurador_id is not None:
            procuracao = repo.obter_procuracao(acionista_id, procurador_id)
            if procuracao is None:
                return AptidaoVoto(
                    apto=False,
                    peso_voto=0,
                    motivo_inaptidao=(
                        f"Instrumento de procuração não encontrado para o procurador "
                        f"'{procurador_id}' outorgado pelo acionista '{acionista_id}'."
                    ),
                    dados_eleitor={
                        "acionista_id": acionista_id,
                        "procurador_id": procurador_id,
                    },
                )

            if not procuracao.esta_vigente(momento):
                return AptidaoVoto(
                    apto=False,
                    peso_voto=0,
                    motivo_inaptidao=(
                        f"Procuração entre outorgante '{acionista_id}' e procurador "
                        f"'{procurador_id}' encontra-se expirada ou revogada."
                    ),
                    dados_eleitor={
                        "acionista_id": acionista_id,
                        "procurador_id": procurador_id,
                    },
                )

        # Validação do acionista titular
        acionista = repo.obter_acionista(acionista_id)
        if acionista is None:
            return AptidaoVoto(
                apto=False,
                peso_voto=0,
                motivo_inaptidao=(
                    f"Acionista titular '{acionista_id}' não encontrado no livro societário."
                ),
                dados_eleitor={"acionista_id": acionista_id},
            )

        if not acionista.ativo:
            return AptidaoVoto(
                apto=False,
                peso_voto=0,
                motivo_inaptidao=(
                    f"Acionista '{acionista.nome}' (ID {acionista_id}) está com cadastro inativo."
                ),
                dados_eleitor={"acionista_id": acionista_id, "nome": acionista.nome},
            )

        if acionista.bloqueado:
            return AptidaoVoto(
                apto=False,
                peso_voto=0,
                motivo_inaptidao=(
                    f"Acionista '{acionista.nome}' (ID {acionista_id}) possui bloqueio societário "
                    "ou judicial no exercício do voto."
                ),
                dados_eleitor={"acionista_id": acionista_id, "nome": acionista.nome},
            )

        if acionista.acoes_ordinarias <= 0:
            return AptidaoVoto(
                apto=False,
                peso_voto=0,
                motivo_inaptidao=(
                    f"Acionista '{acionista.nome}' (ID {acionista_id}) não possui ações ordinárias "
                    "com direito a voto (apenas ações preferenciais ou saldo zerado)."
                ),
                dados_eleitor={
                    "acionista_id": acionista_id,
                    "nome": acionista.nome,
                    "acoes_ordinarias": acionista.acoes_ordinarias,
                    "acoes_preferenciais": acionista.acoes_preferenciais,
                },
            )

        if procurador_id is None:
            delegacao = repo.obter_procuracao_vigente(acionista_id, momento)
            if delegacao is not None:
                return AptidaoVoto(
                    apto=False,
                    peso_voto=0,
                    motivo_inaptidao=(
                        f"Acionista '{acionista.nome}' (ID {acionista_id}) delegou o voto ao "
                        f"procurador '{delegacao.procurador_id}' por procuração vigente; "
                        "revogue a procuração para votar diretamente."
                    ),
                    dados_eleitor={
                        "acionista_id": acionista_id,
                        "nome": acionista.nome,
                        "procurador_id": delegacao.procurador_id,
                    },
                )

        tipo_voto = "representacao_procuracao" if procurador_id else "titular_direto"
        return AptidaoVoto(
            apto=True,
            peso_voto=acionista.acoes_ordinarias,
            dados_eleitor={
                "acionista_id": acionista.id,
                "nome": acionista.nome,
                "acoes_ordinarias": acionista.acoes_ordinarias,
                "procurador_id": procurador_id,
                "tipo_exercicio": tipo_voto,
            },
        )

    @staticmethod
    def validar_candidato_conselho(
        candidato_id: str, repo: RepositorioAssembleia
    ) -> ElegibilidadeCandidato:
        """Verifica se um postulante ao Conselho cumpre os requisitos societários.

        Requisitos:
            - Candidato cadastrado e ativo;
            - Titularidade das ações mínimas requeridas pelo estatuto;
            - Inexistência de conflito de interesses impeditivo.
        """
        candidato = repo.obter_candidato_conselho(candidato_id)
        if candidato is None:
            return ElegibilidadeCandidato(
                elegivel=False,
                motivo_inelegibilidade=f"Candidato ao conselho '{candidato_id}' não encontrado.",
            )

        if not candidato.ativo:
            return ElegibilidadeCandidato(
                elegivel=False,
                motivo_inelegibilidade=(
                    f"Candidato '{candidato.nome}' (ID {candidato_id}) está desativado."
                ),
            )

        if not candidato.titular_acoes:
            return ElegibilidadeCandidato(
                elegivel=False,
                motivo_inelegibilidade=(
                    f"Candidato '{candidato.nome}' (ID {candidato_id}) não cumpre a titularidade "
                    "mínima exigida pelo estatuto social."
                ),
            )

        if candidato.conflito_interesse:
            return ElegibilidadeCandidato(
                elegivel=False,
                motivo_inelegibilidade=(
                    f"Candidato '{candidato.nome}' (ID {candidato_id}) possui conflito de "
                    "interesses impeditivo para atuação no conselho."
                ),
            )

        return ElegibilidadeCandidato(
            elegivel=True,
            detalhes={"candidato_id": candidato.id, "nome": candidato.nome},
        )

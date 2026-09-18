"""Validador de elegibilidade para eleições do Centro Acadêmico (CA)."""

from votacao.dados.ca import RepositorioCA
from votacao.modelos import AptidaoVoto, ElegibilidadeCandidato


class ValidadorElegibilidadeCA:
    """Valida regras de aptidão de voto para discentes e elegibilidade de chapas."""

    @staticmethod
    def validar_eleitor(ra: str, repo: RepositorioCA) -> AptidaoVoto:
        """Verifica se o discente está apto a votar na eleição do Centro Acadêmico.

        Requisitos:
            - Registro Acadêmico cadastrado na instituição;
            - Matrícula regular ativa;
            - Ausência de suspensão disciplinar vigente.
        """
        discente = repo.obter_discente(ra)
        if discente is None:
            return AptidaoVoto(
                apto=False,
                peso_voto=0,
                motivo_inaptidao=f"Discente com RA '{ra}' não encontrado no cadastro acadêmico.",
            )

        if not discente.matricula_ativa:
            return AptidaoVoto(
                apto=False,
                peso_voto=0,
                motivo_inaptidao=(
                    f"Discente '{discente.nome}' (RA {ra}) não possui matrícula regular ativa."
                ),
                dados_eleitor={"ra": discente.ra, "nome": discente.nome},
            )

        if discente.suspenso:
            return AptidaoVoto(
                apto=False,
                peso_voto=0,
                motivo_inaptidao=(
                    f"Discente '{discente.nome}' (RA {ra}) possui suspensão disciplinar ativa."
                ),
                dados_eleitor={"ra": discente.ra, "nome": discente.nome},
            )

        return AptidaoVoto(
            apto=True,
            peso_voto=1,
            dados_eleitor={
                "ra": discente.ra,
                "nome": discente.nome,
                "curso": discente.curso,
            },
        )

    @staticmethod
    def validar_candidato_chapa(nome_chapa: str, repo: RepositorioCA) -> ElegibilidadeCandidato:
        """Verifica se a chapa cumpre todos os requisitos estatutários do CA.

        Requisitos:
            - Chapa cadastrada e ativa/homologada;
            - Composição de integrantes não vazia;
            - Todos os integrantes cadastrados e com matrícula regular ativa;
            - Nenhum integrante suspenso disciplinarmente;
            - Nenhum integrante apto a se formar no próximo semestre (mandato inviabilizado).
        """
        chapa = repo.obter_chapa(nome_chapa)
        if chapa is None:
            return ElegibilidadeCandidato(
                elegivel=False,
                motivo_inelegibilidade=(
                    f"Chapa '{nome_chapa}' não encontrada no registro eleitoral."
                ),
            )

        if not chapa.ativa:
            return ElegibilidadeCandidato(
                elegivel=False,
                motivo_inelegibilidade=f"Chapa '{chapa.nome}' está inativa ou não foi homologada.",
                detalhes={"nome": chapa.nome},
            )

        if not chapa.integrantes_ra:
            return ElegibilidadeCandidato(
                elegivel=False,
                motivo_inelegibilidade=f"Chapa '{chapa.nome}' não possui integrantes registrados.",
                detalhes={"nome": chapa.nome},
            )

        for ra in chapa.integrantes_ra:
            discente = repo.obter_discente(ra)
            if discente is None:
                return ElegibilidadeCandidato(
                    elegivel=False,
                    motivo_inelegibilidade=(
                        f"Integrante com RA '{ra}' da chapa '{chapa.nome}' "
                        "não foi encontrado no cadastro acadêmico."
                    ),
                    detalhes={"ra_invalido": ra},
                )

            if not discente.matricula_ativa:
                return ElegibilidadeCandidato(
                    elegivel=False,
                    motivo_inelegibilidade=(
                        f"Integrante '{discente.nome}' (RA {ra}) não possui matrícula ativa."
                    ),
                    detalhes={"ra": ra, "nome": discente.nome},
                )

            if discente.suspenso:
                return ElegibilidadeCandidato(
                    elegivel=False,
                    motivo_inelegibilidade=(
                        f"Integrante '{discente.nome}' (RA {ra}) possui suspensão disciplinar."
                    ),
                    detalhes={"ra": ra, "nome": discente.nome},
                )

            if discente.formando_proximo_semestre:
                return ElegibilidadeCandidato(
                    elegivel=False,
                    motivo_inelegibilidade=(
                        f"Integrante '{discente.nome}' (RA {ra}) está apto a se formar "
                        "no próximo semestre, descumprindo o estatuto de permanência da diretoria."
                    ),
                    detalhes={"ra": ra, "nome": discente.nome},
                )

        return ElegibilidadeCandidato(
            elegivel=True,
            detalhes={
                "nome_chapa": chapa.nome,
                "total_integrantes": len(chapa.integrantes_ra),
                "plano_gestao": chapa.plano_gestao,
            },
        )

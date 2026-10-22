"""Validador de elegibilidade para deliberações parlamentares no Congresso Nacional."""

from datetime import datetime
from typing import Any, ClassVar

from votacao.dados.congresso import RepositorioCongresso
from votacao.elegibilidade.base import ValidadorContexto
from votacao.modelos import AptidaoVoto, CasaLegislativa, ElegibilidadeCandidato, Usuario


class ValidadorElegibilidadeCongresso(ValidadorContexto):
    """Valida aptidão de parlamentares para votação e pauta de matérias legislativas."""

    OPCOES_PADRAO: ClassVar[set[str]] = {"SIM", "NAO", "ABSTENCAO", "BRANCO"}

    def autenticar(self, identificador: str, repo: Any) -> Usuario | None:
        """Autentica o parlamentar no cadastro funcional do Congresso."""
        parlamentar = repo.obter_parlamentar(identificador.strip())
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
        repo: Any,
        *,
        casa: CasaLegislativa | None = None,
        procurador_id: str | None = None,
        momento: datetime | None = None,
    ) -> AptidaoVoto:
        """Consulta centralizada de aptidão do parlamentar ao voto na Casa especificada."""
        if casa is None:
            msg = "Para consulta no contexto CONGRESSO, a CasaLegislativa deve ser informada."
            raise ValueError(msg)
        return self.validar_eleitor(
            parlamentar_id=eleitor_id,
            casa_votacao=casa,
            repo=repo,
        )

    def validar_opcao(
        self,
        opcao_ou_candidato: str,
        repo: Any,
        *,
        casa: CasaLegislativa | None = None,
    ) -> ElegibilidadeCandidato:
        """Valida se a opção é voto parlamentar padrão ou matéria pautada."""
        if casa is None:
            msg = "Para validação no contexto CONGRESSO, a CasaLegislativa deve ser informada."
            raise ValueError(msg)
        opcao_norm = opcao_ou_candidato.strip().upper()
        if opcao_norm in self.OPCOES_PADRAO:
            return ElegibilidadeCandidato(elegivel=True, detalhes={"tipo": "voto_parlamentar"})
        return self.validar_materia(
            materia_id=opcao_ou_candidato,
            casa_votacao=casa,
            repo=repo,
        )

    @staticmethod
    def validar_eleitor(
        parlamentar_id: str,
        casa_votacao: CasaLegislativa,
        repo: RepositorioCongresso,
    ) -> AptidaoVoto:
        """Verifica se o parlamentar está apto a votar na sessão plenária da Casa.

        Requisitos:
            - Parlamentar cadastrado na base funcional;
            - Pertencente à Casa da votação (deputado na Câmara, senador no Senado);
            - Não estar em gozo de licença formal (médica/pessoal ou assunção de ministério);
            - Não estar sob suspensão do mandato por Conselho de Ética ou ordem judicial;
            - Estar no exercício efetivo do mandato representativo.
        """
        parlamentar = repo.obter_parlamentar(parlamentar_id)
        if parlamentar is None:
            return AptidaoVoto(
                apto=False,
                peso_voto=0,
                motivo_inaptidao=(
                    f"Parlamentar '{parlamentar_id}' não encontrado no cadastro do Congresso."
                ),
            )

        if parlamentar.casa != casa_votacao:
            return AptidaoVoto(
                apto=False,
                peso_voto=0,
                motivo_inaptidao=(
                    f"Parlamentar '{parlamentar.nome}' é membro do(a) "
                    f"{parlamentar.casa.value} e não possui competência para votar "
                    f"em deliberações do(a) {casa_votacao.value}."
                ),
                dados_eleitor={"parlamentar_id": parlamentar.id, "nome": parlamentar.nome},
            )

        if parlamentar.licenciado:
            return AptidaoVoto(
                apto=False,
                peso_voto=0,
                motivo_inaptidao=(
                    f"Parlamentar '{parlamentar.nome}' encontra-se formalmente "
                    "licenciado do mandato."
                ),
                dados_eleitor={"parlamentar_id": parlamentar.id, "nome": parlamentar.nome},
            )

        if parlamentar.suspenso:
            return AptidaoVoto(
                apto=False,
                peso_voto=0,
                motivo_inaptidao=(
                    f"Parlamentar '{parlamentar.nome}' encontra-se suspenso "
                    "do exercício parlamentar."
                ),
                dados_eleitor={"parlamentar_id": parlamentar.id, "nome": parlamentar.nome},
            )

        if not parlamentar.em_exercicio:
            return AptidaoVoto(
                apto=False,
                peso_voto=0,
                motivo_inaptidao=(
                    f"Parlamentar '{parlamentar.nome}' não está no exercício efetivo do mandato."
                ),
                dados_eleitor={"parlamentar_id": parlamentar.id, "nome": parlamentar.nome},
            )

        return AptidaoVoto(
            apto=True,
            peso_voto=1,
            dados_eleitor={
                "id": parlamentar.id,
                "nome": parlamentar.nome,
                "casa": parlamentar.casa.value,
                "partido": parlamentar.partido,
                "uf": parlamentar.uf,
            },
        )

    @staticmethod
    def validar_materia(
        materia_id: str,
        casa_votacao: CasaLegislativa,
        repo: RepositorioCongresso,
    ) -> ElegibilidadeCandidato:
        """Verifica se a matéria legislativa está apta para deliberação na sessão.

        Requisitos:
            - Matéria devidamente registrada e pautada (ativa);
            - Tramitação ocorrendo na Casa legislativa da votação atual.
        """
        materia = repo.obter_materia(materia_id)
        if materia is None:
            return ElegibilidadeCandidato(
                elegivel=False,
                motivo_inelegibilidade=f"Matéria legislativa '{materia_id}' não encontrada.",
            )

        if not materia.ativa:
            return ElegibilidadeCandidato(
                elegivel=False,
                motivo_inelegibilidade=(
                    f"Matéria '{materia.id}' não se encontra pautada ou está arquivada."
                ),
                detalhes={"id": materia.id},
            )

        if materia.casa_atual != casa_votacao:
            return ElegibilidadeCandidato(
                elegivel=False,
                motivo_inelegibilidade=(
                    f"Matéria '{materia.id}' está pautada para tramitação "
                    f"na {materia.casa_atual.value}, não na {casa_votacao.value}."
                ),
                detalhes={"id": materia.id, "casa_materia": materia.casa_atual.value},
            )

        return ElegibilidadeCandidato(
            elegivel=True,
            detalhes={
                "id": materia.id,
                "tipo": materia.tipo.value,
                "casa": materia.casa_atual.value,
                "titulo": materia.titulo,
            },
        )

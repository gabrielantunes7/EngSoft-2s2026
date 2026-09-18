"""Modelos e repositório de dados mockados para o Centro Acadêmico (CA)."""

from dataclasses import dataclass, field

from votacao.dados.base import RepositorioBase


@dataclass(frozen=True)
class Discente:
    """Representa um discente universitário no banco de dados acadêmico.

    Attributes:
        ra: Registro Acadêmico único do estudante.
        nome: Nome completo do aluno.
        curso: Nome ou código do curso de graduação/pós.
        matricula_ativa: Indica se o estudante está regularmente matriculado.
        formando_proximo_semestre: Indica se está no período letivo imediatamente
            anterior à conclusão do curso (impedimento para compor chapa).
        suspenso: Indica se possui suspensão disciplinar ativa.
    """

    ra: str
    nome: str
    curso: str
    matricula_ativa: bool = True
    formando_proximo_semestre: bool = False
    suspenso: bool = False

    def __post_init__(self) -> None:
        if not self.ra.strip():
            msg = "O RA do discente não pode ser vazio."
            raise ValueError(msg)
        if not self.nome.strip():
            msg = "O nome do discente não pode ser vazio."
            raise ValueError(msg)


@dataclass(frozen=True)
class ChapaCA:
    """Representa uma chapa concorrente à eleição de diretoria do CA.

    Attributes:
        nome: Nome ou número identificador da chapa.
        integrantes_ra: Lista/tupla de RAs dos discentes que compõem a chapa.
        plano_gestao: Resumo ou diretrizes do plano de gestão submetido.
        ativa: Indica se a chapa está homologada e apta a receber votos.
    """

    nome: str
    integrantes_ra: tuple[str, ...] = field(default_factory=tuple)
    plano_gestao: str = ""
    ativa: bool = True

    def __post_init__(self) -> None:
        if not self.nome.strip():
            msg = "O nome da chapa não pode ser vazio."
            raise ValueError(msg)


class RepositorioCA(RepositorioBase):
    """Repositório em memória para persistência mockada de discentes e chapas do CA."""

    def __init__(self) -> None:
        self._discentes: dict[str, Discente] = {}
        self._chapas: dict[str, ChapaCA] = {}

    def adicionar_discente(self, discente: Discente) -> None:
        """Cadastra ou atualiza um discente no repositório."""
        self._discentes[discente.ra.strip()] = discente

    def obter_discente(self, ra: str) -> Discente | None:
        """Busca um discente pelo RA."""
        return self._discentes.get(ra.strip())

    def listar_discentes(self) -> list[Discente]:
        """Retorna todos os discentes cadastrados."""
        return list(self._discentes.values())

    def adicionar_chapa(self, chapa: ChapaCA) -> None:
        """Cadastra ou atualiza uma chapa no repositório."""
        self._chapas[chapa.nome.strip().upper()] = chapa

    def obter_chapa(self, nome: str) -> ChapaCA | None:
        """Busca uma chapa pelo nome (case-insensitive)."""
        return self._chapas.get(nome.strip().upper())

    def listar_chapas(self) -> list[ChapaCA]:
        """Retorna todas as chapas cadastradas."""
        return list(self._chapas.values())

    def limpar(self) -> None:
        """Remove todos os dados de discentes e chapas."""
        self._discentes.clear()
        self._chapas.clear()

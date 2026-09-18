"""Modelos e repositório de dados mockados para o Congresso Nacional."""

from dataclasses import dataclass

from votacao.dados.base import RepositorioBase
from votacao.modelos import CasaLegislativa, TipoMateriaCongresso


@dataclass(frozen=True)
class Parlamentar:
    """Representa um deputado federal ou senador no cadastro parlamentar.

    Attributes:
        id: Identificador parlamentar único (matrícula/código funcional).
        nome: Nome parlamentar completo.
        casa: Casa legislativa de atuação (CAMARA ou SENADO).
        partido: Sigla do partido político.
        uf: Unidade Federativa de representação (ex: 'SP', 'RJ', 'DF').
        em_exercicio: Indica se o parlamentar está no exercício regular do mandato.
        licenciado: Indica se o parlamentar está de licença médica/pessoal ou cargo no executivo.
        suspenso: Indica se está suspenso pelo Conselho de Ética ou decisão judicial.
    """

    id: str
    nome: str
    casa: CasaLegislativa
    partido: str
    uf: str
    em_exercicio: bool = True
    licenciado: bool = False
    suspenso: bool = False

    def __post_init__(self) -> None:
        if not self.id.strip():
            msg = "O identificador do parlamentar não pode ser vazio."
            raise ValueError(msg)
        if not self.nome.strip():
            msg = "O nome do parlamentar não pode ser vazio."
            raise ValueError(msg)
        if not self.partido.strip():
            msg = "O partido do parlamentar não pode ser vazio."
            raise ValueError(msg)
        if not self.uf.strip():
            msg = "A UF do parlamentar não pode ser vazia."
            raise ValueError(msg)


@dataclass(frozen=True)
class MateriaLegislativa:
    """Representa uma proposição legislativa submetida a votação em plenário.

    Attributes:
        id: Identificador oficial da matéria (ex: 'PL-1234/2026', 'PEC-45/2026').
        tipo: Tipo da matéria legislativa com rito constitucional próprio.
        casa_atual: Casa onde a votação da matéria está ocorrendo (CAMARA ou SENADO).
        titulo: Ementa ou resumo do projeto de lei/emenda.
        ativa: Indica se a matéria está pautada para deliberação na sessão.
    """

    id: str
    tipo: TipoMateriaCongresso
    casa_atual: CasaLegislativa
    titulo: str = ""
    ativa: bool = True

    def __post_init__(self) -> None:
        if not self.id.strip():
            msg = "O identificador da matéria legislativa não pode ser vazio."
            raise ValueError(msg)


class RepositorioCongresso(RepositorioBase):
    """Repositório em memória para persistência mockada de parlamentares e matérias."""

    def __init__(self) -> None:
        self._parlamentares: dict[str, Parlamentar] = {}
        self._materias: dict[str, MateriaLegislativa] = {}

    def adicionar_parlamentar(self, parlamentar: Parlamentar) -> None:
        """Cadastra ou atualiza um parlamentar no repositório."""
        self._parlamentares[parlamentar.id.strip()] = parlamentar

    def obter_parlamentar(self, id_parlamentar: str) -> Parlamentar | None:
        """Busca um parlamentar pelo identificador funcional."""
        return self._parlamentares.get(id_parlamentar.strip())

    def listar_parlamentares(self, casa: CasaLegislativa | None = None) -> list[Parlamentar]:
        """Retorna lista de parlamentares cadastrados, opcionalmente filtrados por Casa."""
        if casa is None:
            return list(self._parlamentares.values())
        return [p for p in self._parlamentares.values() if p.casa == casa]

    def total_em_exercicio(self, casa: CasaLegislativa) -> int:
        """Contabiliza quantos membros da Casa estão no exercício do mandato."""
        return sum(
            1
            for p in self._parlamentares.values()
            if p.casa == casa and p.em_exercicio and not p.licenciado and not p.suspenso
        )

    def adicionar_materia(self, materia: MateriaLegislativa) -> None:
        """Cadastra ou atualiza uma matéria legislativa pautada."""
        self._materias[materia.id.strip().upper()] = materia

    def obter_materia(self, id_materia: str) -> MateriaLegislativa | None:
        """Busca uma matéria legislativa pelo identificador."""
        return self._materias.get(id_materia.strip().upper())

    def listar_materias(self, casa: CasaLegislativa | None = None) -> list[MateriaLegislativa]:
        """Retorna todas as matérias pautadas, opcionalmente filtradas por Casa."""
        if casa is None:
            return list(self._materias.values())
        return [m for m in self._materias.values() if m.casa_atual == casa]

    def limpar(self) -> None:
        """Remove todos os dados de parlamentares e matérias legislativas."""
        self._parlamentares.clear()
        self._materias.clear()

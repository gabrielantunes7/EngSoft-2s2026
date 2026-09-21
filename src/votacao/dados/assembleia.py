"""Modelos e repositório de dados mockados para Assembleias de Acionistas."""

from dataclasses import dataclass
from datetime import UTC, datetime

from votacao.dados.base import RepositorioBase


@dataclass(frozen=True)
class Acionista:
    """Representa um investidor acionista no livro de registro de ações.

    Attributes:
        id: Identificador único (CPF, CNPJ ou código de custódia).
        nome: Razão social ou nome civil do acionista.
        acoes_ordinarias: Quantidade de ações ordinárias (com direito a voto).
        acoes_preferenciais: Quantidade de ações preferenciais (sem direito a voto).
        bloqueado: Indica se há bloqueio judicial ou restrição estatutária no exercício do voto.
        ativo: Indica se o cadastro acionário está ativo.
    """

    id: str
    nome: str
    acoes_ordinarias: int
    acoes_preferenciais: int = 0
    bloqueado: bool = False
    ativo: bool = True

    def __post_init__(self) -> None:
        if not self.id.strip():
            msg = "O identificador do acionista não pode ser vazio."
            raise ValueError(msg)
        if not self.nome.strip():
            msg = "O nome do acionista não pode ser vazio."
            raise ValueError(msg)
        if self.acoes_ordinarias < 0:
            msg = "A quantidade de ações ordinárias não pode ser negativa."
            raise ValueError(msg)
        if self.acoes_preferenciais < 0:
            msg = "A quantidade de ações preferenciais não pode ser negativa."
            raise ValueError(msg)


@dataclass(frozen=True)
class Procuracao:
    """Instrumento legal de mandato e representação de voto em assembleia.

    Attributes:
        outorgante_id: ID do acionista titular que transfere os poderes de voto.
        procurador_id: ID ou CPF do representante legalmente constituído.
        data_expiracao: Data e hora limite de validade do instrumento.
        ativa: Indica se o instrumento permanece vigente e não revogado.
    """

    outorgante_id: str
    procurador_id: str
    data_expiracao: datetime | None = None
    ativa: bool = True

    def __post_init__(self) -> None:
        if not self.outorgante_id.strip():
            msg = "O outorgante da procuração não pode ser vazio."
            raise ValueError(msg)
        if not self.procurador_id.strip():
            msg = "O procurador da procuração não pode ser vazio."
            raise ValueError(msg)

    def esta_vigente(self, momento: datetime | None = None) -> bool:
        """Verifica se a procuração está ativa e não expirada no momento dado."""
        if not self.ativa:
            return False
        if self.data_expiracao is not None:
            referencia = momento or datetime.now(UTC)
            if self.data_expiracao.tzinfo is None and referencia.tzinfo is not None:
                referencia = referencia.replace(tzinfo=None)
            elif self.data_expiracao.tzinfo is not None and referencia.tzinfo is None:
                referencia = referencia.replace(tzinfo=UTC)
            if referencia > self.data_expiracao:
                return False
        return True


@dataclass(frozen=True)
class Procurador:
    """Representante habilitado a receber procurações de voto em assembleia.

    Attributes:
        id: Identificador único do procurador (CPF, CNPJ ou código de credenciamento).
        nome: Nome civil ou razão social do procurador.
        credenciado: Indica se o credenciamento perante a companhia está regular.
        ativo: Indica se o cadastro do procurador está ativo.
    """

    id: str
    nome: str
    credenciado: bool = True
    ativo: bool = True

    def __post_init__(self) -> None:
        if not self.id.strip():
            msg = "O identificador do procurador não pode ser vazio."
            raise ValueError(msg)
        if not self.nome.strip():
            msg = "O nome do procurador não pode ser vazio."
            raise ValueError(msg)


@dataclass(frozen=True)
class CandidatoConselho:
    """Candidato à eleição de Conselho de Administração ou Diretoria.

    Attributes:
        id: Identificador único do postulante.
        nome: Nome completo do candidato.
        titular_acoes: Se é titular de cotas/ações exigidas pelo estatuto.
        conflito_interesse: Se possui impedimento legal por conflito de interesse.
        ativo: Se a candidatura está homologada para deliberação.
    """

    id: str
    nome: str
    titular_acoes: bool = True
    conflito_interesse: bool = False
    ativo: bool = True

    def __post_init__(self) -> None:
        if not self.id.strip():
            msg = "O ID do candidato ao conselho não pode ser vazio."
            raise ValueError(msg)
        if not self.nome.strip():
            msg = "O nome do candidato ao conselho não pode ser vazio."
            raise ValueError(msg)


class RepositorioAssembleia(RepositorioBase):
    """Repositório em memória para persistência mockada de acionistas e procurações."""

    def __init__(self) -> None:
        self._acionistas: dict[str, Acionista] = {}
        self._procuracoes: dict[tuple[str, str], Procuracao] = {}
        self._procuradores: dict[str, Procurador] = {}
        self._candidatos: dict[str, CandidatoConselho] = {}

    def adicionar_acionista(self, acionista: Acionista) -> None:
        """Cadastra ou atualiza um acionista no repositório."""
        self._acionistas[acionista.id.strip()] = acionista

    def obter_acionista(self, id_acionista: str) -> Acionista | None:
        """Busca um acionista pelo identificador."""
        return self._acionistas.get(id_acionista.strip())

    def listar_acionistas(self) -> list[Acionista]:
        """Retorna todos os acionistas cadastrados."""
        return list(self._acionistas.values())

    def total_capital_votante(self) -> int:
        """Calcula a soma das ações ordinárias de todos os acionistas ativos."""
        return sum(
            a.acoes_ordinarias for a in self._acionistas.values() if a.ativo and not a.bloqueado
        )

    def adicionar_procuracao(self, procuracao: Procuracao) -> None:
        """Registra ou atualiza um instrumento de procuração."""
        chave = (procuracao.outorgante_id.strip(), procuracao.procurador_id.strip())
        self._procuracoes[chave] = procuracao

    def obter_procuracao(self, outorgante_id: str, procurador_id: str) -> Procuracao | None:
        """Recupera procuração entre outorgante e procurador específicos."""
        chave = (outorgante_id.strip(), procurador_id.strip())
        return self._procuracoes.get(chave)

    def listar_procuracoes_do_outorgante(self, outorgante_id: str) -> list[Procuracao]:
        """Lista todas as procurações emitidas por um dado acionista."""
        return [p for p in self._procuracoes.values() if p.outorgante_id == outorgante_id.strip()]

    def listar_procuracoes_do_procurador(self, procurador_id: str) -> list[Procuracao]:
        """Lista todas as procurações recebidas por um dado procurador."""
        return [p for p in self._procuracoes.values() if p.procurador_id == procurador_id.strip()]

    def adicionar_procurador(self, procurador: Procurador) -> None:
        """Cadastra ou atualiza um procurador no repositório."""
        self._procuradores[procurador.id.strip()] = procurador

    def obter_procurador(self, id_procurador: str) -> Procurador | None:
        """Busca um procurador pelo identificador."""
        return self._procuradores.get(id_procurador.strip())

    def listar_procuradores(self) -> list[Procurador]:
        """Retorna todos os procuradores cadastrados."""
        return list(self._procuradores.values())

    def adicionar_candidato_conselho(self, candidato: CandidatoConselho) -> None:
        """Registra uma candidatura ao conselho."""
        self._candidatos[candidato.id.strip()] = candidato

    def obter_candidato_conselho(self, id_candidato: str) -> CandidatoConselho | None:
        """Busca um candidato ao conselho pelo ID."""
        return self._candidatos.get(id_candidato.strip())

    def listar_candidatos_conselho(self) -> list[CandidatoConselho]:
        """Retorna todos os candidatos ao conselho cadastrados."""
        return list(self._candidatos.values())

    def limpar(self) -> None:
        """Remove todos os dados acionários, procurações, procuradores e candidaturas."""
        self._acionistas.clear()
        self._procuracoes.clear()
        self._procuradores.clear()
        self._candidatos.clear()

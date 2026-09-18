"""Dados simulados padrão (seed) e agregador de banco de dados mockado."""

from datetime import UTC, datetime, timedelta

from votacao.dados.assembleia import (
    Acionista,
    CandidatoConselho,
    Procuracao,
    RepositorioAssembleia,
)
from votacao.dados.ca import ChapaCA, Discente, RepositorioCA
from votacao.dados.congresso import (
    MateriaLegislativa,
    Parlamentar,
    RepositorioCongresso,
)
from votacao.modelos import CasaLegislativa, TipoMateriaCongresso


def carregar_dados_padrao_ca(repo: RepositorioCA | None = None) -> RepositorioCA:
    """Preenche o repositório do Centro Acadêmico com discentes e chapas simulados."""
    r = repo if repo is not None else RepositorioCA()

    # Discentes aptos regulares
    r.adicionar_discente(
        Discente(ra="247314", nome="Lucas Bussinger", curso="Engenharia de Software")
    )
    r.adicionar_discente(
        Discente(ra="242352", nome="Gabriel Montagna", curso="Engenharia de Software")
    )
    r.adicionar_discente(
        Discente(ra="281199", nome="Gabriel Antunes", curso="Engenharia de Software")
    )
    r.adicionar_discente(Discente(ra="254467", nome="Lucas Lembo", curso="Engenharia de Software"))
    r.adicionar_discente(Discente(ra="205237", nome="Rafael Dosso", curso="Engenharia de Software"))

    # Discente formando no próximo semestre (inapto para chapa, apto para votar)
    r.adicionar_discente(
        Discente(
            ra="111222",
            nome="Mariana Veterana",
            curso="Engenharia de Software",
            formando_proximo_semestre=True,
        )
    )

    # Discente com matrícula trancada/inativa (inapto para votar e concorrer)
    r.adicionar_discente(
        Discente(
            ra="333444",
            nome="Carlos Trancado",
            curso="Engenharia de Software",
            matricula_ativa=False,
        )
    )

    # Discente suspenso disciplinarmente
    r.adicionar_discente(
        Discente(
            ra="555666",
            nome="Juliana Suspensa",
            curso="Engenharia de Software",
            suspenso=True,
        )
    )

    # Chapas registradas
    r.adicionar_chapa(
        ChapaCA(
            nome="Chapa Renova",
            integrantes_ra=("247314", "242352", "281199"),
            plano_gestao="Integração universidade-empresa e melhorias laboratoriais.",
            ativa=True,
        )
    )
    r.adicionar_chapa(
        ChapaCA(
            nome="Chapa Futuro",
            integrantes_ra=("254467", "205237"),
            plano_gestao="Acessibilidade, transparência e acolhimento estudantil.",
            ativa=True,
        )
    )
    r.adicionar_chapa(
        ChapaCA(
            nome="Chapa Invalida",
            integrantes_ra=("111222",),  # Contém aluna formando no próximo semestre
            plano_gestao="Gestão de transição rápida.",
            ativa=True,
        )
    )
    r.adicionar_chapa(
        ChapaCA(
            nome="Chapa Desistente",
            integrantes_ra=("247314",),
            plano_gestao="Desistência formal antes do pleito.",
            ativa=False,
        )
    )

    return r


def carregar_dados_padrao_assembleia(
    repo: RepositorioAssembleia | None = None,
) -> RepositorioAssembleia:
    """Preenche o repositório de assembleia com acionistas e procurações simuladas."""
    r = repo if repo is not None else RepositorioAssembleia()

    # Acionistas titulares
    r.adicionar_acionista(
        Acionista(
            id="AC-001",
            nome="Holding Alpha Participações S.A.",
            acoes_ordinarias=500_000,
            acoes_preferenciais=100_000,
        )
    )
    r.adicionar_acionista(
        Acionista(
            id="AC-002",
            nome="Fundo Beta Capital",
            acoes_ordinarias=300_000,
            acoes_preferenciais=50_000,
        )
    )
    r.adicionar_acionista(
        Acionista(
            id="AC-003",
            nome="Investidor Individual Silva",
            acoes_ordinarias=150_000,
            acoes_preferenciais=0,
        )
    )
    r.adicionar_acionista(
        Acionista(
            id="AC-004",
            nome="Investidor Sem Direito a Voto",
            acoes_ordinarias=0,
            acoes_preferenciais=80_000,
        )
    )
    r.adicionar_acionista(
        Acionista(
            id="AC-005",
            nome="Acionista Bloqueado Judicial",
            acoes_ordinarias=100_000,
            bloqueado=True,
        )
    )
    r.adicionar_acionista(
        Acionista(
            id="AC-006",
            nome="Acionista Desativado",
            acoes_ordinarias=50_000,
            ativo=False,
        )
    )

    # Procurações
    agora = datetime.now(UTC)
    r.adicionar_procuracao(
        Procuracao(
            outorgante_id="AC-001",
            procurador_id="PROC-101",
            data_expiracao=agora + timedelta(days=30),
            ativa=True,
        )
    )
    r.adicionar_procuracao(
        Procuracao(
            outorgante_id="AC-002",
            procurador_id="PROC-102",
            data_expiracao=agora - timedelta(days=1),  # Expirada
            ativa=True,
        )
    )
    r.adicionar_procuracao(
        Procuracao(
            outorgante_id="AC-003",
            procurador_id="PROC-103",
            data_expiracao=agora + timedelta(days=30),
            ativa=False,  # Revogada
        )
    )

    # Candidatos a Conselho
    r.adicionar_candidato_conselho(
        CandidatoConselho(
            id="CONS-01",
            nome="Dr. Roberto Conselheiro",
            titular_acoes=True,
            conflito_interesse=False,
        )
    )
    r.adicionar_candidato_conselho(
        CandidatoConselho(
            id="CONS-02",
            nome="Concorrente Direto Impedido",
            titular_acoes=True,
            conflito_interesse=True,
        )
    )

    return r


def carregar_dados_padrao_congresso(
    repo: RepositorioCongresso | None = None,
) -> RepositorioCongresso:
    """Preenche o repositório do Congresso Nacional com parlamentares e matérias."""
    r = repo if repo is not None else RepositorioCongresso()

    # Deputados Federais
    r.adicionar_parlamentar(
        Parlamentar(
            id="DEP-001",
            nome="Deputada Maria Silva",
            casa=CasaLegislativa.CAMARA,
            partido="PUNI",
            uf="SP",
            em_exercicio=True,
        )
    )
    r.adicionar_parlamentar(
        Parlamentar(
            id="DEP-002",
            nome="Deputado João Santos",
            casa=CasaLegislativa.CAMARA,
            partido="PENG",
            uf="RJ",
            em_exercicio=True,
        )
    )
    r.adicionar_parlamentar(
        Parlamentar(
            id="DEP-003",
            nome="Deputado Licenciado (Ministro)",
            casa=CasaLegislativa.CAMARA,
            partido="PUNI",
            uf="MG",
            em_exercicio=False,
            licenciado=True,
        )
    )
    r.adicionar_parlamentar(
        Parlamentar(
            id="DEP-004",
            nome="Deputado Suspenso",
            casa=CasaLegislativa.CAMARA,
            partido="PENG",
            uf="RS",
            em_exercicio=False,
            suspenso=True,
        )
    )

    # Senadores
    r.adicionar_parlamentar(
        Parlamentar(
            id="SEN-001",
            nome="Senadora Ana Oliveira",
            casa=CasaLegislativa.SENADO,
            partido="PUNI",
            uf="SP",
            em_exercicio=True,
        )
    )
    r.adicionar_parlamentar(
        Parlamentar(
            id="SEN-002",
            nome="Senador Marcos Souza",
            casa=CasaLegislativa.SENADO,
            partido="PENG",
            uf="BA",
            em_exercicio=True,
        )
    )
    r.adicionar_parlamentar(
        Parlamentar(
            id="SEN-003",
            nome="Senador Licenciado",
            casa=CasaLegislativa.SENADO,
            partido="PUNI",
            uf="PR",
            em_exercicio=False,
            licenciado=True,
        )
    )

    # Matérias Legislativas
    r.adicionar_materia(
        MateriaLegislativa(
            id="PL-101/2026",
            tipo=TipoMateriaCongresso.LEI_ORDINARIA,
            casa_atual=CasaLegislativa.CAMARA,
            titulo="Incentivo a laboratórios de software aberto.",
            ativa=True,
        )
    )
    r.adicionar_materia(
        MateriaLegislativa(
            id="PLP-202/2026",
            tipo=TipoMateriaCongresso.LEI_COMPLEMENTAR,
            casa_atual=CasaLegislativa.CAMARA,
            titulo="Normas complementares para votação eletrônica auditável.",
            ativa=True,
        )
    )
    r.adicionar_materia(
        MateriaLegislativa(
            id="PEC-50/2026",
            tipo=TipoMateriaCongresso.PEC,
            casa_atual=CasaLegislativa.SENADO,
            titulo="Emenda Constitucional de Modernização da Cidadania Digital.",
            ativa=True,
        )
    )
    r.adicionar_materia(
        MateriaLegislativa(
            id="PL-ARQUIVADO",
            tipo=TipoMateriaCongresso.LEI_ORDINARIA,
            casa_atual=CasaLegislativa.CAMARA,
            titulo="Projeto retirado de pauta.",
            ativa=False,
        )
    )

    return r


class BancoDadosMock:
    """Contêiner que agrega repositórios mockados e banco relacional SQL para todos os domínios."""

    def __init__(self, popular: bool = True, usar_sql: bool = False) -> None:
        from votacao.dados.banco_sql import BancoDadosSQL

        self.ca = RepositorioCA()
        self.assembleia = RepositorioAssembleia()
        self.congresso = RepositorioCongresso()
        self.banco_sql = BancoDadosSQL()
        self.banco_sql.inicializar_schema()
        self.banco_sql.carregar_seeds()

        if popular:
            if usar_sql:
                self.recarregar_dados_do_sql()
            else:
                self.recarregar_dados_padrao()

    def recarregar_dados_padrao(self) -> None:
        """Limpa e reinsere os dados simulados padrão em todos os repositórios via código."""
        self.limpar_todos()
        carregar_dados_padrao_ca(self.ca)
        carregar_dados_padrao_assembleia(self.assembleia)
        carregar_dados_padrao_congresso(self.congresso)

    def recarregar_dados_do_sql(self) -> None:
        """Limpa e popula os repositórios lendo diretamente das tabelas SQL relacionais."""
        self.limpar_todos()
        self.banco_sql.carregar_repositorios_a_partir_do_sql(
            repo_ca=self.ca,
            repo_assembleia=self.assembleia,
            repo_congresso=self.congresso,
        )

    def limpar_todos(self) -> None:
        """Esvazia todos os repositórios gerenciados."""
        self.ca.limpar()
        self.assembleia.limpar()
        self.congresso.limpar()

"""Testes da delegação de voto: procurador credenciado, procurações e poder de voto."""

from datetime import UTC, datetime, timedelta

import pytest

from votacao.dados import (
    Acionista,
    BancoDadosMock,
    Procuracao,
    Procurador,
    RepositorioAssembleia,
)
from votacao.procuracoes import ProcuracaoInvalidaError, ServicoProcuracao

AGORA = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
EM_30_DIAS = AGORA + timedelta(days=30)


@pytest.fixture
def repo() -> RepositorioAssembleia:
    repo = RepositorioAssembleia()
    repo.adicionar_acionista(Acionista(id="AC-A", nome="Alfa", acoes_ordinarias=100))
    repo.adicionar_acionista(Acionista(id="AC-B", nome="Beta", acoes_ordinarias=50))
    repo.adicionar_acionista(
        Acionista(id="AC-BLOQUEADO", nome="Bloqueado", acoes_ordinarias=10, bloqueado=True)
    )
    repo.adicionar_acionista(
        Acionista(id="AC-INATIVO", nome="Inativo", acoes_ordinarias=10, ativo=False)
    )
    repo.adicionar_acionista(
        Acionista(id="AC-PREF", nome="Preferencialista", acoes_ordinarias=0, acoes_preferenciais=30)
    )
    repo.adicionar_procurador(Procurador(id="PROC-1", nome="Advocacia Um"))
    repo.adicionar_procurador(Procurador(id="PROC-2", nome="Advocacia Dois"))
    repo.adicionar_procurador(
        Procurador(id="PROC-DESCRED", nome="Sem Credencial", credenciado=False)
    )
    repo.adicionar_procurador(Procurador(id="PROC-INATIVO", nome="Encerrado", ativo=False))
    return repo


@pytest.fixture
def servico(repo: RepositorioAssembleia) -> ServicoProcuracao:
    return ServicoProcuracao(repo)


# --- Procurador credenciado ---


def test_procurador_nasce_credenciado_e_ativo():
    procurador = Procurador(id="PROC-1", nome="Advocacia Alfa")

    assert procurador.credenciado is True
    assert procurador.ativo is True


@pytest.mark.parametrize(
    ("id_procurador", "nome", "mensagem"),
    [
        pytest.param("  ", "Advocacia Alfa", "identificador do procurador", id="id-vazio"),
        pytest.param("PROC-1", "  ", "nome do procurador", id="nome-vazio"),
    ],
)
def test_procurador_recusa_campos_vazios(id_procurador: str, nome: str, mensagem: str):
    with pytest.raises(ValueError, match=mensagem):
        Procurador(id=id_procurador, nome=nome)


def test_repositorio_cadastra_e_consulta_procurador_ignorando_espacos():
    repo = RepositorioAssembleia()
    procurador = Procurador(id=" PROC-1 ", nome="Advocacia Alfa")

    repo.adicionar_procurador(procurador)

    assert repo.obter_procurador("PROC-1") == procurador
    assert repo.obter_procurador("PROC-INEXISTENTE") is None
    assert repo.listar_procuradores() == [procurador]


def test_repositorio_atualiza_procurador_descredenciado():
    repo = RepositorioAssembleia()
    repo.adicionar_procurador(Procurador(id="PROC-1", nome="Advocacia Alfa"))

    repo.adicionar_procurador(Procurador(id="PROC-1", nome="Advocacia Alfa", credenciado=False))

    assert len(repo.listar_procuradores()) == 1
    assert repo.obter_procurador("PROC-1").credenciado is False


def test_repositorio_lista_apenas_procuracoes_do_procurador():
    repo = RepositorioAssembleia()
    de_a = Procuracao(outorgante_id="AC-A", procurador_id="PROC-1")
    de_b = Procuracao(outorgante_id="AC-B", procurador_id="PROC-1")
    de_c = Procuracao(outorgante_id="AC-C", procurador_id="PROC-2")
    for procuracao in (de_a, de_b, de_c):
        repo.adicionar_procuracao(procuracao)

    assert repo.listar_procuracoes_do_procurador(" PROC-1 ") == [de_a, de_b]
    assert repo.listar_procuracoes_do_procurador("PROC-INEXISTENTE") == []


def test_limpar_remove_procuradores_junto_com_o_resto():
    repo = RepositorioAssembleia()
    repo.adicionar_acionista(Acionista(id="AC-A", nome="Alfa", acoes_ordinarias=10))
    repo.adicionar_procurador(Procurador(id="PROC-1", nome="Advocacia Alfa"))

    repo.limpar()

    assert repo.listar_procuradores() == []
    assert repo.listar_acionistas() == []


def test_dados_padrao_cadastram_como_credenciado_todo_procurador_das_procuracoes():
    repo = BancoDadosMock().assembleia
    procuracoes = [
        p
        for acionista in repo.listar_acionistas()
        for p in repo.listar_procuracoes_do_outorgante(acionista.id)
    ]

    assert procuracoes, "os dados padrão devem trazer procurações de exemplo"
    for procuracao in procuracoes:
        procurador = repo.obter_procurador(procuracao.procurador_id)
        assert procurador is not None, procuracao.procurador_id
        assert procurador.credenciado
        assert procurador.ativo


# --- Cadastro de procurações ---


def test_cadastra_procuracao_vigente_e_a_registra_no_repositorio(
    servico: ServicoProcuracao, repo: RepositorioAssembleia
):
    procuracao = servico.cadastrar("AC-A", "PROC-1", data_expiracao=EM_30_DIAS, momento=AGORA)

    assert procuracao.outorgante_id == "AC-A"
    assert procuracao.procurador_id == "PROC-1"
    assert procuracao.data_expiracao == EM_30_DIAS
    assert procuracao.esta_vigente(AGORA)
    assert repo.obter_procuracao("AC-A", "PROC-1") == procuracao


def test_cadastra_procuracao_sem_prazo_e_sem_informar_o_momento(servico: ServicoProcuracao):
    procuracao = servico.cadastrar(" AC-A ", " PROC-1 ")

    assert procuracao.outorgante_id == "AC-A"
    assert procuracao.data_expiracao is None
    assert procuracao.esta_vigente()


def test_cadastra_com_expiracao_relativa_ao_relogio_real_quando_sem_momento(
    servico: ServicoProcuracao,
):
    amanha = datetime.now(UTC) + timedelta(days=1)

    procuracao = servico.cadastrar("AC-A", "PROC-1", data_expiracao=amanha)

    assert procuracao.esta_vigente()


@pytest.mark.parametrize(
    ("outorgante", "trecho"),
    [
        pytest.param("AC-FANTASMA", "não encontrado", id="inexistente"),
        pytest.param("AC-INATIVO", "cadastro inativo", id="inativo"),
        pytest.param("AC-BLOQUEADO", "bloqueio", id="bloqueado"),
        pytest.param("AC-PREF", "não possui ações ordinárias", id="sem-direito-a-voto"),
    ],
)
def test_recusa_outorgante_que_nao_pode_delegar(
    servico: ServicoProcuracao, repo: RepositorioAssembleia, outorgante: str, trecho: str
):
    with pytest.raises(ProcuracaoInvalidaError, match=trecho):
        servico.cadastrar(outorgante, "PROC-1", momento=AGORA)

    assert repo.listar_procuracoes_do_procurador("PROC-1") == []


@pytest.mark.parametrize(
    ("procurador", "trecho"),
    [
        pytest.param("PROC-FANTASMA", "não está cadastrado", id="nao-cadastrado"),
        pytest.param("PROC-DESCRED", "não está credenciado", id="descredenciado"),
        pytest.param("PROC-INATIVO", "cadastro inativo", id="inativo"),
    ],
)
def test_recusa_procurador_nao_credenciado(
    servico: ServicoProcuracao, repo: RepositorioAssembleia, procurador: str, trecho: str
):
    with pytest.raises(ProcuracaoInvalidaError, match=trecho):
        servico.cadastrar("AC-A", procurador, momento=AGORA)

    assert repo.listar_procuracoes_do_outorgante("AC-A") == []


def test_recusa_procuracao_do_acionista_a_si_mesmo(servico: ServicoProcuracao):
    with pytest.raises(ProcuracaoInvalidaError, match="a si mesmo"):
        servico.cadastrar("AC-A", " AC-A ", momento=AGORA)


@pytest.mark.parametrize(
    "expiracao",
    [
        pytest.param(AGORA - timedelta(seconds=1), id="passado"),
        pytest.param(AGORA - timedelta(days=365), id="ano-passado"),
        pytest.param(datetime(2026, 9, 20, 12, 0), id="passado-sem-fuso"),
    ],
)
def test_recusa_expiracao_que_nao_esta_no_futuro(servico: ServicoProcuracao, expiracao: datetime):
    with pytest.raises(ProcuracaoInvalidaError, match="precisa estar no futuro"):
        servico.cadastrar("AC-A", "PROC-1", data_expiracao=expiracao, momento=AGORA)


def test_recusa_segunda_procuracao_vigente_do_mesmo_outorgante(servico: ServicoProcuracao):
    servico.cadastrar("AC-A", "PROC-1", data_expiracao=EM_30_DIAS, momento=AGORA)

    with pytest.raises(ProcuracaoInvalidaError, match=r"já possui procuração vigente.*'PROC-1'"):
        servico.cadastrar("AC-A", "PROC-2", momento=AGORA)

    assert servico.obter_vigente("AC-A", AGORA).procurador_id == "PROC-1"


def test_aceita_nova_procuracao_depois_de_revogar_a_anterior(servico: ServicoProcuracao):
    servico.cadastrar("AC-A", "PROC-1", momento=AGORA)
    servico.revogar("AC-A", "PROC-1")

    nova = servico.cadastrar("AC-A", "PROC-2", momento=AGORA)

    assert servico.obter_vigente("AC-A", AGORA) == nova


def test_aceita_reconstituir_procuracao_revogada_ao_mesmo_procurador(servico: ServicoProcuracao):
    servico.cadastrar("AC-A", "PROC-1", momento=AGORA)
    servico.revogar("AC-A", "PROC-1")

    servico.cadastrar("AC-A", "PROC-1", momento=AGORA)

    assert servico.obter_vigente("AC-A", AGORA).procurador_id == "PROC-1"


def test_aceita_nova_procuracao_quando_a_anterior_expirou(servico: ServicoProcuracao):
    servico.cadastrar("AC-A", "PROC-1", data_expiracao=EM_30_DIAS, momento=AGORA)
    depois_do_prazo = EM_30_DIAS + timedelta(days=1)

    nova = servico.cadastrar("AC-A", "PROC-2", momento=depois_do_prazo)

    assert servico.obter_vigente("AC-A", depois_do_prazo) == nova


def test_outorgantes_distintos_podem_ter_o_mesmo_procurador(servico: ServicoProcuracao):
    servico.cadastrar("AC-A", "PROC-1", momento=AGORA)
    servico.cadastrar("AC-B", "PROC-1", momento=AGORA)

    assert servico.obter_vigente("AC-A", AGORA).procurador_id == "PROC-1"
    assert servico.obter_vigente("AC-B", AGORA).procurador_id == "PROC-1"


# --- Revogação ---


def test_revogar_torna_a_procuracao_nao_vigente_e_a_mantem_no_repositorio(
    servico: ServicoProcuracao, repo: RepositorioAssembleia
):
    servico.cadastrar("AC-A", "PROC-1", momento=AGORA)

    revogada = servico.revogar("AC-A", "PROC-1")

    assert revogada.ativa is False
    assert repo.obter_procuracao("AC-A", "PROC-1") == revogada
    assert servico.obter_vigente("AC-A", AGORA) is None


def test_revogar_procuracao_inexistente_e_recusado(servico: ServicoProcuracao):
    with pytest.raises(ProcuracaoInvalidaError, match=r"Não há procuração.*'AC-A'.*'PROC-1'"):
        servico.revogar("AC-A", "PROC-1")


def test_revogar_procuracao_ja_revogada_e_recusado(servico: ServicoProcuracao):
    servico.cadastrar("AC-A", "PROC-1", momento=AGORA)
    servico.revogar("AC-A", "PROC-1")

    with pytest.raises(ProcuracaoInvalidaError, match="já foi revogada"):
        servico.revogar("AC-A", "PROC-1")


# --- Consulta da procuração vigente ---


def test_obter_vigente_e_nulo_sem_procuracao(servico: ServicoProcuracao):
    assert servico.obter_vigente("AC-A", AGORA) is None


def test_obter_vigente_considera_o_momento_consultado(servico: ServicoProcuracao):
    servico.cadastrar("AC-A", "PROC-1", data_expiracao=EM_30_DIAS, momento=AGORA)

    assert servico.obter_vigente("AC-A", AGORA + timedelta(days=29)) is not None
    assert servico.obter_vigente("AC-A", EM_30_DIAS + timedelta(seconds=1)) is None


# --- Poder de voto consolidado ---


def _com_procurador_acionista(repo: RepositorioAssembleia, acoes: int = 30) -> None:
    """Cadastra AC-P, que é ao mesmo tempo acionista e procurador credenciado."""
    repo.adicionar_acionista(Acionista(id="AC-P", nome="Pedro", acoes_ordinarias=acoes))
    repo.adicionar_procurador(Procurador(id="AC-P", nome="Pedro"))


def test_poder_de_voto_soma_as_acoes_dos_outorgantes_do_procurador(servico: ServicoProcuracao):
    servico.cadastrar("AC-B", "PROC-1", momento=AGORA)
    servico.cadastrar("AC-A", "PROC-1", momento=AGORA)

    poder = servico.calcular_poder_de_voto("PROC-1", AGORA)

    assert poder.procurador_id == "PROC-1"
    assert poder.peso_proprio == 0
    assert poder.peso_delegado == 150
    assert poder.peso_total == 150
    assert poder.outorgantes == ("AC-A", "AC-B")


def test_poder_de_voto_soma_as_acoes_proprias_do_procurador_acionista(
    servico: ServicoProcuracao, repo: RepositorioAssembleia
):
    _com_procurador_acionista(repo)
    servico.cadastrar("AC-A", "AC-P", momento=AGORA)

    poder = servico.calcular_poder_de_voto(" AC-P ", AGORA)

    assert poder.peso_proprio == 30
    assert poder.peso_delegado == 100
    assert poder.peso_total == 130
    assert poder.outorgantes == ("AC-A",)


def test_poder_de_voto_de_acionista_sem_procuracoes_e_o_proprio_peso(
    servico: ServicoProcuracao,
):
    poder = servico.calcular_poder_de_voto("AC-B", AGORA)

    assert poder.peso_proprio == 50
    assert poder.peso_delegado == 0
    assert poder.outorgantes == ()


def test_procurador_que_delegou_o_proprio_voto_exerce_apenas_o_poder_delegado(
    servico: ServicoProcuracao, repo: RepositorioAssembleia
):
    _com_procurador_acionista(repo)
    servico.cadastrar("AC-A", "AC-P", momento=AGORA)
    servico.cadastrar("AC-P", "PROC-2", momento=AGORA)

    poder = servico.calcular_poder_de_voto("AC-P", AGORA)

    assert poder.peso_proprio == 0
    assert poder.peso_delegado == 100
    assert poder.outorgantes == ("AC-A",)


@pytest.mark.parametrize(
    "acionista_depois",
    [
        pytest.param(
            Acionista(id="AC-A", nome="Alfa", acoes_ordinarias=100, bloqueado=True), id="bloqueado"
        ),
        pytest.param(
            Acionista(id="AC-A", nome="Alfa", acoes_ordinarias=100, ativo=False), id="inativo"
        ),
        pytest.param(
            Acionista(id="AC-A", nome="Alfa", acoes_ordinarias=0), id="sem-acoes-ordinarias"
        ),
    ],
)
def test_poder_de_voto_ignora_outorgante_que_deixou_de_estar_apto(
    servico: ServicoProcuracao, repo: RepositorioAssembleia, acionista_depois: Acionista
):
    servico.cadastrar("AC-A", "PROC-1", momento=AGORA)
    servico.cadastrar("AC-B", "PROC-1", momento=AGORA)
    repo.adicionar_acionista(acionista_depois)

    poder = servico.calcular_poder_de_voto("PROC-1", AGORA)

    assert poder.peso_delegado == 50
    assert poder.outorgantes == ("AC-B",)


def test_poder_de_voto_ignora_procuracao_revogada(servico: ServicoProcuracao):
    servico.cadastrar("AC-A", "PROC-1", momento=AGORA)
    servico.cadastrar("AC-B", "PROC-1", momento=AGORA)
    servico.revogar("AC-A", "PROC-1")

    poder = servico.calcular_poder_de_voto("PROC-1", AGORA)

    assert poder.peso_delegado == 50
    assert poder.outorgantes == ("AC-B",)


def test_poder_de_voto_ignora_procuracao_expirada_no_momento_consultado(
    servico: ServicoProcuracao,
):
    servico.cadastrar("AC-A", "PROC-1", data_expiracao=EM_30_DIAS, momento=AGORA)
    servico.cadastrar("AC-B", "PROC-1", momento=AGORA)

    depois_do_prazo = EM_30_DIAS + timedelta(days=1)
    poder = servico.calcular_poder_de_voto("PROC-1", depois_do_prazo)

    assert poder.outorgantes == ("AC-B",)
    assert poder.peso_total == 50


def test_poder_de_voto_nao_inclui_outorgantes_de_outro_procurador(servico: ServicoProcuracao):
    servico.cadastrar("AC-A", "PROC-1", momento=AGORA)
    servico.cadastrar("AC-B", "PROC-2", momento=AGORA)

    poder = servico.calcular_poder_de_voto("PROC-1", AGORA)

    assert poder.outorgantes == ("AC-A",)
    assert poder.peso_total == 100


def test_poder_de_voto_e_zero_para_quem_nao_representa_ninguem(servico: ServicoProcuracao):
    poder = servico.calcular_poder_de_voto("PROC-1", AGORA)

    assert poder.peso_total == 0
    assert poder.outorgantes == ()


# --- Titulares do capital consolidado ---


def test_titulares_incluem_o_procurador_quando_as_acoes_dele_entram_no_voto(
    servico: ServicoProcuracao, repo: RepositorioAssembleia
):
    _com_procurador_acionista(repo)
    servico.cadastrar("AC-A", "AC-P", momento=AGORA)

    poder = servico.calcular_poder_de_voto("AC-P", AGORA)

    assert poder.titulares == ("AC-A", "AC-P")


def test_titulares_excluem_o_procurador_que_delegou_o_proprio_voto(
    servico: ServicoProcuracao, repo: RepositorioAssembleia
):
    _com_procurador_acionista(repo)
    servico.cadastrar("AC-A", "AC-P", momento=AGORA)
    servico.cadastrar("AC-P", "PROC-2", momento=AGORA)

    poder = servico.calcular_poder_de_voto("AC-P", AGORA)

    assert poder.titulares == ("AC-A",)


def test_titulares_de_procurador_que_nao_e_acionista_sao_so_os_outorgantes(
    servico: ServicoProcuracao,
):
    servico.cadastrar("AC-B", "PROC-1", momento=AGORA)
    servico.cadastrar("AC-A", "PROC-1", momento=AGORA)

    poder = servico.calcular_poder_de_voto("PROC-1", AGORA)

    assert poder.titulares == ("AC-A", "AC-B")


def test_titulares_de_acionista_sem_procuracoes_e_ele_mesmo(servico: ServicoProcuracao):
    assert servico.calcular_poder_de_voto("AC-B", AGORA).titulares == ("AC-B",)


@pytest.mark.parametrize(
    ("id_classe", "outorgante_id", "procurador_id", "deve_aceitar", "trecho_erro"),
    [
        ("outorgante_e_procurador_validos", "AC-A", "PROC-1", True, ""),
        ("outorgante_inexistente", "AC-FANTASMA", "PROC-1", False, "não encontrado"),
        ("outorgante_inativo", "AC-INATIVO", "PROC-1", False, "cadastro inativo"),
        ("outorgante_bloqueado", "AC-BLOQUEADO", "PROC-1", False, "bloqueio"),
        (
            "outorgante_sem_acoes_ordinarias",
            "AC-PREF",
            "PROC-1",
            False,
            "não possui ações ordinárias",
        ),
        (
            "procurador_nao_cadastrado",
            "AC-A",
            "PROC-FANTASMA",
            False,
            "não está cadastrado",
        ),
        (
            "procurador_descredenciado",
            "AC-A",
            "PROC-DESCRED",
            False,
            "não está credenciado",
        ),
        (
            "procurador_inativo",
            "AC-A",
            "PROC-INATIVO",
            False,
            "cadastro inativo",
        ),
        ("autodelegacao", "AC-A", "AC-A", False, "a si mesmo"),
    ],
)
def test_procuracao_validade_outorgante_e_procurador(
    servico: ServicoProcuracao,
    id_classe: str,
    outorgante_id: str,
    procurador_id: str,
    deve_aceitar: bool,
    trecho_erro: str,
):
    if deve_aceitar:
        proc = servico.cadastrar(outorgante_id, procurador_id, momento=AGORA)
        assert proc.outorgante_id == outorgante_id, id_classe
        assert proc.procurador_id == procurador_id, id_classe
        assert proc.esta_vigente(AGORA) is True, id_classe
    else:
        with pytest.raises(ProcuracaoInvalidaError, match=trecho_erro):
            servico.cadastrar(outorgante_id, procurador_id, momento=AGORA)


@pytest.mark.parametrize(
    ("id_caso", "acoes_ordinarias", "deve_aceitar", "peso_delegado_esperado"),
    [
        ("zero_acoes_ordinarias", 0, False, 0),
        ("uma_acao_ordinaria", 1, True, 1),
        ("duas_acoes_ordinarias", 2, True, 2),
    ],
)
def test_procuracao_fronteira_acoes_ordinarias_outorgante(
    id_caso: str,
    acoes_ordinarias: int,
    deve_aceitar: bool,
    peso_delegado_esperado: int,
):
    repositorio = RepositorioAssembleia()
    repositorio.adicionar_acionista(
        Acionista(
            id="AC-LIMITE",
            nome="Acionista Fronteira",
            acoes_ordinarias=acoes_ordinarias,
            acoes_preferenciais=50,
        )
    )
    repositorio.adicionar_procurador(Procurador(id="PROC-1", nome="Procurador Credenciado"))
    srv = ServicoProcuracao(repositorio)

    if deve_aceitar:
        procuracao = srv.cadastrar("AC-LIMITE", "PROC-1", momento=AGORA)
        assert procuracao.esta_vigente(AGORA) is True, id_caso
        poder = srv.calcular_poder_de_voto("PROC-1", momento=AGORA)
        assert poder.peso_delegado == peso_delegado_esperado, id_caso
    else:
        with pytest.raises(ProcuracaoInvalidaError, match="não possui ações ordinárias"):
            srv.cadastrar("AC-LIMITE", "PROC-1", momento=AGORA)


@pytest.mark.parametrize(
    ("id_caso", "momento_consulta", "esperado_vigente"),
    [
        (
            "um_segundo_antes_expiracao",
            EM_30_DIAS - timedelta(seconds=1),
            True,
        ),
        (
            "no_instante_exato_expiracao",
            EM_30_DIAS,
            True,
        ),
        (
            "um_segundo_apos_expiracao",
            EM_30_DIAS + timedelta(seconds=1),
            False,
        ),
    ],
)
def test_procuracao_fronteira_temporal_vigencia(
    servico: ServicoProcuracao,
    id_caso: str,
    momento_consulta: datetime,
    esperado_vigente: bool,
):
    procuracao = servico.cadastrar("AC-A", "PROC-1", data_expiracao=EM_30_DIAS, momento=AGORA)

    assert procuracao.esta_vigente(momento_consulta) is esperado_vigente, id_caso
    vigente_no_repo = servico.obter_vigente("AC-A", momento=momento_consulta)
    if esperado_vigente:
        assert vigente_no_repo == procuracao, id_caso
    else:
        assert vigente_no_repo is None, id_caso


@pytest.mark.parametrize(
    ("id_caso", "data_expiracao_cadastro", "deve_aceitar"),
    [
        ("cadastro_expiracao_1s_antes", AGORA - timedelta(seconds=1), False),
        ("cadastro_expiracao_no_instante_exato", AGORA, True),
        ("cadastro_expiracao_1s_depois", AGORA + timedelta(seconds=1), True),
    ],
)
def test_procuracao_fronteira_temporal_no_cadastro(
    id_caso: str,
    data_expiracao_cadastro: datetime,
    deve_aceitar: bool,
):
    repositorio = RepositorioAssembleia()
    repositorio.adicionar_acionista(Acionista(id="AC-A", nome="Alfa", acoes_ordinarias=100))
    repositorio.adicionar_procurador(Procurador(id="PROC-1", nome="Advocacia Um"))
    srv = ServicoProcuracao(repositorio)

    if deve_aceitar:
        proc = srv.cadastrar(
            "AC-A",
            "PROC-1",
            data_expiracao=data_expiracao_cadastro,
            momento=AGORA,
        )
        assert proc.esta_vigente(AGORA) is True, id_caso
    else:
        with pytest.raises(ProcuracaoInvalidaError, match="precisa estar no futuro"):
            srv.cadastrar(
                "AC-A",
                "PROC-1",
                data_expiracao=data_expiracao_cadastro,
                momento=AGORA,
            )

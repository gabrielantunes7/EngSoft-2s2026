"""Testes da delegação de voto: procurador credenciado, procurações e poder de voto."""

import pytest

from votacao.dados import (
    Acionista,
    BancoDadosMock,
    Procuracao,
    Procurador,
    RepositorioAssembleia,
)

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

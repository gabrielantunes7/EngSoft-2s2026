"""Testes unitários de elegibilidade para o Centro Acadêmico (CA)."""

from votacao.dados.ca import ChapaCA, Discente, RepositorioCA
from votacao.elegibilidade.validador_ca import ValidadorElegibilidadeCA


def test_elegibilidade_eleitor_ca_apto():
    repo = RepositorioCA()
    repo.adicionar_discente(Discente(ra="247314", nome="Lucas", curso="EngSoft"))

    aptidao = ValidadorElegibilidadeCA.validar_eleitor("247314", repo)
    assert aptidao.apto is True
    assert aptidao.peso_voto == 1
    assert aptidao.motivo_inaptidao is None
    assert aptidao.dados_eleitor["ra"] == "247314"


def test_elegibilidade_eleitor_ca_inexistente():
    repo = RepositorioCA()
    aptidao = ValidadorElegibilidadeCA.validar_eleitor("000000", repo)
    assert aptidao.apto is False
    assert aptidao.peso_voto == 0
    assert "não encontrado" in (aptidao.motivo_inaptidao or "")


def test_elegibilidade_eleitor_ca_matricula_inativa():
    repo = RepositorioCA()
    repo.adicionar_discente(
        Discente(ra="111", nome="Aluno Trancado", curso="EC", matricula_ativa=False)
    )

    aptidao = ValidadorElegibilidadeCA.validar_eleitor("111", repo)
    assert aptidao.apto is False
    assert "não possui matrícula regular ativa" in (aptidao.motivo_inaptidao or "")


def test_elegibilidade_eleitor_ca_suspenso():
    repo = RepositorioCA()
    repo.adicionar_discente(Discente(ra="222", nome="Aluno Suspenso", curso="EC", suspenso=True))

    aptidao = ValidadorElegibilidadeCA.validar_eleitor("222", repo)
    assert aptidao.apto is False
    assert "suspensão disciplinar ativa" in (aptidao.motivo_inaptidao or "")


def test_elegibilidade_chapa_valida():
    repo = RepositorioCA()
    repo.adicionar_discente(Discente(ra="1", nome="D1", curso="EngSoft"))
    repo.adicionar_discente(Discente(ra="2", nome="D2", curso="EngSoft"))
    repo.adicionar_chapa(ChapaCA(nome="Chapa Viva", integrantes_ra=("1", "2"), ativa=True))

    eleg = ValidadorElegibilidadeCA.validar_candidato_chapa("Chapa Viva", repo)
    assert eleg.elegivel is True
    assert eleg.motivo_inelegibilidade is None
    assert eleg.detalhes["total_integrantes"] == 2


def test_elegibilidade_chapa_inexistente():
    repo = RepositorioCA()
    eleg = ValidadorElegibilidadeCA.validar_candidato_chapa("Chapa Fantasma", repo)
    assert eleg.elegivel is False
    assert "não encontrada" in (eleg.motivo_inelegibilidade or "")


def test_elegibilidade_chapa_inativa():
    repo = RepositorioCA()
    repo.adicionar_chapa(ChapaCA(nome="Chapa Cancelada", integrantes_ra=(), ativa=False))

    eleg = ValidadorElegibilidadeCA.validar_candidato_chapa("Chapa Cancelada", repo)
    assert eleg.elegivel is False
    assert "inativa ou não foi homologada" in (eleg.motivo_inelegibilidade or "")


def test_elegibilidade_chapa_sem_integrantes():
    repo = RepositorioCA()
    repo.adicionar_chapa(ChapaCA(nome="Chapa Vazia", integrantes_ra=(), ativa=True))

    eleg = ValidadorElegibilidadeCA.validar_candidato_chapa("Chapa Vazia", repo)
    assert eleg.elegivel is False
    assert "não possui integrantes registrados" in (eleg.motivo_inelegibilidade or "")


def test_elegibilidade_chapa_integrante_inexistente():
    repo = RepositorioCA()
    repo.adicionar_chapa(ChapaCA(nome="Chapa 1", integrantes_ra=("999",), ativa=True))

    eleg = ValidadorElegibilidadeCA.validar_candidato_chapa("Chapa 1", repo)
    assert eleg.elegivel is False
    assert "não foi encontrado no cadastro acadêmico" in (eleg.motivo_inelegibilidade or "")


def test_elegibilidade_chapa_integrante_matricula_inativa():
    repo = RepositorioCA()
    repo.adicionar_discente(Discente(ra="1", nome="D1", curso="EngSoft", matricula_ativa=False))
    repo.adicionar_chapa(ChapaCA(nome="Chapa 1", integrantes_ra=("1",), ativa=True))

    eleg = ValidadorElegibilidadeCA.validar_candidato_chapa("Chapa 1", repo)
    assert eleg.elegivel is False
    assert "não possui matrícula ativa" in (eleg.motivo_inelegibilidade or "")


def test_elegibilidade_chapa_integrante_suspenso():
    repo = RepositorioCA()
    repo.adicionar_discente(Discente(ra="1", nome="D1", curso="EngSoft", suspenso=True))
    repo.adicionar_chapa(ChapaCA(nome="Chapa 1", integrantes_ra=("1",), ativa=True))

    eleg = ValidadorElegibilidadeCA.validar_candidato_chapa("Chapa 1", repo)
    assert eleg.elegivel is False
    assert "possui suspensão disciplinar" in (eleg.motivo_inelegibilidade or "")


def test_elegibilidade_chapa_integrante_formando_proximo_semestre():
    repo = RepositorioCA()
    repo.adicionar_discente(
        Discente(ra="1", nome="Veterano", curso="EngSoft", formando_proximo_semestre=True)
    )
    repo.adicionar_chapa(ChapaCA(nome="Chapa 1", integrantes_ra=("1",), ativa=True))

    eleg = ValidadorElegibilidadeCA.validar_candidato_chapa("Chapa 1", repo)
    assert eleg.elegivel is False
    assert "apto a se formar no próximo semestre" in (eleg.motivo_inelegibilidade or "")

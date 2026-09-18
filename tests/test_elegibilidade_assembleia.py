"""Testes unitários de elegibilidade para Assembleias de Acionistas."""

from datetime import UTC, datetime, timedelta

from votacao.dados.assembleia import (
    Acionista,
    CandidatoConselho,
    Procuracao,
    RepositorioAssembleia,
)
from votacao.elegibilidade.validador_assembleia import (
    ValidadorElegibilidadeAssembleia,
)


def test_elegibilidade_acionista_titular_apto():
    repo = RepositorioAssembleia()
    repo.adicionar_acionista(
        Acionista(
            id="AC-1", nome="Alpha S.A.", acoes_ordinarias=100_000, acoes_preferenciais=50_000
        )
    )

    aptidao = ValidadorElegibilidadeAssembleia.validar_eleitor("AC-1", repo)
    assert aptidao.apto is True
    assert aptidao.peso_voto == 100_000
    assert aptidao.dados_eleitor["tipo_exercicio"] == "titular_direto"


def test_elegibilidade_acionista_inexistente():
    repo = RepositorioAssembleia()
    aptidao = ValidadorElegibilidadeAssembleia.validar_eleitor("AC-FANTASMA", repo)
    assert aptidao.apto is False
    assert aptidao.peso_voto == 0
    assert "não encontrado" in (aptidao.motivo_inaptidao or "")


def test_elegibilidade_acionista_inativo():
    repo = RepositorioAssembleia()
    repo.adicionar_acionista(
        Acionista(id="AC-2", nome="Beta S.A.", acoes_ordinarias=50_000, ativo=False)
    )

    aptidao = ValidadorElegibilidadeAssembleia.validar_eleitor("AC-2", repo)
    assert aptidao.apto is False
    assert "cadastro inativo" in (aptidao.motivo_inaptidao or "")


def test_elegibilidade_acionista_bloqueado():
    repo = RepositorioAssembleia()
    repo.adicionar_acionista(
        Acionista(id="AC-3", nome="Gama S.A.", acoes_ordinarias=50_000, bloqueado=True)
    )

    aptidao = ValidadorElegibilidadeAssembleia.validar_eleitor("AC-3", repo)
    assert aptidao.apto is False
    assert "bloqueio" in (aptidao.motivo_inaptidao or "")


def test_elegibilidade_acionista_sem_acoes_ordinarias():
    repo = RepositorioAssembleia()
    repo.adicionar_acionista(
        Acionista(id="AC-4", nome="Delta S.A.", acoes_ordinarias=0, acoes_preferenciais=100_000)
    )

    aptidao = ValidadorElegibilidadeAssembleia.validar_eleitor("AC-4", repo)
    assert aptidao.apto is False
    assert "não possui ações ordinárias com direito a voto" in (aptidao.motivo_inaptidao or "")


def test_elegibilidade_com_procuracao_valida():
    repo = RepositorioAssembleia()
    repo.adicionar_acionista(Acionista(id="AC-1", nome="Alpha S.A.", acoes_ordinarias=75_000))
    agora = datetime.now(UTC)
    repo.adicionar_procuracao(
        Procuracao(
            outorgante_id="AC-1",
            procurador_id="PROC-1",
            data_expiracao=agora + timedelta(days=5),
            ativa=True,
        )
    )

    aptidao = ValidadorElegibilidadeAssembleia.validar_eleitor(
        acionista_id="AC-1",
        repo=repo,
        procurador_id="PROC-1",
        momento=agora,
    )
    assert aptidao.apto is True
    assert aptidao.peso_voto == 75_000
    assert aptidao.dados_eleitor["tipo_exercicio"] == "representacao_procuracao"
    assert aptidao.dados_eleitor["procurador_id"] == "PROC-1"


def test_elegibilidade_com_procuracao_inexistente():
    repo = RepositorioAssembleia()
    repo.adicionar_acionista(Acionista(id="AC-1", nome="Alpha S.A.", acoes_ordinarias=75_000))

    aptidao = ValidadorElegibilidadeAssembleia.validar_eleitor(
        acionista_id="AC-1",
        repo=repo,
        procurador_id="PROC-INEXISTENTE",
    )
    assert aptidao.apto is False
    assert "não encontrado para o procurador" in (aptidao.motivo_inaptidao or "")


def test_elegibilidade_com_procuracao_expirada():
    repo = RepositorioAssembleia()
    repo.adicionar_acionista(Acionista(id="AC-1", nome="Alpha S.A.", acoes_ordinarias=75_000))
    agora = datetime.now(UTC)
    repo.adicionar_procuracao(
        Procuracao(
            outorgante_id="AC-1",
            procurador_id="PROC-1",
            data_expiracao=agora - timedelta(days=1),
            ativa=True,
        )
    )

    aptidao = ValidadorElegibilidadeAssembleia.validar_eleitor(
        acionista_id="AC-1",
        repo=repo,
        procurador_id="PROC-1",
        momento=agora,
    )
    assert aptidao.apto is False
    assert "expirada ou revogada" in (aptidao.motivo_inaptidao or "")


def test_elegibilidade_candidato_conselho_apto():
    repo = RepositorioAssembleia()
    repo.adicionar_candidato_conselho(
        CandidatoConselho(
            id="CAND-1",
            nome="Silvia Engenheira",
            titular_acoes=True,
            conflito_interesse=False,
            ativo=True,
        )
    )

    eleg = ValidadorElegibilidadeAssembleia.validar_candidato_conselho("CAND-1", repo)
    assert eleg.elegivel is True
    assert eleg.motivo_inelegibilidade is None


def test_elegibilidade_candidato_conselho_inexistente():
    repo = RepositorioAssembleia()
    eleg = ValidadorElegibilidadeAssembleia.validar_candidato_conselho("CAND-999", repo)
    assert eleg.elegivel is False
    assert "não encontrado" in (eleg.motivo_inelegibilidade or "")


def test_elegibilidade_candidato_conselho_desativado():
    repo = RepositorioAssembleia()
    repo.adicionar_candidato_conselho(CandidatoConselho(id="CAND-2", nome="Silvia", ativo=False))

    eleg = ValidadorElegibilidadeAssembleia.validar_candidato_conselho("CAND-2", repo)
    assert eleg.elegivel is False
    assert "desativado" in (eleg.motivo_inelegibilidade or "")


def test_elegibilidade_candidato_conselho_sem_titularidade():
    repo = RepositorioAssembleia()
    repo.adicionar_candidato_conselho(
        CandidatoConselho(id="CAND-3", nome="Silvia", titular_acoes=False)
    )

    eleg = ValidadorElegibilidadeAssembleia.validar_candidato_conselho("CAND-3", repo)
    assert eleg.elegivel is False
    assert "titularidade mínima exigida" in (eleg.motivo_inelegibilidade or "")


def test_elegibilidade_candidato_conselho_conflito_interesses():
    repo = RepositorioAssembleia()
    repo.adicionar_candidato_conselho(
        CandidatoConselho(id="CAND-4", nome="Silvia", conflito_interesse=True)
    )

    eleg = ValidadorElegibilidadeAssembleia.validar_candidato_conselho("CAND-4", repo)
    assert eleg.elegivel is False
    assert "conflito de interesses" in (eleg.motivo_inelegibilidade or "")

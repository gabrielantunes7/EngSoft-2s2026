"""Testes da irrepetibilidade de matéria rejeitada na mesma sessão legislativa (#35).

Antes da #35, uma matéria rejeitada podia ser reinstanciada no instante seguinte
(evidência E2 / D-RITO-05 da Atividade 3), e não havia como arquivá-la ou retirá-la de
pauta. A PEC rejeitada não volta na mesma sessão legislativa (CF, art. 60, § 5º); o
projeto de lei só volta mediante proposta da maioria absoluta (art. 67).
"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from votacao.dados.congresso import MateriaLegislativa, RepositorioCongresso
from votacao.modelos import CasaLegislativa, TipoMateriaCongresso, Voto
from votacao.regras.congresso import RegraCongresso
from votacao.tramitacao import (
    MateriaIrrepetivelError,
    StatusTramitacao,
    TramitacaoInvalidaError,
    TramitacaoLegislativa,
    sessao_legislativa_corrente,
)

PL = TipoMateriaCongresso.LEI_ORDINARIA
PEC = TipoMateriaCongresso.PEC


def _repo(materia_id: str, tipo: TipoMateriaCongresso) -> RepositorioCongresso:
    repo = RepositorioCongresso()
    repo.adicionar_materia(
        MateriaLegislativa(id=materia_id, tipo=tipo, casa_atual=CasaLegislativa.CAMARA)
    )
    return repo


def _rejeitar(tramitacao: TramitacaoLegislativa) -> None:
    sessao = tramitacao.nova_sessao()
    sessao.abrir()
    quorum = sessao.quorum_instalacao or 0
    sessao.registrar_presenca(*(f"P{i}" for i in range(quorum)))
    sessao.liberar_votacao()
    for i in range(RegraCongresso.QUORUM_INSTALACAO_CAMARA):
        sessao.registrar_voto(Voto(eleitor_id=f"N{i}", opcao="NAO"))
    sessao.encerrar_votacao()
    sessao.apurar()
    tramitacao.registrar_resultado(sessao)
    assert tramitacao.status == StatusTramitacao.REJEITADA


def _rejeitada(materia_id: str, tipo: TipoMateriaCongresso, sessao: int = 2026):
    repo = _repo(materia_id, tipo)
    _rejeitar(TramitacaoLegislativa(materia_id, tipo, repo=repo, sessao_legislativa=sessao))
    return repo


# --- Sessão legislativa ----------------------------------------------------------------


def test_tramitacao_identifica_a_sessao_legislativa():
    assert TramitacaoLegislativa("PL-1", PL, sessao_legislativa=2026).sessao_legislativa == 2026


def test_sessao_legislativa_padrao_e_a_do_ano_corrente():
    assert TramitacaoLegislativa("PL-1", PL).sessao_legislativa == datetime.now(UTC).year
    assert sessao_legislativa_corrente(datetime(2027, 3, 1, tzinfo=UTC)) == 2027


def test_materia_rejeitada_fica_arquivada_com_a_sessao_legislativa():
    repo = _rejeitada("PL-1/2026", PL)

    materia = repo.obter_materia("PL-1/2026")
    assert materia.ativa is False
    assert materia.arquivamento == "REJEITADA"
    assert materia.sessao_legislativa_arquivamento == 2026


# --- PEC: art. 60, § 5º ----------------------------------------------------------------


def test_pec_rejeitada_nao_volta_na_mesma_sessao_legislativa():
    repo = _rejeitada("PEC-1/2026", PEC)

    with pytest.raises(MateriaIrrepetivelError, match=r"art\. 60, § 5º"):
        TramitacaoLegislativa("PEC-1/2026", PEC, repo=repo, sessao_legislativa=2026)


def test_pec_nao_admite_a_excecao_da_maioria_absoluta():
    repo = _rejeitada("PEC-1/2026", PEC)

    with pytest.raises(MateriaIrrepetivelError, match=r"art\. 60, § 5º"):
        TramitacaoLegislativa(
            "PEC-1/2026", PEC, repo=repo, sessao_legislativa=2026, proposta_maioria_absoluta=True
        )


# --- Projeto de lei: art. 67 -----------------------------------------------------------


def test_lei_rejeitada_nao_volta_na_mesma_sessao_sem_maioria_absoluta():
    repo = _rejeitada("PL-1/2026", PL)

    with pytest.raises(MateriaIrrepetivelError, match=r"art\. 67"):
        TramitacaoLegislativa("PL-1/2026", PL, repo=repo, sessao_legislativa=2026)


def test_lei_rejeitada_volta_na_mesma_sessao_com_proposta_da_maioria_absoluta():
    repo = _rejeitada("PL-1/2026", PL)

    tramitacao = TramitacaoLegislativa(
        "PL-1/2026", PL, repo=repo, sessao_legislativa=2026, proposta_maioria_absoluta=True
    )

    assert tramitacao.status == StatusTramitacao.EM_TRAMITACAO
    materia = repo.obter_materia("PL-1/2026")
    assert materia.ativa is True
    assert materia.arquivamento is None


def test_mensagem_da_recusa_e_explicativa():
    repo = _rejeitada("PL-1/2026", PL)

    with pytest.raises(MateriaIrrepetivelError) as erro:
        TramitacaoLegislativa("PL-1/2026", PL, repo=repo, sessao_legislativa=2026)

    assert "sessão legislativa de 2026" in str(erro.value)
    assert "maioria absoluta" in str(erro.value)


# --- Sessão legislativa posterior ------------------------------------------------------


@pytest.mark.parametrize("tipo", [PL, PEC], ids=["lei", "pec"])
def test_em_sessao_legislativa_posterior_a_reapresentacao_e_aceita(tipo):
    repo = _rejeitada("M-1", tipo, sessao=2026)

    tramitacao = TramitacaoLegislativa("M-1", tipo, repo=repo, sessao_legislativa=2027)

    assert tramitacao.status == StatusTramitacao.EM_TRAMITACAO
    assert repo.obter_materia("M-1").ativa is True


# --- Retirada de pauta -----------------------------------------------------------------


def test_retirada_de_pauta_arquiva_sem_decisao_de_merito():
    repo = _repo("PL-2/2026", PL)
    tramitacao = TramitacaoLegislativa("PL-2/2026", PL, repo=repo, sessao_legislativa=2026)

    status = tramitacao.retirar_de_pauta("Requerimento do autor")

    assert status == StatusTramitacao.ARQUIVADA
    assert status.concluida is True
    assert tramitacao.historico == ()
    assert tramitacao.motivo_arquivamento == "Requerimento do autor"
    materia = repo.obter_materia("PL-2/2026")
    assert (materia.ativa, materia.arquivamento) == (False, "RETIRADA")


@pytest.mark.parametrize("tipo", [PL, PEC], ids=["lei", "pec"])
def test_materia_retirada_de_pauta_nao_fica_sujeita_a_irrepetibilidade(tipo):
    repo = _repo("M-2", tipo)
    TramitacaoLegislativa("M-2", tipo, repo=repo, sessao_legislativa=2026).retirar_de_pauta(
        "Perda de objeto"
    )

    tramitacao = TramitacaoLegislativa("M-2", tipo, repo=repo, sessao_legislativa=2026)

    assert tramitacao.status == StatusTramitacao.EM_TRAMITACAO


def test_retirada_exige_motivo_e_materia_em_tramitacao():
    tramitacao = TramitacaoLegislativa("PL-3", PL)
    with pytest.raises(ValueError, match="motivo"):
        tramitacao.retirar_de_pauta(" ")

    tramitacao.retirar_de_pauta("Requerimento do autor")
    with pytest.raises(TramitacaoInvalidaError, match="ARQUIVADA"):
        tramitacao.retirar_de_pauta("De novo")
    with pytest.raises(TramitacaoInvalidaError, match="ARQUIVADA"):
        tramitacao.nova_sessao()


# --- Matéria concluída com aprovação e arquivada sem motivo ---------------------------


def test_materia_promulgada_nao_volta_a_tramitar():
    repo = _repo("PEC-9", PEC)
    TramitacaoLegislativa("PEC-9", PEC, repo=repo, sessao_legislativa=2026)
    materia = repo.obter_materia("PEC-9")
    repo.adicionar_materia(
        replace(
            materia, ativa=False, arquivamento="CONCLUIDA", sessao_legislativa_arquivamento=2026
        )
    )

    with pytest.raises(ValueError, match="arquivada"):
        TramitacaoLegislativa("PEC-9", PEC, repo=repo, sessao_legislativa=2027)


def test_sem_repositorio_nao_ha_historico_para_aplicar_a_irrepetibilidade():
    # Limite conhecido: a irrepetibilidade consulta o cadastro da matéria.
    _rejeitar(TramitacaoLegislativa("PL-4", PL, sessao_legislativa=2026))

    tramitacao = TramitacaoLegislativa("PL-4", PL, sessao_legislativa=2026)

    assert tramitacao.status == StatusTramitacao.EM_TRAMITACAO


# --- Revisão do PR #79: a trava não pode ser contornada --------------------------------


def test_pec_rejeitada_apresentada_como_lei_continua_recusada_e_mantem_o_registro():
    repo = _rejeitada("PEC-5/2026", PEC)

    # Tipo errado + maioria absoluta: antes, passava pela trava, reativava a matéria e só
    # depois falhava, apagando o registro da rejeição.
    with pytest.raises(MateriaIrrepetivelError, match=r"art\. 60, § 5º"):
        TramitacaoLegislativa(
            "PEC-5/2026", PL, repo=repo, sessao_legislativa=2026, proposta_maioria_absoluta=True
        )

    materia = repo.obter_materia("PEC-5/2026")
    assert (materia.ativa, materia.arquivamento) == (False, "REJEITADA")
    with pytest.raises(MateriaIrrepetivelError):
        TramitacaoLegislativa("PEC-5/2026", PEC, repo=repo, sessao_legislativa=2026)


def test_falha_na_conferencia_do_cadastro_nao_apaga_o_registro_da_rejeicao():
    repo = _rejeitada("PL-6/2026", PL, sessao=2026)

    # Sessão posterior (a reapresentação seria admitida), mas o tipo diverge do cadastro.
    with pytest.raises(ValueError, match="cadastrada como LEI_ORDINARIA"):
        TramitacaoLegislativa("PL-6/2026", PEC, repo=repo, sessao_legislativa=2027)

    materia = repo.obter_materia("PL-6/2026")
    assert materia.ativa is False
    assert materia.arquivamento == "REJEITADA"
    assert materia.sessao_legislativa_arquivamento == 2026
    with pytest.raises(MateriaIrrepetivelError, match=r"art\. 67"):
        TramitacaoLegislativa("PL-6/2026", PL, repo=repo, sessao_legislativa=2026)

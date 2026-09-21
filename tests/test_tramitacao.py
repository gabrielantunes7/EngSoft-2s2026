"""Testes da tramitação bicameral com turnos por tipo de matéria."""

import pytest

from votacao.auditoria import LogDeAuditoria, TipoEvento
from votacao.dados.congresso import MateriaLegislativa, RepositorioCongresso
from votacao.elegibilidade.validador_congresso import ValidadorElegibilidadeCongresso
from votacao.modelos import CasaLegislativa, StatusResultado, TipoMateriaCongresso, Voto
from votacao.regras.congresso import RegraCongresso
from votacao.sessao import EstadoSessao, SessaoVotacao
from votacao.tramitacao import (
    StatusTramitacao,
    TramitacaoInvalidaError,
    TramitacaoLegislativa,
)

# Votos SIM suficientes para aprovar qualquer matéria, com quórum, em cada Casa.
APROVAR = {
    CasaLegislativa.CAMARA: RegraCongresso.MINIMO_PEC_CAMARA + 2,
    CasaLegislativa.SENADO: RegraCongresso.MINIMO_PEC_SENADO + 1,
}
# Presentes suficientes para instalar a sessão, mas maioria contrária.
REJEITAR = {
    CasaLegislativa.CAMARA: (100, RegraCongresso.QUORUM_INSTALACAO_CAMARA),
    CasaLegislativa.SENADO: (10, RegraCongresso.QUORUM_INSTALACAO_SENADO),
}


def _votar(sessao: SessaoVotacao, sim: int, nao: int = 0) -> None:
    sessao.abrir()
    sessao.liberar_votacao()
    for i in range(sim):
        sessao.registrar_voto(Voto(eleitor_id=f"{sessao.id_sessao}-S{i}", opcao="SIM"))
    for i in range(nao):
        sessao.registrar_voto(Voto(eleitor_id=f"{sessao.id_sessao}-N{i}", opcao="NAO"))
    sessao.encerrar_votacao()
    sessao.apurar()


def _deliberar(
    tramitacao: TramitacaoLegislativa, sim: int, nao: int = 0
) -> tuple[SessaoVotacao, StatusTramitacao]:
    sessao = tramitacao.nova_sessao()
    _votar(sessao, sim, nao)
    return sessao, tramitacao.registrar_resultado(sessao)


def _aprovar(tramitacao: TramitacaoLegislativa) -> tuple[SessaoVotacao, StatusTramitacao]:
    return _deliberar(tramitacao, sim=APROVAR[tramitacao.casa_atual])


def _rejeitar(tramitacao: TramitacaoLegislativa) -> tuple[SessaoVotacao, StatusTramitacao]:
    sim, nao = REJEITAR[tramitacao.casa_atual]
    return _deliberar(tramitacao, sim=sim, nao=nao)


def test_tramitacao_materia_vazia():
    with pytest.raises(ValueError, match="identificador"):
        TramitacaoLegislativa("  ", TipoMateriaCongresso.PEC)


@pytest.mark.parametrize(
    ("tipo", "turnos"),
    [
        (TipoMateriaCongresso.LEI_ORDINARIA, 1),
        (TipoMateriaCongresso.LEI_COMPLEMENTAR, 1),
        (TipoMateriaCongresso.PEC, 2),
    ],
)
def test_tramitacao_nasce_no_primeiro_turno_da_casa_iniciadora(
    tipo: TipoMateriaCongresso, turnos: int
):
    tramitacao = TramitacaoLegislativa("MAT-1/2026", tipo)

    assert tramitacao.status == StatusTramitacao.EM_TRAMITACAO
    assert tramitacao.casa_atual == CasaLegislativa.CAMARA
    assert tramitacao.casa_revisora == CasaLegislativa.SENADO
    assert tramitacao.turno_atual == 1
    assert tramitacao.turnos_por_casa == turnos
    assert tramitacao.historico == ()
    assert tramitacao.id_proxima_sessao == "MAT-1/2026-CAMARA-T1"


def test_tramitacao_iniciada_no_senado_revisa_na_camara():
    tramitacao = TramitacaoLegislativa(
        "PL-9/2026", TipoMateriaCongresso.LEI_ORDINARIA, casa_iniciadora=CasaLegislativa.SENADO
    )

    _, status = _aprovar(tramitacao)

    assert status == StatusTramitacao.EM_TRAMITACAO
    assert tramitacao.casa_atual == CasaLegislativa.CAMARA
    assert tramitacao.casa_revisora == CasaLegislativa.CAMARA


def test_tramitacao_nova_sessao_configura_regra_da_materia_e_da_casa():
    tramitacao = TramitacaoLegislativa("PLP-202/2026", TipoMateriaCongresso.LEI_COMPLEMENTAR)

    sessao = tramitacao.nova_sessao()

    assert sessao.id_sessao == "PLP-202/2026-CAMARA-T1"
    assert sessao.estado == EstadoSessao.CRIADA
    assert isinstance(sessao.regra, RegraCongresso)
    assert sessao.regra.materia == TipoMateriaCongresso.LEI_COMPLEMENTAR
    assert sessao.regra.casa == CasaLegislativa.CAMARA
    assert sessao.total_aptos == RegraCongresso.TOTAL_MEMBROS_CAMARA


def test_tramitacao_nova_sessao_aceita_log_com_o_id_previsto():
    tramitacao = TramitacaoLegislativa("PL-101/2026", TipoMateriaCongresso.LEI_ORDINARIA)
    log = LogDeAuditoria(tramitacao.id_proxima_sessao)

    sessao = tramitacao.nova_sessao(log=log)
    _votar(sessao, sim=APROVAR[CasaLegislativa.CAMARA])

    assert log.registros[0].evento == TipoEvento.VOTACAO_ABERTA
    assert log.registros[-1].evento == TipoEvento.RESULTADO_PROCLAMADO
    assert log.verificar_integridade().integro


def test_tramitacao_lei_ordinaria_aprovada_nas_duas_casas():
    tramitacao = TramitacaoLegislativa("PL-101/2026", TipoMateriaCongresso.LEI_ORDINARIA)

    sessao_camara, status_camara = _aprovar(tramitacao)
    assert status_camara == StatusTramitacao.EM_TRAMITACAO
    assert tramitacao.casa_atual == CasaLegislativa.SENADO
    assert tramitacao.turno_atual == 1

    sessao_senado, status_senado = _aprovar(tramitacao)
    assert status_senado == StatusTramitacao.APROVADA

    assert [r.id_sessao for r in tramitacao.historico] == [
        "PL-101/2026-CAMARA-T1",
        "PL-101/2026-SENADO-T1",
    ]
    assert sessao_camara.id_sessao == "PL-101/2026-CAMARA-T1"
    assert sessao_senado.id_sessao == "PL-101/2026-SENADO-T1"
    assert all(r.valida for r in tramitacao.historico)


def test_tramitacao_pec_exige_dois_turnos_em_cada_casa():
    tramitacao = TramitacaoLegislativa("PEC-50/2026", TipoMateriaCongresso.PEC)

    etapas = []
    for _ in range(4):
        assert tramitacao.status == StatusTramitacao.EM_TRAMITACAO
        sessao, _ = _aprovar(tramitacao)
        etapas.append(sessao.id_sessao)

    assert tramitacao.status == StatusTramitacao.APROVADA
    assert etapas == [
        "PEC-50/2026-CAMARA-T1",
        "PEC-50/2026-CAMARA-T2",
        "PEC-50/2026-SENADO-T1",
        "PEC-50/2026-SENADO-T2",
    ]
    assert [(r.casa, r.turno) for r in tramitacao.historico] == [
        (CasaLegislativa.CAMARA, 1),
        (CasaLegislativa.CAMARA, 2),
        (CasaLegislativa.SENADO, 1),
        (CasaLegislativa.SENADO, 2),
    ]


def test_tramitacao_rejeicao_encerra_o_rito():
    tramitacao = TramitacaoLegislativa("PEC-50/2026", TipoMateriaCongresso.PEC)
    _aprovar(tramitacao)

    _, status = _rejeitar(tramitacao)

    assert status == StatusTramitacao.REJEITADA
    assert tramitacao.historico[-1].resultado.status == StatusResultado.REJEITADO
    assert tramitacao.casa_atual == CasaLegislativa.CAMARA
    assert tramitacao.turno_atual == 2
    with pytest.raises(TramitacaoInvalidaError, match="REJEITADA"):
        tramitacao.nova_sessao()


def test_tramitacao_concluida_recusa_novo_registro():
    tramitacao = TramitacaoLegislativa("PL-101/2026", TipoMateriaCongresso.LEI_ORDINARIA)
    _aprovar(tramitacao)
    sessao, _ = _aprovar(tramitacao)
    assert tramitacao.status == StatusTramitacao.APROVADA

    with pytest.raises(TramitacaoInvalidaError, match="APROVADA"):
        tramitacao.nova_sessao()
    with pytest.raises(TramitacaoInvalidaError, match="APROVADA"):
        tramitacao.registrar_resultado(sessao)


def test_tramitacao_quorum_insuficiente_mantem_a_etapa():
    tramitacao = TramitacaoLegislativa("PL-101/2026", TipoMateriaCongresso.LEI_ORDINARIA)

    _, status = _deliberar(tramitacao, sim=RegraCongresso.QUORUM_INSTALACAO_CAMARA - 1)

    assert status == StatusTramitacao.EM_TRAMITACAO
    assert tramitacao.casa_atual == CasaLegislativa.CAMARA
    assert tramitacao.turno_atual == 1
    assert len(tramitacao.historico) == 1
    assert tramitacao.historico[0].valida is False
    assert tramitacao.historico[0].resultado.status == StatusResultado.QUORUM_INSUFICIENTE

    nova = tramitacao.nova_sessao()
    assert nova.id_sessao == "PL-101/2026-CAMARA-T1"
    _votar(nova, sim=APROVAR[CasaLegislativa.CAMARA])
    tramitacao.registrar_resultado(nova)

    assert tramitacao.casa_atual == CasaLegislativa.SENADO
    assert [r.valida for r in tramitacao.historico] == [False, True]


def test_tramitacao_recusa_sessao_nao_apurada():
    tramitacao = TramitacaoLegislativa("PL-101/2026", TipoMateriaCongresso.LEI_ORDINARIA)
    sessao = tramitacao.nova_sessao()
    sessao.abrir()

    with pytest.raises(TramitacaoInvalidaError, match="ainda não foi apurada"):
        tramitacao.registrar_resultado(sessao)

    assert tramitacao.historico == ()


def test_tramitacao_recusa_sessao_de_outra_etapa():
    tramitacao = TramitacaoLegislativa("PL-101/2026", TipoMateriaCongresso.LEI_ORDINARIA)
    tramitacao = TramitacaoLegislativa("PL-101/2026", TipoMateriaCongresso.LEI_ORDINARIA)
    tramitacao.nova_sessao()
    intrusa = SessaoVotacao(
        "PL-101/2026-SENADO-T1",
        RegraCongresso(TipoMateriaCongresso.LEI_ORDINARIA, CasaLegislativa.SENADO),
    )
    _votar(intrusa, sim=APROVAR[CasaLegislativa.SENADO])

    with pytest.raises(TramitacaoInvalidaError, match="não é a sessão convocada"):
        tramitacao.registrar_resultado(intrusa)

    assert tramitacao.casa_atual == CasaLegislativa.CAMARA
    assert tramitacao.turno_atual == 1
    assert tramitacao.historico == ()


def test_tramitacao_recusa_registrar_a_mesma_sessao_duas_vezes():
    tramitacao = TramitacaoLegislativa("PEC-50/2026", TipoMateriaCongresso.PEC)
    sessao, _ = _aprovar(tramitacao)
    assert tramitacao.turno_atual == 2

    with pytest.raises(TramitacaoInvalidaError, match="já teve seu resultado registrado"):
        tramitacao.registrar_resultado(sessao)

    assert tramitacao.turno_atual == 2
    assert len(tramitacao.historico) == 1


def _repo_com(materia: MateriaLegislativa) -> RepositorioCongresso:
    repo = RepositorioCongresso()
    repo.adicionar_materia(materia)
    return repo


def _pl_na_camara(**ajustes) -> MateriaLegislativa:
    campos = {
        "id": "PL-101/2026",
        "tipo": TipoMateriaCongresso.LEI_ORDINARIA,
        "casa_atual": CasaLegislativa.CAMARA,
        "titulo": "Projeto de teste",
        "ativa": True,
    }
    campos.update(ajustes)
    return MateriaLegislativa(**campos)


def test_tramitacao_recusa_materia_ausente_do_repositorio():
    with pytest.raises(ValueError, match="não está cadastrada"):
        TramitacaoLegislativa(
            "PL-404/2026", TipoMateriaCongresso.LEI_ORDINARIA, repo=RepositorioCongresso()
        )


def test_tramitacao_recusa_materia_arquivada():
    repo = _repo_com(_pl_na_camara(ativa=False))

    with pytest.raises(ValueError, match="arquivada"):
        TramitacaoLegislativa("PL-101/2026", TipoMateriaCongresso.LEI_ORDINARIA, repo=repo)


def test_tramitacao_recusa_tipo_divergente_do_cadastro():
    repo = _repo_com(_pl_na_camara())

    with pytest.raises(ValueError, match="cadastrada como LEI_ORDINARIA"):
        TramitacaoLegislativa("PL-101/2026", TipoMateriaCongresso.PEC, repo=repo)


def test_tramitacao_recusa_casa_iniciadora_divergente_do_cadastro():
    repo = _repo_com(_pl_na_camara(casa_atual=CasaLegislativa.SENADO))

    with pytest.raises(ValueError, match="pautada na SENADO"):
        TramitacaoLegislativa("PL-101/2026", TipoMateriaCongresso.LEI_ORDINARIA, repo=repo)


def test_tramitacao_move_a_materia_para_a_casa_revisora_no_repositorio():
    repo = _repo_com(_pl_na_camara())
    tramitacao = TramitacaoLegislativa("PL-101/2026", TipoMateriaCongresso.LEI_ORDINARIA, repo=repo)
    validador = ValidadorElegibilidadeCongresso()
    assert validador.validar_materia("PL-101/2026", CasaLegislativa.CAMARA, repo).elegivel

    _aprovar(tramitacao)

    materia = repo.obter_materia("PL-101/2026")
    assert materia is not None
    assert materia.casa_atual == CasaLegislativa.SENADO
    assert materia.ativa is True
    assert materia.titulo == "Projeto de teste"
    assert validador.validar_materia("PL-101/2026", CasaLegislativa.SENADO, repo).elegivel
    recusa = validador.validar_materia("PL-101/2026", CasaLegislativa.CAMARA, repo)
    assert recusa.elegivel is False
    assert "SENADO" in (recusa.motivo_inelegibilidade or "")


def test_tramitacao_pec_so_muda_de_casa_no_repositorio_apos_os_dois_turnos():
    repo = _repo_com(_pl_na_camara(id="PEC-50/2026", tipo=TipoMateriaCongresso.PEC))
    tramitacao = TramitacaoLegislativa("PEC-50/2026", TipoMateriaCongresso.PEC, repo=repo)

    _aprovar(tramitacao)
    materia = repo.obter_materia("PEC-50/2026")
    assert materia is not None
    assert materia.casa_atual == CasaLegislativa.CAMARA

    _aprovar(tramitacao)
    materia = repo.obter_materia("PEC-50/2026")
    assert materia is not None
    assert materia.casa_atual == CasaLegislativa.SENADO


def test_tramitacao_aprovada_arquiva_a_materia_no_repositorio():
    repo = _repo_com(_pl_na_camara())
    tramitacao = TramitacaoLegislativa("PL-101/2026", TipoMateriaCongresso.LEI_ORDINARIA, repo=repo)

    _aprovar(tramitacao)
    _, status = _aprovar(tramitacao)

    assert status == StatusTramitacao.APROVADA
    materia = repo.obter_materia("PL-101/2026")
    assert materia is not None
    assert materia.ativa is False
    recusa = ValidadorElegibilidadeCongresso().validar_materia(
        "PL-101/2026", CasaLegislativa.SENADO, repo
    )
    assert recusa.elegivel is False


def test_tramitacao_rejeitada_arquiva_a_materia_no_repositorio():
    repo = _repo_com(_pl_na_camara())
    tramitacao = TramitacaoLegislativa("PL-101/2026", TipoMateriaCongresso.LEI_ORDINARIA, repo=repo)

    _, status = _rejeitar(tramitacao)

    assert status == StatusTramitacao.REJEITADA
    materia = repo.obter_materia("PL-101/2026")
    assert materia is not None
    assert materia.ativa is False
    assert materia.casa_atual == CasaLegislativa.CAMARA


def test_tramitacao_sem_repositorio_nao_toca_em_cadastro_algum():
    repo = _repo_com(_pl_na_camara())
    tramitacao = TramitacaoLegislativa("PL-101/2026", TipoMateriaCongresso.LEI_ORDINARIA)

    _aprovar(tramitacao)
    _aprovar(tramitacao)

    materia = repo.obter_materia("PL-101/2026")
    assert materia is not None
    assert materia.casa_atual == CasaLegislativa.CAMARA
    assert materia.ativa is True


def test_tramitacao_ignora_materia_removida_do_repositorio_apos_o_inicio():
    repo = _repo_com(_pl_na_camara())
    tramitacao = TramitacaoLegislativa("PL-101/2026", TipoMateriaCongresso.LEI_ORDINARIA, repo=repo)
    repo.limpar()

    _aprovar(tramitacao)

    assert tramitacao.casa_atual == CasaLegislativa.SENADO
    assert repo.obter_materia("PL-101/2026") is None

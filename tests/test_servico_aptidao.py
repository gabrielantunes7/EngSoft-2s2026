"""Testes unitários e de integração para o ServicoElegibilidade."""

from datetime import UTC, datetime

import pytest

from votacao.dados.seeds import BancoDadosMock
from votacao.modelos import CasaLegislativa
from votacao.servicos import ServicoElegibilidade


@pytest.fixture
def servico() -> ServicoElegibilidade:
    """Fixture com o serviço instanciado com o banco mockado padrão."""
    banco = BancoDadosMock(popular=True)
    return ServicoElegibilidade(banco=banco)


def test_autenticar_ca(servico: ServicoElegibilidade):
    # Usuário válido
    user = servico.autenticar("247314", "CA")
    assert user is not None
    assert user.id == "247314"
    assert user.nome == "Lucas Bussinger"
    assert user.ativo is True
    assert "@dac.unicamp.br" in user.email

    # Usuário inexistente
    assert servico.autenticar("999999", "CA") is None

    # Usuário com matrícula trancada (inativo)
    user_trancado = servico.autenticar("333444", "CA")
    assert user_trancado is not None
    assert user_trancado.ativo is False

    # Usuário suspenso (inativo para uso)
    user_suspenso = servico.autenticar("555666", "CA")
    assert user_suspenso is not None
    assert user_suspenso.ativo is False


def test_autenticar_assembleia(servico: ServicoElegibilidade):
    # Acionista titular regular
    user = servico.autenticar("AC-001", "ASSEMBLEIA")
    assert user is not None
    assert user.id == "AC-001"
    assert user.ativo is True

    # Acionista bloqueado (inativo para autenticação)
    user_bloq = servico.autenticar("AC-005", "ASSEMBLEIA")
    assert user_bloq is not None
    assert user_bloq.ativo is False

    # Acionista inexistente
    assert servico.autenticar("AC-INEXISTENTE", "ASSEMBLEIA") is None


def test_autenticar_congresso(servico: ServicoElegibilidade):
    # Deputado em exercício
    user_dep = servico.autenticar("DEP-001", "CONGRESSO")
    assert user_dep is not None
    assert user_dep.ativo is True
    assert "@camara.leg.br" in user_dep.email

    # Senador em exercício
    user_sen = servico.autenticar("SEN-001", "CONGRESSO")
    assert user_sen is not None
    assert user_sen.ativo is True
    assert "@senado.leg.br" in user_sen.email

    # Parlamentar licenciado
    user_lic = servico.autenticar("DEP-003", "CONGRESSO")
    assert user_lic is not None
    assert user_lic.ativo is False

    # Inexistente
    assert servico.autenticar("DEP-999", "CONGRESSO") is None


def test_autenticar_contexto_invalido(servico: ServicoElegibilidade):
    with pytest.raises(ValueError, match="Contexto de votação desconhecido"):
        servico.autenticar("123", "CONTEXTO_INEXISTENTE")


def test_consultar_aptidao_ca(servico: ServicoElegibilidade):
    apt_ok = servico.consultar_aptidao("247314", "CA")
    assert apt_ok.apto is True
    assert apt_ok.peso_voto == 1

    apt_invalido = servico.consultar_aptidao("333444", "CA")
    assert apt_invalido.apto is False
    assert apt_invalido.peso_voto == 0


def test_consultar_aptidao_assembleia_direto_e_procurador(servico: ServicoElegibilidade):
    # Voto direto de acionista sem procuração vigente (a de AC-003 foi revogada)
    apt_titular = servico.consultar_aptidao("AC-003", "ASSEMBLEIA")
    assert apt_titular.apto is True
    assert apt_titular.peso_voto == 150_000

    # Voto direto de acionista cuja procuração expirou
    apt_titular_exp = servico.consultar_aptidao("AC-002", "ASSEMBLEIA")
    assert apt_titular_exp.apto is True
    assert apt_titular_exp.peso_voto == 300_000

    # Quem delegou o voto por procuração vigente não vota diretamente
    apt_delegou = servico.consultar_aptidao("AC-001", "ASSEMBLEIA")
    assert apt_delegou.apto is False
    assert apt_delegou.peso_voto == 0
    assert "PROC-101" in (apt_delegou.motivo_inaptidao or "")

    # Voto com procuração válida
    agora = datetime.now(UTC)
    apt_proc = servico.consultar_aptidao(
        eleitor_id="AC-001",
        contexto="ASSEMBLEIA",
        procurador_id="PROC-101",
        momento=agora,
    )
    assert apt_proc.apto is True
    assert apt_proc.peso_voto == 500_000
    assert apt_proc.dados_eleitor["procurador_id"] == "PROC-101"

    # Voto com procuração expirada
    apt_proc_exp = servico.consultar_aptidao(
        eleitor_id="AC-002",
        contexto="ASSEMBLEIA",
        procurador_id="PROC-102",
        momento=agora,
    )
    assert apt_proc_exp.apto is False


def test_consultar_aptidao_congresso(servico: ServicoElegibilidade):
    # Erro se casa for None
    with pytest.raises(ValueError, match="a CasaLegislativa deve ser informada"):
        servico.consultar_aptidao("DEP-001", "CONGRESSO")

    # Aptidão na Câmara
    apt = servico.consultar_aptidao("DEP-001", "CONGRESSO", casa=CasaLegislativa.CAMARA)
    assert apt.apto is True
    assert apt.peso_voto == 1

    # Inaptidão de deputado votando no Senado
    apt_err = servico.consultar_aptidao("DEP-001", "CONGRESSO", casa=CasaLegislativa.SENADO)
    assert apt_err.apto is False


def test_validar_candidato_ou_opcao_ca(servico: ServicoElegibilidade):
    # Chapa válida
    eleg = servico.validar_candidato_ou_opcao("Chapa Renova", "CA")
    assert eleg.elegivel is True

    # Voto em Branco ou Nulo
    assert servico.validar_candidato_ou_opcao("BRANCO", "CA").elegivel is True
    assert servico.validar_candidato_ou_opcao("NULO", "CA").elegivel is True

    # Chapa inválida (contém formando)
    assert servico.validar_candidato_ou_opcao("Chapa Invalida", "CA").elegivel is False


def test_validar_candidato_ou_opcao_assembleia(servico: ServicoElegibilidade):
    # Deliberações gerais
    assert servico.validar_candidato_ou_opcao("SIM", "ASSEMBLEIA").elegivel is True
    assert servico.validar_candidato_ou_opcao("NAO", "ASSEMBLEIA").elegivel is True
    assert servico.validar_candidato_ou_opcao("ABSTENCAO", "ASSEMBLEIA").elegivel is True

    # Candidato a conselho
    eleg_cons = servico.validar_candidato_ou_opcao("CONS-01", "ASSEMBLEIA")
    assert eleg_cons.elegivel is True

    eleg_bloq = servico.validar_candidato_ou_opcao("CONS-02", "ASSEMBLEIA")
    assert eleg_bloq.elegivel is False


def test_validar_candidato_ou_opcao_congresso(servico: ServicoElegibilidade):
    with pytest.raises(ValueError, match="a CasaLegislativa deve ser informada"):
        servico.validar_candidato_ou_opcao("SIM", "CONGRESSO")

    # Opção padrão
    eleg_sim = servico.validar_candidato_ou_opcao("SIM", "CONGRESSO", casa=CasaLegislativa.CAMARA)
    assert eleg_sim.elegivel is True

    # Matéria pautada
    eleg_mat = servico.validar_candidato_ou_opcao(
        "PL-101/2026", "CONGRESSO", casa=CasaLegislativa.CAMARA
    )
    assert eleg_mat.elegivel is True


def test_autorizar_voto_ca_sucesso(servico: ServicoElegibilidade):
    voto = servico.autorizar_voto(
        eleitor_id="247314",
        opcao="Chapa Renova",
        contexto="CA",
    )
    assert voto.eleitor_id == "247314"
    assert voto.opcao == "CHAPA RENOVA"
    assert voto.peso == 1
    assert voto.timestamp is not None


def test_autorizar_voto_ca_eleitor_inapto(servico: ServicoElegibilidade):
    with pytest.raises(PermissionError, match="inapto para votar"):
        servico.autorizar_voto(
            eleitor_id="333444",  # Aluno trancado
            opcao="Chapa Renova",
            contexto="CA",
        )


def test_autorizar_voto_ca_opcao_invalida(servico: ServicoElegibilidade):
    with pytest.raises(ValueError, match="inelegível para votação"):
        servico.autorizar_voto(
            eleitor_id="247314",
            opcao="Chapa Invalida",
            contexto="CA",
        )


def test_autorizar_voto_assembleia_titular_e_procurador(servico: ServicoElegibilidade):
    # Titular sem procuração vigente (a de AC-002 expirou)
    voto_titular = servico.autorizar_voto(
        eleitor_id="AC-002",
        opcao="SIM",
        contexto="ASSEMBLEIA",
    )
    assert voto_titular.eleitor_id == "AC-002"
    assert voto_titular.opcao == "SIM"
    assert voto_titular.peso == 300_000

    # Titular que delegou o voto é recusado enquanto a procuração estiver vigente
    with pytest.raises(PermissionError, match="delegou o voto ao procurador 'PROC-101'"):
        servico.autorizar_voto(
            eleitor_id="AC-001",
            opcao="SIM",
            contexto="ASSEMBLEIA",
        )

    # Procurador
    voto_proc = servico.autorizar_voto(
        eleitor_id="AC-001",
        opcao="NAO",
        contexto="ASSEMBLEIA",
        procurador_id="PROC-101",
    )
    assert voto_proc.eleitor_id == "AC-001#rep:PROC-101"
    assert voto_proc.opcao == "NAO"
    assert voto_proc.peso == 500_000


def test_autorizar_voto_congresso(servico: ServicoElegibilidade):
    voto = servico.autorizar_voto(
        eleitor_id="DEP-001",
        opcao="SIM",
        contexto="CONGRESSO",
        casa=CasaLegislativa.CAMARA,
    )
    assert voto.eleitor_id == "DEP-001"
    assert voto.opcao == "SIM"
    assert voto.peso == 1


def test_autorizar_voto_sem_validar_opcao(servico: ServicoElegibilidade):
    voto = servico.autorizar_voto(
        eleitor_id="247314",
        opcao="Chapa Inexistente Qualquer",
        contexto="CA",
        validar_opcao=False,
    )
    assert voto.eleitor_id == "247314"
    assert voto.opcao == "CHAPA INEXISTENTE QUALQUER"
    assert voto.peso == 1

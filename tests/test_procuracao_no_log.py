"""Testes do registro de votos por procuração no log de auditoria (história #42).

Antes da #42, o VOTO_REGISTRADO guardava só o peso consolidado: o acionista ausente não
conseguia verificar se as suas ações entraram no cômputo, e a Mesa não conseguia auditar
sobreposição de cotas delegadas (D-AUD-08; Lei das S/A, art. 126, § 1º).
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from votacao.auditoria import LogDeAuditoria, PoliticaIdentificacao, TipoEvento
from votacao.dados.seeds import BancoDadosMock
from votacao.modelos import Representacao, Voto
from votacao.servicos import ServicoElegibilidade


def _log() -> LogDeAuditoria:
    return LogDeAuditoria("AGE-2026", politica=PoliticaIdentificacao.NOMINAL)


@pytest.fixture
def servico() -> ServicoElegibilidade:
    servico = ServicoElegibilidade(BancoDadosMock())
    # AC-001 -> PROC-101 já existe nos dados de exemplo; AC-003 também delega a PROC-101.
    servico.procuracoes.cadastrar(
        "AC-003", "PROC-101", data_expiracao=datetime.now(UTC) + timedelta(days=10)
    )
    return servico


# --- Composição do voto ----------------------------------------------------------------


def test_voto_consolidado_discrimina_cada_representado(servico: ServicoElegibilidade):
    voto = servico.autorizar_voto_do_procurador("PROC-101", "SIM")

    assert voto.peso_proprio == 0
    assert voto.representacoes == (
        Representacao("AC-001", 500_000, "PROC:AC-001>PROC-101"),
        Representacao("AC-003", 150_000, "PROC:AC-003>PROC-101"),
    )
    assert voto.peso == 650_000


def test_voto_por_procuracao_de_um_outorgante_discrimina_o_mandato(
    servico: ServicoElegibilidade,
):
    voto = servico.autorizar_voto(
        eleitor_id="AC-001", opcao="NAO", contexto="ASSEMBLEIA", procurador_id="PROC-101"
    )

    assert voto.peso_proprio == 0
    assert voto.representacoes == (Representacao("AC-001", 500_000, "PROC:AC-001>PROC-101"),)


def test_voto_direto_continua_sem_representacoes(servico: ServicoElegibilidade):
    voto = servico.autorizar_voto(eleitor_id="AC-002", opcao="SIM", contexto="ASSEMBLEIA")

    assert voto.representacoes == ()
    assert voto.peso_proprio is None


# --- Validação da soma dos pesos -------------------------------------------------------


def test_soma_dos_representados_com_peso_proprio_deve_igualar_o_peso():
    reps = (Representacao("AC-001", 500, "PROC:AC-001>P"),)

    with pytest.raises(ValueError, match="difere do peso próprio somado"):
        Voto(eleitor_id="P", opcao="SIM", peso=600, representacoes=reps, peso_proprio=0)

    voto = Voto(eleitor_id="P", opcao="SIM", peso=600, representacoes=reps, peso_proprio=100)
    assert voto.peso == 600


def test_voto_por_procuracao_exige_peso_proprio():
    reps = (Representacao("AC-001", 500, "PROC:AC-001>P"),)

    with pytest.raises(ValueError, match="peso próprio"):
        Voto(eleitor_id="P", opcao="SIM", peso=500, representacoes=reps)


def test_outorgante_repetido_no_mesmo_voto_e_recusado():
    reps = (
        Representacao("AC-001", 500, "PROC:AC-001>P"),
        Representacao("AC-001", 500, "PROC:AC-001>P"),
    )

    with pytest.raises(ValueError, match="duas vezes"):
        Voto(eleitor_id="P", opcao="SIM", peso=1000, representacoes=reps, peso_proprio=0)


# --- Registro no log -------------------------------------------------------------------


def test_log_nominal_serializa_representacoes_e_peso_proprio(servico: ServicoElegibilidade):
    log = _log()

    registro = log.registrar_voto(servico.autorizar_voto_do_procurador("PROC-101", "SIM"))

    assert registro.dados["procurador_id"] == "PROC-101"
    assert registro.dados["peso_proprio"] == 0
    assert registro.dados["representacoes"] == [
        {"outorgante_id": "AC-001", "peso": 500_000, "procuracao_id": "PROC:AC-001>PROC-101"},
        {"outorgante_id": "AC-003", "peso": 150_000, "procuracao_id": "PROC:AC-003>PROC-101"},
    ]
    soma = registro.dados["peso_proprio"] + sum(r["peso"] for r in registro.dados["representacoes"])
    assert soma == registro.dados["peso"]


def test_serializacao_e_deterministica_independente_da_ordem_de_entrada():
    reps = (
        Representacao("AC-009", 10, "PROC:AC-009>P"),
        Representacao("AC-001", 20, "PROC:AC-001>P"),
    )
    voto_a = Voto(eleitor_id="P", opcao="SIM", peso=30, representacoes=reps, peso_proprio=0)
    voto_b = replace(voto_a, representacoes=tuple(reversed(reps)))

    dados_a = _log().registrar_voto(voto_a).dados
    dados_b = _log().registrar_voto(voto_b).dados

    assert dados_a["representacoes"] == dados_b["representacoes"]
    assert [r["outorgante_id"] for r in dados_a["representacoes"]] == ["AC-001", "AC-009"]


def test_adulterar_um_representado_e_detectado_pela_cadeia(servico: ServicoElegibilidade):
    log = _log()
    log.registrar(TipoEvento.VOTACAO_ABERTA)
    log.registrar_voto(servico.autorizar_voto_do_procurador("PROC-101", "SIM"))
    original = log.registros[1]
    reps = [dict(r) for r in original.dados["representacoes"]]
    reps[1]["peso"] = 1  # rouba ações do AC-003

    log._registros[1] = replace(original, dados={**original.dados, "representacoes": reps})

    resultado = log.verificar_integridade()
    assert resultado.integro is False
    assert resultado.indice_divergente == 1


def test_procurador_sem_acoes_proprias_vota_so_com_as_fracoes_dos_representados(
    servico: ServicoElegibilidade,
):
    voto = servico.autorizar_voto_do_procurador("PROC-101", "SIM")
    log = _log()

    registro = log.registrar_voto(voto)

    assert registro.dados["peso_proprio"] == 0
    assert registro.dados["peso"] == sum(r["peso"] for r in registro.dados["representacoes"])
    assert log.consultar_outorgante("PROC-101") == []


# --- Consulta individual por outorgante ------------------------------------------------


def test_consulta_por_outorgante_mostra_onde_as_acoes_foram_computadas(
    servico: ServicoElegibilidade,
):
    log = _log()
    log.registrar(TipoEvento.VOTACAO_ABERTA)
    log.registrar_voto(
        servico.autorizar_voto(eleitor_id="AC-002", opcao="NAO", contexto="ASSEMBLEIA")
    )
    log.registrar_voto(servico.autorizar_voto_do_procurador("PROC-101", "SIM"))

    assert log.consultar_outorgante("AC-003") == [
        {
            "indice": 2,
            "votante": "PROC-101",
            "peso": 150_000,
            "opcao": "SIM",
            "procuracao_id": "PROC:AC-003>PROC-101",
        }
    ]
    assert log.consultar_outorgante("AC-002") == [
        {"indice": 1, "votante": "AC-002", "peso": 300_000, "opcao": "NAO", "procuracao_id": None}
    ]
    assert log.consultar_outorgante("AC-005") == []


def test_procurador_acionista_aparece_com_o_peso_proprio():
    reps = (Representacao("AC-001", 500, "PROC:AC-001>AC-007"),)
    voto = Voto(eleitor_id="AC-007", opcao="SIM", peso=700, representacoes=reps, peso_proprio=200)
    log = _log()
    log.registrar_voto(voto)

    assert log.consultar_outorgante("AC-007") == [
        {"indice": 0, "votante": "AC-007", "peso": 200, "opcao": "SIM", "procuracao_id": None}
    ]
    assert log.consultar_outorgante("AC-001")[0]["peso"] == 500


def test_consulta_por_outorgante_exige_log_nominal():
    with pytest.raises(ValueError, match="sigiloso"):
        LogDeAuditoria("CA-2026").consultar_outorgante("AC-001")


# --- Duplicidade -----------------------------------------------------------------------


def test_cotas_de_quem_ja_votou_diretamente_sao_recusadas(servico: ServicoElegibilidade):
    log = _log()
    log.registrar_voto(Voto(eleitor_id="AC-003", opcao="NAO", peso=150_000))

    with pytest.raises(ValueError, match=r"Duplicidade.*AC-003"):
        log.registrar_voto(servico.autorizar_voto_do_procurador("PROC-101", "SIM"))


def test_outorgante_ja_representado_nao_e_computado_de_novo(servico: ServicoElegibilidade):
    log = _log()
    log.registrar_voto(
        servico.autorizar_voto(
            eleitor_id="AC-001", opcao="SIM", contexto="ASSEMBLEIA", procurador_id="PROC-101"
        )
    )

    with pytest.raises(ValueError, match=r"Duplicidade.*AC-001"):
        log.registrar_voto(servico.autorizar_voto_do_procurador("PROC-101", "SIM"))


def test_voto_recusado_por_duplicidade_nao_entra_na_cadeia(servico: ServicoElegibilidade):
    log = _log()
    log.registrar_voto(Voto(eleitor_id="AC-001", opcao="NAO", peso=500_000))

    with pytest.raises(ValueError):
        log.registrar_voto(servico.autorizar_voto_do_procurador("PROC-101", "SIM"))

    assert len(log.registros) == 1


# --- Retrocompatibilidade --------------------------------------------------------------


def test_voto_direto_no_log_nominal_mantem_o_formato_anterior():
    registro = _log().registrar_voto(Voto(eleitor_id="AC-002", opcao="SIM", peso=300_000))

    assert registro.dados == {"eleitor_id": "AC-002", "opcao": "SIM", "peso": 300_000}


def test_log_sigiloso_continua_sem_conteudo_no_voto_por_procuracao(
    servico: ServicoElegibilidade,
):
    log = LogDeAuditoria("CA-2026")

    registro = log.registrar_voto(servico.autorizar_voto_do_procurador("PROC-101", "SIM"))

    assert registro.dados == {}

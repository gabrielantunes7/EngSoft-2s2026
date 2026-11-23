"""Testes automatizados da camada de interface gráfica (UI), controlador e servidor HTTP."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from UI.app import EstadoAplicacaoUI
from UI.servidor import criar_servidor
from votacao.sessao import EstadoSessao, VotoRecusadoError
from votacao.tramitacao import TramitacaoInvalidaError


class TestEstadoAplicacaoUI:
    """Valida todas as operações de domínio expostas pelo controlador da interface gráfica."""

    def test_inicializacao_e_cenario_demonstracao(self) -> None:
        app = EstadoAplicacaoUI()
        estado = app.obter_estado_completo()

        assert "sessoes" in estado
        assert "ELEICAO-CA-2026" in estado["sessoes"]
        assert "AGE-2026-01" in estado["sessoes"]
        assert "PL-101/2026" in estado["tramitacoes"]

        sessao_ca = estado["sessoes"]["ELEICAO-CA-2026"]
        assert sessao_ca["estado"] == EstadoSessao.EM_VOTACAO.value
        assert sessao_ca["auditoria"]["cadeia_integra"] is True

    def test_resetar_sistema(self) -> None:
        app = EstadoAplicacaoUI()
        app.cadastrar_discente({"ra": "999999", "nome": "Novo Aluno"})
        assert app.banco.ca.obter_discente("999999") is not None

        estado_reset = app.resetar_sistema(usar_sql=False)
        assert app.banco.ca.obter_discente("999999") is None
        assert "ELEICAO-CA-2026" in estado_reset["sessoes"]

        estado_sql = app.resetar_sistema(usar_sql=True)
        assert "ELEICAO-CA-2026" in estado_sql["sessoes"]

    def test_cadastro_e_elegibilidade_ca(self) -> None:
        app = EstadoAplicacaoUI()
        disc = app.cadastrar_discente(
            {
                "ra": "202699",
                "nome": "Carla Silva",
                "curso": "Ciência da Computação",
                "semestre": 3,
                "matricula_ativa": True,
                "situacao_regular": True,
            }
        )
        assert disc["ra"] == "202699"
        assert disc["apto_votar"] is True

        chapa = app.cadastrar_chapa(
            {
                "id": "CHAPA-TESTE",
                "nome": "CHAPA-TESTE",
                "presidente_ra": "202699",
                "vice_ra": "247314",
                "proposta": "Melhorias",
                "regular": True,
            }
        )
        assert chapa["nome"] == "CHAPA-TESTE"
        assert chapa["elegivel"] is True

    def test_cadastro_e_poder_assembleia(self) -> None:
        app = EstadoAplicacaoUI()
        ac = app.cadastrar_acionista(
            {
                "id": "AC-NOVO",
                "nome": "Fundo Alpha",
                "acoes_on": 50000,
                "acoes_pn": 10000,
                "pn_com_voto": False,
                "adimplente": True,
            }
        )
        assert ac["id"] == "AC-NOVO"
        assert ac["peso_voto"] == 50000

        proc = app.cadastrar_procurador({"id": "PROC-NOVO", "nome": "Advogado Teste"})
        assert proc["id"] == "PROC-NOVO"

        procuracao = app.cadastrar_procuracao(
            {
                "outorgante_id": "AC-NOVO",
                "procurador_id": "PROC-NOVO",
                "validade_dias": 10,
            }
        )
        assert procuracao["outorgante_id"] == "AC-NOVO"
        assert procuracao["ativa"] is True

        rev = app.revogar_procuracao({"outorgante_id": "AC-NOVO", "procurador_id": "PROC-NOVO"})
        assert rev["ativa"] is False

        cand = app.cadastrar_candidato_conselho(
            {"id": "CAND-NOVO", "nome": "Conselheiro Alpha", "conflito_interesse": False}
        )
        assert cand["id"] == "CAND-NOVO"
        assert cand["elegivel"] is True

    def test_cadastro_congresso_e_parlamentares(self) -> None:
        app = EstadoAplicacaoUI()
        parl = app.cadastrar_parlamentar(
            {
                "id": "DEP-TESTE",
                "nome": "Deputada Teste",
                "casa": "CAMARA",
                "partido": "NOVO",
                "uf": "SP",
                "em_exercicio": True,
            }
        )
        assert parl["id"] == "DEP-TESTE"
        assert parl["apto_votar"] is True

        mat = app.cadastrar_materia(
            {
                "id": "PL-500/2026",
                "tipo": "PL",
                "titulo": "Incentivo à Pesquisa",
                "ementa": "Ementa teste",
                "casa_atual": "CAMARA",
                "autor_id": "DEP-TESTE",
            }
        )
        assert mat["id"] == "PL-500/2026"
        assert "PL-500/2026" in app.tramitacoes

    def test_fluxo_completo_sessao_ca(self) -> None:
        app = EstadoAplicacaoUI()
        sessao = app.criar_sessao(
            id_sessao="SESSAO-CA-TESTE",
            contexto="CA",
            titulo="Eleição Diretoria Teste",
            quorum_minimo_votantes=2,
            percentual_quorum_minimo=0.1,
            abrir_imediatamente=True,
            liberar_imediatamente=True,
        )
        assert sessao["estado"] == "EM_VOTACAO"

        voto1 = app.registrar_voto_na_sessao(
            "SESSAO-CA-TESTE",
            {"eleitor_id": "247314", "opcao": "Chapa Renova"},
        )
        assert voto1["protocolo"] is not None

        voto2 = app.registrar_voto_na_sessao(
            "SESSAO-CA-TESTE",
            {"eleitor_id": "242352", "opcao": "Chapa Renova"},
        )
        assert voto2["protocolo"] is not None

        # Verifica protocolo na auditoria
        verif = app.verificar_protocolo_auditoria("SESSAO-CA-TESTE", voto1["protocolo"])
        assert verif["encontrado"] is True

        # Apuração
        apuracao = app.apurar_sessao("SESSAO-CA-TESTE")
        assert apuracao["resultado"] is not None
        assert apuracao["resultado"]["quorum_atingido"] is True
        assert apuracao["resultado"]["vencedor"] == "CHAPA RENOVA"

    def test_sigilo_do_voto_no_ca(self) -> None:
        # D-AUD-02/03/04 (Atividade 3): na eleição de CA nada do que a UI expõe pode
        # ligar um eleitor à sua opção, nem durante nem depois da votação.
        app = EstadoAplicacaoUI()
        res = app.registrar_voto_na_sessao(
            "ELEICAO-CA-2026", {"eleitor_id": "247314", "opcao": "Chapa Futuro"}
        )

        assert res["voto"] == {"peso": 1, "sigiloso": True}

        sessao = app.serializar_sessao("ELEICAO-CA-2026")
        assert sessao["voto_secreto"] is True
        assert sessao["votos"] == []
        assert sessao["contagem_parcial"] == {}
        assert sessao["total_votos"] == 1

        registros_voto = [
            r for r in sessao["auditoria"]["registros"] if r["evento"] == "VOTO_REGISTRADO"
        ]
        assert registros_voto == [
            {**registros_voto[0], "timestamp": None, "dados": {"conteudo": "sigiloso"}}
        ]

        verif = app.verificar_protocolo_auditoria("ELEICAO-CA-2026", res["protocolo"])
        assert verif["encontrado"] is True
        assert verif["registro"]["dados"] == {"conteudo": "sigiloso"}
        assert verif["registro"]["timestamp"] is None

        # Durante a votação, nenhuma resposta contém a opção votada nem o eleitor.
        app.registrar_voto_na_sessao(
            "ELEICAO-CA-2026", {"eleitor_id": "242352", "opcao": "Chapa Futuro"}
        )
        em_votacao = json.dumps(app.obter_estado_completo(), ensure_ascii=False)
        assert "CHAPA FUTURO" not in em_votacao
        assert "247314" not in json.dumps(app.serializar_sessao("ELEICAO-CA-2026"))

        # Após a apuração só o resultado agregado é público; o eleitor segue oculto.
        app.apurar_sessao("ELEICAO-CA-2026")
        final = app.serializar_sessao("ELEICAO-CA-2026")
        assert final["resultado"]["vencedor"] == "CHAPA FUTURO"
        assert final["votos"] == []
        assert "247314" not in json.dumps(final, ensure_ascii=False)
        assert "242352" not in json.dumps(final, ensure_ascii=False)

        # A ocultação é só de exibição: o log interno segue íntegro para recontagem.
        sessao_dominio = app.sessoes["ELEICAO-CA-2026"]
        assert sessao_dominio.log is not None
        assert sessao_dominio.log.verificar_integridade().integro is True

    def test_voto_aberto_e_nominal_na_assembleia(self) -> None:
        # Na assembleia societária o voto é aberto (Lei das S/A, história #44).
        app = EstadoAplicacaoUI()
        res = app.registrar_voto_na_sessao(
            "AGE-2026-01", {"eleitor_id": "AC-002", "opcao": "SIM", "modo": "DIRETO"}
        )
        assert res["voto"]["eleitor_id"] == "AC-002"
        assert res["voto"]["opcao"] == "SIM"

        sessao = app.serializar_sessao("AGE-2026-01")
        assert sessao["voto_secreto"] is False
        assert sessao["votos"][0]["eleitor_id"] == "AC-002"
        assert "SIM" in sessao["contagem_parcial"]
        registro = next(
            r for r in sessao["auditoria"]["registros"] if r["evento"] == "VOTO_REGISTRADO"
        )
        assert registro["dados"]["opcao"] == "SIM"
        assert registro["timestamp"] is not None

    def test_fluxo_voto_societario_com_procuracao(self) -> None:
        app = EstadoAplicacaoUI()
        app.criar_sessao(
            id_sessao="SESSAO-ASS-TESTE",
            contexto="ASSEMBLEIA",
            titulo="Assembleia Geral Teste",
            tipo_decisao="MAIORIA_SIMPLES",
            abrir_imediatamente=True,
            liberar_imediatamente=True,
        )

        # Voto direto de acionista
        res_direto = app.registrar_voto_na_sessao(
            "SESSAO-ASS-TESTE",
            {"eleitor_id": "AC-002", "opcao": "SIM", "modo": "DIRETO"},
        )
        assert res_direto["voto"]["peso"] > 0

        # Outorga e voto por procuração (AC-003 através de PROC-102)
        app.cadastrar_procuracao(
            {"outorgante_id": "AC-003", "procurador_id": "PROC-102", "validade_dias": 10}
        )
        res_proc = app.registrar_voto_na_sessao(
            "SESSAO-ASS-TESTE",
            {
                "eleitor_id": "AC-003",
                "procurador_id": "PROC-102",
                "opcao": "SIM",
                "modo": "PROCURACAO",
            },
        )
        assert res_proc["voto"]["peso"] > 0

        # Voto consolidado do procurador (PROC-101)
        res_cons = app.registrar_voto_na_sessao(
            "SESSAO-ASS-TESTE",
            {
                "procurador_id": "PROC-101",
                "opcao": "NAO",
                "modo": "CONSOLIDADO_PROCURADOR",
            },
        )
        assert res_cons["voto"]["peso"] > 0

    def test_suspensao_e_retomada_pela_interface(self) -> None:
        # #38: suspender preserva os votos; a retomada devolve a votação.
        app = EstadoAplicacaoUI()
        app.registrar_voto_na_sessao(
            "ELEICAO-CA-2026", {"eleitor_id": "247314", "opcao": "Chapa Renova"}
        )

        suspensa = app.suspender_sessao("ELEICAO-CA-2026", "Questão de ordem")
        assert suspensa["estado"] == "SUSPENSA"
        assert suspensa["motivo_suspensao"] == "Questão de ordem"
        assert suspensa["total_votos"] == 1

        with pytest.raises(VotoRecusadoError, match="suspensa"):
            app.registrar_voto_na_sessao(
                "ELEICAO-CA-2026", {"eleitor_id": "242352", "opcao": "Chapa Renova"}
            )

        retomada = app.retomar_sessao("ELEICAO-CA-2026")
        assert retomada["estado"] == "EM_VOTACAO"
        assert retomada["motivo_suspensao"] is None
        assert retomada["total_suspensoes"] == 1
        app.registrar_voto_na_sessao(
            "ELEICAO-CA-2026", {"eleitor_id": "242352", "opcao": "Chapa Renova"}
        )
        assert app.apurar_sessao("ELEICAO-CA-2026")["resultado"]["vencedor"] == "CHAPA RENOVA"

        eventos = [r["evento"] for r in retomada["auditoria"]["registros"]]
        assert eventos[-2:] == ["VOTACAO_SUSPENSA", "VOTACAO_RETOMADA"]

    def test_anulacao_pela_interface(self) -> None:
        # #39: anular descarta o resultado e fica no log com o motivo.
        app = EstadoAplicacaoUI()
        for ra in ("247314", "242352"):
            app.registrar_voto_na_sessao(
                "ELEICAO-CA-2026", {"eleitor_id": ra, "opcao": "Chapa Renova"}
            )
        app.apurar_sessao("ELEICAO-CA-2026")

        anulada = app.anular_sessao("ELEICAO-CA-2026", "Eleitor inapto votou")

        assert anulada["estado"] == "ANULADA"
        assert anulada["motivo_anulacao"] == "Eleitor inapto votou"
        assert anulada["resultado"] is None
        assert anulada["auditoria"]["registros"][-1]["evento"] == "SESSAO_ANULADA"

    def test_anulacao_na_tramitacao_mantem_a_etapa(self) -> None:
        app = EstadoAplicacaoUI()
        conv = app.convocar_sessao_tramitacao("PL-101/2026", liberar_imediatamente=False)
        id_sessao = conv["sessao"]["id_sessao"]
        app.registrar_presenca_sessao(id_sessao, {"bancada": 300})
        app.liberar_votacao_sessao(id_sessao)
        app.simular_votacao_plenario(id_sessao, {"votos_sim": 280})

        app.anular_sessao(id_sessao, "Painel de votação com defeito")
        tram = app.tramitacoes["PL-101/2026"]
        assert tram.casa_atual.value == "CAMARA"
        assert tram.historico == ()

        # Nova sessão para a mesma etapa; a anulada fica arquivada como tentativa
        nova = app.convocar_sessao_tramitacao("PL-101/2026", liberar_imediatamente=False)
        assert nova["sessao"]["id_sessao"] == id_sessao
        assert nova["sessao"]["estado"] == "CRIADA"
        tentativas = [s for s in app.sessoes if "TENTATIVA" in s]
        assert [app.serializar_sessao(t)["estado"] for t in tentativas] == ["ANULADA"]

    def test_anulacoes_seguidas_no_mesmo_turno_preservam_todas_as_tentativas(self) -> None:
        # Revisão do PR #70: a sessão anulada não entra no histórico da tramitação, e a
        # chave da tentativa arquivada não pode depender dele.
        app = EstadoAplicacaoUI()
        anuladas = []
        for motivo in ("Painel com defeito", "Quórum fraudado", "Erro de pauta"):
            sessao = app.convocar_sessao_tramitacao("PL-101/2026", liberar_imediatamente=False)[
                "sessao"
            ]
            app.abrir_sessao(sessao["id_sessao"])
            app.anular_sessao(sessao["id_sessao"], motivo)
            anuladas.append(motivo)
        app.convocar_sessao_tramitacao("PL-101/2026", liberar_imediatamente=False)

        tentativas = sorted(s for s in app.sessoes if "TENTATIVA" in s)
        assert tentativas == [
            "PL-101/2026-CAMARA-T1-TENTATIVA-1",
            "PL-101/2026-CAMARA-T1-TENTATIVA-2",
            "PL-101/2026-CAMARA-T1-TENTATIVA-3",
        ]
        motivos = [app.serializar_sessao(t)["motivo_anulacao"] for t in tentativas]
        assert motivos == anuladas
        assert all(t in app.metadados_sessoes for t in tentativas)

    def test_anulacao_recusada_depois_do_registro_na_tramitacao(self) -> None:
        app = EstadoAplicacaoUI()
        id_sessao = app.convocar_sessao_tramitacao("PL-101/2026", liberar_imediatamente=False)[
            "sessao"
        ]["id_sessao"]
        app.registrar_presenca_sessao(id_sessao, {"bancada": 300})
        app.liberar_votacao_sessao(id_sessao)
        app.simular_votacao_plenario(id_sessao, {"votos_sim": 280})
        app.apurar_sessao(id_sessao)

        with pytest.raises(ValueError, match="já foi registrado na tramitação"):
            app.anular_sessao(id_sessao, "Vício")
        assert app.serializar_sessao(id_sessao)["estado"] == "ENCERRADA"

    @staticmethod
    def _turno_aprovado(app: EstadoAplicacaoUI, materia: str, com_emenda: bool = False) -> dict:
        sessao = app.convocar_sessao_tramitacao(materia, liberar_imediatamente=False)["sessao"]
        id_sessao = sessao["id_sessao"]
        app.registrar_presenca_sessao(id_sessao, {"bancada": sessao["quorum_instalacao"]})
        app.liberar_votacao_sessao(id_sessao)
        app.simular_votacao_plenario(id_sessao, {"votos_sim": sessao["quorum_instalacao"]})
        return app.apurar_sessao(id_sessao, com_emenda=com_emenda)

    def test_emenda_da_revisora_volta_a_iniciadora_pela_interface(self) -> None:
        # #33: a revisora aprova com emenda; a iniciadora aprecia as emendas.
        app = EstadoAplicacaoUI()
        self._turno_aprovado(app, "PL-101/2026")  # Câmara
        tram = app._serializar_tramitacao(app.tramitacoes["PL-101/2026"])
        assert tram["fase"] == "CASA_REVISORA"
        assert tram["aceita_emenda"] is True

        self._turno_aprovado(app, "PL-101/2026", com_emenda=True)  # Senado emenda
        tram = app._serializar_tramitacao(app.tramitacoes["PL-101/2026"])
        assert tram["fase"] == "APRECIACAO_EMENDAS"
        assert tram["casa_atual"] == "CAMARA"
        assert tram["id_proxima_sessao"] == "PL-101/2026-CAMARA-EMENDAS"
        assert tram["historico"][-1]["com_emenda"] is True

        conv = app.convocar_sessao_tramitacao("PL-101/2026", liberar_imediatamente=False)
        assert (
            "Apreciação das emendas" in app.metadados_sessoes[conv["sessao"]["id_sessao"]]["titulo"]
        )

        # A iniciadora rejeita as emendas: prevalece o seu texto, e a matéria é aprovada
        id_emendas = conv["sessao"]["id_sessao"]
        app.registrar_presenca_sessao(id_emendas, {"bancada": 300})
        app.liberar_votacao_sessao(id_emendas)
        app.simular_votacao_plenario(id_emendas, {"votos_sim": 20, "votos_nao": 270})
        app.apurar_sessao(id_emendas)

        tram = app._serializar_tramitacao(app.tramitacoes["PL-101/2026"])
        assert tram["status"] == "ENVIADA_A_SANCAO"  # #34: a lei segue para a sanção
        assert tram["texto_prevalecente"] == "INICIADORA"
        assert [e["evento"] for e in tram["log_rito"]] == [
            "TRAMITACAO_CASA_ALTERADA",
            "TRAMITACAO_CASA_ALTERADA",
            "TRAMITACAO_ENVIADA_A_SANCAO",
        ]

    def test_sancao_e_veto_pela_interface(self) -> None:
        # #34: a lei aprovada vai à sanção; o veto é apreciado em cada Casa.
        app = EstadoAplicacaoUI()
        self._turno_aprovado(app, "PL-101/2026")
        self._turno_aprovado(app, "PL-101/2026")
        tram = app._serializar_tramitacao(app.tramitacoes["PL-101/2026"])
        assert tram["status"] == "ENVIADA_A_SANCAO"
        assert tram["concluida"] is False
        assert tram["em_deliberacao"] is False

        with pytest.raises(ValueError, match="razões do veto"):
            app.vetar_tramitacao("PL-101/2026", "")
        tram = app.vetar_tramitacao("PL-101/2026", "Vício de iniciativa")
        assert tram["status"] == "VETO_EM_APRECIACAO"
        assert tram["id_proxima_sessao"] == "PL-101/2026-VETO-CAMARA"
        assert tram["em_deliberacao"] is True

        conv = app.convocar_sessao_tramitacao("PL-101/2026", liberar_imediatamente=False)
        assert "Apreciação do veto" in app.metadados_sessoes[conv["sessao"]["id_sessao"]]["titulo"]
        # Derrubada exige maioria absoluta: 257 na Câmara e 41 no Senado
        for _casa in ("CAMARA", "SENADO"):
            sessao = app.convocar_sessao_tramitacao("PL-101/2026", liberar_imediatamente=False)[
                "sessao"
            ]
            id_sessao = sessao["id_sessao"]
            app.registrar_presenca_sessao(id_sessao, {"bancada": sessao["quorum_instalacao"]})
            app.liberar_votacao_sessao(id_sessao)
            app.simular_votacao_plenario(id_sessao, {"votos_sim": sessao["quorum_instalacao"]})
            app.apurar_sessao(id_sessao)

        tram = app._serializar_tramitacao(app.tramitacoes["PL-101/2026"])
        assert tram["status"] == "APROVADA"
        assert tram["concluida"] is True
        assert tram["log_rito"][-1]["dados"]["decisao"] == "VETO_DERRUBADO"

    def test_sancao_de_materia_em_tramitacao_e_recusada(self) -> None:
        app = EstadoAplicacaoUI()
        with pytest.raises(TramitacaoInvalidaError, match="aprovada nas duas Casas"):
            app.sancionar_tramitacao("PL-101/2026")
        with pytest.raises(KeyError, match="não encontrada"):
            app.sancionar_tramitacao("PL-999/2026")

    def test_emenda_fora_da_revisora_e_recusada_antes_da_apuracao(self) -> None:
        app = EstadoAplicacaoUI()
        sessao = app.convocar_sessao_tramitacao("PL-101/2026", liberar_imediatamente=False)[
            "sessao"
        ]
        app.registrar_presenca_sessao(sessao["id_sessao"], {"bancada": 300})
        app.liberar_votacao_sessao(sessao["id_sessao"])

        with pytest.raises(ValueError, match="apenas a Casa revisora emenda"):
            app.apurar_sessao(sessao["id_sessao"], com_emenda=True)
        # A recusa veio antes da apuração: a sessão segue em votação
        assert app.serializar_sessao(sessao["id_sessao"])["estado"] == "EM_VOTACAO"

        with pytest.raises(ValueError, match="só se aplica a sessões de tramitação"):
            app.apurar_sessao("ELEICAO-CA-2026", com_emenda=True)

    def test_registro_de_presenca_valida_parlamentar_e_casa(self) -> None:
        # #37: só compõem o quórum parlamentares da Casa da sessão e em exercício.
        app = EstadoAplicacaoUI()
        id_sessao = app.convocar_sessao_tramitacao("PL-101/2026", liberar_imediatamente=False)[
            "sessao"
        ]["id_sessao"]

        with pytest.raises(ValueError, match="SENADO"):
            app.registrar_presenca_sessao(id_sessao, {"parlamentares": ["SEN-001"]})
        with pytest.raises(ValueError, match="exercício"):
            app.registrar_presenca_sessao(id_sessao, {"parlamentares": ["DEP-003"]})
        with pytest.raises(KeyError, match="não encontrado"):
            app.registrar_presenca_sessao(id_sessao, {"parlamentares": ["DEP-999"]})
        with pytest.raises(ValueError, match="ultrapassaria os 513"):
            app.registrar_presenca_sessao(id_sessao, {"bancada": 514})
        with pytest.raises(ValueError, match="Informe ao menos"):
            app.registrar_presenca_sessao(id_sessao, {})
        with pytest.raises(ValueError, match="só se aplica a sessões do Congresso"):
            app.registrar_presenca_sessao("ELEICAO-CA-2026", {"bancada": 10})

        # Nenhuma tentativa inválida deixou presença registrada
        assert app.serializar_sessao(id_sessao)["total_presentes"] == 0

        sessao = app.registrar_presenca_sessao(
            id_sessao, {"parlamentares": ["DEP-001", "DEP-002"], "bancada": 255}
        )
        assert sessao["total_presentes"] == 257
        assert app.liberar_votacao_sessao(id_sessao)["estado"] == "EM_VOTACAO"

    def test_fluxo_tramitacao_e_sessao_congresso(self) -> None:
        app = EstadoAplicacaoUI()
        res_conv = app.convocar_sessao_tramitacao("PL-101/2026", liberar_imediatamente=True)
        id_sessao = res_conv["sessao"]["id_sessao"]
        assert "PL-101/2026" in id_sessao

        # #37: sem presença, a votação não é liberada; a sessão fica ABERTA com aviso.
        assert res_conv["sessao"]["estado"] == "ABERTA"
        assert res_conv["sessao"]["quorum_instalacao"] == 257
        assert "há 0 presentes e são exigidos 257" in res_conv["aviso"]

        presenca = app.registrar_presenca_sessao(id_sessao, {"bancada": 320})
        assert presenca["total_presentes"] == 320
        assert app.liberar_votacao_sessao(id_sessao)["estado"] == "EM_VOTACAO"

        # Simulação de bancada no plenário
        sim = app.simular_votacao_plenario(
            id_sessao,
            {"votos_sim": 260, "votos_nao": 50, "votos_abstencao": 5, "votos_branco": 0},
        )
        assert sim["votos_adicionados"] == 315
        # Os votantes da bancada já estavam presentes: não são contados de novo.
        assert sim["sessao"]["total_presentes"] == 320

        # Apuração avança a matéria na tramitação bicameral
        apur = app.apurar_sessao(id_sessao)
        assert apur["resultado"]["status"] == "APROVADO"

        tram = app.tramitacoes["PL-101/2026"]
        assert tram.casa_atual.value == "SENADO"

    def test_erros_e_validacoes(self) -> None:
        app = EstadoAplicacaoUI()

        with pytest.raises(ValueError, match="Contexto inválido"):
            app.criar_sessao("X", "INVALIDO", "Titulo")

        with pytest.raises(KeyError, match="não encontrada"):
            app.serializar_sessao("INEXISTENTE")

        with pytest.raises(ValueError, match="Informe um hash"):
            app.verificar_protocolo_auditoria("ELEICAO-CA-2026", "   ")

        with pytest.raises(ValueError, match="não encontrada no cadastro"):
            app.iniciar_tramitacao("MATERIA-NAO-EXISTE")

        with pytest.raises(ValueError, match="só se aplica a sessões do Congresso"):
            app.simular_votacao_plenario("ELEICAO-CA-2026", {"votos_sim": 10})

    def test_cenarios_completos_assembleia_deliberacoes_e_conselho(self) -> None:
        app = EstadoAplicacaoUI()

        # 1. Assembleia com Quórum Qualificado sobre total do capital
        sessao_qualif = app.criar_sessao(
            id_sessao="AGE-QUALIFICADA-2026",
            contexto="ASSEMBLEIA",
            titulo="Reforma do Estatuto com Quórum Qualificado",
            tipo_decisao="QUORUM_QUALIFICADO",
            percentual_quorum_instalacao=0.25,
            base_calculo_sobre_total_capital=True,
            abrir_imediatamente=True,
            liberar_imediatamente=True,
        )
        assert sessao_qualif["meta"]["tipo_decisao"] == "QUALIFICADA_DOIS_TERCOS"

        # Voto de acionista não impedido
        res_voto = app.registrar_voto_na_sessao(
            "AGE-QUALIFICADA-2026",
            {"eleitor_id": "AC-002", "opcao": "SIM", "modo": "DIRETO"},
        )
        assert res_voto["protocolo"] is not None

        # 2. Voto em Eleição de Conselho de Administração com candidato cadastrado
        app.cadastrar_candidato_conselho(
            {"id": "CONS-ELEITO", "nome": "Dr. Fernando", "conflito_interesse": False}
        )
        res_cand = app.registrar_voto_na_sessao(
            "AGE-QUALIFICADA-2026",
            {"eleitor_id": "AC-003", "opcao": "CONS-ELEITO", "modo": "DIRETO"},
        )
        assert res_cand["voto"]["opcao"] == "CONS-ELEITO"

        # Candidato com conflito de interesse é bloqueado pelo serviço de elegibilidade
        app.cadastrar_candidato_conselho(
            {"id": "CONS-IMPEDIDO", "nome": "Dr. Conflitante", "conflito_interesse": True}
        )
        with pytest.raises(ValueError, match="inelegível"):
            app.registrar_voto_na_sessao(
                "AGE-QUALIFICADA-2026",
                {"eleitor_id": "AC-003", "opcao": "CONS-IMPEDIDO", "modo": "DIRETO"},
            )

    def test_tramitacao_completa_pec_quatro_turnos_e_promulgacao(self) -> None:
        """Verifica o ciclo completo da PEC (2 turnos na Câmara e 2 turnos no Senado).

        Aprovada nas duas Casas, a PEC é promulgada pelas Mesas, sem sanção
        (CF, art. 60, § 3º; #34).
        """
        app = EstadoAplicacaoUI()

        # Protocolar nova PEC
        app.cadastrar_materia(
            {
                "id": "PEC-77/2026",
                "tipo": "PEC",
                "titulo": "Reforma Tributária e Digital",
                "ementa": "Altera regras de tributação de software",
                "casa_atual": "CAMARA",
            }
        )
        tram = app.tramitacoes["PEC-77/2026"]
        assert tram.turnos_por_casa == 2

        # Turno 1 na Câmara (exige 3/5 = 308 votos SIM)
        res1 = app.convocar_sessao_tramitacao("PEC-77/2026", liberar_imediatamente=True)
        s1 = res1["sessao"]["id_sessao"]
        app.registrar_presenca_sessao(s1, {"bancada": 350})
        app.liberar_votacao_sessao(s1)
        app.simular_votacao_plenario(s1, {"votos_sim": 310, "votos_nao": 40})
        app.apurar_sessao(s1)
        assert tram.turno_atual == 2
        assert tram.casa_atual.value == "CAMARA"

        # Turno 2 na Câmara
        res2 = app.convocar_sessao_tramitacao("PEC-77/2026", liberar_imediatamente=True)
        s2 = res2["sessao"]["id_sessao"]
        app.registrar_presenca_sessao(s2, {"bancada": 345})
        app.liberar_votacao_sessao(s2)
        app.simular_votacao_plenario(s2, {"votos_sim": 315, "votos_nao": 30})
        app.apurar_sessao(s2)
        assert tram.casa_atual.value == "SENADO"
        assert tram.turno_atual == 1

        # Turno 1 no Senado (exige 3/5 = 49 votos SIM)
        res3 = app.convocar_sessao_tramitacao("PEC-77/2026", liberar_imediatamente=True)
        s3 = res3["sessao"]["id_sessao"]
        app.registrar_presenca_sessao(s3, {"bancada": 65})
        app.liberar_votacao_sessao(s3)
        app.simular_votacao_plenario(s3, {"votos_sim": 55, "votos_nao": 10})
        app.apurar_sessao(s3)
        assert tram.casa_atual.value == "SENADO"
        assert tram.turno_atual == 2

        # Turno 2 no Senado -> aprovação final e promulgação da PEC
        res4 = app.convocar_sessao_tramitacao("PEC-77/2026", liberar_imediatamente=True)
        s4 = res4["sessao"]["id_sessao"]
        app.registrar_presenca_sessao(s4, {"bancada": 64})
        app.liberar_votacao_sessao(s4)
        app.simular_votacao_plenario(s4, {"votos_sim": 52, "votos_nao": 12})
        app.apurar_sessao(s4)
        assert tram.status.value == "PROMULGADA"

    def test_auditoria_completa_e_ancora_encerramento(self) -> None:
        """Verifica a integridade da cadeia de blocos SHA-256 e a âncora de fechamento."""
        app = EstadoAplicacaoUI()
        app.criar_sessao(
            id_sessao="SESSAO-AUDIT-TESTE",
            contexto="CA",
            titulo="Sessão Auditável",
            abrir_imediatamente=True,
            liberar_imediatamente=True,
        )

        # Lança voto e confere protocolo
        voto = app.registrar_voto_na_sessao(
            "SESSAO-AUDIT-TESTE",
            {"eleitor_id": "247314", "opcao": "Chapa Renova"},
        )
        protocolo = voto["protocolo"]
        assert len(protocolo) == 64  # Hash SHA-256

        # Encerramento emite a âncora
        app.encerrar_votacao_sessao("SESSAO-AUDIT-TESTE")
        assert "SESSAO-AUDIT-TESTE" in app.ancoras_emitidas
        ancora = app.ancoras_emitidas["SESSAO-AUDIT-TESTE"]
        assert ancora.total_votos == 1
        assert len(ancora.hash_encerramento) == 64

        # Serialização da auditoria reflete integridade validada
        detalhes = app.serializar_sessao("SESSAO-AUDIT-TESTE")
        assert detalhes["auditoria"]["integro"] is True
        assert detalhes["auditoria"]["cadeia_integra"] is True
        assert detalhes["auditoria"]["ancora"] is not None


class TestServidorHTTP:
    """Valida as rotas REST e o fornecimento de arquivos estáticos pelo servidor HTTP."""

    # A ordem importa: @pytest.fixture precisa envolver o classmethod. Com
    # @classmethod por fora, o pytest não reconhece a fixture.
    @pytest.fixture(scope="class")
    @classmethod
    def servidor_teste(cls) -> Iterator[tuple[str, EstadoAplicacaoUI]]:
        app = EstadoAplicacaoUI()
        servidor = criar_servidor(host="127.0.0.1", porta=0, estado_app=app, silencioso=True)
        porta = servidor.server_address[1]
        base_url = f"http://127.0.0.1:{porta}"

        thread = threading.Thread(target=servidor.serve_forever, daemon=True)
        thread.start()

        yield base_url, app

        servidor.shutdown()
        servidor.server_close()

    def _get(self, base_url: str, path: str) -> tuple[int, Any, dict[str, str]]:
        req = Request(f"{base_url}{path}")
        try:
            with urlopen(req) as resp:
                status = resp.status
                headers = dict(resp.headers)
                corpo = resp.read()
                try:
                    payload = json.loads(corpo.decode("utf-8"))
                except Exception:
                    payload = corpo
                return status, payload, headers
        except HTTPError as exc:
            corpo = exc.read()
            try:
                payload = json.loads(corpo.decode("utf-8"))
            except Exception:
                payload = corpo
            return exc.code, payload, dict(exc.headers)

    def _post(self, base_url: str, path: str, dados: dict[str, Any]) -> tuple[int, Any]:
        corpo = json.dumps(dados).encode("utf-8")
        req = Request(f"{base_url}{path}", data=corpo, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req) as resp:
                status = resp.status
                resposta = json.loads(resp.read().decode("utf-8"))
                return status, resposta
        except HTTPError as exc:
            resposta = json.loads(exc.read().decode("utf-8"))
            return exc.code, resposta

    def test_arquivos_estaticos_e_saude(
        self, servidor_teste: tuple[str, EstadoAplicacaoUI]
    ) -> None:
        base_url, _ = servidor_teste

        status, payload, headers = self._get(base_url, "/api/saude")
        assert status == 200
        assert payload == {"status": "ok"}
        assert headers.get("Access-Control-Allow-Origin") == "*"

        status_html, corpo_html, _ = self._get(base_url, "/")
        assert status_html == 200
        assert b"<!DOCTYPE html>" in corpo_html

        status_css, corpo_css, _ = self._get(base_url, "/styles.css")
        assert status_css == 200
        assert b"--primary" in corpo_css

        status_js, corpo_js, _ = self._get(base_url, "/app.js")
        assert status_js == 200
        assert b"carregarEstadoCompleto" in corpo_js

    def test_endpoints_api_rest(self, servidor_teste: tuple[str, EstadoAplicacaoUI]) -> None:
        base_url, _ = servidor_teste

        status, estado, _ = self._get(base_url, "/api/estado")
        assert status == 200
        assert "sessoes" in estado

        # Consultar sessão existente
        status, sessao, _ = self._get(base_url, "/api/sessoes/ELEICAO-CA-2026")
        assert status == 200
        assert sessao["id_sessao"] == "ELEICAO-CA-2026"

        # Consultar sessão inexistente
        status_404, err_404, _ = self._get(base_url, "/api/sessoes/NAO-EXISTE")
        assert status_404 == 404
        assert "erro" in err_404

        # Criar sessão via POST
        status_post, nova_sessao = self._post(
            base_url,
            "/api/sessoes",
            {
                "id_sessao": "SESSAO-API-TESTE",
                "contexto": "CA",
                "titulo": "Sessão API",
                "abrir_imediatamente": True,
                "liberar_imediatamente": True,
            },
        )
        assert status_post == 201
        assert nova_sessao["id_sessao"] == "SESSAO-API-TESTE"

        # Votar via POST com discente cadastrado no mock (247314)
        status_voto, res_voto = self._post(
            base_url,
            "/api/sessoes/SESSAO-API-TESTE/votar",
            {"eleitor_id": "247314", "opcao": "Chapa Renova"},
        )
        assert status_voto == 200
        assert "protocolo" in res_voto

        # Apurar via POST
        status_apurar, res_apurar = self._post(
            base_url,
            "/api/sessoes/SESSAO-API-TESTE/apurar",
            {},
        )
        assert status_apurar == 200
        assert res_apurar["resultado"] is not None

        # Verificar protocolo via POST
        prot = res_voto["protocolo"]
        status_verif, res_verif = self._post(
            base_url,
            "/api/sessoes/SESSAO-API-TESTE/verificar-protocolo",
            {"protocolo": prot},
        )
        assert status_verif == 200
        assert res_verif["encontrado"] is True

        # Outorgar e revogar procuração via POST
        st_proc, _ = self._post(
            base_url,
            "/api/assembleia/procuracoes",
            {"outorgante_id": "AC-002", "procurador_id": "PROC-102", "validade_dias": 15},
        )
        assert st_proc == 201

        st_rev, res_rev = self._post(
            base_url,
            "/api/assembleia/procuracoes/revogar",
            {"outorgante_id": "AC-002", "procurador_id": "PROC-102"},
        )
        assert st_rev == 200
        assert res_rev["ativa"] is False

        # Protocolar matéria e convocar tramitação via POST
        st_mat, _ = self._post(
            base_url,
            "/api/congresso/materias",
            {
                "id": "PL-888/2026",
                "tipo": "PL",
                "titulo": "Dados Abertos",
                "ementa": "Ementa",
                "casa_atual": "CAMARA",
            },
        )
        assert st_mat == 201

        st_conv, res_conv = self._post(
            base_url,
            "/api/tramitacoes/PL-888%2F2026/convocar-sessao",
            {"liberar_imediatamente": True},
        )
        assert st_conv == 201
        id_sessao_tram = res_conv["sessao"]["id_sessao"]

        # Sem quórum de presença a votação não abre (#37): 409 ao tentar liberar
        st_lib, _ = self._post(base_url, f"/api/sessoes/{id_sessao_tram}/liberar", {})
        assert st_lib == 409

        # Registrar presença via POST: parlamentar cadastrado da Casa + bancada
        st_pres, res_pres = self._post(
            base_url,
            f"/api/sessoes/{id_sessao_tram}/presenca",
            {"parlamentares": ["DEP-001"], "bancada": 300},
        )
        assert st_pres == 200
        assert res_pres["total_presentes"] == 301
        st_lib, res_lib = self._post(base_url, f"/api/sessoes/{id_sessao_tram}/liberar", {})
        assert st_lib == 200
        assert res_lib["estado"] == "EM_VOTACAO"

        # Simular bancada via POST
        st_sim, res_sim = self._post(
            base_url,
            f"/api/sessoes/{id_sessao_tram}/simular-plenario",
            {"votos_sim": 270, "votos_nao": 20},
        )
        assert st_sim == 200
        assert res_sim["votos_adicionados"] == 290

        # #34 pela API: sancionar matéria ainda em tramitação é 409; inexistente é 404
        st_sanc, _ = self._post(base_url, "/api/tramitacoes/PL-888%2F2026/sancionar", {})
        assert st_sanc == 409
        st_inex, _ = self._post(base_url, "/api/tramitacoes/PL-000%2F2026/vetar", {"razoes": "x"})
        assert st_inex == 404

        # Endpoint POST inexistente -> 404
        st_404, res_404 = self._post(base_url, "/api/nao-existe", {})
        assert st_404 == 404
        assert "erro" in res_404

        # Resetar via POST
        status_reset, _ = self._post(base_url, "/api/resetar", {"usar_sql": False})
        assert status_reset == 200

    def test_resetar_com_sql_em_thread_do_servidor(
        self, servidor_teste: tuple[str, EstadoAplicacaoUI]
    ) -> None:
        # O estado (e a conexão SQLite) é criado na thread do teste, mas a
        # requisição é atendida em outra thread do servidor: antes da correção,
        # isso levantava sqlite3.ProgrammingError e esvaziava os cadastros.
        base_url, _ = servidor_teste
        status, estado = self._post(base_url, "/api/resetar", {"usar_sql": True})
        assert status == 200
        assert len(estado["ca"]["discentes"]) > 0
        assert "ELEICAO-CA-2026" in estado["sessoes"]

    def test_conflitos_de_estado_retornam_409(
        self, servidor_teste: tuple[str, EstadoAplicacaoUI]
    ) -> None:
        base_url, _ = servidor_teste
        self._post(
            base_url,
            "/api/sessoes",
            {
                "id_sessao": "SESSAO-CONFLITO",
                "contexto": "CA",
                "abrir_imediatamente": True,
                "liberar_imediatamente": True,
            },
        )
        voto = {"eleitor_id": "247314", "opcao": "Chapa Renova"}
        assert self._post(base_url, "/api/sessoes/SESSAO-CONFLITO/votar", voto)[0] == 200

        # Voto duplicado é recusado pela sessão: conflito, não erro interno
        st_dup, res_dup = self._post(base_url, "/api/sessoes/SESSAO-CONFLITO/votar", voto)
        assert st_dup == 409
        assert "já votou" in res_dup["erro"]

        # Encerrar e depois apurar (EM_APURACAO -> ENCERRADA) é o fluxo válido
        assert self._post(base_url, "/api/sessoes/SESSAO-CONFLITO/encerrar", {})[0] == 200
        assert self._post(base_url, "/api/sessoes/SESSAO-CONFLITO/apurar", {})[0] == 200

        # #38 pela API: suspender sem motivo é 400; votar com a sessão suspensa é 409
        self._post(
            base_url,
            "/api/sessoes",
            {
                "id_sessao": "SESSAO-SUSP",
                "contexto": "CA",
                "abrir_imediatamente": True,
                "liberar_imediatamente": True,
            },
        )
        assert self._post(base_url, "/api/sessoes/SESSAO-SUSP/suspender", {})[0] == 400
        st_susp, res_susp = self._post(
            base_url, "/api/sessoes/SESSAO-SUSP/suspender", {"motivo": "Questão de ordem"}
        )
        assert st_susp == 200
        assert res_susp["estado"] == "SUSPENSA"
        assert self._post(base_url, "/api/sessoes/SESSAO-SUSP/votar", voto)[0] == 409
        assert self._post(base_url, "/api/sessoes/SESSAO-SUSP/encerrar", {})[0] == 409
        st_ret, res_ret = self._post(base_url, "/api/sessoes/SESSAO-SUSP/retomar", {})
        assert st_ret == 200
        assert res_ret["estado"] == "EM_VOTACAO"

        # #39 pela API: anular sem motivo é 400; votar em sessão anulada é 409
        assert self._post(base_url, "/api/sessoes/SESSAO-SUSP/anular", {})[0] == 400
        st_anul, res_anul = self._post(
            base_url, "/api/sessoes/SESSAO-SUSP/anular", {"motivo": "Credenciamento falho"}
        )
        assert st_anul == 200
        assert res_anul["estado"] == "ANULADA"
        assert self._post(base_url, "/api/sessoes/SESSAO-SUSP/votar", voto)[0] == 409
        assert self._post(base_url, "/api/sessoes/SESSAO-SUSP/anular", {"motivo": "x"})[0] == 409

        # Apurar de novo uma sessão já encerrada é transição inválida
        st_rep, _ = self._post(base_url, "/api/sessoes/SESSAO-CONFLITO/apurar", {})
        assert st_rep == 409

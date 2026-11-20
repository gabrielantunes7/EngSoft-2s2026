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
from votacao.sessao import EstadoSessao


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

    def test_fluxo_tramitacao_e_sessao_congresso(self) -> None:
        app = EstadoAplicacaoUI()
        res_conv = app.convocar_sessao_tramitacao("PL-101/2026", liberar_imediatamente=True)
        id_sessao = res_conv["sessao"]["id_sessao"]
        assert "PL-101/2026" in id_sessao

        # Simulação de bancada no plenário
        sim = app.simular_votacao_plenario(
            id_sessao,
            {"votos_sim": 260, "votos_nao": 50, "votos_abstencao": 5, "votos_branco": 0},
        )
        assert sim["votos_adicionados"] == 315

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
        """Verifica o ciclo completo da PEC (2 turnos na Câmara e 2 turnos no Senado)."""
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
        app.simular_votacao_plenario(s1, {"votos_sim": 310, "votos_nao": 40})
        app.apurar_sessao(s1)
        assert tram.turno_atual == 2
        assert tram.casa_atual.value == "CAMARA"

        # Turno 2 na Câmara
        res2 = app.convocar_sessao_tramitacao("PEC-77/2026", liberar_imediatamente=True)
        s2 = res2["sessao"]["id_sessao"]
        app.simular_votacao_plenario(s2, {"votos_sim": 315, "votos_nao": 30})
        app.apurar_sessao(s2)
        assert tram.casa_atual.value == "SENADO"
        assert tram.turno_atual == 1

        # Turno 1 no Senado (exige 3/5 = 49 votos SIM)
        res3 = app.convocar_sessao_tramitacao("PEC-77/2026", liberar_imediatamente=True)
        s3 = res3["sessao"]["id_sessao"]
        app.simular_votacao_plenario(s3, {"votos_sim": 55, "votos_nao": 10})
        app.apurar_sessao(s3)
        assert tram.casa_atual.value == "SENADO"
        assert tram.turno_atual == 2

        # Turno 2 no Senado -> Aprovação final e promulgação da PEC!
        res4 = app.convocar_sessao_tramitacao("PEC-77/2026", liberar_imediatamente=True)
        s4 = res4["sessao"]["id_sessao"]
        app.simular_votacao_plenario(s4, {"votos_sim": 52, "votos_nao": 12})
        app.apurar_sessao(s4)
        assert tram.status.value == "APROVADA"

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

        # Simular bancada via POST
        st_sim, res_sim = self._post(
            base_url,
            f"/api/sessoes/{id_sessao_tram}/simular-plenario",
            {"votos_sim": 270, "votos_nao": 20},
        )
        assert st_sim == 200
        assert res_sim["votos_adicionados"] == 290

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

        # Apurar de novo uma sessão já encerrada é transição inválida
        st_rep, _ = self._post(base_url, "/api/sessoes/SESSAO-CONFLITO/apurar", {})
        assert st_rep == 409

"""Servidor HTTP e API REST JSON para a interface gráfica (UI) do sistema de votação."""

from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from UI.app import EstadoAplicacaoUI
from votacao.sessao import TransicaoInvalidaError, VotoRecusadoError
from votacao.tramitacao import TramitacaoInvalidaError

DIRETORIO_STATIC = Path(__file__).resolve().parent / "static"

TIPOS_MIME: dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class ServidorVotacaoHTTP(ThreadingHTTPServer):
    """Servidor HTTP multi-thread que mantém a instância de EstadoAplicacaoUI."""

    allow_reuse_address = True

    def __init__(
        self,
        endereco: tuple[str, int],
        manipulador: type[BaseHTTPRequestHandler],
        estado_app: EstadoAplicacaoUI | None = None,
        silencioso: bool = False,
    ) -> None:
        self.estado_app = estado_app or EstadoAplicacaoUI()
        self.silencioso = silencioso
        # Cada requisição roda em uma thread, mas o estado (sessões em memória e a
        # conexão SQLite) não é thread-safe: todo acesso a ele passa por esta trava.
        self.trava_estado = threading.Lock()
        super().__init__(endereco, manipulador)


class ManipuladorRequisicoesUI(BaseHTTPRequestHandler):
    """Manipulador HTTP responsável por servir arquivos estáticos e endpoints `/api/*`."""

    server: ServidorVotacaoHTTP

    def log_message(self, format: str, *args: Any) -> None:
        if getattr(self.server, "silencioso", False):
            return
        super().log_message(format, *args)

    @property
    def app(self) -> EstadoAplicacaoUI:
        return self.server.estado_app

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._adicionar_cabecalhos_cors()
        self.end_headers()

    def do_GET(self) -> None:
        caminho = urlparse(self.path).path

        if caminho == "/api/saude":
            self._enviar_json(HTTPStatus.OK, {"status": "ok"})
            return

        if caminho == "/api/estado":
            with self.server.trava_estado:
                estado = self.app.obter_estado_completo()
            self._enviar_json(HTTPStatus.OK, estado)
            return

        if caminho.startswith("/api/sessoes/"):
            id_sessao = unquote(caminho.removeprefix("/api/sessoes/")).strip("/")
            try:
                with self.server.trava_estado:
                    sessao = self.app.serializar_sessao(id_sessao)
                self._enviar_json(HTTPStatus.OK, sessao)
            except KeyError as exc:
                self._enviar_json(HTTPStatus.NOT_FOUND, {"erro": str(exc.args[0])})
            return

        if caminho.startswith("/api/"):
            self._enviar_json(
                HTTPStatus.NOT_FOUND,
                {"erro": f"Endpoint GET não encontrado: {caminho}"},
            )
            return

        self._servir_arquivo_estatico(caminho)

    def do_POST(self) -> None:
        caminho = urlparse(self.path).path
        try:
            corpo = self._ler_corpo_json()
            with self.server.trava_estado:
                status, resposta = self._rotear_post(caminho, corpo)
            self._enviar_json(status, resposta)
        except KeyError as exc:
            msg = exc.args[0] if exc.args else str(exc)
            self._enviar_json(HTTPStatus.NOT_FOUND, {"erro": str(msg)})
        except PermissionError as exc:
            self._enviar_json(HTTPStatus.FORBIDDEN, {"erro": str(exc)})
        except (VotoRecusadoError, TransicaoInvalidaError, TramitacaoInvalidaError) as exc:
            # Recusas do domínio (voto duplicado, fora da janela, transição de estado
            # inválida) dependem do estado atual da sessão: conflito, não erro interno.
            self._enviar_json(HTTPStatus.CONFLICT, {"erro": str(exc)})
        except ValueError as exc:
            self._enviar_json(HTTPStatus.BAD_REQUEST, {"erro": str(exc)})
        except Exception as exc:  # pragma: no cover - salvaguarda para erros inesperados
            self._enviar_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"erro": f"Erro interno ao processar requisição: {exc}"},
            )

    def _rotear_post(self, caminho: str, corpo: dict[str, Any]) -> tuple[HTTPStatus, Any]:
        if caminho == "/api/resetar":
            usar_sql = bool(corpo.get("usar_sql", False))
            return HTTPStatus.OK, self.app.resetar_sistema(usar_sql=usar_sql)

        if caminho == "/api/ca/discentes":
            return HTTPStatus.CREATED, self.app.cadastrar_discente(corpo)

        if caminho == "/api/ca/chapas":
            return HTTPStatus.CREATED, self.app.cadastrar_chapa(corpo)

        if caminho == "/api/assembleia/acionistas":
            return HTTPStatus.CREATED, self.app.cadastrar_acionista(corpo)

        if caminho == "/api/assembleia/procuradores":
            return HTTPStatus.CREATED, self.app.cadastrar_procurador(corpo)

        if caminho == "/api/assembleia/procuracoes":
            return HTTPStatus.CREATED, self.app.cadastrar_procuracao(corpo)

        if caminho == "/api/assembleia/procuracoes/revogar":
            return HTTPStatus.OK, self.app.revogar_procuracao(corpo)

        if caminho == "/api/assembleia/candidatos":
            return HTTPStatus.CREATED, self.app.cadastrar_candidato_conselho(corpo)

        if caminho == "/api/congresso/parlamentares":
            return HTTPStatus.CREATED, self.app.cadastrar_parlamentar(corpo)

        if caminho == "/api/congresso/materias":
            return HTTPStatus.CREATED, self.app.cadastrar_materia(corpo)

        if caminho == "/api/aptidao":
            return HTTPStatus.OK, self.app.consultar_aptidao_ui(corpo)

        if caminho == "/api/tramitacoes":
            materia_id = str(corpo.get("materia_id", ""))
            return HTTPStatus.CREATED, self.app.iniciar_tramitacao(materia_id)

        if caminho == "/api/tramitacoes/convocar-sessao":
            materia_id = str(corpo.get("materia_id", ""))
            liberar = bool(corpo.get("liberar_imediatamente", True))
            return HTTPStatus.CREATED, self.app.convocar_sessao_tramitacao(
                materia_id=materia_id,
                liberar_imediatamente=liberar,
            )

        if caminho.startswith("/api/tramitacoes/") and caminho.endswith("/sancionar"):
            meio = caminho.removeprefix("/api/tramitacoes/").removesuffix("/sancionar")
            return HTTPStatus.OK, self.app.sancionar_tramitacao(unquote(meio).strip("/"))

        if caminho.startswith("/api/tramitacoes/") and caminho.endswith("/vetar"):
            meio = caminho.removeprefix("/api/tramitacoes/").removesuffix("/vetar")
            razoes = str(corpo.get("razoes", ""))
            return HTTPStatus.OK, self.app.vetar_tramitacao(unquote(meio).strip("/"), razoes)

        if caminho.startswith("/api/tramitacoes/") and caminho.endswith("/convocar-sessao"):
            meio = caminho.removeprefix("/api/tramitacoes/").removesuffix("/convocar-sessao")
            materia_id = unquote(meio).strip("/")
            liberar = bool(corpo.get("liberar_imediatamente", True))
            return HTTPStatus.CREATED, self.app.convocar_sessao_tramitacao(
                materia_id=materia_id,
                liberar_imediatamente=liberar,
            )

        if caminho == "/api/sessoes":
            sessao_criada = self.app.criar_sessao(
                id_sessao=str(corpo.get("id_sessao", "")),
                contexto=str(corpo.get("contexto", "CA")),
                titulo=str(corpo.get("titulo", "")),
                quorum_minimo_votantes=int(corpo.get("quorum_minimo_votantes", 1)),
                percentual_quorum_minimo=float(corpo.get("percentual_quorum_minimo", 0.0)),
                tipo_decisao=str(corpo.get("tipo_decisao", "MAIORIA_SIMPLES")),
                percentual_quorum_instalacao=float(corpo.get("percentual_quorum_instalacao", 0.25)),
                base_calculo_sobre_total_capital=bool(
                    corpo.get("base_calculo_sobre_total_capital", False)
                ),
                casa=str(corpo.get("casa", "CAMARA")),
                materia=str(corpo.get("materia", "PL")),
                materia_id=corpo.get("materia_id"),
                abrir_imediatamente=bool(corpo.get("abrir_imediatamente", False)),
                liberar_imediatamente=bool(corpo.get("liberar_imediatamente", False)),
            )
            return HTTPStatus.CREATED, sessao_criada

        if caminho.startswith("/api/sessoes/"):
            restante = caminho.removeprefix("/api/sessoes/")
            partes = restante.rsplit("/", 1)
            if len(partes) == 2:
                id_sessao = unquote(partes[0]).strip("/")
                acao = partes[1].strip("/")
                if acao == "abrir":
                    return HTTPStatus.OK, self.app.abrir_sessao(id_sessao)
                if acao == "liberar":
                    duracao = corpo.get("duracao_minutos")
                    duracao_int = int(duracao) if duracao not in (None, "") else None
                    return HTTPStatus.OK, self.app.liberar_votacao_sessao(
                        id_sessao,
                        duracao_minutos=duracao_int,
                    )
                if acao == "votar":
                    return HTTPStatus.OK, self.app.registrar_voto_na_sessao(id_sessao, corpo)
                if acao == "presenca":
                    return HTTPStatus.OK, self.app.registrar_presenca_sessao(id_sessao, corpo)
                if acao == "simular-plenario":
                    return HTTPStatus.OK, self.app.simular_votacao_plenario(id_sessao, corpo)
                if acao == "suspender":
                    motivo = str(corpo.get("motivo", ""))
                    return HTTPStatus.OK, self.app.suspender_sessao(id_sessao, motivo)
                if acao == "anular":
                    motivo = str(corpo.get("motivo", ""))
                    return HTTPStatus.OK, self.app.anular_sessao(id_sessao, motivo)
                if acao == "retomar":
                    return HTTPStatus.OK, self.app.retomar_sessao(id_sessao)
                if acao == "encerrar":
                    return HTTPStatus.OK, self.app.encerrar_votacao_sessao(id_sessao)
                if acao == "apurar":
                    com_emenda = bool(corpo.get("com_emenda", False))
                    return HTTPStatus.OK, self.app.apurar_sessao(id_sessao, com_emenda=com_emenda)
                if acao == "verificar-protocolo":
                    protocolo = str(corpo.get("protocolo", ""))
                    return HTTPStatus.OK, self.app.verificar_protocolo_auditoria(
                        id_sessao,
                        protocolo,
                    )

        return (
            HTTPStatus.NOT_FOUND,
            {"erro": f"Endpoint POST não encontrado: {caminho}"},
        )

    def _servir_arquivo_estatico(self, caminho: str) -> None:
        relativo = "index.html" if caminho in ("", "/") else caminho.lstrip("/")
        alvo = (DIRETORIO_STATIC / relativo).resolve()

        if not str(alvo).startswith(str(DIRETORIO_STATIC.resolve())) or not alvo.is_file():
            # Fallback SPA para index.html se não for rota de arquivo conhecida
            if "." not in Path(relativo).name and (DIRETORIO_STATIC / "index.html").is_file():
                alvo = (DIRETORIO_STATIC / "index.html").resolve()
            else:
                self._enviar_json(
                    HTTPStatus.NOT_FOUND,
                    {"erro": f"Recurso estático não encontrado: {caminho}"},
                )
                return

        conteudo = alvo.read_bytes()
        tipo_mime = TIPOS_MIME.get(alvo.suffix.lower(), "application/octet-stream")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", tipo_mime)
        self.send_header("Content-Length", str(len(conteudo)))
        self.send_header("Cache-Control", "no-store")
        self._adicionar_cabecalhos_cors()
        self.end_headers()
        self.wfile.write(conteudo)

    def _ler_corpo_json(self) -> dict[str, Any]:
        tamanho_str = self.headers.get("Content-Length", "0")
        tamanho = int(tamanho_str) if tamanho_str.isdigit() else 0
        if tamanho <= 0:
            return {}
        bruto = self.rfile.read(tamanho).decode("utf-8")
        if not bruto.strip():
            return {}
        try:
            dados = json.loads(bruto)
        except json.JSONDecodeError as exc:
            msg = f"JSON inválido no corpo da requisição: {exc}"
            raise ValueError(msg) from exc
        if not isinstance(dados, dict):
            msg = "O corpo JSON da requisição deve ser um objeto."
            raise ValueError(msg)
        return dados

    def _enviar_json(self, status: HTTPStatus, payload: Any) -> None:
        corpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self._adicionar_cabecalhos_cors()
        self.end_headers()
        self.wfile.write(corpo)

    def _adicionar_cabecalhos_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def criar_servidor(
    host: str = "127.0.0.1",
    porta: int = 8080,
    estado_app: EstadoAplicacaoUI | None = None,
    silencioso: bool = False,
) -> ServidorVotacaoHTTP:
    """Cria e retorna uma instância configurada do servidor HTTP da UI."""
    return ServidorVotacaoHTTP(
        (host, porta),
        ManipuladorRequisicoesUI,
        estado_app=estado_app,
        silencioso=silencioso,
    )


def iniciar_servidor(
    host: str = "127.0.0.1",
    porta: int = 8080,
    abrir_navegador: bool = False,
) -> None:  # pragma: no cover
    """Inicia o servidor web interativo e bloqueia até interrupção (Ctrl+C)."""
    servidor = criar_servidor(host=host, porta=porta)
    host_real, porta_real = servidor.server_address[:2]
    url = f"http://{host_real}:{porta_real}"
    print("=" * 72)
    print("  SISTEMA DE VOTAÇÃO — INTERFACE GRÁFICA WEB (RESPONSIVA DESKTOP/MOBILE)")
    print(f"  Acesse no navegador: {url}")
    print("  Pressione Ctrl+C para encerrar o servidor.")
    print("=" * 72)
    if abrir_navegador:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando servidor da interface gráfica...")
    finally:
        servidor.server_close()


def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    """Ponto de entrada de linha de comando (`python -m UI`)."""
    parser = argparse.ArgumentParser(
        description="Inicia a interface gráfica web do Sistema de Votação."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Endereço IP para bind do servidor (padrão: 127.0.0.1, use 0.0.0.0 para rede local).",
    )
    parser.add_argument(
        "--porta",
        "--port",
        type=int,
        default=8080,
        dest="porta",
        help="Porta TCP do servidor HTTP (padrão: 8080).",
    )
    parser.add_argument(
        "--abrir",
        action="store_true",
        help="Abre automaticamente a interface no navegador padrão.",
    )
    args = parser.parse_args(argv)
    iniciar_servidor(host=args.host, porta=args.porta, abrir_navegador=args.abrir)

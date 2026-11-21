"""Controlador de estado e fachada de domínio para a interface gráfica (UI)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

from votacao.auditoria import LogDeAuditoria, RegistroAuditoria, ResumoEncerramento, TipoEvento
from votacao.dados.assembleia import Acionista, CandidatoConselho, Procurador
from votacao.dados.ca import ChapaCA, Discente
from votacao.dados.congresso import MateriaLegislativa, Parlamentar
from votacao.dados.seeds import BancoDadosMock
from votacao.fabricas import FabricaAssembleia, FabricaCA, FabricaCongresso
from votacao.modelos import (
    CasaLegislativa,
    StatusResultado,
    TipoDecisaoAssembleia,
    TipoMateriaCongresso,
    Voto,
)
from votacao.regras.assembleia import RegraAssembleia
from votacao.regras.ca import RegraCA
from votacao.regras.congresso import RegraCongresso
from votacao.servicos import ServicoElegibilidade
from votacao.sessao import EstadoSessao, QuorumInstalacaoError, SessaoVotacao
from votacao.tramitacao import FaseTramitacao, TramitacaoLegislativa

# Política de sigilo por contexto (descoberta D-AUD-04 da Atividade 3): a eleição de
# CA é secreta; na assembleia o voto é aberto e nominal (Lei das S/A e CVM, história
# #44) e no Congresso a votação é nominal. A UI só expõe votos individuais, opções em
# registros de auditoria e parciais quando o contexto não exige sigilo.
CONTEXTOS_VOTO_SECRETO = frozenset({"CA"})
DADOS_VOTO_SIGILOSO: dict[str, Any] = {"conteudo": "sigiloso"}


def voto_e_secreto(contexto: str) -> bool:
    """Indica se o contexto exige voto secreto."""
    return str(contexto).upper() in CONTEXTOS_VOTO_SECRETO


def registro_de_voto_oculto(registro: RegistroAuditoria, secreto: bool) -> bool:
    """Um registro de voto tem seu conteúdo e horário ocultos em contexto secreto."""
    return secreto and registro.evento == TipoEvento.VOTO_REGISTRADO


def dados_publicos_do_registro(registro: RegistroAuditoria, secreto: bool) -> dict[str, Any]:
    """Dados do registro que podem ser exibidos, sem a opção de um voto secreto.

    O log de auditoria guarda a opção (necessária para a cadeia de hash e a
    recontagem); apenas a exibição é restringida.
    """
    if registro_de_voto_oculto(registro, secreto):
        return dict(DADOS_VOTO_SIGILOSO)
    return registro.dados


class EstadoAplicacaoUI:
    """Mantém o estado em memória da aplicação web e orquestra todos os subsistemas."""

    def __init__(self) -> None:
        self.banco = BancoDadosMock(popular=True)
        self.servico = ServicoElegibilidade(self.banco)
        self.sessoes: dict[str, SessaoVotacao] = {}
        self.metadados_sessoes: dict[str, dict[str, Any]] = {}
        self.ancoras_emitidas: dict[str, ResumoEncerramento] = {}
        self.tramitacoes: dict[str, TramitacaoLegislativa] = {}
        self._inicializar_cenario_demonstracao()

    def _inicializar_cenario_demonstracao(self) -> None:
        """Cria sessões e tramitações iniciais para facilitar a exploração imediata na UI."""
        # 1. Sessão de Eleição de Centro Acadêmico já aberta para votação
        self.criar_sessao(
            id_sessao="ELEICAO-CA-2026",
            contexto="CA",
            titulo="Eleição da Diretoria do Centro Acadêmico 2026",
            quorum_minimo_votantes=2,
            percentual_quorum_minimo=0.2,
            abrir_imediatamente=True,
            liberar_imediatamente=True,
        )

        # 2. Sessão de Assembleia Geral Extraordinária aberta para votação
        self.criar_sessao(
            id_sessao="AGE-2026-01",
            contexto="ASSEMBLEIA",
            titulo="AGE — Aprovação de Fusão e Reforma Estatutária",
            tipo_decisao="MAIORIA_ABSOLUTA",
            percentual_quorum_instalacao=0.25,
            base_calculo_sobre_total_capital=False,
            abrir_imediatamente=True,
            liberar_imediatamente=True,
        )

        # 3. Tramitação legislativa ativa para o PL-101/2026
        self.iniciar_tramitacao(materia_id="PL-101/2026")

    def resetar_sistema(self, usar_sql: bool = False) -> dict[str, Any]:
        """Restaura todos os dados padrão, sessões de demonstração e tramitações."""
        if usar_sql:
            self.banco.recarregar_dados_do_sql()
        else:
            self.banco.recarregar_dados_padrao()
        self.servico = ServicoElegibilidade(self.banco)
        self.sessoes.clear()
        self.metadados_sessoes.clear()
        self.ancoras_emitidas.clear()
        self.tramitacoes.clear()
        self._inicializar_cenario_demonstracao()
        return self.obter_estado_completo()

    # =========================================================================
    # SERIALIZAÇÃO E LEITURA DE ESTADO COMPLETO
    # =========================================================================

    def obter_estado_completo(self) -> dict[str, Any]:
        """Retorna um snapshot completo e serializável em JSON de todo o sistema."""
        discentes = [self._serializar_discente(d) for d in self.banco.ca.listar_discentes()]
        chapas = [self._serializar_chapa(c) for c in self.banco.ca.listar_chapas()]

        acionistas = [
            self._serializar_acionista(a) for a in self.banco.assembleia.listar_acionistas()
        ]
        procuradores = [
            self._serializar_procurador(p) for p in self.banco.assembleia.listar_procuradores()
        ]
        procuracoes = [self._serializar_procuracao(p) for p in self._listar_todas_procuracoes()]
        candidatos_conselho = [
            self._serializar_candidato_conselho(c)
            for c in self.banco.assembleia.listar_candidatos_conselho()
        ]

        parlamentares = [
            self._serializar_parlamentar(p) for p in self.banco.congresso.listar_parlamentares()
        ]
        materias = [self._serializar_materia(m) for m in self.banco.congresso.listar_materias()]

        sessoes = {id_s: self.serializar_sessao(id_s) for id_s in self.sessoes}
        tramitacoes = {
            t.materia_id: self._serializar_tramitacao(t) for t in self.tramitacoes.values()
        }

        aptos_ca = sum(1 for d in discentes if d["apto_votar"])
        capital_votante = self.banco.assembleia.total_capital_votante()

        ancoras_dict = {}
        for k, v in self.ancoras_emitidas.items():
            d = asdict(v)
            d["hash_final"] = v.hash_encerramento
            ancoras_dict[k] = d

        return {
            "resumo": {
                "total_discentes": len(discentes),
                "discentes_aptos": aptos_ca,
                "total_chapas": len(chapas),
                "chapas_elegiveis": sum(1 for c in chapas if c["elegivel"]),
                "total_acionistas": len(acionistas),
                "capital_votante": capital_votante,
                "total_procuradores": len(procuradores),
                "procuracoes_vigentes": sum(1 for p in procuracoes if p["vigente"]),
                "total_parlamentares": len(parlamentares),
                "deputados_exercicio": self.banco.congresso.total_em_exercicio(
                    CasaLegislativa.CAMARA
                ),
                "senadores_exercicio": self.banco.congresso.total_em_exercicio(
                    CasaLegislativa.SENADO
                ),
                "total_materias": len(materias),
                "total_sessoes": len(sessoes),
                "sessoes_em_votacao": sum(
                    1 for s in sessoes.values() if s["estado"] == EstadoSessao.EM_VOTACAO.value
                ),
                "total_tramitacoes": len(tramitacoes),
            },
            "ca": {
                "discentes": discentes,
                "chapas": chapas,
            },
            "assembleia": {
                "acionistas": acionistas,
                "procuradores": procuradores,
                "procuracoes": procuracoes,
                "candidatos_conselho": candidatos_conselho,
                "capital_votante": capital_votante,
            },
            "congresso": {
                "parlamentares": parlamentares,
                "materias": materias,
            },
            "sessoes": sessoes,
            "metadados_sessoes": dict(self.metadados_sessoes),
            "ancoras_emitidas": ancoras_dict,
            "tramitacoes": tramitacoes,
        }

    def _listar_todas_procuracoes(self) -> list[Any]:
        vistas: dict[tuple[str, str], Any] = {}
        for ac in self.banco.assembleia.listar_acionistas():
            for proc in self.banco.assembleia.listar_procuracoes_do_outorgante(ac.id):
                vistas[(proc.outorgante_id, proc.procurador_id)] = proc
        for pr in self.banco.assembleia.listar_procuradores():
            for proc in self.banco.assembleia.listar_procuracoes_do_procurador(pr.id):
                vistas[(proc.outorgante_id, proc.procurador_id)] = proc
        return list(vistas.values())

    def _serializar_discente(self, d: Discente) -> dict[str, Any]:
        apt = self.servico.consultar_aptidao(d.ra, "CA")
        return {
            "ra": d.ra,
            "nome": d.nome,
            "curso": d.curso,
            "semestre": getattr(d, "semestre", 1),
            "matricula_ativa": d.matricula_ativa,
            "formando_proximo_semestre": d.formando_proximo_semestre,
            "suspenso": d.suspenso,
            "apto_votar": apt.apto,
            "motivo_inaptidao": apt.motivo_inaptidao,
        }

    def _serializar_chapa(self, c: ChapaCA) -> dict[str, Any]:
        eleg = self.servico.validar_candidato_ou_opcao(c.nome, "CA")
        pres = c.integrantes_ra[0] if c.integrantes_ra else ""
        vice = c.integrantes_ra[1] if len(c.integrantes_ra) > 1 else ""
        return {
            "id": c.nome,
            "nome": c.nome,
            "integrantes_ra": list(c.integrantes_ra),
            "presidente_ra": pres,
            "vice_ra": vice,
            "plano_gestao": c.plano_gestao,
            "proposta": c.plano_gestao,
            "ativa": c.ativa,
            "elegivel": eleg.elegivel,
            "motivo_inelegibilidade": eleg.motivo_inelegibilidade,
        }

    def _serializar_acionista(self, a: Acionista) -> dict[str, Any]:
        apt = self.servico.consultar_aptidao(a.id, "ASSEMBLEIA")
        proc_vigente = self.servico.procuracoes.obter_vigente(a.id)
        return {
            "id": a.id,
            "nome": a.nome,
            "acoes_on": a.acoes_ordinarias,
            "acoes_pn": a.acoes_preferenciais,
            "acoes_ordinarias": a.acoes_ordinarias,
            "acoes_preferenciais": a.acoes_preferenciais,
            "bloqueado": a.bloqueado,
            "ativo": a.ativo,
            "apto_votar": apt.apto,
            "apto_votar_direto": apt.apto,
            "peso_voto": apt.peso_voto,
            "motivo_inaptidao": apt.motivo_inaptidao,
            "procurador_vigente": proc_vigente.procurador_id if proc_vigente else None,
        }

    def _serializar_procurador(self, p: Procurador) -> dict[str, Any]:
        poder = self.servico.procuracoes.calcular_poder_de_voto(p.id)
        return {
            "id": p.id,
            "nome": p.nome,
            "credenciado": p.credenciado,
            "ativo": p.ativo,
            "peso_proprio": poder.peso_proprio,
            "peso_delegado": poder.peso_delegado,
            "peso_total": poder.peso_total,
            "outorgantes": list(poder.outorgantes),
            "titulares": list(poder.titulares),
        }

    def _serializar_procuracao(self, p: Any) -> dict[str, Any]:
        return {
            "outorgante_id": p.outorgante_id,
            "procurador_id": p.procurador_id,
            "data_expiracao": p.data_expiracao.isoformat() if p.data_expiracao else None,
            "ativa": p.ativa,
            "vigente": p.esta_vigente(),
        }

    def _serializar_candidato_conselho(self, c: CandidatoConselho) -> dict[str, Any]:
        eleg = self.servico.validar_candidato_ou_opcao(c.id, "ASSEMBLEIA")
        return {
            "id": c.id,
            "nome": c.nome,
            "titular_acoes": c.titular_acoes,
            "conflito_interesse": c.conflito_interesse,
            "ativo": c.ativo,
            "elegivel": eleg.elegivel,
            "motivo_inelegibilidade": eleg.motivo_inelegibilidade,
        }

    def _serializar_parlamentar(self, p: Parlamentar) -> dict[str, Any]:
        apt = self.servico.consultar_aptidao(p.id, "CONGRESSO", casa=p.casa)
        return {
            "id": p.id,
            "nome": p.nome,
            "casa": p.casa.value,
            "partido": p.partido,
            "uf": p.uf,
            "em_exercicio": p.em_exercicio,
            "licenciado": p.licenciado,
            "suspenso": p.suspenso,
            "apto_votar": apt.apto,
            "motivo_inaptidao": apt.motivo_inaptidao,
        }

    def _serializar_materia(self, m: MateriaLegislativa) -> dict[str, Any]:
        return {
            "id": m.id,
            "tipo": m.tipo.value,
            "casa_atual": m.casa_atual.value,
            "titulo": m.titulo,
            "ativa": m.ativa,
            "em_tramitacao": m.id.upper() in self.tramitacoes,
        }

    def serializar_sessao(self, id_sessao: str) -> dict[str, Any]:
        if id_sessao not in self.sessoes:
            msg = f"Sessão '{id_sessao}' não encontrada."
            raise KeyError(msg)

        s = self.sessoes[id_sessao]
        meta = self.metadados_sessoes.get(id_sessao, {})
        contexto = meta.get("contexto", self._inferir_contexto_regra(s.regra))
        secreto = voto_e_secreto(contexto)

        # Voto secreto: nenhum voto individual sai da sessão (nem eleitor, nem opção,
        # nem horário) e não há parcial durante a votação, que permitiria ligar cada
        # incremento a quem acabou de votar. O resultado só aparece após a apuração.
        votos_serializados = (
            []
            if secreto
            else [
                {
                    "eleitor_id": v.eleitor_id,
                    "opcao": v.opcao,
                    "peso": v.peso,
                    "timestamp": v.timestamp.isoformat() if v.timestamp else None,
                    "representados": list(v.representados),
                }
                for v in s.votos
            ]
        )

        contagem_parcial: dict[str, int] = {}
        if not secreto:
            for v in s.votos:
                contagem_parcial[v.opcao] = contagem_parcial.get(v.opcao, 0) + v.peso

        resultado_dict: dict[str, Any] | None = None
        if s.resultado is not None:
            r = s.resultado
            resultado_dict = {
                "status": r.status.value,
                "vencedor_ou_decisao": r.vencedor_ou_decisao,
                "vencedor": r.vencedor_ou_decisao,
                "quorum_atingido": r.quorum_atingido,
                "total_votantes": r.total_votantes,
                "total_votos": r.total_votantes,
                "total_peso_apurado": r.total_peso_apurado,
                "contagem": dict(r.contagem_por_opcao),
                "contagem_por_opcao": dict(r.contagem_por_opcao),
                "percentual_vencedor": r.percentual_vencedor,
                "detalhes": dict(r.detalhes),
            }

        auditoria_dict = self._serializar_auditoria(s, secreto=secreto)

        return {
            "id_sessao": s.id_sessao,
            "titulo": meta.get("titulo", s.id_sessao),
            "contexto": contexto,
            "voto_secreto": secreto,
            "estado": s.estado.value,
            "total_aptos": s.total_aptos,
            "quorum_instalacao": s.quorum_instalacao,
            "total_presentes": s.total_presentes,
            "motivo_suspensao": s.motivo_suspensao,
            "total_suspensoes": s.total_suspensoes,
            "motivo_anulacao": s.motivo_anulacao,
            "inicio_votacao": s.inicio_votacao.isoformat() if s.inicio_votacao else None,
            "fim_votacao": s.fim_votacao.isoformat() if s.fim_votacao else None,
            "total_votos": len(s.votos),
            "peso_parcial_total": sum(v.peso for v in s.votos),
            "contagem_parcial": contagem_parcial,
            "votos": votos_serializados,
            "regra_info": self._descrever_regra(s.regra),
            "meta": meta,
            "opcoes_sugeridas": self._opcoes_para_sessao(contexto, meta),
            "resultado": resultado_dict,
            "auditoria": auditoria_dict,
        }

    def _serializar_auditoria(self, s: SessaoVotacao, secreto: bool = False) -> dict[str, Any]:
        log = s.log
        if log is None:
            return {
                "ativo": False,
                "integro": True,
                "ultimo_hash": None,
                "registros": [],
                "ancora": None,
            }

        ancora = self.ancoras_emitidas.get(s.id_sessao)
        verif = log.verificar_integridade(ancora=ancora)
        registros = [
            {
                "indice": r.indice,
                "evento": r.evento.value,
                "id_votacao": r.id_votacao,
                # O horário exato de cada voto também liga voto a eleitor (D-AUD-03).
                "timestamp": (
                    None if registro_de_voto_oculto(r, secreto) else r.timestamp.isoformat()
                ),
                "dados": dados_publicos_do_registro(r, secreto),
                "hash_anterior": r.hash_anterior,
                "hash": r.hash,
            }
            for r in log.registros
        ]
        return {
            "ativo": True,
            "integro": verif.integro,
            "cadeia_integra": verif.integro,
            "indice_divergente": verif.indice_divergente,
            "motivo_divergencia": verif.motivo,
            "ultimo_hash": log.ultimo_hash,
            "total_registros": len(registros),
            "registros": registros,
            "ancora": asdict(ancora) if ancora else None,
            "ancora_json": ancora.para_json() if ancora else None,
        }

    def _serializar_tramitacao(self, t: TramitacaoLegislativa) -> dict[str, Any]:
        materia = self.banco.congresso.obter_materia(t.materia_id)
        sessao_atual_id: str | None = None
        if t._sessao_convocada is not None:
            sessao_atual_id = t._sessao_convocada.id_sessao

        historico = [
            {
                "id_sessao": h.id_sessao,
                "casa": h.casa.value,
                "turno": h.turno,
                "valida": h.valida,
                "status_resultado": h.resultado.status.value,
                "fase": h.fase.value,
                "com_emenda": h.com_emenda,
                "texto_prevalecente": (
                    h.texto_prevalecente.value if h.texto_prevalecente else None
                ),
                "decisao": h.resultado.vencedor_ou_decisao,
                "total_votantes": h.resultado.total_votantes,
                "contagem_por_opcao": dict(h.resultado.contagem_por_opcao),
            }
            for h in t.historico
        ]
        concluida = t.status.value in ("APROVADA", "REJEITADA")
        aprovada = t.status.value == "APROVADA"
        return {
            "materia_id": t.materia_id,
            "titulo": materia.titulo if materia else t.materia_id,
            "tipo": t.tipo.value,
            "status": t.status.value,
            "concluida": concluida,
            "aprovada": aprovada,
            "fase": t.fase.value,
            "aceita_emenda": t.aceita_emenda,
            "texto_prevalecente": t.texto_prevalecente.value if t.texto_prevalecente else None,
            "log_rito": [
                {"evento": r.evento.value, "dados": r.dados, "timestamp": r.timestamp.isoformat()}
                for r in (t.log.registros if t.log is not None else ())
            ],
            "casa_iniciadora": t.casa_iniciadora.value,
            "casa_revisora": t.casa_revisora.value,
            "casa_atual": t.casa_atual.value,
            "turno_atual": t.turno_atual,
            "turnos_por_casa": t.turnos_por_casa,
            "id_proxima_sessao": t.id_proxima_sessao,
            "sessao_convocada_id": sessao_atual_id,
            "historico": historico,
        }

    def _inferir_contexto_regra(self, regra: Any) -> str:
        if isinstance(regra, RegraCA):
            return "CA"
        if isinstance(regra, RegraAssembleia):
            return "ASSEMBLEIA"
        return "CONGRESSO"

    def _descrever_regra(self, regra: Any) -> dict[str, Any]:
        if isinstance(regra, RegraCA):
            return {
                "tipo": "RegraCA",
                "descricao": "Maioria simples de votos válidos (peso unitário)",
                "quorum_minimo_votantes": regra.quorum_minimo_votantes,
                "percentual_quorum_minimo": regra.percentual_quorum_minimo,
            }
        if isinstance(regra, RegraAssembleia):
            return {
                "tipo": "RegraAssembleia",
                "descricao": f"Voto ponderado por ações ON ({regra.tipo_decisao.value})",
                "tipo_decisao": regra.tipo_decisao.value,
                "percentual_quorum_instalacao": regra.percentual_quorum_instalacao,
                "base_calculo_sobre_total_capital": regra.base_calculo_sobre_total_capital,
            }
        if isinstance(regra, RegraCongresso):
            return {
                "tipo": "RegraCongresso",
                "descricao": f"{regra.materia.value} na {regra.casa.value}",
                "materia": regra.materia.value,
                "casa": regra.casa.value,
                "total_membros": regra.total_membros,
                "quorum_instalacao": regra.quorum_instalacao,
            }
        return {"tipo": type(regra).__name__, "descricao": "Regra customizada"}

    def _opcoes_para_sessao(self, contexto: str, meta: dict[str, Any]) -> list[str]:
        if contexto == "CA":
            chapas_ativas = [
                c.nome
                for c in self.banco.ca.listar_chapas()
                if c.ativa and self.servico.validar_candidato_ou_opcao(c.nome, "CA").elegivel
            ]
            return [*chapas_ativas, "BRANCO", "NULO"]
        if contexto == "ASSEMBLEIA":
            cands = [
                c.id
                for c in self.banco.assembleia.listar_candidatos_conselho()
                if c.ativo and self.servico.validar_candidato_ou_opcao(c.id, "ASSEMBLEIA").elegivel
            ]
            return ["SIM", "NAO", "ABSTENCAO", "BRANCO", *cands]
        return ["SIM", "NAO", "ABSTENCAO", "BRANCO"]

    @staticmethod
    def _converter_tipo_materia(valor: str) -> TipoMateriaCongresso:
        val = valor.strip().upper()
        mapa = {
            "PL": TipoMateriaCongresso.LEI_ORDINARIA,
            "LEI_ORDINARIA": TipoMateriaCongresso.LEI_ORDINARIA,
            "PLP": TipoMateriaCongresso.LEI_COMPLEMENTAR,
            "LEI_COMPLEMENTAR": TipoMateriaCongresso.LEI_COMPLEMENTAR,
            "PEC": TipoMateriaCongresso.PEC,
        }
        if val in mapa:
            return mapa[val]
        return TipoMateriaCongresso(val)

    # =========================================================================
    # CADASTROS E MUTAÇÕES DE DADOS (CA, ASSEMBLEIA, CONGRESSO)
    # =========================================================================

    def cadastrar_discente(self, dados: dict[str, Any]) -> dict[str, Any]:
        discente = Discente(
            ra=str(dados.get("ra", "")).strip(),
            nome=str(dados.get("nome", "")).strip(),
            curso=str(dados.get("curso", "Engenharia de Software")).strip()
            or "Engenharia de Software",
            matricula_ativa=bool(dados.get("matricula_ativa", True)),
            formando_proximo_semestre=bool(dados.get("formando_proximo_semestre", False)),
            suspenso=bool(dados.get("suspenso", False)),
        )
        self.banco.ca.adicionar_discente(discente)
        return self._serializar_discente(discente)

    def cadastrar_chapa(self, dados: dict[str, Any]) -> dict[str, Any]:
        nome = str(dados.get("nome", "") or dados.get("id", "")).strip()
        integrantes_raw = dados.get("integrantes_ra", [])
        if not integrantes_raw:
            pres = str(dados.get("presidente_ra", "")).strip()
            vice = str(dados.get("vice_ra", "")).strip()
            integrantes_raw = [r for r in (pres, vice) if r]

        if isinstance(integrantes_raw, str):
            integrantes = tuple(
                ra.strip() for ra in integrantes_raw.replace(";", ",").split(",") if ra.strip()
            )
        else:
            integrantes = tuple(str(ra).strip() for ra in integrantes_raw if str(ra).strip())

        chapa = ChapaCA(
            nome=nome,
            integrantes_ra=integrantes,
            plano_gestao=str(dados.get("plano_gestao", "") or dados.get("proposta", "")).strip(),
            ativa=bool(dados.get("ativa", True) and dados.get("regular", True)),
        )
        self.banco.ca.adicionar_chapa(chapa)
        return self._serializar_chapa(chapa)

    def cadastrar_acionista(self, dados: dict[str, Any]) -> dict[str, Any]:
        on = dados.get("acoes_on", dados.get("acoes_ordinarias", 0))
        pn = dados.get("acoes_pn", dados.get("acoes_preferenciais", 0))
        bloqueado = dados.get("bloqueado", dados.get("impedido", False))
        acionista = Acionista(
            id=str(dados.get("id", "")).strip(),
            nome=str(dados.get("nome", "")).strip(),
            acoes_ordinarias=int(on),
            acoes_preferenciais=int(pn),
            bloqueado=bool(bloqueado),
            ativo=bool(dados.get("ativo", True)),
        )
        self.banco.assembleia.adicionar_acionista(acionista)
        return self._serializar_acionista(acionista)

    def cadastrar_procurador(self, dados: dict[str, Any]) -> dict[str, Any]:
        procurador = Procurador(
            id=str(dados.get("id", "")).strip(),
            nome=str(dados.get("nome", "")).strip(),
            credenciado=bool(dados.get("credenciado", True)),
            ativo=bool(dados.get("ativo", True)),
        )
        self.banco.assembleia.adicionar_procurador(procurador)
        return self._serializar_procurador(procurador)

    def cadastrar_procuracao(self, dados: dict[str, Any]) -> dict[str, Any]:
        outorgante_id = str(dados.get("outorgante_id", "")).strip()
        procurador_id = str(dados.get("procurador_id", "")).strip()
        dias_validade = dados.get("validade_dias", dados.get("dias_validade", 30))
        expiracao: datetime | None = None
        if dias_validade is not None and str(dias_validade).strip() != "":
            expiracao = datetime.now(UTC) + timedelta(days=float(dias_validade))
        proc = self.servico.procuracoes.cadastrar(
            outorgante_id=outorgante_id,
            procurador_id=procurador_id,
            data_expiracao=expiracao,
        )
        return self._serializar_procuracao(proc)

    def revogar_procuracao(self, dados: dict[str, Any]) -> dict[str, Any]:
        outorgante_id = str(dados.get("outorgante_id", "")).strip()
        procurador_id = str(dados.get("procurador_id", "")).strip()
        proc = self.servico.procuracoes.revogar(outorgante_id, procurador_id)
        return self._serializar_procuracao(proc)

    def cadastrar_candidato_conselho(self, dados: dict[str, Any]) -> dict[str, Any]:
        candidato = CandidatoConselho(
            id=str(dados.get("id", "")).strip(),
            nome=str(dados.get("nome", "")).strip(),
            titular_acoes=bool(dados.get("titular_acoes", True)),
            conflito_interesse=bool(dados.get("conflito_interesse", False)),
            ativo=bool(dados.get("ativo", True)),
        )
        self.banco.assembleia.adicionar_candidato_conselho(candidato)
        return self._serializar_candidato_conselho(candidato)

    def cadastrar_parlamentar(self, dados: dict[str, Any]) -> dict[str, Any]:
        casa_str = str(dados.get("casa", "CAMARA")).strip().upper()
        casa = CasaLegislativa(casa_str)
        parlamentar = Parlamentar(
            id=str(dados.get("id", "")).strip(),
            nome=str(dados.get("nome", "")).strip(),
            casa=casa,
            partido=str(dados.get("partido", "")).strip().upper(),
            uf=str(dados.get("uf", "")).strip().upper(),
            em_exercicio=bool(dados.get("em_exercicio", True)),
            licenciado=bool(dados.get("licenciado", False)),
            suspenso=bool(dados.get("suspenso", False)),
        )
        self.banco.congresso.adicionar_parlamentar(parlamentar)
        return self._serializar_parlamentar(parlamentar)

    def cadastrar_materia(self, dados: dict[str, Any]) -> dict[str, Any]:
        tipo_str = str(dados.get("tipo", "LEI_ORDINARIA")).strip().upper()
        casa_str = str(dados.get("casa_atual", "CAMARA")).strip().upper()
        materia = MateriaLegislativa(
            id=str(dados.get("id", "")).strip().upper(),
            tipo=self._converter_tipo_materia(tipo_str),
            casa_atual=CasaLegislativa(casa_str),
            titulo=str(dados.get("titulo", "")).strip(),
            ativa=bool(dados.get("ativa", True)),
        )
        self.banco.congresso.adicionar_materia(materia)
        self.iniciar_tramitacao(materia.id)
        return self._serializar_materia(materia)

    # =========================================================================
    # GESTÃO DE SESSÕES DE VOTAÇÃO E CABINE DE VOTO
    # =========================================================================

    def criar_sessao(
        self,
        id_sessao: str,
        contexto: str,
        titulo: str = "",
        quorum_minimo_votantes: int = 0,
        percentual_quorum_minimo: float = 0.0,
        tipo_decisao: str = "MAIORIA_SIMPLES",
        percentual_quorum_instalacao: float = 0.0,
        base_calculo_sobre_total_capital: bool = False,
        materia: str = "LEI_ORDINARIA",
        casa: str = "CAMARA",
        materia_id: str | None = None,
        abrir_imediatamente: bool = False,
        liberar_imediatamente: bool = False,
    ) -> dict[str, Any]:
        id_limpo = id_sessao.strip()
        if not id_limpo:
            msg = "O identificador da sessão não pode ser vazio."
            raise ValueError(msg)
        if id_limpo in self.sessoes:
            msg = f"Já existe uma sessão com o identificador '{id_limpo}'."
            raise ValueError(msg)

        ctx = contexto.strip().upper()
        log = LogDeAuditoria(id_limpo)

        if ctx == "CA":
            aptos = sum(
                1
                for d in self.banco.ca.listar_discentes()
                if self.servico.consultar_aptidao(d.ra, "CA").apto
            )
            sessao = FabricaCA().criar_sessao(
                id_sessao=id_limpo,
                total_aptos=aptos,
                quorum_minimo_votantes=int(quorum_minimo_votantes),
                percentual_quorum_minimo=float(percentual_quorum_minimo),
                log=log,
            )
            meta = {"contexto": "CA", "titulo": titulo.strip() or id_limpo}
        elif ctx == "ASSEMBLEIA":
            capital = self.banco.assembleia.total_capital_votante()
            dec_str = tipo_decisao.strip().upper()
            mapa_decisao = {
                "MAIORIA_SIMPLES": TipoDecisaoAssembleia.MAIORIA_SIMPLES,
                "MAIORIA_ABSOLUTA": TipoDecisaoAssembleia.MAIORIA_ABSOLUTA,
                "QUORUM_QUALIFICADO": TipoDecisaoAssembleia.QUALIFICADA_DOIS_TERCOS,
                "QUALIFICADA_DOIS_TERCOS": TipoDecisaoAssembleia.QUALIFICADA_DOIS_TERCOS,
                "QUALIFICADA_TRES_QUINTOS": TipoDecisaoAssembleia.QUALIFICADA_TRES_QUINTOS,
                "DOIS_TERCOS": TipoDecisaoAssembleia.QUALIFICADA_DOIS_TERCOS,
            }
            if dec_str in mapa_decisao:
                decisao_enum = mapa_decisao[dec_str]
            else:
                decisao_enum = TipoDecisaoAssembleia(dec_str)
            sessao = FabricaAssembleia().criar_sessao(
                id_sessao=id_limpo,
                total_aptos=capital,
                tipo_decisao=decisao_enum,
                percentual_quorum_instalacao=float(percentual_quorum_instalacao),
                base_calculo_sobre_total_capital=bool(base_calculo_sobre_total_capital),
                log=log,
            )
            meta = {
                "contexto": "ASSEMBLEIA",
                "titulo": titulo.strip() or id_limpo,
                "tipo_decisao": decisao_enum.value,
            }
        elif ctx == "CONGRESSO":
            casa_enum = CasaLegislativa(casa.strip().upper())
            materia_enum = self._converter_tipo_materia(materia)
            fabrica_congresso = FabricaCongresso()
            regra_congresso = fabrica_congresso.criar_regra(materia=materia_enum, casa=casa_enum)
            sessao = fabrica_congresso.criar_sessao(
                id_sessao=id_limpo,
                materia=materia_enum,
                casa=casa_enum,
                log=log,
                regra=regra_congresso,
                quorum_instalacao=regra_congresso.quorum_instalacao,
            )
            meta = {
                "contexto": "CONGRESSO",
                "titulo": titulo.strip() or id_limpo,
                "casa": casa_enum.value,
                "materia": materia_enum.value,
                "materia_id": materia_id,
            }
        else:
            msg = f"Contexto inválido: '{contexto}'. Use CA, ASSEMBLEIA ou CONGRESSO."
            raise ValueError(msg)

        if abrir_imediatamente or liberar_imediatamente:
            sessao.abrir()
        aviso = self._liberar_se_houver_quorum(sessao) if liberar_imediatamente else None

        self.sessoes[id_limpo] = sessao
        self.metadados_sessoes[id_limpo] = meta
        resposta = self.serializar_sessao(id_limpo)
        if aviso:
            resposta["aviso"] = aviso
        return resposta

    @staticmethod
    def _liberar_se_houver_quorum(sessao: SessaoVotacao) -> str | None:
        """Libera a votação; sem quórum de presença, mantém a sessão ABERTA e avisa."""
        try:
            sessao.liberar_votacao()
        except QuorumInstalacaoError as exc:
            return f"{exc} Registre a presença dos parlamentares e libere a votação."
        return None

    def registrar_presenca_sessao(self, id_sessao: str, dados: dict[str, Any]) -> dict[str, Any]:
        """Registra presentes numa sessão: parlamentares cadastrados e/ou bancada em lote.

        `parlamentares` são identificadores do cadastro, que precisam pertencer à Casa da
        sessão e estar em exercício. `bancada` simula a presença de N parlamentares
        genéricos, com os mesmos identificadores usados pela simulação de votos, para
        que quem estiver presente e votar não seja contado duas vezes.
        """
        sessao = self._obter_sessao(id_sessao)
        if not isinstance(sessao.regra, RegraCongresso):
            msg = "O registro de presença só se aplica a sessões do Congresso."
            raise ValueError(msg)

        ids: list[str] = []
        for bruto in dados.get("parlamentares") or []:
            pid = str(bruto).strip()
            parlamentar = self.banco.congresso.obter_parlamentar(pid)
            if parlamentar is None:
                msg = f"Parlamentar '{pid}' não encontrado no cadastro."
                raise KeyError(msg)
            if parlamentar.casa != sessao.regra.casa:
                msg = (
                    f"{parlamentar.nome} é da {parlamentar.casa.value} e não pode compor o "
                    f"quórum de uma sessão da {sessao.regra.casa.value}."
                )
                raise ValueError(msg)
            if not parlamentar.em_exercicio or parlamentar.licenciado or parlamentar.suspenso:
                msg = f"{parlamentar.nome} não está no exercício do mandato."
                raise ValueError(msg)
            ids.append(parlamentar.id)

        bancada = int(dados.get("bancada") or 0)
        if bancada < 0:
            msg = "A quantidade de presentes da bancada não pode ser negativa."
            raise ValueError(msg)
        prefixo = sessao.regra.casa.value[:3]
        ids.extend(f"{prefixo}-BANCADA-{seq:03d}" for seq in range(1, bancada + 1))

        if not ids:
            msg = "Informe ao menos um parlamentar ou a quantidade de presentes da bancada."
            raise ValueError(msg)
        novos = set(ids) - sessao.presentes
        if sessao.total_presentes + len(novos) > sessao.regra.total_membros:
            msg = (
                f"A presença ({sessao.total_presentes + len(novos)}) ultrapassaria os "
                f"{sessao.regra.total_membros} membros da {sessao.regra.casa.value}."
            )
            raise ValueError(msg)

        sessao.registrar_presenca(*ids)
        return self.serializar_sessao(id_sessao)

    def suspender_sessao(self, id_sessao: str, motivo: str) -> dict[str, Any]:
        """Suspende a votação em curso, preservando os votos já colhidos (#38)."""
        sessao = self._obter_sessao(id_sessao)
        sessao.suspender(motivo)
        return self.serializar_sessao(id_sessao)

    def anular_sessao(self, id_sessao: str, motivo: str) -> dict[str, Any]:
        """Anula uma sessão viciada, registrando o motivo (#39).

        Na interface, a apuração de uma sessão de tramitação já registra o resultado no
        rito. Anulá-la depois disso deixaria a matéria avançada por uma sessão anulada,
        então a anulação só é aceita antes desse registro.
        """
        sessao = self._obter_sessao(id_sessao)
        materia_id = self.metadados_sessoes.get(id_sessao, {}).get("tramitacao_materia_id")
        tram = self.tramitacoes.get(materia_id) if materia_id else None
        if tram is not None and any(r.id_sessao == sessao.id_sessao for r in tram.historico):
            msg = (
                f"O resultado da sessão '{id_sessao}' já foi registrado na tramitação de "
                f"{materia_id}; a anulação deve ocorrer antes da apuração."
            )
            raise ValueError(msg)
        sessao.anular(motivo)
        return self.serializar_sessao(id_sessao)

    def retomar_sessao(self, id_sessao: str) -> dict[str, Any]:
        """Retoma a votação suspensa, sem estender a janela de votação (#38)."""
        sessao = self._obter_sessao(id_sessao)
        sessao.retomar()
        return self.serializar_sessao(id_sessao)

    def abrir_sessao(self, id_sessao: str) -> dict[str, Any]:
        sessao = self._obter_sessao(id_sessao)
        sessao.abrir()
        return self.serializar_sessao(id_sessao)

    def liberar_votacao_sessao(
        self,
        id_sessao: str,
        duracao_minutos: int | None = None,
    ) -> dict[str, Any]:
        sessao = self._obter_sessao(id_sessao)
        if sessao.estado == EstadoSessao.CRIADA:
            sessao.abrir()

        inicio: datetime | None = None
        fim: datetime | None = None
        if duracao_minutos is not None and int(duracao_minutos) > 0:
            inicio = datetime.now(UTC) - timedelta(seconds=5)
            fim = datetime.now(UTC) + timedelta(minutes=int(duracao_minutos))

        sessao.liberar_votacao(inicio=inicio, fim=fim)
        return self.serializar_sessao(id_sessao)

    def encerrar_votacao_sessao(self, id_sessao: str) -> dict[str, Any]:
        sessao = self._obter_sessao(id_sessao)
        sessao.encerrar_votacao()
        if sessao.log is not None:
            self.ancoras_emitidas[id_sessao] = sessao.log.resumo_encerramento()
        return self.serializar_sessao(id_sessao)

    def apurar_sessao(self, id_sessao: str, com_emenda: bool = False) -> dict[str, Any]:
        """Apura a sessão e, se for de tramitação, registra o resultado no rito.

        `com_emenda` indica que a Casa revisora aprovou a matéria com emendas (#33). É
        validado antes da apuração, para que uma indicação inválida não deixe a sessão
        apurada e sem registro; e só se aplica se o resultado for de aprovação.
        """
        sessao = self._obter_sessao(id_sessao)
        meta = self.metadados_sessoes.get(id_sessao, {})
        tramitacao_id = meta.get("tramitacao_materia_id")
        tram = self.tramitacoes.get(tramitacao_id) if tramitacao_id else None
        if com_emenda and (tram is None or tram._sessao_convocada is not sessao):
            msg = "A indicação de emenda só se aplica a sessões de tramitação legislativa."
            raise ValueError(msg)
        if com_emenda and tram is not None and not tram.aceita_emenda:
            msg = (
                f"A matéria {tramitacao_id} está na fase {tram.fase.value}: apenas a Casa "
                "revisora emenda o projeto (CF, art. 65)."
            )
            raise ValueError(msg)

        if sessao.estado == EstadoSessao.EM_VOTACAO:
            sessao.encerrar_votacao()
            if sessao.log is not None:
                self.ancoras_emitidas[id_sessao] = sessao.log.resumo_encerramento()

        resultado = sessao.apurar()

        if tram is not None and tram._sessao_convocada is sessao:
            aprovou = resultado.status == StatusResultado.APROVADO
            tram.registrar_resultado(sessao, com_emenda=com_emenda and aprovou)

        return self.serializar_sessao(id_sessao)

    def registrar_voto_na_sessao(self, id_sessao: str, dados: dict[str, Any]) -> dict[str, Any]:
        sessao = self._obter_sessao(id_sessao)
        meta = self.metadados_sessoes.get(id_sessao, {})
        contexto = meta.get("contexto", self._inferir_contexto_regra(sessao.regra))

        modo = str(dados.get("modo", "DIRETO")).strip().upper()
        eleitor_id = str(dados.get("eleitor_id", "")).strip()
        procurador_id = str(dados.get("procurador_id", "")).strip() or None
        opcao = str(dados.get("opcao", "")).strip()

        casa: CasaLegislativa | None = None
        if contexto == "CONGRESSO":
            casa_str = meta.get("casa") or dados.get("casa") or "CAMARA"
            casa = CasaLegislativa(str(casa_str).upper())

        if contexto == "ASSEMBLEIA" and modo == "CONSOLIDADO_PROCURADOR":
            id_proc = procurador_id or eleitor_id
            voto = self.servico.autorizar_voto_do_procurador(
                procurador_id=id_proc,
                opcao=opcao,
            )
        else:
            id_proc = procurador_id if (contexto == "ASSEMBLEIA" and modo == "PROCURACAO") else None
            voto = self.servico.autorizar_voto(
                eleitor_id=eleitor_id,
                opcao=opcao,
                contexto=contexto,
                casa=casa,
                procurador_id=id_proc,
            )

        protocolo = sessao.registrar_voto(voto)
        # O recibo de um voto secreto comprova a inclusão (protocolo), não o conteúdo.
        voto_publico: dict[str, Any] = (
            {"peso": voto.peso, "sigiloso": True}
            if voto_e_secreto(contexto)
            else {
                "eleitor_id": voto.eleitor_id,
                "opcao": voto.opcao,
                "peso": voto.peso,
                "representados": list(voto.representados),
            }
        )
        return {
            "protocolo": protocolo,
            "voto": voto_publico,
            "sessao": self.serializar_sessao(id_sessao),
        }

    def simular_votacao_plenario(self, id_sessao: str, dados: dict[str, Any]) -> dict[str, Any]:
        """Permite lançar votos de bancada em lote numa sessão do Congresso para testar quóruns."""
        sessao = self._obter_sessao(id_sessao)
        if not isinstance(sessao.regra, RegraCongresso):
            msg = "A simulação de bancada de plenário só se aplica a sessões do Congresso."
            raise ValueError(msg)

        qtd_sim = max(0, int(dados.get("votos_sim", 0)))
        qtd_nao = max(0, int(dados.get("votos_nao", 0)))
        qtd_abst = max(0, int(dados.get("votos_abstencao", 0)))
        qtd_branco = max(0, int(dados.get("votos_branco", 0)))

        total_lote = qtd_sim + qtd_nao + qtd_abst + qtd_branco
        if total_lote <= 0:
            msg = "Informe pelo menos 1 voto para a votação em lote do plenário."
            raise ValueError(msg)

        prefixo = sessao.regra.casa.value[:3]
        existentes = len(sessao.votos)
        if existentes + total_lote > sessao.regra.total_membros:
            msg = (
                f"O total de votos ({existentes + total_lote}) ultrapassaria o limite "
                f"constitucional de {sessao.regra.total_membros} parlamentares na "
                f"{sessao.regra.casa.value}."
            )
            raise ValueError(msg)

        protocolos: list[str] = []
        plano = [
            ("SIM", qtd_sim),
            ("NAO", qtd_nao),
            ("ABSTENCAO", qtd_abst),
            ("BRANCO", qtd_branco),
        ]
        seq = existentes + 1
        for opcao, quantidade in plano:
            for _ in range(quantidade):
                eleitor_id = f"{prefixo}-BANCADA-{seq:03d}"
                seq += 1
                p = sessao.registrar_voto(Voto(eleitor_id=eleitor_id, opcao=opcao, peso=1))
                if p:
                    protocolos.append(p)

        return {
            "votos_adicionados": total_lote,
            "ultimo_protocolo": protocolos[-1] if protocolos else None,
            "sessao": self.serializar_sessao(id_sessao),
        }

    # =========================================================================
    # TRAMITAÇÃO LEGISLATIVA BICAMERAL
    # =========================================================================

    def iniciar_tramitacao(self, materia_id: str) -> dict[str, Any]:
        id_limpo = materia_id.strip().upper()
        materia = self.banco.congresso.obter_materia(id_limpo)
        if materia is None:
            msg = f"Matéria '{id_limpo}' não encontrada no cadastro do Congresso."
            raise ValueError(msg)

        tram = TramitacaoLegislativa(
            materia_id=materia.id,
            tipo=materia.tipo,
            casa_iniciadora=materia.casa_atual,
            repo=self.banco.congresso,
            log=LogDeAuditoria(materia.id),
        )
        self.tramitacoes[id_limpo] = tram
        return self._serializar_tramitacao(tram)

    def convocar_sessao_tramitacao(
        self,
        materia_id: str,
        liberar_imediatamente: bool = True,
    ) -> dict[str, Any]:
        id_limpo = materia_id.strip().upper()
        if id_limpo not in self.tramitacoes:
            self.iniciar_tramitacao(id_limpo)

        tram = self.tramitacoes[id_limpo]
        id_sessao = tram.id_proxima_sessao
        if id_sessao in self.sessoes:
            # Arquiva sessão anterior do mesmo turno (ex.: inválida por falta de quórum)
            sufixo = len(tram.historico)
            chave_antiga = f"{id_sessao}-TENTATIVA-{sufixo}"
            sessao_antiga = self.sessoes.pop(id_sessao)
            sessao_antiga.id_sessao = chave_antiga
            self.sessoes[chave_antiga] = sessao_antiga
            if id_sessao in self.metadados_sessoes:
                self.metadados_sessoes[chave_antiga] = self.metadados_sessoes.pop(id_sessao)
            if id_sessao in self.ancoras_emitidas:
                self.ancoras_emitidas[chave_antiga] = self.ancoras_emitidas.pop(id_sessao)

        log = LogDeAuditoria(id_sessao)
        sessao = tram.nova_sessao(log=log)
        etapa = (
            "Apreciação das emendas"
            if tram.fase == FaseTramitacao.APRECIACAO_EMENDAS
            else f"{tram.turno_atual}º Turno"
        )
        chave_mapa = id_sessao

        aviso: str | None = None
        if liberar_imediatamente:
            sessao.abrir()
            aviso = self._liberar_se_houver_quorum(sessao)

        materia_obj = self.banco.congresso.obter_materia(id_limpo)
        titulo_materia = materia_obj.titulo if materia_obj else id_limpo
        self.sessoes[chave_mapa] = sessao
        self.metadados_sessoes[chave_mapa] = {
            "contexto": "CONGRESSO",
            "titulo": (f"{id_limpo} ({tram.casa_atual.value} — {etapa}): {titulo_materia}"),
            "casa": tram.casa_atual.value,
            "materia": tram.tipo.value,
            "materia_id": id_limpo,
            "tramitacao_materia_id": id_limpo,
        }
        resposta: dict[str, Any] = {
            "tramitacao": self._serializar_tramitacao(tram),
            "sessao": self.serializar_sessao(chave_mapa),
        }
        if aviso:
            resposta["aviso"] = aviso
        return resposta

    # =========================================================================
    # AUDITORIA E CONSULTA DE APTIDÃO
    # =========================================================================

    def verificar_protocolo_auditoria(self, id_sessao: str, protocolo: str) -> dict[str, Any]:
        sessao = self._obter_sessao(id_sessao)
        prot_limpo = protocolo.strip()
        if not prot_limpo:
            msg = "Informe um hash de protocolo para verificação."
            raise ValueError(msg)
        if sessao.log is None:
            return {"encontrado": False, "id_sessao": id_sessao, "protocolo": prot_limpo}

        meta = self.metadados_sessoes.get(id_sessao, {})
        secreto = voto_e_secreto(meta.get("contexto", self._inferir_contexto_regra(sessao.regra)))
        encontrado = sessao.log.contem_protocolo(prot_limpo)
        registro_detalhe = None
        for r in sessao.log.registros:
            if r.hash == prot_limpo:
                # Em voto secreto, conferir o protocolo prova a inclusão do voto, mas
                # não pode revelar a opção: isso viabilizaria compra de voto e coação.
                registro_detalhe = {
                    "indice": r.indice,
                    "evento": r.evento.value,
                    "timestamp": None if secreto else r.timestamp.isoformat(),
                    "dados": dados_publicos_do_registro(r, secreto),
                    "hash": r.hash,
                }
                break
        return {
            "encontrado": encontrado,
            "id_sessao": id_sessao,
            "protocolo": prot_limpo,
            "registro": registro_detalhe,
        }

    def consultar_aptidao_ui(self, dados: dict[str, Any]) -> dict[str, Any]:
        eleitor_id = str(dados.get("eleitor_id", "")).strip()
        contexto = str(dados.get("contexto", "CA")).strip().upper()
        procurador_id = str(dados.get("procurador_id", "")).strip() or None
        casa_str = dados.get("casa")
        casa = CasaLegislativa(str(casa_str).upper()) if casa_str else None

        usuario = self.servico.autenticar(eleitor_id, contexto)
        aptidao = self.servico.consultar_aptidao(
            eleitor_id=eleitor_id,
            contexto=contexto,
            casa=casa,
            procurador_id=procurador_id,
        )
        return {
            "autenticado": usuario is not None,
            "usuario": asdict(usuario) if usuario else None,
            "apto": aptidao.apto,
            "peso_voto": aptidao.peso_voto,
            "motivo_inaptidao": aptidao.motivo_inaptidao,
            "dados_eleitor": aptidao.dados_eleitor,
        }

    def _obter_sessao(self, id_sessao: str) -> SessaoVotacao:
        id_limpo = id_sessao.strip()
        if id_limpo not in self.sessoes:
            msg = f"Sessão '{id_limpo}' não encontrada."
            raise KeyError(msg)
        return self.sessoes[id_limpo]

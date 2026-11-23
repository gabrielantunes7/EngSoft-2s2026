/**
 * SISTEMA DE VOTAÇÃO MULTI-INSTITUCIONAL — SPA FRONTEND (DESKTOP & MOBILE)
 */

let estadoApp = null;
let sessaoSelecionadaId = null;
let opcaoVotoSelecionada = null;
// Estado da urna que precisa sobreviver ao redesenho da tela após cada voto:
// o último recibo emitido (por sessão) e o eleitor escolhido no seletor.
let ultimoReciboVoto = null; // { idSessao, protocolo }
let eleitorUrnaSelecionado = null;

// ==========================================================================
// INICIALIZAÇÃO E CICLO DE VIDA
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
  carregarEstadoCompleto();
  // Atualiza periodicamente a cada 5 segundos
  setInterval(carregarEstadoSilencioso, 5000);
});

async function apiFetch(endpoint, opcoes = {}) {
  const defaults = {
    headers: { "Content-Type": "application/json" },
  };
  const config = { ...defaults, ...opcoes };
  const resp = await fetch(endpoint, config);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const msg = data.erro || `Erro HTTP ${resp.status}`;
    throw new Error(msg);
  }
  return data;
}

async function carregarEstadoCompleto() {
  try {
    const estado = await apiFetch("/api/estado");
    estadoApp = estado;
    atualizarTodaInterface();
  } catch (err) {
    mostrarToast(`Erro ao carregar dados do servidor: ${err.message}`, "error");
    const statusEl = document.getElementById("status-conexao");
    if (statusEl) {
      statusEl.textContent = "Servidor Desconectado";
      statusEl.previousElementSibling?.classList.remove("online");
    }
  }
}

async function carregarEstadoSilencioso() {
  try {
    const estado = await apiFetch("/api/estado");
    estadoApp = estado;
    atualizarBadgesEContadores();
  } catch {
    // Silencioso para não incomodar polling em background
  }
}

function atualizarTodaInterface() {
  if (!estadoApp) return;

  const statusEl = document.getElementById("status-conexao");
  if (statusEl) {
    statusEl.textContent = "Sistema Operacional Ativo";
    statusEl.previousElementSibling?.classList.add("online");
  }

  atualizarBadgesEContadores();
  renderizarDashboard();
  renderizarAbaSessoes();
  renderizarAbaCA();
  renderizarAbaAssembleia();
  renderizarAbaCongresso();
  renderizarAbaAuditoria();
  atualizarOpcoesConsultaAptidao();
}

function atualizarBadgesEContadores() {
  if (!estadoApp) return;
  const sessoesAtivas = Object.values(estadoApp.sessoes || {}).filter(
    (s) => ["EM_VOTACAO", "ABERTA", "SUSPENSA"].includes(s.estado)
  ).length;

  const badge = document.getElementById("badge-sessoes-ativas");
  if (badge) badge.textContent = sessoesAtivas;
}

// ==========================================================================
// NAVEGAÇÃO E SIMULADOR DE VIEWPORT (DESKTOP / MOBILE)
// ==========================================================================

function navegarPara(tabId) {
  // Atualiza botões da sidebar
  document.querySelectorAll(".sidebar-nav .nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });

  // Atualiza bottom navigation mobile
  document.querySelectorAll(".mobile-bottom-nav .bottom-nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });

  // Alterna views
  document.querySelectorAll(".tab-view").forEach((view) => {
    view.classList.toggle("active", view.id === `view-${tabId}`);
  });

  // Atualiza títulos do topo
  const titulos = {
    dashboard: ["Painel Geral do Sistema", "Visão consolidada das votações estudantis, societárias e legislativas"],
    sessoes: ["Sessões & Urna Eletrônica", "Gerencie o ciclo de vida das votações e registre votos em tempo real"],
    ca: ["Centro Acadêmico (CA)", "Gestão de discentes, chapas e eleições estudantis com regra de maioria simples"],
    assembleia: ["Assembleia de Acionistas", "Voto proporcional por ações ordinárias e gestão de procurações de voto"],
    congresso: ["Congresso Nacional & Leis", "Processo legislativo bicameral (Câmara e Senado) para PL, PLP e PEC"],
    auditoria: ["Auditoria SHA-256", "Cadeia de custódia criptográfica, integridade de votos e âncora de encerramento"],
  };

  const t = titulos[tabId] || ["Sistema de Votação", "Plataforma multi-institucional"];
  document.getElementById("page-title").textContent = t[0];
  document.getElementById("page-subtitle").textContent = t[1];

  // Cada aba começa do topo; sem isso a nova aba herda a rolagem da anterior.
  window.scrollTo(0, 0);
  document.getElementById("content-viewport")?.scrollTo(0, 0);

  fecharMenuMobile();
}

function abrirMenuMobile() {
  document.getElementById("sidebar").classList.add("open");
  document.getElementById("sidebar-backdrop").classList.add("open");
}

function fecharMenuMobile() {
  document.getElementById("sidebar").classList.remove("open");
  document.getElementById("sidebar-backdrop").classList.remove("open");
}

function alterarSimulacaoViewport(modo) {
  const container = document.getElementById("content-viewport");
  const indicador = document.getElementById("indicador-dispositivo");
  container.classList.remove("viewport-sim-tablet", "viewport-sim-mobile");

  if (modo === "tablet") {
    container.classList.add("viewport-sim-tablet");
    indicador.textContent = "📱 Tablet (768px)";
  } else if (modo === "mobile") {
    container.classList.add("viewport-sim-mobile");
    indicador.textContent = "📱 Celular (420px)";
  } else if (modo === "desktop") {
    indicador.textContent = "🖥️ Desktop Total";
  } else {
    indicador.textContent = "🖥️ Auto";
  }
}

function mostrarToast(mensagem, tipo = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast toast-${tipo}`;
  const icones = { success: "✅", error: "❌", info: "ℹ️" };
  toast.innerHTML = `<span>${icones[tipo] || "ℹ️"}</span><div>${mensagem}</div>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Confirmação em dois cliques no próprio botão, em vez de window.confirm():
// navegadores embutidos e alguns modos de gravação descartam o diálogo nativo
// (confirm() retorna false sem exibir nada) e o reset nunca era executado.
function pedirConfirmacaoNoBotao(botao, mensagem) {
  if (botao.dataset.confirmando === "1") {
    clearTimeout(Number(botao.dataset.timer));
    botao.dataset.confirmando = "";
    botao.innerHTML = botao.dataset.textoOriginal;
    return true;
  }
  botao.dataset.confirmando = "1";
  botao.dataset.textoOriginal = botao.innerHTML;
  botao.innerHTML = mensagem;
  botao.dataset.timer = String(
    setTimeout(() => {
      botao.dataset.confirmando = "";
      botao.innerHTML = botao.dataset.textoOriginal;
    }, 4000)
  );
  return false;
}

async function resetarSistema(usarSql = false, botao = null) {
  if (botao && !pedirConfirmacaoNoBotao(botao, "⚠️ Clique de novo para confirmar")) {
    mostrarToast("Todas as sessões em andamento serão reinicializadas. Clique de novo para confirmar.", "info");
    return;
  }
  try {
    const novoEstado = await apiFetch("/api/resetar", {
      method: "POST",
      body: JSON.stringify({ usar_sql: usarSql }),
    });
    estadoApp = novoEstado;
    atualizarTodaInterface();
    mostrarToast("Sistema reinicializado com sucesso!", "success");
  } catch (err) {
    mostrarToast(`Erro ao resetar: ${err.message}`, "error");
  }
}

function irParaNovaSessao() {
  navegarPara("sessoes");
  const el = document.getElementById("card-criar-sessao");
  if (el) el.scrollIntoView({ behavior: "smooth" });
}

// ==========================================================================
// ABA 1: DASHBOARD (PAINEL GERAL)
// ==========================================================================

function renderizarDashboard() {
  if (!estadoApp) return;

  const totalSessoes = Object.keys(estadoApp.sessoes || {}).length;
  const sessoesEmVotacao = Object.values(estadoApp.sessoes || {}).filter((s) => s.estado === "EM_VOTACAO").length;
  const sessoesEncerradas = Object.values(estadoApp.sessoes || {}).filter((s) => s.estado === "ENCERRADA").length;
  const totalDiscentes = (estadoApp.ca && estadoApp.ca.discentes) ? estadoApp.ca.discentes.length : 0;
  const totalAcionistas = (estadoApp.assembleia && estadoApp.assembleia.acionistas) ? estadoApp.assembleia.acionistas.length : 0;
  const totalParlamentares = (estadoApp.congresso && estadoApp.congresso.parlamentares) ? estadoApp.congresso.parlamentares.length : 0;

  const kpisContainer = document.getElementById("dashboard-kpis");
  kpisContainer.innerHTML = `
    <div class="kpi-card">
      <div class="kpi-icon">🗳️</div>
      <div class="kpi-info">
        <h4>Sessões Cadastradas</h4>
        <div class="kpi-value">${totalSessoes}</div>
        <div class="kpi-detail">${sessoesEmVotacao} em votação | ${sessoesEncerradas} encerradas</div>
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon">🎓</div>
      <div class="kpi-info">
        <h4>Discentes CA</h4>
        <div class="kpi-value">${totalDiscentes}</div>
        <div class="kpi-detail">Colégio eleitoral estudantil</div>
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon">🏢</div>
      <div class="kpi-info">
        <h4>Acionistas S.A.</h4>
        <div class="kpi-value">${totalAcionistas}</div>
        <div class="kpi-detail">Poder proporcional por ações ON</div>
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon">🏛️</div>
      <div class="kpi-info">
        <h4>Parlamentares</h4>
        <div class="kpi-value">${totalParlamentares}</div>
        <div class="kpi-detail">Câmara e Senado Federal</div>
      </div>
    </div>
  `;

  // Lista de sessões no dashboard
  const listaSessoesEl = document.getElementById("dashboard-lista-sessoes");
  const sessoes = Object.values(estadoApp.sessoes || {});
  if (sessoes.length === 0) {
    listaSessoesEl.innerHTML = `<p class="text-muted">Nenhuma sessão de votação criada no momento.</p>`;
    return;
  }

  listaSessoesEl.innerHTML = sessoes
    .map((s) => {
      const meta = s.meta || (estadoApp.metadados_sessoes && estadoApp.metadados_sessoes[s.id_sessao]) || {};
      const statusBadge = obterBadgeEstado(s.estado);
      const totalVotos = s.total_votos || (s.votos ? s.votos.length : 0);
      return `
        <div class="card" style="margin-bottom: 0.75rem; padding: 0.85rem; background: var(--bg-subtle);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem;">
            <div>
              <span class="badge badge-subtle">${meta.contexto || "SESSÃO"}</span>
              <strong style="margin-left: 0.35rem; font-size: 0.95rem;">${meta.titulo || s.id_sessao}</strong>
              <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
                ID: <code>${s.id_sessao}</code> | Votos computados: <strong>${totalVotos}</strong>
              </div>
            </div>
            <div>${statusBadge}</div>
          </div>
          <div style="display: flex; gap: 0.4rem; margin-top: 0.65rem; justify-content: flex-end;">
            <button class="btn btn-outline btn-sm" onclick="selecionarSessao('${s.id_sessao}')">
              🗳️ Abrir Urna
            </button>
          </div>
        </div>
      `;
    })
    .join("");
}

function obterBadgeEstado(estado) {
  switch (estado) {
    case "CRIADA":
      return `<span class="badge badge-subtle">⚪ Criada</span>`;
    case "ABERTA":
      return `<span class="badge badge-info">🔵 Aberta</span>`;
    case "EM_VOTACAO":
      return `<span class="badge badge-success">🟢 Em Votação</span>`;
    case "ANULADA":
      return `<span class="badge badge-danger">⛔ Anulada</span>`;
    case "SUSPENSA":
      return `<span class="badge badge-warning">⏸️ Suspensa</span>`;
    case "EM_APURACAO":
      return `<span class="badge badge-warning">🟡 Em Apuração</span>`;
    case "ENCERRADA":
      return `<span class="badge badge-danger">🔴 Encerrada</span>`;
    default:
      return `<span class="badge badge-subtle">${estado}</span>`;
  }
}

// ==========================================================================
// ABA 2: SESSÕES DE VOTAÇÃO & URNA ELETRÔNICA
// ==========================================================================

function renderizarAbaSessoes() {
  if (!estadoApp) return;

  const sessoes = Object.values(estadoApp.sessoes || {});
  const containerLista = document.getElementById("lista-seletor-sessoes");

  if (sessoes.length === 0) {
    containerLista.innerHTML = `<p class="text-muted" style="padding: 1rem;">Nenhuma sessão criada.</p>`;
    document.getElementById("painel-detalhe-sessao").innerHTML = `
      <div class="card"><p class="text-muted">Crie uma nova sessão ao lado para iniciar a votação.</p></div>
    `;
    return;
  }

  // Se nenhuma selecionada, seleciona a primeira
  if (!sessaoSelecionadaId || !estadoApp.sessoes[sessaoSelecionadaId]) {
    sessaoSelecionadaId = sessoes[0].id_sessao;
  }

  containerLista.innerHTML = sessoes
    .map((s) => {
      const selecionada = s.id_sessao === sessaoSelecionadaId;
      const meta = s.meta || (estadoApp.metadados_sessoes && estadoApp.metadados_sessoes[s.id_sessao]) || {};
      return `
        <div class="card" style="cursor: pointer; margin-bottom: 0.5rem; padding: 0.75rem; border-color: ${
          selecionada ? "var(--primary)" : "var(--border)"
        }; background: ${selecionada ? "var(--primary-light)" : "var(--bg-card)"};"
             onclick="selecionarSessao('${s.id_sessao}')">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong style="font-size: 0.88rem;">${meta.titulo || s.id_sessao}</strong>
            ${obterBadgeEstado(s.estado)}
          </div>
          <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">
            ID: <code>${s.id_sessao}</code> | Votos: ${s.total_votos || 0}
          </div>
        </div>
      `;
    })
    .join("");

  renderizarDetalheSessao(sessaoSelecionadaId);
}

function selecionarSessao(idSessao) {
  sessaoSelecionadaId = idSessao;
  opcaoVotoSelecionada = null;
  navegarPara("sessoes");
  renderizarAbaSessoes();
}

function renderizarDetalheSessao(idSessao) {
  const sessao = estadoApp.sessoes[idSessao];
  const painel = document.getElementById("painel-detalhe-sessao");
  if (!sessao) {
    painel.innerHTML = `<div class="card"><p>Sessão não encontrada.</p></div>`;
    return;
  }

  const meta = sessao.meta || (estadoApp.metadados_sessoes && estadoApp.metadados_sessoes[idSessao]) || {};
  const contexto = meta.contexto || "CA";
  const emVotacao = sessao.estado === "EM_VOTACAO";
  const podeAbrir = sessao.estado === "CRIADA";
  const podeLiberar = sessao.estado === "ABERTA" || sessao.estado === "CRIADA";
  const podeEncerrar = sessao.estado === "EM_VOTACAO";
  const podeSuspender = sessao.estado === "EM_VOTACAO";
  // #33: só a sessão convocada pela tramitação na Casa revisora pode aprovar com emenda.
  const tramDaSessao = meta.tramitacao_materia_id && estadoApp.tramitacoes
    ? estadoApp.tramitacoes[meta.tramitacao_materia_id]
    : null;
  const aceitaEmenda = Boolean(
    tramDaSessao && tramDaSessao.aceita_emenda && tramDaSessao.sessao_convocada_id === sessao.id_sessao
  );
  const anulada = sessao.estado === "ANULADA";
  const podeAnular = !["CRIADA", "ANULADA"].includes(sessao.estado);
  const suspensa = sessao.estado === "SUSPENSA";
  // Apurar é permitido direto da votação (o servidor encerra antes) ou após o
  // encerramento da urna (EM_APURACAO). Uma sessão ENCERRADA já foi apurada.
  const podeApurar = sessao.estado === "EM_VOTACAO" || sessao.estado === "EM_APURACAO";

  // Stepper visual dos estados: EM_APURACAO deixa a etapa 4 ativa (em andamento)
  // e ENCERRADA a marca como concluída.
  const estados = ["CRIADA", "ABERTA", "EM_VOTACAO", "EM_APURACAO", "ENCERRADA"];
  // SUSPENSA é um desvio temporário da etapa de votação (#38): ocupa a etapa 3.
  const ordemAtual = suspensa ? 2 : estados.indexOf(sessao.estado);
  const rotuloEtapaVotacao = suspensa ? "Suspensa" : "Em Votação";
  const rotuloEtapaFinal = anulada
    ? "⛔ Anulada"
    : sessao.estado === "EM_APURACAO"
      ? "Em Apuração"
      : "Encerrada / Apurada";

  const stepperHtml = `
    <div class="session-stepper">
      <div class="step-item ${ordemAtual >= 0 ? (ordemAtual === 0 ? "active" : "completed") : ""}">
        <span class="step-dot">${ordemAtual > 0 ? "✓" : "1"}</span> Criada
      </div>
      <div class="step-divider"></div>
      <div class="step-item ${ordemAtual >= 1 ? (ordemAtual === 1 ? "active" : "completed") : ""}">
        <span class="step-dot">${ordemAtual > 1 ? "✓" : "2"}</span> Aberta
      </div>
      <div class="step-divider"></div>
      <div class="step-item ${ordemAtual >= 2 ? (ordemAtual === 2 ? "active" : "completed") : ""}">
        <span class="step-dot">${ordemAtual > 2 ? "✓" : suspensa ? "⏸" : "3"}</span> ${rotuloEtapaVotacao}
      </div>
      <div class="step-divider"></div>
      <div class="step-item ${ordemAtual >= 3 ? (ordemAtual === 3 ? "active" : "completed") : ""}">
        <span class="step-dot">${ordemAtual > 3 ? "✓" : "4"}</span> ${rotuloEtapaFinal}
      </div>
    </div>
  `;

  // Urna Eletrônica
  let urnaHtml = "";
  if (emVotacao) {
    urnaHtml = montarUrnaEletronicaHtml(sessao, meta, contexto);
  } else {
    urnaHtml = `
      <div class="urna-panel urna-encerrada">
        <div class="urna-title">
          <h4>🗳️ Urna Eletrônica Inativa</h4>
          ${obterBadgeEstado(sessao.estado)}
        </div>
        <p style="font-size: 0.85rem; color: var(--text-muted);">
          A urna só aceita votos quando a sessão estiver no estado <strong>EM_VOTACAO</strong>.
          ${podeLiberar ? "Clique em 'Liberar Votação' abaixo para permitir votos." : ""}
          ${sessao.estado === "EM_APURACAO" ? "Urna fechada: clique em 'Apurar Resultado' para concluir a sessão." : ""}
          ${
            anulada
              ? `Sessão anulada: <strong>${sessao.motivo_anulacao}</strong>. Os votos permanecem no log de auditoria, mas a sessão não produz resultado.`
              : ""
          }
          ${
            suspensa
              ? `Sessão suspensa: <strong>${sessao.motivo_suspensao}</strong>. Os ${sessao.total_votos} voto(s) já colhidos estão preservados; retome a sessão para continuar a votação.`
              : ""
          }
        </p>
        ${montarReciboVotoHtml(sessao.id_sessao)}
      </div>
    `;
  }

  // Apuração e Resultados (se houver apuração ou votos)
  let apuracaoHtml = "";
  if (sessao.resultado) {
    apuracaoHtml = montarResultadoApuracaoHtml(sessao);
  }

  painel.innerHTML = `
    <div class="card">
      <div class="card-header">
        <div>
          <span class="badge badge-info">${contexto}</span>
          <h3 style="margin-top: 0.35rem;">${meta.titulo || sessao.id_sessao}</h3>
          <p class="card-subtitle">Identificador Oficial: <code>${sessao.id_sessao}</code></p>
        </div>
        <div>${obterBadgeEstado(sessao.estado)}</div>
      </div>

      ${stepperHtml}

      <!-- Barra de Controle de Ciclo de Vida -->
      <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1.25rem;">
        ${podeAbrir ? `<button class="btn btn-secondary btn-sm" onclick="acaoSessao('${sessao.id_sessao}', 'abrir')">▶️ Abrir Sessão</button>` : ""}
        ${podeLiberar ? `<button class="btn btn-primary btn-sm" onclick="acaoSessao('${sessao.id_sessao}', 'liberar')">🔓 Liberar Votação</button>` : ""}
        ${podeEncerrar ? `<button class="btn btn-danger btn-sm" onclick="acaoSessao('${sessao.id_sessao}', 'encerrar')">⏹️ Encerrar Votação</button>` : ""}
        ${suspensa ? `<button class="btn btn-primary btn-sm" onclick="acaoSessao('${sessao.id_sessao}', 'retomar')">▶️ Retomar Sessão</button>` : ""}
        ${podeApurar && aceitaEmenda ? `<label style="display: flex; align-items: center; gap: 0.35rem; font-size: 0.8rem;"><input type="checkbox" id="apurar-com-emenda" /> Aprovação com emendas (Casa revisora)</label>` : ""}
        ${podeApurar ? `<button class="btn btn-success btn-sm" onclick="apurarSessao('${sessao.id_sessao}')">📊 Apurar Resultado</button>` : ""}
      </div>
      ${
        podeSuspender
          ? `
        <form onsubmit="submeterSuspensao(event, '${sessao.id_sessao}')" style="display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: flex-end; margin-bottom: 1.25rem;">
          <div style="flex: 3; min-width: 200px;">
            <label for="motivo-suspensao" style="font-size: 0.72rem;">Motivo da suspensão</label>
            <input type="text" id="motivo-suspensao" placeholder="Ex.: queda de quórum, questão de ordem" />
          </div>
          <button type="submit" class="btn btn-secondary btn-sm" style="flex: 1; min-width: 140px;">⏸️ Suspender Sessão</button>
        </form>
      `
          : ""
      }

      ${montarAnulacaoHtml(sessao, podeAnular)}
      ${montarPainelPresencaHtml(sessao, meta)}
      ${urnaHtml}
      ${apuracaoHtml}
    </div>
  `;

  // Preenche dinamicamente o select de eleitores da urna
  if (emVotacao) {
    preencherEleitoresUrna(contexto, sessao);
  }
}

// #37: quórum de instalação aferido na abertura. A presença é registrada à parte do
// voto, e a votação só é liberada com a maioria absoluta da Casa presente (CF, art. 47).
function montarPainelPresencaHtml(sessao, meta) {
  if (sessao.quorum_instalacao === null || sessao.quorum_instalacao === undefined) return "";
  const aceitaPresenca = ["CRIADA", "ABERTA", "EM_VOTACAO", "SUSPENSA"].includes(sessao.estado);
  const atingido = sessao.total_presentes >= sessao.quorum_instalacao;
  const perc = Math.min(100, (sessao.total_presentes / sessao.quorum_instalacao) * 100).toFixed(1);
  const casa = meta.casa || null;
  const parls = ((estadoApp.congresso && estadoApp.congresso.parlamentares) || []).filter(
    (p) => (!casa || p.casa === casa) && p.apto_votar
  );

  return `
    <div class="urna-panel" style="margin-bottom: 1.25rem;">
      <div class="urna-title">
        <h4>🙋 Quórum de Instalação (Presença)</h4>
        <span class="badge ${atingido ? "badge-success" : "badge-warning"}">
          ${atingido ? "Quórum atingido" : "Quórum não atingido"}
        </span>
      </div>
      <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.5rem;">
        A votação só é liberada com a maioria absoluta da Casa presente (CF, art. 47).
        Presença e voto são registros distintos: um presente pode não votar.
      </p>
      <div class="chart-row">
        <div class="chart-row-label">
          <span>Presentes: <strong>${sessao.total_presentes}</strong> de ${sessao.total_aptos}</span>
          <span>Mínimo exigido: <strong>${sessao.quorum_instalacao}</strong></span>
        </div>
        <div class="chart-bar-bg"><div class="chart-bar-fill ${atingido ? "fill-green" : "fill-red"}" style="width: ${perc}%;"></div></div>
      </div>
      ${
        aceitaPresenca
          ? `
        <form onsubmit="submeterPresenca(event, '${sessao.id_sessao}')" style="display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: flex-end; margin-top: 0.75rem;">
          <div style="flex: 2; min-width: 180px;">
            <label for="presenca-parlamentar" style="font-size: 0.72rem;">Parlamentar cadastrado</label>
            <select id="presenca-parlamentar">
              <option value="">— nenhum —</option>
              ${parls.map((p) => `<option value="${p.id}">${p.id} — ${p.nome}</option>`).join("")}
            </select>
          </div>
          <div style="flex: 1; min-width: 110px;">
            <label for="presenca-bancada" style="font-size: 0.72rem;">Bancada (quantidade)</label>
            <input type="number" id="presenca-bancada" min="0" max="${sessao.total_aptos}" value="${atingido ? 0 : sessao.quorum_instalacao}" />
          </div>
          <button type="submit" class="btn btn-secondary btn-sm" style="flex: 1 0 100%;">Registrar Presença</button>
        </form>
      `
          : ""
      }
    </div>
  `;
}

function montarAnulacaoHtml(sessao, podeAnular) {
  if (!podeAnular) return "";
  return `
    <details style="margin-bottom: 1.25rem;">
      <summary style="cursor: pointer; font-size: 0.85rem; color: var(--danger);">⛔ Anular sessão viciada</summary>
      <form onsubmit="submeterAnulacao(event, '${sessao.id_sessao}')" style="display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: flex-end; margin-top: 0.5rem;">
        <div style="flex: 3; min-width: 200px;">
          <label for="motivo-anulacao" style="font-size: 0.72rem;">Motivo da anulação (vício apurado)</label>
          <input type="text" id="motivo-anulacao" placeholder="Ex.: eleitor inapto votou, falha no credenciamento" />
        </div>
        <button type="submit" class="btn btn-danger btn-sm" style="flex: 1; min-width: 140px;">Anular Sessão</button>
      </form>
    </details>
  `;
}

async function submeterAnulacao(event, idSessao) {
  event.preventDefault();
  const motivo = document.getElementById("motivo-anulacao").value;
  try {
    await apiFetch(`/api/sessoes/${encodeURIComponent(idSessao)}/anular`, {
      method: "POST",
      body: JSON.stringify({ motivo }),
    });
    mostrarToast("Sessão anulada. O motivo ficou registrado no log de auditoria.", "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao anular: ${err.message}`, "error");
  }
}

async function submeterSuspensao(event, idSessao) {
  event.preventDefault();
  const motivo = document.getElementById("motivo-suspensao").value;
  try {
    await apiFetch(`/api/sessoes/${encodeURIComponent(idSessao)}/suspender`, {
      method: "POST",
      body: JSON.stringify({ motivo }),
    });
    mostrarToast("Sessão suspensa. Os votos já colhidos estão preservados.", "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao suspender: ${err.message}`, "error");
  }
}

async function submeterPresenca(event, idSessao) {
  event.preventDefault();
  const parlamentar = document.getElementById("presenca-parlamentar").value;
  const bancada = parseInt(document.getElementById("presenca-bancada").value || "0", 10);
  const payload = { parlamentares: parlamentar ? [parlamentar] : [], bancada };
  try {
    const res = await apiFetch(`/api/sessoes/${encodeURIComponent(idSessao)}/presenca`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    mostrarToast(`Presença registrada: ${res.total_presentes} presentes.`, "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao registrar presença: ${err.message}`, "error");
  }
}

function montarUrnaEletronicaHtml(sessao, meta, contexto) {
  let opcoes = (sessao.opcoes_sugeridas && sessao.opcoes_sugeridas.length > 0)
    ? sessao.opcoes_sugeridas
    : ["SIM", "NAO", "ABSTENCAO", "BRANCO"];

  const botoesOpcoes = opcoes
    .map(
      (op) => `
      <button type="button" class="btn-opcao-voto ${opcaoVotoSelecionada === op ? "selected" : ""}"
              onclick="selecionarOpcaoVoto('${op}')">
        <span>${op}</span>
      </button>
    `
    )
    .join("");

  return `
    <div class="urna-panel">
      <div class="urna-title">
        <h4>🗳️ Cabine de Votação (Urna Eletrônica)</h4>
        <span class="badge badge-success">Cabine Liberada</span>
      </div>

      <form id="form-voto-urna" onsubmit="submeterVotoUrna(event, '${sessao.id_sessao}')" class="form-stack">
        <div class="form-row">
          <div class="form-group">
            <label for="urna-eleitor-id">Identificação do Eleitor / Votante</label>
            <select id="urna-eleitor-id" required onchange="aoTrocarEleitorUrna(this.value)"></select>
          </div>
          ${
            contexto === "ASSEMBLEIA"
              ? `
            <div class="form-group">
              <label for="urna-modo-assembleia">Modo de Voto Societário</label>
              <select id="urna-modo-assembleia" onchange="aoTrocarModoAssembleia()">
                <option value="DIRETO">Voto Direto (Acionista Titular)</option>
                <option value="PROCURACAO">Por Procuração (Outorgante)</option>
                <option value="CONSOLIDADO_PROCURADOR">Poder Consolidado do Procurador</option>
              </select>
            </div>
          `
              : ""
          }
        </div>

        <div id="urna-procurador-container" class="form-group" style="display: none;">
          <label for="urna-procurador-id">Procurador Representante</label>
          <select id="urna-procurador-id"></select>
        </div>

        <div class="form-group">
          <label>Selecione sua Escolha / Voto:</label>
          <div class="opcoes-voto-grid">${botoesOpcoes}</div>
          <input type="hidden" id="urna-opcao-voto" value="${opcaoVotoSelecionada || ""}" required />
        </div>

        <button type="submit" class="btn btn-primary btn-lg btn-block">
          Confirmar e Gravar Voto Criptografado
        </button>
      </form>

      ${montarReciboVotoHtml(sessao.id_sessao)}

      ${
        contexto === "CONGRESSO"
          ? `
        <hr class="divider" />
        <div style="background: var(--bg-card); padding: 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border);">
          <h5>⚡ Simulação de Plenário em Lote (Bancada)</h5>
          <p style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.5rem;">
            Teste quóruns regimentais rapidamente injetando votos parlamentares em bloco:
          </p>
          <form onsubmit="submeterSimulacaoPlenario(event, '${sessao.id_sessao}')" style="display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: flex-end;">
            <div style="flex: 1; min-width: 70px;">
              <label style="font-size: 0.72rem;">SIM</label>
              <input type="number" id="sim-votos-sim" value="257" min="0" style="padding: 0.3rem;" />
            </div>
            <div style="flex: 1; min-width: 70px;">
              <label style="font-size: 0.72rem;">NÃO</label>
              <input type="number" id="sim-votos-nao" value="50" min="0" style="padding: 0.3rem;" />
            </div>
            <div style="flex: 1; min-width: 70px;">
              <label style="font-size: 0.72rem;">ABST</label>
              <input type="number" id="sim-votos-abst" value="10" min="0" style="padding: 0.3rem;" />
            </div>
            <div style="flex: 1; min-width: 70px;">
              <label style="font-size: 0.72rem;">BRANCO</label>
              <input type="number" id="sim-votos-branco" value="5" min="0" style="padding: 0.3rem;" />
            </div>
            <button type="submit" class="btn btn-secondary btn-sm" style="flex: 1 0 100%;">Lançar Bancada</button>
          </form>
        </div>
      `
          : ""
      }
    </div>
  `;
}

function preencherEleitoresUrna(contexto, sessao) {
  const select = document.getElementById("urna-eleitor-id");
  if (!select || !estadoApp) return;

  const meta = sessao ? (sessao.meta || (estadoApp.metadados_sessoes && estadoApp.metadados_sessoes[sessao.id_sessao]) || {}) : {};

  let opcoes = [];
  if (contexto === "CA") {
    opcoes = (estadoApp.ca && estadoApp.ca.discentes)
      ? estadoApp.ca.discentes.map((d) => ({
          id: d.ra,
          nome: `${d.ra} — ${d.nome} ${d.apto_votar ? "✅" : "❌ (Inapto)"}`,
        }))
      : [];
  } else if (contexto === "ASSEMBLEIA") {
    opcoes = (estadoApp.assembleia && estadoApp.assembleia.acionistas)
      ? estadoApp.assembleia.acionistas.map((a) => ({
          id: a.id,
          nome: `${a.id} — ${a.nome} (${a.acoes_on} ON) ${a.apto_votar ? "✅" : "❌"}`,
        }))
      : [];
  } else if (contexto === "CONGRESSO") {
    const casaSessao = meta.casa || null;
    let parls = (estadoApp.congresso && estadoApp.congresso.parlamentares) ? estadoApp.congresso.parlamentares : [];
    if (casaSessao) {
      parls = parls.filter((p) => p.casa === casaSessao);
    }
    opcoes = parls.map((p) => ({
      id: p.id,
      nome: `${p.id} — ${p.nome} (${p.casa} / ${p.partido}) ${p.apto_votar ? "✅" : "❌"}`,
    }));
  }

  select.innerHTML = opcoes.map((o) => `<option value="${o.id}">${o.nome}</option>`).join("");
  if (eleitorUrnaSelecionado && opcoes.some((o) => o.id === eleitorUrnaSelecionado)) {
    select.value = eleitorUrnaSelecionado;
  }
}

function montarReciboVotoHtml(idSessao) {
  if (!ultimoReciboVoto || ultimoReciboVoto.idSessao !== idSessao) return "";
  return `
    <div id="resultado-voto-protocolo" class="protocolo-box">
      <strong>🔐 Protocolo Criptográfico de Voto (SHA-256):</strong><br />
      <code>${ultimoReciboVoto.protocolo}</code><br />
      <small style="color: #94a3b8;">Guarde este hash para verificar a integridade do seu voto na aba de Auditoria.</small>
    </div>
  `;
}

function selecionarOpcaoVoto(opcao) {
  opcaoVotoSelecionada = opcao;
  const input = document.getElementById("urna-opcao-voto");
  if (input) input.value = opcao;

  document.querySelectorAll(".btn-opcao-voto").forEach((b) => {
    b.classList.toggle("selected", b.textContent.trim() === opcao);
  });
}

function aoTrocarModoAssembleia() {
  const modo = document.getElementById("urna-modo-assembleia").value;
  const containerProc = document.getElementById("urna-procurador-container");
  const selectProc = document.getElementById("urna-procurador-id");

  if (modo === "PROCURACAO") {
    containerProc.style.display = "block";
    const procs = (estadoApp.assembleia && estadoApp.assembleia.procuradores) ? estadoApp.assembleia.procuradores : [];
    selectProc.innerHTML = procs.map((p) => `<option value="${p.id}">${p.id} — ${p.nome}</option>`).join("");
  } else if (modo === "CONSOLIDADO_PROCURADOR") {
    containerProc.style.display = "none";
    // Altera o seletor principal de eleitores para os procuradores
    const selectEleitor = document.getElementById("urna-eleitor-id");
    const procs = (estadoApp.assembleia && estadoApp.assembleia.procuradores) ? estadoApp.assembleia.procuradores : [];
    selectEleitor.innerHTML = procs.map((p) => `<option value="${p.id}">${p.id} — ${p.nome} (Total: ${p.peso_total} ações)</option>`).join("");
  } else {
    containerProc.style.display = "none";
    preencherEleitoresUrna("ASSEMBLEIA", estadoApp.sessoes[sessaoSelecionadaId]);
  }
}

function aoTrocarEleitorUrna(eleitorId) {
  eleitorUrnaSelecionado = eleitorId;
}

async function submeterVotoUrna(event, idSessao) {
  event.preventDefault();
  const eleitorId = document.getElementById("urna-eleitor-id").value;
  const opcao = document.getElementById("urna-opcao-voto").value;

  if (!opcao) {
    mostrarToast("Selecione uma opção de voto!", "error");
    return;
  }

  const payload = {
    eleitor_id: eleitorId,
    opcao: opcao,
  };

  const modoEl = document.getElementById("urna-modo-assembleia");
  if (modoEl) {
    payload.modo = modoEl.value;
    if (payload.modo === "PROCURACAO") {
      payload.procurador_id = document.getElementById("urna-procurador-id").value;
    }
  }

  try {
    const res = await apiFetch(`/api/sessoes/${idSessao}/votar`, {
      method: "POST",
      body: JSON.stringify(payload),
    });

    mostrarToast(`Voto registrado com sucesso!`, "success");
    // Guarda o recibo antes de redesenhar: o painel da urna é recriado por
    // carregarEstadoCompleto() e o exibe a partir deste estado.
    ultimoReciboVoto = { idSessao, protocolo: res.protocolo };
    eleitorUrnaSelecionado = eleitorId;

    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao votar: ${err.message}`, "error");
  }
}

async function submeterSimulacaoPlenario(event, idSessao) {
  event.preventDefault();
  const sim = parseInt(document.getElementById("sim-votos-sim").value, 10) || 0;
  const nao = parseInt(document.getElementById("sim-votos-nao").value, 10) || 0;
  const abst = parseInt(document.getElementById("sim-votos-abst").value, 10) || 0;
  const branco = parseInt(document.getElementById("sim-votos-branco").value, 10) || 0;

  try {
    const res = await apiFetch(`/api/sessoes/${idSessao}/simular-plenario`, {
      method: "POST",
      body: JSON.stringify({
        votos_sim: sim,
        votos_nao: nao,
        votos_abstencao: abst,
        votos_branco: branco,
      }),
    });
    mostrarToast(`${res.votos_adicionados} votos de plenário computados com sucesso!`, "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro na simulação de bancada: ${err.message}`, "error");
  }
}

async function apurarSessao(idSessao) {
  const marcador = document.getElementById("apurar-com-emenda");
  const comEmenda = Boolean(marcador && marcador.checked);
  try {
    const res = await apiFetch(`/api/sessoes/${encodeURIComponent(idSessao)}/apurar`, {
      method: "POST",
      body: JSON.stringify({ com_emenda: comEmenda }),
    });
    const aviso = comEmenda && res.resultado && res.resultado.status === "APROVADO"
      ? " Aprovada com emendas: a matéria volta à Casa iniciadora."
      : "";
    mostrarToast(`Sessão apurada.${aviso}`, "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao apurar: ${err.message}`, "error");
  }
}

async function acaoSessao(idSessao, acao) {
  try {
    await apiFetch(`/api/sessoes/${idSessao}/${acao}`, { method: "POST" });
    mostrarToast(`Ação '${acao}' executada com sucesso!`, "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro: ${err.message}`, "error");
  }
}

function montarResultadoApuracaoHtml(sessao) {
  const r = sessao.resultado;
  if (!r) return "";

  const total = r.total_votos || 1;
  const contagem = r.contagem || {};
  const barrasHtml = Object.entries(contagem)
    .map(([opcao, votos]) => {
      const perc = ((votos / total) * 100).toFixed(1);
      let corClass = "fill-gray";
      if (opcao === "SIM") corClass = "fill-green";
      else if (opcao === "NAO") corClass = "fill-red";
      else if (opcao.startsWith("CHAPA") || opcao.startsWith("CAND")) corClass = "fill-green";

      return `
        <div class="chart-row">
          <div class="chart-row-label">
            <span>${opcao}</span>
            <span>${votos} ${votos === 1 ? "voto" : "votos"} (${perc}%)</span>
          </div>
          <div class="chart-bar-bg">
            <div class="chart-bar-fill ${corClass}" style="width: ${perc}%;"></div>
          </div>
        </div>
      `;
    })
    .join("");

  const statusBadge =
    r.status === "APROVADO" || r.status === "ELEITO"
      ? `<span class="badge badge-success">${r.status}</span>`
      : r.status === "REJEITADO"
      ? `<span class="badge badge-danger">${r.status}</span>`
      : `<span class="badge badge-warning">${r.status}</span>`;

  return `
    <div style="margin-top: 1.5rem; padding: 1.25rem; background: var(--bg-card); border: 2px solid var(--border-strong); border-radius: var(--radius-md);">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
        <h4>📊 Resultado Oficial da Apuração</h4>
        ${statusBadge}
      </div>
      <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.75rem;">
        Quórum atingido: <strong>${r.quorum_atingido ? "SIM ✅" : "NÃO ❌"}</strong> | Total computado: <strong>${r.total_votos}</strong>
        ${r.vencedor ? ` | Vencedor: <strong>${r.vencedor}</strong>` : ""}
      </div>
      <div class="apuracao-chart">${barrasHtml}</div>
    </div>
  `;
}

function alternarCamposNovaSessao() {
  const ctx = document.getElementById("nova-sessao-contexto").value;
  document.getElementById("campos-sessao-ca").style.display = ctx === "CA" ? "block" : "none";
  document.getElementById("campos-sessao-assembleia").style.display = ctx === "ASSEMBLEIA" ? "block" : "none";
  document.getElementById("campos-sessao-congresso").style.display = ctx === "CONGRESSO" ? "block" : "none";
}

async function submeterCriarSessao(event) {
  event.preventDefault();
  const idSessao = document.getElementById("nova-sessao-id").value;
  const ctx = document.getElementById("nova-sessao-contexto").value;
  const titulo = document.getElementById("nova-sessao-titulo").value;
  const abrir = document.getElementById("nova-sessao-abrir").checked;
  const liberar = document.getElementById("nova-sessao-liberar").checked;

  const payload = {
    id_sessao: idSessao,
    contexto: ctx,
    titulo: titulo,
    abrir_imediatamente: abrir,
    liberar_imediatamente: liberar,
  };

  if (ctx === "CA") {
    payload.quorum_minimo_votantes = parseInt(document.getElementById("ca-quorum-min").value, 10);
    payload.percentual_quorum_minimo = parseFloat(document.getElementById("ca-quorum-perc").value);
  } else if (ctx === "ASSEMBLEIA") {
    payload.tipo_decisao = document.getElementById("ass-tipo-decisao").value;
    payload.percentual_quorum_instalacao = parseFloat(document.getElementById("ass-quorum-inst").value);
    payload.base_calculo_sobre_total_capital = document.getElementById("ass-base-capital-total").checked;
  } else if (ctx === "CONGRESSO") {
    payload.casa = document.getElementById("cong-casa").value;
    payload.materia = document.getElementById("cong-materia").value;
  }

  try {
    const criada = await apiFetch("/api/sessoes", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    mostrarToast(`Sessão '${criada.id_sessao}' criada com sucesso!`, "success");
    if (criada.aviso) mostrarToast(criada.aviso, "info");
    sessaoSelecionadaId = criada.id_sessao;
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao criar sessão: ${err.message}`, "error");
  }
}

// ==========================================================================
// CONSULTA RÁPIDA DE APTIDÃO (DASHBOARD)
// ==========================================================================

function atualizarOpcoesConsultaAptidao() {
  if (!estadoApp) return;
  const ctx = document.getElementById("apt-contexto").value;
  const grupoCasa = document.getElementById("grupo-apt-casa");
  const grupoProc = document.getElementById("grupo-apt-procurador");
  const selectEleitor = document.getElementById("apt-eleitor");
  const selectProc = document.getElementById("apt-procurador");

  grupoCasa.style.display = ctx === "CONGRESSO" ? "block" : "none";
  grupoProc.style.display = ctx === "ASSEMBLEIA" ? "block" : "none";

  let opcoes = [];
  if (ctx === "CA") {
    opcoes = (estadoApp.ca && estadoApp.ca.discentes)
      ? estadoApp.ca.discentes.map((d) => ({ id: d.ra, label: `${d.ra} — ${d.nome}` }))
      : [];
  } else if (ctx === "ASSEMBLEIA") {
    opcoes = (estadoApp.assembleia && estadoApp.assembleia.acionistas)
      ? estadoApp.assembleia.acionistas.map((a) => ({ id: a.id, label: `${a.id} — ${a.nome}` }))
      : [];
    const procs = (estadoApp.assembleia && estadoApp.assembleia.procuradores) ? estadoApp.assembleia.procuradores : [];
    selectProc.innerHTML =
      `<option value="">— Voto Direto (Sem Procurador) —</option>` +
      procs.map((p) => `<option value="${p.id}">${p.id} — ${p.nome}</option>`).join("");
  } else if (ctx === "CONGRESSO") {
    const casa = document.getElementById("apt-casa").value;
    const parls = (estadoApp.congresso && estadoApp.congresso.parlamentares) ? estadoApp.congresso.parlamentares : [];
    opcoes = parls
      .filter((p) => p.casa === casa)
      .map((p) => ({ id: p.id, label: `${p.id} — ${p.nome} (${p.partido})` }));
  }

  selectEleitor.innerHTML = opcoes.map((o) => `<option value="${o.id}">${o.label}</option>`).join("");
}

async function submeterConsultaAptidao(event) {
  event.preventDefault();
  const ctx = document.getElementById("apt-contexto").value;
  const eleitorId = document.getElementById("apt-eleitor").value;
  const procId = document.getElementById("apt-procurador").value || null;
  const casa = ctx === "CONGRESSO" ? document.getElementById("apt-casa").value : null;

  try {
    const res = await apiFetch("/api/aptidao", {
      method: "POST",
      body: JSON.stringify({
        contexto: ctx,
        eleitor_id: eleitorId,
        procurador_id: procId,
        casa: casa,
      }),
    });

    const box = document.getElementById("resultado-consulta-aptidao");
    box.style.display = "block";
    box.className = `aptidao-result-box ${res.apto ? "badge-success" : "badge-danger"}`;
    box.style.padding = "0.85rem";
    box.style.borderRadius = "var(--radius-md)";
    box.style.marginTop = "0.75rem";
    box.innerHTML = `
      <div style="font-weight: 700; font-size: 0.95rem;">
        ${res.apto ? "✅ ELEITOR APTO A VOTAR" : "❌ ELEITOR INAPTO"}
      </div>
      <div style="font-size: 0.82rem; margin-top: 0.35rem;">
        Peso do Voto: <strong>${res.peso_voto}</strong>
        ${res.motivo_inaptidao ? `<br />Motivo: <em>${res.motivo_inaptidao}</em>` : ""}
      </div>
    `;
  } catch (err) {
    mostrarToast(`Erro ao consultar aptidão: ${err.message}`, "error");
  }
}

// ==========================================================================
// ABA 3: CENTRO ACADÊMICO (CA)
// ==========================================================================

function renderizarAbaCA() {
  if (!estadoApp || !estadoApp.ca) return;

  // Atualiza selects de presidente/vice da chapa
  const discentes = estadoApp.ca.discentes || [];
  const chapas = estadoApp.ca.chapas || [];

  const selectPres = document.getElementById("ca-chapa-pres");
  const selectVice = document.getElementById("ca-chapa-vice");
  if (selectPres && selectVice) {
    const optionsHtml = discentes
      .map((d) => `<option value="${d.ra}">${d.ra} — ${d.nome}</option>`)
      .join("");
    selectPres.innerHTML = optionsHtml;
    selectVice.innerHTML = optionsHtml;
  }

  // Tabela Chapas
  const tabChapas = document.getElementById("tabela-ca-chapas");
  if (tabChapas) {
    tabChapas.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Nome</th>
            <th>Presidente</th>
            <th>Vice</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${chapas
            .map(
              (c) => `
            <tr>
              <td><code>${c.id}</code></td>
              <td><strong>${c.nome}</strong></td>
              <td>${c.presidente_ra}</td>
              <td>${c.vice_ra}</td>
              <td>${
                c.elegivel
                  ? `<span class="badge badge-success">Homologada</span>`
                  : `<span class="badge badge-danger" title="${c.motivo_inelegibilidade || ""}">Inelegível</span>`
              }</td>
            </tr>
          `
            )
            .join("")}
        </tbody>
      </table>
    `;
  }

  // Tabela Discentes
  const tabDisc = document.getElementById("tabela-ca-discentes");
  if (tabDisc) {
    tabDisc.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>RA</th>
            <th>Nome</th>
            <th>Curso</th>
            <th>Sem.</th>
            <th>Aptidão</th>
          </tr>
        </thead>
        <tbody>
          ${discentes
            .map(
              (d) => `
            <tr>
              <td><code>${d.ra}</code></td>
              <td>${d.nome}</td>
              <td>${d.curso}</td>
              <td>${d.semestre}º</td>
              <td>${
                d.apto_votar
                  ? `<span class="badge badge-success">Apto (1 voto)</span>`
                  : `<span class="badge badge-danger">${d.motivo_inaptidao || "Inapto"}</span>`
              }</td>
            </tr>
          `
            )
            .join("")}
        </tbody>
      </table>
    `;
  }
}

async function submeterCadastroDiscente(event) {
  event.preventDefault();
  const payload = {
    ra: document.getElementById("ca-disc-ra").value,
    nome: document.getElementById("ca-disc-nome").value,
    curso: document.getElementById("ca-disc-curso").value,
    semestre: parseInt(document.getElementById("ca-disc-semestre").value, 10),
    matricula_ativa: document.getElementById("ca-disc-ativa").checked,
    situacao_regular: document.getElementById("ca-disc-regular").checked,
    suspenso: document.getElementById("ca-disc-suspenso").checked,
    formado: document.getElementById("ca-disc-formado").checked,
  };

  try {
    await apiFetch("/api/ca/discentes", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    mostrarToast("Discente cadastrado com sucesso!", "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao cadastrar discente: ${err.message}`, "error");
  }
}

async function submeterCadastroChapa(event) {
  event.preventDefault();
  const payload = {
    id: document.getElementById("ca-chapa-id").value,
    nome: document.getElementById("ca-chapa-nome").value,
    proposta: document.getElementById("ca-chapa-proposta").value,
    presidente_ra: document.getElementById("ca-chapa-pres").value,
    vice_ra: document.getElementById("ca-chapa-vice").value,
    regular: document.getElementById("ca-chapa-regular").checked,
  };

  try {
    await apiFetch("/api/ca/chapas", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    mostrarToast("Chapa registrada com sucesso!", "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao registrar chapa: ${err.message}`, "error");
  }
}

// ==========================================================================
// ABA 4: ASSEMBLEIA DE ACIONISTAS E PROCURAÇÕES
// ==========================================================================

function renderizarAbaAssembleia() {
  if (!estadoApp || !estadoApp.assembleia) return;

  const acionistas = estadoApp.assembleia.acionistas || [];
  const procuradores = estadoApp.assembleia.procuradores || [];
  const procuracoes = estadoApp.assembleia.procuracoes || [];
  const candidatos = estadoApp.assembleia.candidatos || [];

  // Preenche selects de outorga de procuração
  const selectOutorgante = document.getElementById("ass-proc-outorgante");
  const selectProcurador = document.getElementById("ass-proc-procurador");
  if (selectOutorgante && selectProcurador) {
    selectOutorgante.innerHTML = acionistas
      .map((a) => `<option value="${a.id}">${a.id} — ${a.nome} (${a.acoes_on} ON)</option>`)
      .join("");
    selectProcurador.innerHTML = procuradores
      .map((p) => `<option value="${p.id}">${p.id} — ${p.nome}</option>`)
      .join("");
  }

  // Tabela Procurações
  const tabProc = document.getElementById("tabela-ass-procuracoes");
  if (tabProc) {
    tabProc.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Outorgante</th>
            <th>Procurador</th>
            <th>Status</th>
            <th>Ação</th>
          </tr>
        </thead>
        <tbody>
          ${procuracoes
            .map(
              (p) => `
            <tr>
              <td><code>${p.outorgante_id}</code></td>
              <td><code>${p.procurador_id}</code></td>
              <td>${
                p.ativa && p.vigente
                  ? `<span class="badge badge-success">Vigente</span>`
                  : `<span class="badge badge-danger">Revogada / Expirada</span>`
              }</td>
              <td>
                ${
                  p.ativa
                    ? `<button class="btn btn-outline btn-sm" onclick="revogarProcuracao('${p.outorgante_id}', '${p.procurador_id}')">Revogar</button>`
                    : "—"
                }
              </td>
            </tr>
          `
            )
            .join("")}
        </tbody>
      </table>
    `;
  }

  // Tabela Procuradores Consolidado
  const tabProcs = document.getElementById("tabela-ass-procuradores");
  if (tabProcs) {
    tabProcs.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Nome</th>
            <th>Próprio</th>
            <th>Delegado</th>
            <th>Total de Votos</th>
          </tr>
        </thead>
        <tbody>
          ${procuradores
            .map(
              (p) => `
            <tr>
              <td><code>${p.id}</code></td>
              <td><strong>${p.nome}</strong></td>
              <td>${p.peso_proprio}</td>
              <td>${p.peso_delegado}</td>
              <td><strong style="color: var(--primary);">${p.peso_total}</strong></td>
            </tr>
          `
            )
            .join("")}
        </tbody>
      </table>
    `;
  }

  // Tabela Acionistas
  const tabAcionistas = document.getElementById("tabela-ass-acionistas");
  if (tabAcionistas) {
    tabAcionistas.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Nome</th>
            <th>Ações ON</th>
            <th>Ações PN</th>
            <th>Aptidão</th>
          </tr>
        </thead>
        <tbody>
          ${acionistas
            .map(
              (a) => `
            <tr>
              <td><code>${a.id}</code></td>
              <td>${a.nome}</td>
              <td><strong>${a.acoes_on}</strong></td>
              <td>${a.acoes_pn}</td>
              <td>${
                a.apto_votar
                  ? `<span class="badge badge-success">${a.peso_voto} votos</span>`
                  : `<span class="badge badge-danger">${a.motivo_inaptidao || "Inapto"}</span>`
              }</td>
            </tr>
          `
            )
            .join("")}
        </tbody>
      </table>
    `;
  }

  // Tabela Candidatos Conselho
  const tabCands = document.getElementById("tabela-ass-candidatos");
  if (tabCands) {
    tabCands.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Nome</th>
            <th>Elegibilidade</th>
          </tr>
        </thead>
        <tbody>
          ${candidatos
            .map(
              (c) => `
            <tr>
              <td><code>${c.id}</code></td>
              <td>${c.nome}</td>
              <td>${
                c.elegivel
                  ? `<span class="badge badge-success">Elegível</span>`
                  : `<span class="badge badge-danger">${c.motivo_inelegibilidade || "Inelegível"}</span>`
              }</td>
            </tr>
          `
            )
            .join("")}
        </tbody>
      </table>
    `;
  }
}

async function submeterCadastroAcionista(event) {
  event.preventDefault();
  const payload = {
    id: document.getElementById("ass-ac-id").value,
    nome: document.getElementById("ass-ac-nome").value,
    acoes_on: parseInt(document.getElementById("ass-ac-on").value, 10),
    acoes_pn: parseInt(document.getElementById("ass-ac-pn").value, 10),
    pn_com_voto: document.getElementById("ass-ac-pn-voto").checked,
    adimplente: document.getElementById("ass-ac-adimplente").checked,
    impedido: document.getElementById("ass-ac-impedido").checked,
    ativo: document.getElementById("ass-ac-ativo").checked,
  };

  try {
    await apiFetch("/api/assembleia/acionistas", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    mostrarToast("Acionista cadastrado com sucesso!", "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao cadastrar acionista: ${err.message}`, "error");
  }
}

async function submeterCadastroProcurador(event) {
  event.preventDefault();
  const payload = {
    id: document.getElementById("ass-pr-id").value,
    nome: document.getElementById("ass-pr-nome").value,
    credenciado: document.getElementById("ass-pr-cred").checked,
  };

  try {
    await apiFetch("/api/assembleia/procuradores", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    mostrarToast("Procurador cadastrado com sucesso!", "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao cadastrar procurador: ${err.message}`, "error");
  }
}

async function submeterCadastroProcuracao(event) {
  event.preventDefault();
  const payload = {
    outorgante_id: document.getElementById("ass-proc-outorgante").value,
    procurador_id: document.getElementById("ass-proc-procurador").value,
    validade_dias: parseInt(document.getElementById("ass-proc-dias").value, 10),
  };

  try {
    await apiFetch("/api/assembleia/procuracoes", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    mostrarToast("Procuração outorgada com sucesso!", "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao outorgar procuração: ${err.message}`, "error");
  }
}

async function revogarProcuracao(outorganteId, procuradorId) {
  try {
    await apiFetch("/api/assembleia/procuracoes/revogar", {
      method: "POST",
      body: JSON.stringify({ outorgante_id: outorganteId, procurador_id: procuradorId }),
    });
    mostrarToast("Procuração revogada com sucesso!", "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao revogar procuração: ${err.message}`, "error");
  }
}

async function submeterCadastroCandidatoConselho(event) {
  event.preventDefault();
  const payload = {
    id: document.getElementById("ass-cand-id").value,
    nome: document.getElementById("ass-cand-nome").value,
    conflito_interesse: document.getElementById("ass-cand-conflito").checked,
  };

  try {
    await apiFetch("/api/assembleia/candidatos", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    mostrarToast("Candidato ao conselho cadastrado com sucesso!", "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao cadastrar candidato: ${err.message}`, "error");
  }
}

// ==========================================================================
// ABA 5: CONGRESSO NACIONAL & TRAMITAÇÃO BICAMERAL
// ==========================================================================

function renderizarAbaCongresso() {
  if (!estadoApp || !estadoApp.congresso) return;

  const materias = estadoApp.congresso.materias || [];
  const parlamentares = estadoApp.congresso.parlamentares || [];
  const tramitacoes = estadoApp.tramitacoes || {};

  // Atualiza autores no select de matéria
  const selectAutor = document.getElementById("cong-mat-autor");
  if (selectAutor) {
    selectAutor.innerHTML = parlamentares
      .map((p) => `<option value="${p.id}">${p.id} — ${p.nome} (${p.casa})</option>`)
      .join("");
  }

  // Cards de Tramitação Bicameral
  const containerTram = document.getElementById("lista-tramitacoes-congresso");
  if (containerTram) {
    const chaves = Object.keys(tramitacoes);
    if (chaves.length === 0) {
      containerTram.innerHTML = `<p class="text-muted">Nenhuma matéria em tramitação no momento.</p>`;
    } else {
      containerTram.innerHTML = chaves
        .map((chave) => {
          const t = tramitacoes[chave];
          const concluida = t.concluida;
          const badges = {
            EM_TRAMITACAO: `<span class="badge badge-info">EM ANDAMENTO</span>`,
            ENVIADA_A_SANCAO: `<span class="badge badge-warning">ENVIADA À SANÇÃO</span>`,
            VETO_EM_APRECIACAO: `<span class="badge badge-warning">VETO EM APRECIAÇÃO</span>`,
            APROVADA: `<span class="badge badge-success">APROVADA</span>`,
            PROMULGADA: `<span class="badge badge-success">PROMULGADA</span>`,
            REJEITADA: `<span class="badge badge-danger">REJEITADA</span>`,
            ARQUIVADA: `<span class="badge badge-subtle">RETIRADA DE PAUTA</span>`,
          };
          const statusBadge = badges[t.status] || `<span class="badge badge-subtle">${t.status}</span>`;
          const emEmendas = t.fase === "APRECIACAO_EMENDAS" && t.status === "EM_TRAMITACAO";
          const emVeto = t.status === "VETO_EM_APRECIACAO";
          const passouPorEmendas = t.fase === "APRECIACAO_EMENDAS" || Boolean(t.texto_prevalecente);
          const ehPec = t.tipo === "PEC";
          // Venceu as duas Casas só quem chegou à sanção, ao veto ou a um desfecho
          // aprovativo; rejeitada ou retirada de pauta para na Casa em que estava.
          const congressoVencido = ["ENVIADA_A_SANCAO", "VETO_EM_APRECIACAO", "APROVADA", "PROMULGADA"].includes(
            t.status
          );
          const rotulosFase = {
            CASA_INICIADORA: "Casa iniciadora",
            CASA_REVISORA: "Casa revisora",
            APRECIACAO_EMENDAS: "Apreciação das emendas da revisora (CF, art. 65)",
            APRECIACAO_VETO: "Apreciação do veto: maioria absoluta em cada Casa, votação aberta (CF, art. 66, § 4º)",
          };
          const rotuloFase = t.status === "REJEITADA" && !t.razoes_veto
            ? `Rejeitada na ${t.casa_atual} (sessão legislativa ${t.sessao_legislativa}): ${ehPec ? "não pode ser reapresentada nesta sessão legislativa (CF, art. 60, § 5º)" : "só volta nesta sessão com proposta da maioria absoluta (CF, art. 67)"}`
            : t.status === "ARQUIVADA"
            ? `Retirada de pauta, sem decisão de mérito: ${t.motivo_arquivamento}`
            : t.status === "ENVIADA_A_SANCAO"
            ? "Aguardando sanção ou veto do Presidente da República (CF, art. 66)"
            : t.status === "PROMULGADA"
              ? "Promulgada pelas Mesas da Câmara e do Senado (CF, art. 60, § 3º)"
              : concluida && t.razoes_veto
                ? t.status === "APROVADA"
                  ? "Veto derrubado pelo Congresso: lei aprovada (CF, art. 66, § 5º)"
                  : "Veto mantido: matéria rejeitada"
                : concluida && t.status === "APROVADA" && !t.razoes_veto && !ehPec
                  ? "Sancionada pelo Presidente da República (CF, art. 66)"
                  : rotulosFase[t.fase] || t.fase;
          const veto = t.razoes_veto ? `<br />Razões do veto: <strong>${t.razoes_veto}</strong>` : "";
          const textoFinal = t.texto_prevalecente
            ? `<br />Texto que prevaleceu: <strong>${t.texto_prevalecente === "REVISORA" ? "da revisora (emendas acolhidas)" : "da iniciadora (emendas rejeitadas)"}</strong>`
            : "";

          return `
            <div class="tramitacao-card">
              <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                  <span class="badge badge-subtle">${t.tipo}</span>
                  <strong style="margin-left: 0.35rem;">${t.materia_id}</strong>
                </div>
                ${statusBadge}
              </div>
              <div style="font-size: 0.8rem; color: var(--text-muted);">
                Casa Atual: <strong>${t.casa_atual}</strong> | ${emEmendas || emVeto ? "Sessão única por Casa" : `Turno: <strong>${t.turno_atual}º</strong>`}
                <br />Fase: ${rotuloFase}${textoFinal}${veto}
              </div>
              <div class="tramitacao-stepper">
                <span class="tramitacao-stage ${t.fase === "CASA_INICIADORA" && t.status === "EM_TRAMITACAO" ? "active" : t.fase !== "CASA_INICIADORA" || congressoVencido ? "done" : ""}">
                  Iniciadora (${t.casa_iniciadora})
                </span>
                <span>➔</span>
                <span class="tramitacao-stage ${t.fase === "CASA_REVISORA" && t.status === "EM_TRAMITACAO" ? "active" : congressoVencido || passouPorEmendas ? "done" : ""}">
                  Revisora (${t.casa_revisora})
                </span>
                ${
                  passouPorEmendas
                    ? `<span>➔</span><span class="tramitacao-stage ${emEmendas ? "active" : "done"}">Emendas (${t.casa_iniciadora})</span>`
                    : ""
                }
                <span>➔</span>
                <span class="tramitacao-stage ${t.status === "ENVIADA_A_SANCAO" ? "active" : ["APROVADA", "PROMULGADA"].includes(t.status) ? "done" : ""}">
                  ${ehPec ? "Promulgação" : "Sanção"}
                </span>
                ${
                  emVeto || t.razoes_veto
                    ? `<span>➔</span><span class="tramitacao-stage ${emVeto ? "active" : "done"}">Veto (${t.casa_atual})</span>`
                    : ""
                }
              </div>
              ${
                t.em_deliberacao
                  ? `
                <button class="btn btn-primary btn-sm btn-block" onclick="convocarSessaoTramitacao('${t.materia_id}')">
                  🏛️ Convocar Sessão do Plenário (${t.id_proxima_sessao})
                </button>
              `
                  : ""
              }
              <div style="font-size: 0.75rem; color: var(--text-muted);">Sessão legislativa: ${t.sessao_legislativa} (CF, art. 57)</div>
              ${
                t.status === "EM_TRAMITACAO"
                  ? `
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem;">
                  <input type="text" id="motivo-retirada-${t.materia_id}" placeholder="Motivo da retirada de pauta" style="flex: 2; min-width: 160px;" />
                  <button class="btn btn-outline btn-sm" style="flex: 1; min-width: 120px;" onclick="retirarDePauta('${t.materia_id}')">📤 Retirar de pauta</button>
                </div>
              `
                  : ""
              }
              ${
                ["REJEITADA", "ARQUIVADA"].includes(t.status)
                  ? `
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; align-items: center;">
                  ${
                    t.status === "REJEITADA" && !ehPec
                      ? `<label style="font-size: 0.8rem; display: flex; gap: 0.35rem; align-items: center;"><input type="checkbox" id="maioria-absoluta-${t.materia_id}" /> Proposta da maioria absoluta (CF, art. 67)</label>`
                      : ""
                  }
                  <button class="btn btn-secondary btn-sm" onclick="reapresentarMateria('${t.materia_id}')">🔁 Reapresentar matéria</button>
                </div>
              `
                  : ""
              }
              ${
                t.status === "ENVIADA_A_SANCAO"
                  ? `
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; align-items: flex-end;">
                  <button class="btn btn-success btn-sm" style="flex: 1; min-width: 120px;" onclick="sancionarTramitacao('${t.materia_id}')">✍️ Sancionar</button>
                  <input type="text" id="razoes-veto-${t.materia_id}" placeholder="Razões do veto" style="flex: 2; min-width: 160px;" />
                  <button class="btn btn-danger btn-sm" style="flex: 1; min-width: 120px;" onclick="vetarTramitacao('${t.materia_id}')">🚫 Vetar</button>
                </div>
              `
                  : ""
              }
            </div>
          `;
        })
        .join("");
    }
  }

  // Tabela Parlamentares
  const tabParl = document.getElementById("tabela-cong-parlamentares");
  if (tabParl) {
    tabParl.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Nome</th>
            <th>Casa</th>
            <th>Partido / UF</th>
            <th>Status de Voto</th>
          </tr>
        </thead>
        <tbody>
          ${parlamentares
            .map(
              (p) => `
            <tr>
              <td><code>${p.id}</code></td>
              <td><strong>${p.nome}</strong></td>
              <td>${p.casa === "CAMARA" ? "Câmara dos Deputados" : "Senado Federal"}</td>
              <td>${p.partido} / ${p.uf}</td>
              <td>${
                p.apto_votar
                  ? `<span class="badge badge-success">Apto (Exercício)</span>`
                  : `<span class="badge badge-danger">${p.motivo_inaptidao || "Inapto"}</span>`
              }</td>
            </tr>
          `
            )
            .join("")}
        </tbody>
      </table>
    `;
  }
}

async function retirarDePauta(materiaId) {
  const campo = document.getElementById(`motivo-retirada-${materiaId}`);
  try {
    await apiFetch(`/api/tramitacoes/${encodeURIComponent(materiaId)}/retirar`, {
      method: "POST",
      body: JSON.stringify({ motivo: campo ? campo.value : "" }),
    });
    mostrarToast(`${materiaId} retirada de pauta, sem decisão de mérito.`, "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao retirar de pauta: ${err.message}`, "error");
  }
}

async function reapresentarMateria(materiaId) {
  const marcador = document.getElementById(`maioria-absoluta-${materiaId}`);
  try {
    await apiFetch("/api/tramitacoes", {
      method: "POST",
      body: JSON.stringify({
        materia_id: materiaId,
        proposta_maioria_absoluta: Boolean(marcador && marcador.checked),
      }),
    });
    mostrarToast(`${materiaId} reapresentada: nova tramitação iniciada.`, "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Reapresentação recusada: ${err.message}`, "error");
  }
}

async function sancionarTramitacao(materiaId) {
  try {
    await apiFetch(`/api/tramitacoes/${encodeURIComponent(materiaId)}/sancionar`, { method: "POST" });
    mostrarToast(`${materiaId} sancionada: tramitação concluída como aprovada.`, "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao sancionar: ${err.message}`, "error");
  }
}

async function vetarTramitacao(materiaId) {
  const campo = document.getElementById(`razoes-veto-${materiaId}`);
  const razoes = campo ? campo.value : "";
  try {
    await apiFetch(`/api/tramitacoes/${encodeURIComponent(materiaId)}/vetar`, {
      method: "POST",
      body: JSON.stringify({ razoes }),
    });
    mostrarToast(`${materiaId} vetada: convoque a apreciação do veto (maioria absoluta em cada Casa).`, "info");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao vetar: ${err.message}`, "error");
  }
}

async function convocarSessaoTramitacao(materiaId) {
  try {
    const res = await apiFetch(`/api/tramitacoes/${encodeURIComponent(materiaId)}/convocar-sessao`, {
      method: "POST",
      body: JSON.stringify({ liberar_imediatamente: true }),
    });
    if (res.aviso) {
      // #37: sem quórum de presença, a sessão é convocada mas a votação não é liberada.
      mostrarToast(`Sessão '${res.sessao.id_sessao}' convocada. ${res.aviso}`, "info");
    } else {
      mostrarToast(`Sessão '${res.sessao.id_sessao}' convocada e liberada com sucesso!`, "success");
    }
    sessaoSelecionadaId = res.sessao.id_sessao;
    await carregarEstadoCompleto();
    navegarPara("sessoes");
  } catch (err) {
    mostrarToast(`Erro ao convocar sessão: ${err.message}`, "error");
  }
}

async function submeterCadastroMateria(event) {
  event.preventDefault();
  const payload = {
    id: document.getElementById("cong-mat-id").value,
    tipo: document.getElementById("cong-mat-tipo").value,
    titulo: document.getElementById("cong-mat-titulo").value,
    ementa: document.getElementById("cong-mat-ementa").value,
    casa_atual: document.getElementById("cong-mat-casa").value,
    autor_id: document.getElementById("cong-mat-autor").value,
  };

  try {
    await apiFetch("/api/congresso/materias", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    mostrarToast("Matéria legislativa protocolada com sucesso!", "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao cadastrar matéria: ${err.message}`, "error");
  }
}

async function submeterCadastroParlamentar(event) {
  event.preventDefault();
  const payload = {
    id: document.getElementById("cong-parl-id").value,
    nome: document.getElementById("cong-parl-nome").value,
    casa: document.getElementById("cong-parl-casa").value,
    partido: document.getElementById("cong-parl-partido").value,
    uf: document.getElementById("cong-parl-uf").value,
    em_exercicio: document.getElementById("cong-parl-exercicio").checked,
    licenciado: document.getElementById("cong-parl-licenciado").checked,
    suspenso: document.getElementById("cong-parl-suspenso").checked,
  };

  try {
    await apiFetch("/api/congresso/parlamentares", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    mostrarToast("Parlamentar cadastrado com sucesso!", "success");
    await carregarEstadoCompleto();
  } catch (err) {
    mostrarToast(`Erro ao cadastrar parlamentar: ${err.message}`, "error");
  }
}

// ==========================================================================
// ABA 6: AUDITORIA CRIPTOGRÁFICA SHA-256
// ==========================================================================

function renderizarAbaAuditoria() {
  if (!estadoApp) return;

  const sessoes = Object.values(estadoApp.sessoes || {});
  const seletor = document.getElementById("auditoria-seletor-sessao");
  if (seletor) {
    // Preserva a sessão escolhida no próprio seletor; sem escolha válida, usa a sessão
    // aberta na aba de Sessões. Antes, cada redesenho voltava à sessão selecionada lá,
    // e não era possível auditar outra pelo seletor.
    const escolhida = seletor.value;
    seletor.innerHTML = sessoes
      .map((s) => `<option value="${s.id_sessao}">${s.id_sessao}</option>`)
      .join("");
    if (escolhida && estadoApp.sessoes[escolhida]) {
      seletor.value = escolhida;
    } else if (sessaoSelecionadaId) {
      seletor.value = sessaoSelecionadaId;
    }
  }

  const idAuditada = seletor ? seletor.value : sessaoSelecionadaId;
  const sessao = estadoApp.sessoes[idAuditada];
  const painel = document.getElementById("painel-auditoria-conteudo");

  if (!sessao || !sessao.auditoria) {
    painel.innerHTML = `<p class="text-muted" style="padding: 1rem;">Nenhum log de auditoria disponível para esta sessão.</p>`;
    return;
  }

  const audit = sessao.auditoria;
  const ancora = estadoApp.ancoras_emitidas ? estadoApp.ancoras_emitidas[idAuditada] : null;

  painel.innerHTML = `
    <div class="grid-2-col">
      <div class="card" style="background: var(--bg-subtle);">
        <h4>🛡️ Status de Integridade da Cadeia</h4>
        <div style="font-size: 0.85rem; margin-top: 0.5rem;">
          Cadeia Criptográfica Íntegra:
          <strong>${audit.cadeia_integra ? "SIM ✅ (SHA-256 Verificado)" : "NÃO ❌"}</strong>
          <br />Total de Blocos Encadeados: <strong>${audit.total_registros}</strong>
          <br />Hash do Topo (Último Evento):
          <br /><code style="font-size: 0.72rem; word-break: break-all;">${audit.ultimo_hash || "—"}</code>
        </div>
      </div>

      <div class="card" style="background: var(--bg-subtle);">
        <h4>⚓ Âncora de Encerramento (ResumoEncerramento)</h4>
        <div style="font-size: 0.85rem; margin-top: 0.5rem;">
          ${
            ancora
              ? `
            Âncora Emitida: <strong style="color: var(--success);">SIM ✅</strong>
            <br />Hash Raiz Final: <code style="font-size: 0.72rem; word-break: break-all;">${ancora.hash_final}</code>
            <br />Total de Votos no Resumo: <strong>${ancora.total_votos}</strong>
          `
              : `<span class="badge badge-subtle">Âncora emitida apenas ao encerrar a sessão.</span>`
          }
        </div>
      </div>
    </div>

    <!-- Recontagem independente a partir do log (#29) -->
    ${
      sessao.estado === "ENCERRADA"
        ? `
    <div class="card" style="margin-top: 1rem;">
      <h4>🧮 Recontagem a partir do log (fiscal)</h4>
      <p class="card-subtitle">Reapura o resultado usando só as cédulas publicadas no encerramento e compara com o resultado proclamado.</p>
      <button class="btn btn-secondary btn-sm" style="margin-top: 0.5rem;" onclick="recontarSessao('${idAuditada}')">Recontar e comparar</button>
      <div id="resultado-recontagem" style="display: none; margin-top: 0.75rem;"></div>
    </div>
    `
        : ""
    }

    <!-- Verificador de Protocolo de Eleitor -->
    <div class="card" style="margin-top: 1rem;">
      <h4>🔍 Verificador Independente de Protocolo de Voto</h4>
      <p class="card-subtitle">Insira o código SHA-256 recebido na cabine para auditar se o voto está na cadeia:</p>
      <form onsubmit="submeterVerificacaoProtocolo(event, '${idAuditada}')" style="display: flex; gap: 0.5rem; margin-top: 0.75rem;">
        <input type="text" id="audit-input-protocolo" placeholder="Cole aqui o hash SHA-256 do protocolo..." required style="flex-grow: 1;" />
        <button type="submit" class="btn btn-secondary">Verificar na Cadeia</button>
      </form>
      <div id="resultado-verificacao-protocolo" style="display: none; margin-top: 0.75rem;"></div>
    </div>

    <!-- Mapa nominal de votação para a ata (#44) -->
    ${
      audit.mapa_nominal
        ? `
    <div class="card" style="margin-top: 1rem;">
      <h4>📜 Mapa de votação para a ata (voto aberto e nominal)</h4>
      <p class="card-subtitle">Exigido em assembleias pela Lei das S/A (art. 130) e pela CVM: cada titular, a sua opção e o peso das suas ações, extraídos do log de auditoria.</p>
      ${
        audit.mapa_nominal.length
          ? `<table class="data-table" style="margin-top: 0.5rem;">
              <thead><tr><th>Votante</th><th>Opção</th><th>Peso total</th><th>Ações próprias e representadas (#42)</th></tr></thead>
              <tbody>${audit.mapa_nominal
                .map((m) => {
                  const votante = m.procurador_id || m.eleitor_id;
                  const composicao = m.representacoes
                    ? [
                        m.peso_proprio ? `próprias: ${m.peso_proprio}` : "sem ações próprias",
                        ...m.representacoes.map(
                          (r) => `${r.outorgante_id}: ${r.peso} <small>(${r.procuracao_id})</small>`
                        ),
                      ].join("<br />")
                    : "voto direto";
                  return `<tr><td>${votante}${m.representacoes ? " <small>(procurador)</small>" : ""}</td><td>${m.opcao}</td><td>${m.peso}</td><td>${composicao}</td></tr>`;
                })
                .join("")}</tbody>
            </table>
            <form onsubmit="consultarOutorgante(event, '${idAuditada}')" style="display: flex; gap: 0.5rem; margin-top: 0.75rem; flex-wrap: wrap;">
              <input type="text" id="consulta-outorgante-id" placeholder="Acionista (ex.: AC-001)" style="flex: 1; min-width: 160px;" />
              <button type="submit" class="btn btn-secondary btn-sm">Onde minhas ações foram computadas?</button>
            </form>
            <div id="resultado-consulta-outorgante" style="display: none; margin-top: 0.5rem;"></div>`
          : `<p class="text-muted">Nenhum voto registrado ainda.</p>`
      }
    </div>
    `
        : ""
    }

    <!-- Lista de Blocos da Cadeia -->
    <div class="card" style="margin-top: 1rem;">
      <h4>⛓️ Blocos Registrados na Cadeia de Custódia (Hash Chain)</h4>
      ${
        sessao.voto_secreto
          ? `<p class="card-subtitle">🔒 Voto secreto: a opção e o horário de cada voto não são exibidos. Os hashes continuam verificáveis e o resultado aparece na apuração.</p>`
          : `<p class="card-subtitle">📢 Votação aberta e nominal neste contexto: as opções registradas são públicas.</p>`
      }
      <div class="hash-chain-list" style="margin-top: 0.75rem;">
        ${(audit.registros || [])
          .map(
            (r) => `
          <div class="hash-chain-node">
            <div class="node-header">
              <span>Bloco #${r.indice}: ${r.evento}</span>
              <small>${r.timestamp || "🔒 horário sigiloso"}</small>
            </div>
            <div class="hash-row"><strong>Hash:</strong> ${r.hash}</div>
            <div class="hash-row"><strong>Hash Anterior:</strong> ${r.hash_anterior}</div>
            <div class="hash-row"><strong>Dados:</strong> ${
              r.dados && r.dados.conteudo === "sigiloso" ? "🔒 conteúdo do voto sigiloso" : JSON.stringify(r.dados)
            }</div>
          </div>
        `
          )
          .join("")}
      </div>
    </div>
  `;
}

async function consultarOutorgante(event, idSessao) {
  event.preventDefault();
  const outorganteId = document.getElementById("consulta-outorgante-id").value;
  const box = document.getElementById("resultado-consulta-outorgante");
  try {
    const res = await apiFetch(`/api/sessoes/${encodeURIComponent(idSessao)}/consultar-outorgante`, {
      method: "POST",
      body: JSON.stringify({ outorgante_id: outorganteId }),
    });
    box.style.display = "block";
    box.innerHTML = res.ocorrencias.length
      ? res.ocorrencias
          .map(
            (o) =>
              `✅ ${res.outorgante_id}: <strong>${o.peso}</strong> ações em <strong>${o.opcao}</strong>, ` +
              (o.procuracao_id ? `votadas por ${o.votante} (${o.procuracao_id})` : "voto direto") +
              ` — bloco #${o.indice}`
          )
          .join("<br />")
      : `ℹ️ As ações de ${res.outorgante_id} não foram computadas nesta votação.`;
  } catch (err) {
    mostrarToast(`Erro na consulta: ${err.message}`, "error");
  }
}

async function recontarSessao(idSessao) {
  const box = document.getElementById("resultado-recontagem");
  try {
    const res = await apiFetch(`/api/sessoes/${encodeURIComponent(idSessao)}/recontar`, { method: "POST" });
    const contagem = Object.entries(res.resultado.contagem_por_opcao)
      .map(([opcao, votos]) => `${opcao}: <strong>${votos}</strong>`)
      .join(" | ");
    const divergencias = Object.entries(res.opcoes_divergentes)
      .map(([opcao, [recontado, proclamado]]) => `<li>${opcao}: recontado ${recontado}, proclamado ${proclamado}</li>`)
      .concat(
        Object.entries(res.campos_divergentes).map(
          ([campo, [recontado, proclamado]]) => `<li>${campo}: recontado ${recontado}, proclamado ${proclamado}</li>`
        )
      )
      .join("");
    const veredito = res.confere
      ? `✅ <strong>Confere:</strong> o resultado proclamado corresponde às cédulas registradas.`
      : res.confere === false
        ? `❌ <strong>Não confere:</strong> o resultado proclamado diverge das cédulas.<ul>${divergencias}</ul>`
        : `ℹ️ Ainda não há resultado proclamado para comparar.`;
    box.className = `badge ${res.confere ? "badge-success" : res.confere === false ? "badge-danger" : "badge-subtle"}`;
    box.style.cssText = "display: block; margin-top: 0.75rem; padding: 0.75rem; white-space: normal; text-transform: none; text-align: left;";
    box.innerHTML = `${veredito}<div style="margin-top: 0.4rem; font-weight: normal;">Recontagem: ${contagem || "sem votos"} — ${res.resultado.status}${res.ancorada ? " (cadeia conferida contra a âncora)" : ""}</div>`;
  } catch (err) {
    mostrarToast(`Recontagem recusada: ${err.message}`, "error");
  }
}

async function submeterVerificacaoProtocolo(event, idSessao) {
  event.preventDefault();
  const prot = document.getElementById("audit-input-protocolo").value;
  try {
    const res = await apiFetch(`/api/sessoes/${idSessao}/verificar-protocolo`, {
      method: "POST",
      body: JSON.stringify({ protocolo: prot }),
    });

    const box = document.getElementById("resultado-verificacao-protocolo");
    box.style.display = "block";
    if (res.situacao) {
      // #28: resposta ao eleitor, conferida contra a âncora do encerramento.
      const estilos = {
        INCLUIDO: ["badge-success", "✅"],
        REGISTRADO_URNA_ABERTA: ["badge-info", "🕒"],
        NAO_ENCONTRADO: ["badge-danger", "❌"],
        CADEIA_REPROVADA: ["badge-danger", "⚠️"],
      };
      const [classe, icone] = estilos[res.situacao] || ["badge-subtle", "ℹ️"];
      box.className = `badge ${classe}`;
      box.style.padding = "0.75rem";
      box.style.borderRadius = "var(--radius-sm)";
      box.style.whiteSpace = "normal";
      box.style.textTransform = "none";
      box.style.textAlign = "left";
      box.innerHTML = `
        <div>${icone} <strong>${res.mensagem}</strong></div>
        <div style="margin-top: 0.4rem; font-weight: normal;">${res.instrucao}</div>
      `;
      return;
    }
    if (res.encontrado) {
      box.className = "badge badge-success";
      box.style.padding = "0.75rem";
      box.style.borderRadius = "var(--radius-sm)";
      const quando = res.registro.timestamp ? ` registrado em ${res.registro.timestamp}` : "";
      const sigilo = res.registro.timestamp
        ? ""
        : "<br />O voto foi incluído na cadeia; por sigilo, a opção escolhida não é exibida.";
      box.innerHTML = `
        ✅ Protocolo Autêntico e Válido!<br />
        Encontrado no Bloco #${res.registro.indice} (${res.registro.evento})${quando}.${sigilo}
      `;
    } else {
      box.className = "badge badge-danger";
      box.style.padding = "0.75rem";
      box.style.borderRadius = "var(--radius-sm)";
      box.innerHTML = `❌ Protocolo NÃO encontrado nesta sessão de votação.`;
    }
  } catch (err) {
    mostrarToast(`Erro ao verificar: ${err.message}`, "error");
  }
}


const API_URL = "";

function escaparHtml(valor) {
  return String(valor ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatarData(valor) {
  if (!valor) return "";
  const data = new Date(valor);
  if (Number.isNaN(data.getTime())) return valor;
  return data.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function rotuloPrioridade(prioridade) {
  const mapa = { critica: "Crítica", alta: "Alta", acompanhamento: "Acompanhamento", estrutural: "Estrutural" };
  return mapa[prioridade] || prioridade || "Não definida";
}

function rotuloStatus(status) {
  const mapa = {
    aguardando_localidade: "Aguardando localidade",
    recebido: "Recebido",
    processado: "Processado",
    erro_ia: "Aguardando reprocessamento",
    em_consolidacao: "Em consolidação",
    aguardando_manifestacao: "Aguardando manifestação",
    em_revisao: "Em revisão",
    contestada: "Contestada",
    revisao_prioritaria: "Revisão prioritária",
    pronta_encaminhamento: "Pronta para encaminhamento",
    encaminhada: "Encaminhada",
    em_analise: "Em análise",
    aceito: "Aceita",
    em_atendimento: "Em atendimento",
    concluido: "Concluído",
    concluida: "Concluída",
    nao_atendido: "Não atendida",
    nao_competente: "Fora da competência",
    sem_destinatario: "Revisão de destinatário",
  };
  return mapa[status] || status || "Não informado";
}

function classePrioridade(prioridade) {
  if (prioridade === "critica") return "vermelho";
  if (prioridade === "alta") return "laranja";
  if (prioridade === "acompanhamento") return "amarelo";
  return "verde";
}

async function apiFetch(caminho, opcoes = {}) {
  let resposta;
  try {
    resposta = await fetch(`${API_URL}${caminho}`, opcoes);
  } catch (causa) {
    const erro = new Error("Sem conexão com o servidor.");
    erro.rede = true;
    erro.causa = causa;
    throw erro;
  }
  let dados = {};
  try { dados = await resposta.json(); } catch (_) {}
  if (!resposta.ok) {
    const erro = new Error(dados.detail || dados.mensagem || `Erro HTTP ${resposta.status}`);
    erro.status = resposta.status;
    erro.rede = false;
    throw erro;
  }
  return dados;
}

function instituicaoSessao() {
  try { return JSON.parse(sessionStorage.getItem("ac_instituicao") || "null"); }
  catch (_) { return null; }
}

function tokenInstitucional() { return sessionStorage.getItem("ac_token") || ""; }

async function apiInstitucionalFetch(caminho, opcoes = {}) {
  const token = tokenInstitucional();
  if (!token) throw new Error("Sessão institucional não encontrada.");
  const headers = new Headers(opcoes.headers || {});
  headers.set("Authorization", `Bearer ${token}`);
  return apiFetch(caminho, { ...opcoes, headers });
}

function sairInstituicao() {
  sessionStorage.removeItem("ac_instituicao");
  sessionStorage.removeItem("ac_token");
  location.href = "instituicao_login.html";
}

function perfilComunitario() {
  try { return JSON.parse(sessionStorage.getItem("ac_perfil") || "null"); }
  catch (_) { return null; }
}

function tokenComunitario() { return sessionStorage.getItem("ac_perfil_token") || ""; }

async function apiComunitarioFetch(caminho, opcoes = {}) {
  const token = tokenComunitario();
  if (!token) throw new Error("Acesse seu perfil comunitário primeiro.");
  const headers = new Headers(opcoes.headers || {});
  headers.set("Authorization", `Bearer ${token}`);
  return apiFetch(caminho, { ...opcoes, headers });
}

function salvarSessaoComunitaria(token, perfil) {
  sessionStorage.setItem("ac_perfil_token", token);
  sessionStorage.setItem("ac_perfil", JSON.stringify(perfil));
}

function sairComunidade() {
  sessionStorage.removeItem("ac_perfil_token");
  sessionStorage.removeItem("ac_perfil");
  location.href = "comunidade.html";
}

let promptInstalacao = null;
window.addEventListener("beforeinstallprompt", (evento) => {
  evento.preventDefault();
  promptInstalacao = evento;
  document.querySelectorAll("[data-install-app]").forEach((b) => b.hidden = false);
});

document.addEventListener("click", async (evento) => {
  const botao = evento.target.closest("[data-install-app]");
  if (!botao || !promptInstalacao) return;
  promptInstalacao.prompt();
  await promptInstalacao.userChoice;
  promptInstalacao = null;
  botao.hidden = true;
});

if ("serviceWorker" in navigator && location.protocol !== "file:") {
  navigator.serviceWorker.register("/app/sw.js").catch((erro) => console.warn("Service worker:", erro));
}

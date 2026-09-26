const areaAcesso = document.getElementById("community-access");
const areaApp = document.getElementById("community-app");
const painel = document.getElementById("community-panel");
const nav = document.getElementById("community-app-nav");
let perfilAtual = perfilComunitario();
let comunidades = [];

async function carregarBase() {
  const [c, p] = await Promise.all([apiFetch("/comunidades"), apiFetch("/comunitario/perfis-demo")]);
  comunidades = c.comunidades || [];
  const opts = comunidades.map(x => `<option value="${x.id}">${escaparHtml(x.nome)}${x.municipio ? ` — ${escaparHtml(x.municipio)}` : ""}</option>`).join("");
  document.getElementById("perfil-comunidade").innerHTML = '<option value="">Selecione</option>' + opts;
  document.getElementById("perfil-existente").innerHTML = '<option value="">Selecione</option>' + (p.perfis || []).map(x => `<option value="${x.id}">${escaparHtml(x.nome_exibicao)} — ${escaparHtml(x.comunidade_nome)} (${x.papel === "representante" ? "representante" : "morador"})</option>`).join("");
}

function mostrarApp(perfil) {
  perfilAtual = perfil;
  sessionStorage.setItem("ac_perfil", JSON.stringify(perfil));
  areaAcesso.hidden = true; areaApp.hidden = false; document.getElementById("btn-sair-comunidade").hidden = false;
  document.getElementById("perfil-tipo").textContent = perfil.papel === "representante" ? "REPRESENTAÇÃO COMUNITÁRIA — DEMONSTRAÇÃO" : "PERFIL DE MORADOR — DEMONSTRAÇÃO";
  document.getElementById("perfil-saudacao").textContent = `Olá, ${perfil.nome_exibicao}`;
  document.getElementById("perfil-contexto").textContent = `${perfil.comunidade_nome}${perfil.funcao_informada ? ` • função informada: ${perfil.funcao_informada}` : ""}`;
  const itens = perfil.papel === "representante"
    ? [["inicio","Início"],["demandas","Demandas"],["avisos","Avisos"],["mensagens","Mensagens"]]
    : [["inicio","Início"],["relatos","Meus relatos"],["avisos","Avisos"],["mensagens","Mensagens"]];
  nav.innerHTML = itens.map(([id,nome],i) => `<button class="${i===0?"active":""}" data-community-view="${id}">${nome}</button>`).join("");
  nav.querySelectorAll("button").forEach(b => b.addEventListener("click", () => abrirAba(b.dataset.communityView, b)));
  abrirAba("inicio", nav.querySelector("button"));
}

async function validarSessaoExistente() {
  if (!tokenComunitario()) return;
  try { const perfil = await apiComunitarioFetch("/comunitario/me"); mostrarApp(perfil); }
  catch (_) { sessionStorage.removeItem("ac_perfil_token"); sessionStorage.removeItem("ac_perfil"); }
}

async function abrirAba(aba, botao) {
  nav.querySelectorAll("button").forEach(b => b.classList.toggle("active", b === botao));
  painel.innerHTML = '<div class="estado-vazio">Carregando...</div>';
  try {
    if (aba === "inicio") return carregarInicio();
    if (aba === "relatos") return carregarRelatos();
    if (aba === "demandas") return carregarDemandas();
    if (aba === "avisos") return carregarAvisos();
    if (aba === "mensagens") return carregarMensagens();
  } catch (erro) { painel.innerHTML = `<div class="estado-vazio">${escaparHtml(erro.message)}</div>`; }
}

async function carregarInicio() {
  const [relatos, avisos, mensagens, demandas] = await Promise.all([
    apiComunitarioFetch("/comunitario/meus-relatos"),
    apiComunitarioFetch("/comunitario/notificacoes"),
    apiComunitarioFetch("/comunitario/mensagens"),
    apiComunitarioFetch("/comunitario/demandas")
  ]);
  const principal = perfilAtual.papel === "representante"
    ? `<div class="home-status-card"><strong>${demandas.demandas.length}</strong><span>demandas da comunidade para acompanhar</span></div>`
    : `<div class="home-status-card"><strong>${relatos.relatos.length}</strong><span>relatos enviados por este perfil</span></div>`;
  painel.innerHTML = `<div class="community-home-grid">${principal}<div class="home-status-card"><strong>${avisos.notificacoes.length}</strong><span>atualizações recentes</span></div><div class="home-status-card"><strong>${mensagens.mensagens.length}</strong><span>mensagens disponíveis</span></div></div><div class="welcome-note"><strong>O que você precisa fazer?</strong><p>Use o botão de relato acima para contar uma situação. As outras áreas mostram apenas o que o seu perfil pode acessar.</p></div>`;
}

async function carregarRelatos() {
  const r = await apiComunitarioFetch("/comunitario/meus-relatos");
  painel.innerHTML = `<div class="panel-title"><div><p class="pequeno">SEUS RELATOS</p><h3>Acompanhamento individual</h3></div></div>${r.relatos.length ? `<div class="lista-demandas">${r.relatos.map(x => `<article class="demanda-card"><div><p class="pequeno">${escaparHtml(x.protocolo)}</p><h3>${escaparHtml(x.demanda_titulo || "Relato recebido")}</h3><p>${x.demanda_status ? rotuloStatus(x.demanda_status) : rotuloStatus(x.status_processamento)}</p><div class="demanda-meta">${x.demanda_prioridade ? `<span>${rotuloPrioridade(x.demanda_prioridade)}</span>` : ""}<span>${formatarData(x.data_recebimento)}</span></div></div></article>`).join("")}</div>` : '<div class="estado-vazio">Você ainda não enviou relatos por este perfil.</div>'}`;
}

async function carregarDemandas() {
  const r = await apiComunitarioFetch("/comunitario/demandas");
  painel.innerHTML = `<div class="panel-title"><div><p class="pequeno">DEMANDAS DA COMUNIDADE</p><h3>Visão do representante</h3></div></div>${r.demandas.length ? `<div class="lista-demandas">${r.demandas.map(d => `<button class="demand-row-button" data-demanda-id="${d.id}"><div><strong>${escaparHtml(d.titulo)}</strong><small>${escaparHtml(d.protocolo)} • ${rotuloStatus(d.status)}</small></div><span class="badge ${classePrioridade(d.prioridade)}">${rotuloPrioridade(d.prioridade)}</span></button>`).join("")}</div>` : '<div class="estado-vazio">Nenhuma demanda consolidada nesta comunidade.</div>'}`;
  painel.querySelectorAll("[data-demanda-id]").forEach(b => b.addEventListener("click", () => abrirDemandaRepresentante(Number(b.dataset.demandaId))));
}

async function abrirDemandaRepresentante(id) {
  const d = await apiComunitarioFetch(`/comunitario/demandas/${id}`);
  painel.innerHTML = `<button id="voltar-demandas" class="text-link">← Voltar às demandas</button><div class="rep-demand-detail"><p class="pequeno">${escaparHtml(d.protocolo)}</p><h2>${escaparHtml(d.titulo)}</h2><p>${escaparHtml(d.resumo)}</p><div class="demanda-meta"><span>${rotuloPrioridade(d.prioridade)}</span><span>${rotuloStatus(d.status)}</span><span>${d.quantidade_relatos} relato(s) consolidados</span></div>${d.informacoes_faltantes?.length ? `<div class="detail-note"><strong>Informações que ainda faltam</strong><ul>${d.informacoes_faltantes.map(x=>`<li>${escaparHtml(x)}</li>`).join("")}</ul></div>`:""}<div class="manifest-box"><h3>Manifestação do representante</h3><select id="manifest-tipo"><option value="confirmar">Confirmar</option><option value="complementar">Complementar</option><option value="contestar">Contestar</option></select><textarea id="manifest-texto" rows="4" placeholder="Explique sua manifestação"></textarea><button id="manifest-enviar" class="btn btn-primary">Registrar manifestação</button><p id="manifest-status" class="status-text"></p></div></div>`;
  document.getElementById("voltar-demandas").addEventListener("click", () => abrirAba("demandas", [...nav.querySelectorAll("button")].find(b=>b.dataset.communityView==="demandas")));
  document.getElementById("manifest-enviar").addEventListener("click", async () => {
    const texto = document.getElementById("manifest-texto").value.trim();
    if (texto.length < 3) return document.getElementById("manifest-status").textContent = "Explique a manifestação.";
    try { const r = await apiComunitarioFetch(`/comunitario/demandas/${id}/manifestacoes`, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({tipo:document.getElementById("manifest-tipo").value,texto}) }); document.getElementById("manifest-status").textContent = r.mensagem; }
    catch (erro) { document.getElementById("manifest-status").textContent = erro.message; }
  });
}

async function carregarAvisos() {
  const r = await apiComunitarioFetch("/comunitario/notificacoes");
  painel.innerHTML = `<div class="panel-title"><div><p class="pequeno">AVISOS</p><h3>Atualizações da comunidade</h3></div></div>${r.notificacoes.length ? `<div class="lista-simples">${r.notificacoes.map(n => `<article><strong>${escaparHtml(n.titulo || "Atualização")}</strong><p>${escaparHtml(n.descricao || rotuloStatus(n.status))}</p><small>${formatarData(n.data_criacao)}</small></article>`).join("")}</div>` : '<div class="estado-vazio">Nenhum aviso recente.</div>'}`;
}

async function carregarMensagens() {
  const r = await apiComunitarioFetch("/comunitario/mensagens");
  painel.innerHTML = `<div class="panel-title"><div><p class="pequeno">MENSAGENS</p><h3>Comunicação institucional</h3></div></div>${r.mensagens.length ? `<div class="lista-simples">${r.mensagens.map(m => `<article><strong>${escaparHtml(m.titulo)}</strong><p>${escaparHtml(m.texto)}</p><small>${escaparHtml(m.instituicao_nome || "Instituição")} • ${formatarData(m.data_criacao)}</small></article>`).join("")}</div>` : '<div class="estado-vazio">Nenhuma mensagem disponível.</div>'}`;
}

document.getElementById("form-cadastro-perfil").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    const r = await apiFetch("/comunitario/cadastro-demo", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({nome_exibicao:document.getElementById("perfil-nome").value.trim(),comunidade_id:Number(document.getElementById("perfil-comunidade").value),papel:document.getElementById("perfil-papel").value,funcao_informada:document.getElementById("perfil-funcao").value.trim()}) });
    salvarSessaoComunitaria(r.token, r.perfil); mostrarApp(r.perfil);
  } catch (erro) { document.getElementById("status-acesso").textContent = erro.message; }
});

document.getElementById("btn-login-perfil").addEventListener("click", async () => {
  const id = Number(document.getElementById("perfil-existente").value); if (!id) return;
  try { const r = await apiFetch("/comunitario/login-demo", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({perfil_id:id}) }); salvarSessaoComunitaria(r.token,r.perfil); mostrarApp(r.perfil); }
  catch (erro) { document.getElementById("status-acesso").textContent = erro.message; }
});

document.getElementById("btn-sair-comunidade").addEventListener("click", sairComunidade);

carregarBase().then(validarSessaoExistente).catch(erro => document.getElementById("status-acesso").textContent = erro.message);

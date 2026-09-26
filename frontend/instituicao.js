const inst = instituicaoSessao();
if (!inst || !tokenInstitucional()) location.href = "instituicao_login.html";
const content = document.getElementById("workspace-content");
const title = document.getElementById("workspace-title");
const drawer = document.getElementById("institution-drawer");
const drawerContent = document.getElementById("institution-drawer-content");
let demandasCache = [];
let comunidadesCache = [];

document.getElementById("institution-identity").innerHTML = `<strong>${escaparHtml(inst?.nome || "Instituição")}</strong><small>${(inst?.areas || []).map(escaparHtml).join(" • ")}</small>`;
document.getElementById("btn-sair-instituicao").addEventListener("click", sairInstituicao);
document.getElementById("institution-nav").querySelectorAll("button").forEach(btn => btn.addEventListener("click", () => abrirView(btn.dataset.view, btn)));
drawer.addEventListener("click", e => { if (e.target === drawer) fecharDrawer(); });

async function dadosBase() {
  const [d, c] = await Promise.all([apiInstitucionalFetch("/institucional/demandas"), apiInstitucionalFetch("/institucional/comunidades")]);
  demandasCache = d.demandas || []; comunidadesCache = c.comunidades || [];
}

function ativarBotao(botao) { document.querySelectorAll("#institution-nav button").forEach(b => b.classList.toggle("active", b === botao)); }
async function abrirView(view, botao) {
  if (botao) ativarBotao(botao);
  content.innerHTML = '<div class="estado-vazio">Carregando...</div>';
  try { await dadosBase(); } catch (erro) { content.innerHTML = `<div class="estado-vazio">${escaparHtml(erro.message)}</div>`; return; }
  const mapaTitulos = {visao:"Visão geral",demandas:"Demandas para análise",prioridades:"Prioridades",comunidades:"Comunidades",mapa:"Mapa territorial",relatorios:"Relatórios",mensagens:"Mensagens",sobre:"Sobre o ambiente institucional"};
  title.textContent = mapaTitulos[view] || "Painel";
  if (view === "visao") renderVisao();
  if (view === "demandas") renderDemandas(demandasCache);
  if (view === "prioridades") renderDemandas(demandasCache.filter(d => ["critica","alta"].includes(d.prioridade)), true);
  if (view === "comunidades") renderComunidades();
  if (view === "mapa") renderMapa();
  if (view === "relatorios") renderRelatorios();
  if (view === "mensagens") renderMensagens();
  if (view === "sobre") renderSobre();
}

function renderVisao() {
  const elevadas = demandasCache.filter(d => ["critica","alta"].includes(d.prioridade)).length;
  const atendimento = demandasCache.filter(d => ["encaminhada","em_analise","em_atendimento"].includes(d.status)).length;
  content.innerHTML = `<div class="institution-kpis"><button data-go="demandas"><span>Demandas compatíveis</span><strong>${demandasCache.length}</strong><small>Abrir fila de trabalho</small></button><button data-go="prioridades"><span>Prioridades elevadas</span><strong>${elevadas}</strong><small>Revisar agora</small></button><button data-go="comunidades"><span>Comunidades no contexto</span><strong>${comunidadesCache.length}</strong><small>Ver acompanhamento</small></button><div><span>Em atendimento</span><strong>${atendimento}</strong><small>Fluxos ativos</small></div></div><section class="institution-section"><div class="section-head"><div><p class="pequeno">FILA RECENTE</p><h2>Demandas relacionadas às áreas da instituição</h2></div></div>${tabelaDemandas(demandasCache.slice(0,8))}</section>`;
  content.querySelectorAll("[data-go]").forEach(b => b.addEventListener("click", () => { const alvo=[...document.querySelectorAll("#institution-nav button")].find(x=>x.dataset.view===b.dataset.go); abrirView(b.dataset.go,alvo); }));
  ligarDemandas();
}

function tabelaDemandas(dados) {
  if (!dados.length) return '<div class="estado-vazio">Nenhuma demanda compatível no momento.</div>';
  return `<div class="institution-table-wrap"><table class="institution-table"><thead><tr><th>Demanda</th><th>Comunidade</th><th>Prioridade</th><th>Status</th><th>Atualização</th></tr></thead><tbody>${dados.map(d=>`<tr data-open-demand="${d.id}"><td><strong>${escaparHtml(d.titulo)}</strong><small>${escaparHtml(d.protocolo)}</small></td><td>${escaparHtml(d.comunidade)}</td><td><span class="badge ${classePrioridade(d.prioridade)}">${rotuloPrioridade(d.prioridade)}</span></td><td>${rotuloStatus(d.status)}</td><td>${formatarData(d.data_atualizacao)}</td></tr>`).join("")}</tbody></table></div>`;
}
function ligarDemandas(){ content.querySelectorAll("[data-open-demand]").forEach(r=>r.addEventListener("click",()=>abrirDemanda(Number(r.dataset.openDemand)))); }
function renderDemandas(dados, prioridade=false){ content.innerHTML = `<section class="institution-section"><div class="section-head"><div><p class="pequeno">${prioridade?"REVISÃO PRIORITÁRIA":"FILA DE TRABALHO"}</p><h2>${prioridade?"Demandas críticas e altas":"Demandas compatíveis"}</h2></div></div>${tabelaDemandas(dados)}</section>`; ligarDemandas(); }

function renderComunidades(){ content.innerHTML = `<section class="institution-section"><div class="section-head"><div><p class="pequeno">MINHAS COMUNIDADES</p><h2>Comunidades com demandas no contexto da instituição</h2></div></div>${comunidadesCache.length?`<div class="institution-community-grid">${comunidadesCache.map(c=>`<button data-community="${c.id}"><div><strong>${escaparHtml(c.nome)}</strong><small>${escaparHtml(c.municipio||"")}</small></div><div class="community-mini-stats"><span>${c.demandas_total} demandas</span><span>${c.prioridades_elevadas||0} elevadas</span><span>${c.em_atendimento||0} em atendimento</span></div></button>`).join("")}</div>`:'<div class="estado-vazio">Nenhuma comunidade vinculada às áreas atuais.</div>'}</section><section id="community-institution-detail"></section>`; content.querySelectorAll("[data-community]").forEach(b=>b.addEventListener("click",()=>abrirResumoComunidade(Number(b.dataset.community)))); }

async function abrirResumoComunidade(id) {
  const box=document.getElementById("community-institution-detail"); box.innerHTML='<div class="estado-vazio">Carregando comunidade...</div>';
  try { const [s,m]=await Promise.all([apiInstitucionalFetch(`/institucional/comunidades/${id}/resumo?periodo=semanal`),apiInstitucionalFetch(`/institucional/comunidades/${id}/resumo?periodo=mensal`)]); box.innerHTML=`<section class="institution-section community-report-detail"><div class="section-head"><div><p class="pequeno">COMUNIDADE</p><h2>${escaparHtml(s.comunidade.nome)}</h2><p>${escaparHtml(s.comunidade.municipio||"")}</p></div></div><div class="period-grid"><article><strong>Últimos 7 dias</strong><span>${s.total_demandas} demandas atualizadas</span><span>${s.prioridades_elevadas} prioridades elevadas</span><span>${s.mensagens} mensagens</span></article><article><strong>Últimos 30 dias</strong><span>${m.total_demandas} demandas atualizadas</span><span>${m.prioridades_elevadas} prioridades elevadas</span><span>${m.mensagens} mensagens</span></article></div><h3>Histórico recente</h3>${s.demandas.length?`<div class="lista-simples">${s.demandas.map(d=>`<article><strong>${escaparHtml(d.titulo)}</strong><p>${rotuloStatus(d.status)} • ${rotuloPrioridade(d.prioridade)}</p><small>${formatarData(d.data_atualizacao)}</small></article>`).join("")}</div>`:'<div class="estado-vazio">Sem alterações no período semanal.</div>'}<div class="future-records"><strong>Estrutura preparada para evolução:</strong><span>comprovantes/recibos de entrega</span><span>problemas de execução</span><span>anexos e histórico de atendimento</span></div></section>`; }
  catch(erro){box.innerHTML=`<div class="estado-vazio">${escaparHtml(erro.message)}</div>`;}
}

function renderMapa(){ content.innerHTML=`<section class="institution-section"><div class="section-head"><div><p class="pequeno">CONTEXTO TERRITORIAL</p><h2>Mapa dentro do ambiente institucional</h2><p>A navegação permanece no painel. O catálogo público mostra somente referências cuja visibilidade possui origem registrada.</p></div></div><iframe class="institution-map-frame" src="mapa.html?embed=1" title="Mapa territorial"></iframe></section>`; }

async function renderRelatorios(){ const modelos=await apiInstitucionalFetch("/institucional/modelos"); content.innerHTML=`<section class="institution-section"><div class="section-head"><div><p class="pequeno">RELATÓRIOS</p><h2>Resumo semanal e mensal</h2><p>Abra uma comunidade na seção Comunidades para consultar os dois períodos.</p></div></div><div class="report-tools"><article><h3>Modelo de referência da organização</h3><p>Anexe um modelo que a organização já usa. Nesta versão ele fica guardado como referência; o preenchimento adaptativo completo é a próxima evolução.</p><input id="modelo-arquivo" type="file" accept=".docx,.pdf,.txt,.xlsx"><button id="btn-modelo" class="btn btn-primary">Anexar modelo</button><p id="modelo-status" class="status-text"></p></article><article><h3>Modelos anexados</h3><div id="modelos-lista">${modelos.modelos.length?modelos.modelos.map(m=>`<div class="model-row"><strong>${escaparHtml(m.nome_original)}</strong><small>${formatarData(m.data_criacao)}</small></div>`).join(""):'<p class="muted">Nenhum modelo anexado.</p>'}</div></article></div></section>`; document.getElementById("btn-modelo").addEventListener("click",anexarModelo); }
async function anexarModelo(){ const arq=document.getElementById("modelo-arquivo").files[0], st=document.getElementById("modelo-status"); if(!arq)return st.textContent="Escolha um arquivo."; const form=new FormData();form.append("arquivo",arq);try{const r=await apiInstitucionalFetch("/institucional/modelos",{method:"POST",body:form});st.textContent=r.mensagem;setTimeout(()=>renderRelatorios(),600);}catch(e){st.textContent=e.message;} }

function renderMensagens(){ content.innerHTML=`<section class="institution-section"><div class="section-head"><div><p class="pequeno">MENSAGENS</p><h2>Comunicação ligada às demandas</h2><p>Abra uma demanda para enviar uma atualização, pedido de informação ou aviso de ação agendada à comunidade correspondente.</p></div></div>${tabelaDemandas(demandasCache.slice(0,20))}</section>`; ligarDemandas(); }
function renderSobre(){ content.innerHTML=`<section class="institution-section institution-about"><p class="pequeno">AMBIENTE INSTITUCIONAL</p><h2>Espaço privado de trabalho para organizações credenciadas.</h2><p>Esta área organiza demandas comunitárias, prioridades, histórico, mensagens e evidências para apoiar análise e atendimento. O protótipo separa a experiência institucional da interface pública e comunitária.</p><div class="feature-grid"><article class="feature"><h3>Rastreabilidade</h3><p>A instituição pode abrir os detalhes e consultar a origem das informações usadas pela IA.</p></article><article class="feature"><h3>Revisão humana</h3><p>Prioridade e roteamento apoiados por IA não substituem validação institucional.</p></article><article class="feature"><h3>Dados restritos</h3><p>Áudio original, quando retido com consentimento, não fica exposto publicamente.</p></article><article class="feature"><h3>Protótipo</h3><p>Login real, verificação documental e integração oficial com sistemas externos permanecem etapas de produção.</p></article></div></section>`; }

async function abrirDemanda(id) {
  drawer.hidden=false; drawerContent.innerHTML='<div class="estado-vazio">Carregando detalhes...</div>';
  try {
    const d=await apiInstitucionalFetch(`/institucional/demandas/${id}`);
    drawerContent.innerHTML=`<div class="drawer-head"><button id="drawer-close">×</button><div><p class="pequeno">${escaparHtml(d.protocolo)}</p><h2>${escaparHtml(d.titulo)}</h2><p>${escaparHtml(d.comunidade)}</p></div></div><div class="demanda-meta"><span class="badge ${classePrioridade(d.prioridade)}">${rotuloPrioridade(d.prioridade)}</span><span>${rotuloStatus(d.status)}</span><span>${d.quantidade_relatos} relato(s)</span></div><section class="drawer-section"><h3>Síntese da IA</h3><p>${escaparHtml(d.resumo)}</p>${d.necessidades?.length?`<ul>${d.necessidades.map(x=>`<li>${escaparHtml(x)}</li>`).join("")}</ul>`:""}<button class="btn" id="btn-avaliar-rota">Consultar agente de roteamento</button><p id="route-result" class="status-text"></p></section><section class="drawer-section"><h3>Origem e evidências</h3><p class="muted">A síntese pode ser conferida contra os relatos preservados. Áudio só aparece quando houve consentimento.</p>${(d.relatos||[]).map(r=>`<article class="source-report"><div class="source-head"><strong>${escaparHtml(r.protocolo)}</strong><span>${escaparHtml(r.perfil_papel?`${r.perfil_nome_exibicao||"Perfil"} • ${r.perfil_papel}${r.perfil_funcao_informada?` • ${r.perfil_funcao_informada}`:""}`:"Relato sem perfil cadastrado")}</span></div><p><b>Original:</b> ${escaparHtml(r.mensagem_original)}</p>${r.texto_formalizado?`<p><b>Versão organizada:</b> ${escaparHtml(r.texto_formalizado)}</p>`:""}${r.audio_disponivel?`<button class="btn btn-small" data-audio-relato="${r.id}">🎧 Ouvir áudio original</button><div id="audio-${r.id}"></div>`:'<small>Áudio original não retido ou sem consentimento.</small>'}</article>`).join("")}</section><section class="drawer-section"><h3>Manifestação comunitária</h3>${d.manifestacoes?.length?d.manifestacoes.map(m=>`<article class="manifest-record"><strong>${escaparHtml(m.tipo)}</strong><p>${escaparHtml(m.texto)}</p><small>${escaparHtml(m.autor||"")} • ${formatarData(m.data_criacao)}</small></article>`).join(""):'<p class="muted">Nenhuma manifestação registrada.</p>'}</section><section class="drawer-section"><h3>Ações institucionais</h3><div class="acoes-linha"><button id="btn-preparar" class="btn">Marcar pronta para encaminhamento</button><button id="btn-encaminhar" class="btn btn-primary">Encaminhar próxima</button><a class="btn" href="relatorio_formal.html?id=${d.id}" target="_blank">Relatório formal</a></div><div class="message-box"><h4>Enviar mensagem à comunidade</h4><select id="msg-tipo"><option value="informacao">Informação</option><option value="pedido_informacao">Pedido de informação</option><option value="acao_agendada">Ação agendada</option></select><input id="msg-titulo" placeholder="Título"><textarea id="msg-texto" rows="3" placeholder="Mensagem"></textarea><button id="btn-msg" class="btn">Enviar mensagem</button><p id="action-status" class="status-text"></p></div></section>`;
    document.getElementById("drawer-close").addEventListener("click",fecharDrawer);
    drawerContent.querySelectorAll("[data-audio-relato]").forEach(b=>b.addEventListener("click",()=>carregarAudio(Number(b.dataset.audioRelato))));
    document.getElementById("btn-avaliar-rota").addEventListener("click",()=>avaliarRota(id));
    document.getElementById("btn-preparar").addEventListener("click",()=>acaoPost(`/institucional/demandas/${id}/preparar-encaminhamento`,{},"Demanda preparada."));
    document.getElementById("btn-encaminhar").addEventListener("click",()=>acaoPost(`/institucional/demandas/${id}/encaminhar-proxima`,null,"Encaminhamento processado."));
    document.getElementById("btn-msg").addEventListener("click",()=>enviarMensagem(id));
  } catch(erro){drawerContent.innerHTML=`<button id="drawer-close" class="drawer-x">×</button><div class="estado-vazio">${escaparHtml(erro.message)}</div>`;document.getElementById("drawer-close").addEventListener("click",fecharDrawer);}
}
function fecharDrawer(){drawer.hidden=true;drawerContent.innerHTML="";}
async function carregarAudio(relatoId){const box=document.getElementById(`audio-${relatoId}`);box.textContent="Carregando áudio...";try{const resposta=await fetch(`/institucional/relatos/${relatoId}/audio`,{headers:{Authorization:`Bearer ${tokenInstitucional()}`}});if(!resposta.ok){const j=await resposta.json();throw new Error(j.detail||"Falha ao carregar áudio.");}const blob=await resposta.blob();const url=URL.createObjectURL(blob);box.innerHTML=`<audio controls src="${url}"></audio>`;}catch(e){box.textContent=e.message;}}
async function avaliarRota(id){const box=document.getElementById("route-result");box.textContent="O agente está consultando as ferramentas...";try{const r=await apiInstitucionalFetch(`/institucional/demandas/${id}/avaliar-roteamento`,{method:"POST"});box.textContent=`${r.instituicao_nome_sugerida||"Sem destino automático"}: ${r.justificativa}`;}catch(e){box.textContent=e.message;}}
async function acaoPost(url,body,mensagem){const st=document.getElementById("action-status");try{const opts={method:"POST"};if(body!==null){opts.headers={"Content-Type":"application/json"};opts.body=JSON.stringify(body);}const r=await apiInstitucionalFetch(url,opts);st.textContent=r.mensagem||mensagem;}catch(e){st.textContent=e.message;}}
async function enviarMensagem(id){const st=document.getElementById("action-status");const titulo=document.getElementById("msg-titulo").value.trim(),texto=document.getElementById("msg-texto").value.trim();if(!titulo||!texto)return st.textContent="Preencha título e mensagem.";try{const r=await apiInstitucionalFetch(`/institucional/demandas/${id}/mensagens`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({tipo:document.getElementById("msg-tipo").value,titulo,texto,publica:true})});st.textContent=r.mensagem;}catch(e){st.textContent=e.message;}}

abrirView("visao", document.querySelector('#institution-nav button[data-view="visao"]'));

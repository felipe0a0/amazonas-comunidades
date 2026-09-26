const relatoEl = document.getElementById("relato");
const comunidadeSelect = document.getElementById("comunidade-select");
const perfil = perfilComunitario();
let comunidades = [];
let gravador = null;
let fluxo = null;
let partes = [];
let propositoGravacao = "relato";
let audioRef = "";
let transcricaoConfirmada = false;
let meioRelato = "texto";

async function carregarComunidades() {
  const r = await apiFetch("/comunidades");
  comunidades = r.comunidades || [];
  comunidadeSelect.innerHTML = '<option value="">Selecione se souber</option>' + comunidades.map(c => `<option value="${c.id}">${escaparHtml(c.nome)}${c.municipio ? ` — ${escaparHtml(c.municipio)}` : ""}</option>`).join("");
  if (perfil?.comunidade_id) comunidadeSelect.value = String(perfil.comunidade_id);
}

function extensaoPorMime(mime) {
  if ((mime || "").includes("mp4")) return "m4a";
  if ((mime || "").includes("ogg")) return "ogg";
  if ((mime || "").includes("wav")) return "wav";
  return "webm";
}

async function iniciarGravacao(proposito = "relato") {
  const status = proposito === "relato" ? document.getElementById("status-audio") : document.getElementById("status-localidade");
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    status.textContent = "Este navegador não oferece gravação. Você pode escrever.";
    return;
  }
  try {
    propositoGravacao = proposito;
    fluxo = await navigator.mediaDevices.getUserMedia({ audio: true });
    const tipos = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
    const suportado = tipos.find(t => MediaRecorder.isTypeSupported?.(t));
    gravador = suportado ? new MediaRecorder(fluxo, { mimeType: suportado }) : new MediaRecorder(fluxo);
    partes = [];
    gravador.ondataavailable = e => { if (e.data.size) partes.push(e.data); };
    gravador.onstop = async () => {
      const blob = new Blob(partes, { type: gravador.mimeType || suportado || "audio/webm" });
      fluxo?.getTracks().forEach(t => t.stop());
      await transcreverBlob(blob, propositoGravacao);
    };
    gravador.start();
    if (proposito === "relato") {
      document.getElementById("btn-gravar").hidden = true;
      document.getElementById("btn-parar").hidden = false;
      document.getElementById("btn-parar").disabled = false;
      document.getElementById("mic-label").textContent = "Gravando...";
    } else {
      document.getElementById("btn-falar-localidade").textContent = "⏹️ Toque para parar";
    }
    status.textContent = "Gravando...";
  } catch (erro) {
    status.textContent = `Não foi possível usar o microfone: ${erro.message}`;
  }
}

function pararGravacao() {
  if (gravador && gravador.state !== "inactive") gravador.stop();
  document.getElementById("btn-gravar").hidden = false;
  document.getElementById("btn-parar").hidden = true;
  document.getElementById("btn-parar").disabled = true;
  document.getElementById("mic-label").textContent = "Toque para falar";
  document.getElementById("btn-falar-localidade").textContent = "🎙️ Falar minha localidade";
}

async function transcreverBlob(blob, proposito) {
  const status = proposito === "relato" ? document.getElementById("status-audio") : document.getElementById("status-localidade");
  status.textContent = "Transcrevendo...";
  const form = new FormData();
  form.append("arquivo", blob, `relato.${extensaoPorMime(blob.type)}`);
  const guardar = proposito === "relato" && document.getElementById("guardar-audio").checked;
  try {
    const r = await apiFetch(`/transcricoes?idioma=pt&guardar_original=${guardar ? "true" : "false"}`, { method: "POST", body: form });
    if (proposito === "relato") {
      meioRelato = "audio";
      relatoEl.value = r.texto;
      audioRef = r.audio_ref || "";
      transcricaoConfirmada = false;
      document.getElementById("audio-preview").src = URL.createObjectURL(blob);
      document.getElementById("audio-preview").hidden = false;
      document.getElementById("confirmacao-audio").hidden = false;
      document.getElementById("text-area-wrap").hidden = false;
      status.textContent = r.modo_teste ? "Modo de teste: a transcrição é simulada para demonstrar o fluxo. Ouça e confirme." : "Transcrição pronta. Ouça o que o sistema entendeu e confirme.";
    } else {
      document.getElementById("referencia-localidade").value = r.texto;
      status.textContent = "Localidade transcrita. Vamos conferir se corresponde a uma comunidade cadastrada.";
      await tentarIdentificarLocalidade(r.texto);
    }
  } catch (erro) {
    status.textContent = erro.message;
  }
}

function ouvirTexto() {
  const texto = relatoEl.value.trim();
  const status = document.getElementById("status-confirmacao");
  if (!texto) return;
  if (!("speechSynthesis" in window)) { status.textContent = "Leitura em voz alta não está disponível neste aparelho."; return; }
  speechSynthesis.cancel();
  const fala = new SpeechSynthesisUtterance(texto);
  fala.lang = "pt-BR"; fala.rate = 0.95;
  fala.onstart = () => status.textContent = "Lendo a transcrição...";
  fala.onend = () => status.textContent = "Se estiver certo, toque em ‘Está certo’.";
  speechSynthesis.speak(fala);
}

async function tentarIdentificarLocalidade(texto = relatoEl.value.trim()) {
  if (!texto) return null;
  const caixa = document.getElementById("localidade-ia");
  caixa.innerHTML = '<div class="estado-vazio">Verificando a localidade mencionada...</div>';
  try {
    const r = await apiFetch("/relatos/identificar-localidade", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texto }) });
    if (r.comunidade_id) {
      comunidadeSelect.value = String(r.comunidade_id);
      caixa.innerHTML = `<div class="ai-found"><span>✓</span><div><strong>Entendi: ${escaparHtml(r.comunidade_catalogada)}</strong><p>Confirme a comunidade abaixo antes de enviar.</p></div></div>`;
    } else if (r.referencia_localidade) {
      document.getElementById("referencia-localidade").value ||= r.referencia_localidade;
      caixa.innerHTML = `<div class="ai-found neutral"><span>?</span><div><strong>Encontrei uma referência de localidade</strong><p>${escaparHtml(r.referencia_localidade)}. Ainda preciso que você confirme a comunidade.</p></div></div>`;
    } else {
      caixa.innerHTML = `<div class="ai-found neutral"><span>?</span><div><strong>Não consegui identificar a comunidade.</strong><p>Você pode escolher, falar a localidade, usar o GPS ou enviar para revisão.</p></div></div>`;
    }
    return r;
  } catch (erro) {
    caixa.innerHTML = `<div class="ai-found neutral"><span>!</span><div><strong>Não foi possível analisar a localidade agora.</strong><p>Escolha manualmente ou envie para revisão.</p></div></div>`;
    return null;
  }
}

async function sugerirGPS() {
  const status = document.getElementById("status-localidade");
  if (!navigator.geolocation) { status.textContent = "GPS não disponível neste navegador."; return; }
  status.textContent = "Obtendo sua localização apenas para sugerir uma comunidade...";
  navigator.geolocation.getCurrentPosition(async pos => {
    try {
      const r = await apiFetch("/comunidades?apenas_publicas=true");
      const comCoords = (r.comunidades || []).filter(c => c.latitude_referencia != null && c.longitude_referencia != null);
      if (!comCoords.length) { status.textContent = "Ainda não há referências públicas com coordenadas suficientes para sugerir uma comunidade."; return; }
      const rad = x => x * Math.PI / 180;
      const dist = c => {
        const R = 6371, lat1 = rad(pos.coords.latitude), lat2 = rad(c.latitude_referencia), dlat = lat2-lat1, dlon = rad(c.longitude_referencia-pos.coords.longitude);
        const a = Math.sin(dlat/2)**2 + Math.cos(lat1)*Math.cos(lat2)*Math.sin(dlon/2)**2;
        return 2*R*Math.asin(Math.sqrt(a));
      };
      const perto = comCoords.map(c => [c, dist(c)]).sort((a,b) => a[1]-b[1])[0];
      comunidadeSelect.value = String(perto[0].id);
      status.textContent = `Sugestão: ${perto[0].nome} (${perto[1].toFixed(1)} km da referência pública). Confirme antes de enviar.`;
    } catch (erro) { status.textContent = erro.message; }
  }, erro => status.textContent = `Não foi possível usar o GPS: ${erro.message}`, { enableHighAccuracy: false, timeout: 8000 });
}

async function cadastrarComunidadeRapida() {
  const nome = document.getElementById("nova-comunidade-nome").value.trim();
  const municipio = document.getElementById("nova-comunidade-municipio").value.trim();
  const status = document.getElementById("status-cadastro-comunidade");
  if (!nome) { status.textContent = "Informe o nome da comunidade."; return; }
  try {
    const r = await apiFetch("/comunidades", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nome, municipio, grau_acesso: "nao_classificado", visibilidade_publica: false, origem_visibilidade: "privada", observacoes: "Referência cadastrada durante o envio de relato." }) });
    await carregarComunidades(); comunidadeSelect.value = String(r.comunidade.id); status.textContent = "Comunidade adicionada como referência privada.";
  } catch (erro) { status.textContent = erro.message; }
}

async function enviarRelato() {
  const texto = relatoEl.value.trim();
  const comunidadeId = Number(comunidadeSelect.value) || null;
  const pendente = document.getElementById("localidade-pendente").checked;
  if (texto.length < 5) { alert("Conte um pouco do que está acontecendo."); return; }
  if (meioRelato === "audio" && !transcricaoConfirmada) { alert("Antes de enviar, confirme o que o sistema entendeu."); return; }
  if (!comunidadeId && !pendente && !perfil) { alert("Confirme uma comunidade ou marque a opção de enviar para revisão de localidade."); return; }

  const dados = {
    comunidade_id: comunidadeId,
    relato: texto,
    meio_relato: meioRelato,
    referencia_localidade: document.getElementById("referencia-localidade").value.trim(),
    localidade_pendente: pendente,
    audio_ref: audioRef,
    consentimento_audio: Boolean(audioRef) && document.getElementById("guardar-audio").checked,
    origem: "web"
  };
  const headers = new Headers({ "Content-Type": "application/json" });
  if (tokenComunitario()) headers.set("Authorization", `Bearer ${tokenComunitario()}`);
  const botao = document.getElementById("btn-enviar"); botao.disabled = true; botao.textContent = "Enviando...";
  try {
    const r = await apiFetch("/relatorios", { method: "POST", headers, body: JSON.stringify(dados) });
    document.getElementById("relato-shell").hidden = true; document.getElementById("localidade-card").hidden = true;
    const sucesso = document.getElementById("sucesso"); sucesso.hidden = false;
    document.getElementById("sucesso-titulo").textContent = r.aguardando_localidade ? "Relato recebido para revisão" : "Relato recebido";
    document.getElementById("sucesso-texto").textContent = r.aguardando_localidade ? `Protocolo ${r.protocolo}. A fala foi preservada e a localidade ainda precisa ser confirmada.` : `Protocolo ${r.protocolo}. O relato foi preservado e organizado no fluxo de acompanhamento.`;
    document.getElementById("link-acompanhar").href = `acompanhar.html?protocolo=${encodeURIComponent(r.protocolo)}`;
  } catch (erro) { alert(`Não foi possível enviar: ${erro.message}`); }
  finally { botao.disabled = false; botao.textContent = "Enviar relato"; }
}

document.getElementById("btn-gravar").addEventListener("click", () => iniciarGravacao("relato"));
document.getElementById("btn-parar").addEventListener("click", pararGravacao);
document.getElementById("btn-escrever").addEventListener("click", () => { meioRelato = "texto"; document.getElementById("text-area-wrap").hidden = false; relatoEl.focus(); });
document.getElementById("btn-ouvir").addEventListener("click", ouvirTexto);
document.getElementById("btn-confirmar").addEventListener("click", () => { transcricaoConfirmada = true; document.getElementById("status-confirmacao").textContent = "Confirmado."; });
document.getElementById("btn-refazer").addEventListener("click", () => { relatoEl.value = ""; audioRef = ""; transcricaoConfirmada = false; document.getElementById("confirmacao-audio").hidden = true; document.getElementById("audio-preview").hidden = true; iniciarGravacao("relato"); });
document.getElementById("btn-continuar").addEventListener("click", async () => { if (relatoEl.value.trim().length < 5) { alert("Fale ou escreva o que está acontecendo primeiro."); return; } document.getElementById("localidade-card").hidden = false; document.getElementById("localidade-card").scrollIntoView({ behavior: "smooth" }); if (perfil?.comunidade_id) { comunidadeSelect.value = String(perfil.comunidade_id); document.getElementById("localidade-ia").innerHTML = `<div class="ai-found"><span>✓</span><div><strong>Comunidade do seu perfil: ${escaparHtml(perfil.comunidade_nome)}</strong><p>O relato será associado ao seu perfil comunitário.</p></div></div>`; } else await tentarIdentificarLocalidade(); });
document.getElementById("btn-gps").addEventListener("click", sugerirGPS);
document.getElementById("btn-falar-localidade").addEventListener("click", () => { if (gravador && gravador.state === "recording") pararGravacao(); else iniciarGravacao("localidade"); });
document.getElementById("btn-cadastrar-comunidade").addEventListener("click", cadastrarComunidadeRapida);
document.getElementById("btn-enviar").addEventListener("click", enviarRelato);
relatoEl.addEventListener("input", () => { if (meioRelato === "audio") transcricaoConfirmada = false; });

carregarComunidades().catch(erro => document.getElementById("status-localidade").textContent = erro.message);
const params = new URLSearchParams(location.search);
if (params.get("texto")) { relatoEl.value = params.get("texto"); document.getElementById("text-area-wrap").hidden = false; }

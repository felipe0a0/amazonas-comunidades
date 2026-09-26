const form = document.getElementById("form-acompanhar");
const resultado = document.getElementById("resultado-acompanhamento");
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const protocolo = document.getElementById("protocolo").value.trim();
  resultado.hidden = false;
  resultado.innerHTML = '<div class="estado-vazio">Consultando...</div>';
  try {
    const r = await apiFetch(`/publico/acompanhar/${encodeURIComponent(protocolo)}`);
    const demanda = r.demanda;
    resultado.innerHTML = `
      <p class="pequeno">${escaparHtml(r.protocolo)}</p>
      <h2>${demanda ? escaparHtml(demanda.titulo) : (r.localidade_pendente ? "Localidade pendente" : "Relato recebido")}</h2>
      <p>${r.localidade_pendente ? "O relato foi preservado e aguarda confirmação da localidade." : "Seu relato está registrado no sistema."}</p>
      ${demanda ? `<div class="demanda-meta"><span>${rotuloPrioridade(demanda.prioridade)}</span><span>${rotuloStatus(demanda.status)}</span></div>` : ""}
      ${demanda?.historico?.length ? `<div class="timeline compact-timeline">${demanda.historico.map(h => `<div class="timeline-item"><strong>${escaparHtml(rotuloStatus(h.status))}</strong><p>${escaparHtml(h.descricao || "Atualização registrada.")}</p><small>${formatarData(h.data_criacao)}</small></div>`).join("")}</div>` : ""}`;
  } catch (erro) {
    resultado.innerHTML = `<div class="estado-vazio">${escaparHtml(erro.message)}</div>`;
  }
});

const qp = new URLSearchParams(location.search).get("protocolo"); if (qp) { document.getElementById("protocolo").value = qp; form.requestSubmit(); }

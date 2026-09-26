async function carregarInicio() {
  try {
    const d = await apiFetch("/dashboard");
    document.getElementById("stat-comunidades").textContent = d.comunidades ?? 0;
    document.getElementById("stat-relatos").textContent = d.relatos ?? 0;
    document.getElementById("stat-demandas").textContent = d.demandas ?? 0;
    document.getElementById("stat-atendimento").textContent = d.em_atendimento ?? 0;
  } catch (erro) {
    console.warn("Dashboard público indisponível:", erro);
  }
}
carregarInicio();

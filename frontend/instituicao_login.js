const select = document.getElementById("instituicao-select");
const status = document.getElementById("login-status");
async function carregar() {
  try { const r = await apiFetch("/instituicoes"); select.innerHTML = '<option value="">Selecione</option>' + r.instituicoes.map(i => `<option value="${i.id}">${escaparHtml(i.nome)}</option>`).join(""); }
  catch (erro) { status.textContent = erro.message; }
}
document.getElementById("btn-login-instituicao").addEventListener("click", async () => {
  const id = Number(select.value); if (!id) return status.textContent = "Selecione uma organização.";
  try { const r = await apiFetch("/institucional/login-demo", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({instituicao_id:id}) }); sessionStorage.setItem("ac_token",r.token); sessionStorage.setItem("ac_instituicao",JSON.stringify(r.instituicao)); location.href="instituicao.html"; }
  catch (erro) { status.textContent = erro.message; }
});
carregar();

import mimetypes
import secrets
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from agente import formalizar_relato, identificar_localidade
from banco import (
    atualizar_encaminhamento,
    atualizar_texto_formalizado,
    criar_banco,
    criar_comunidade,
    criar_mensagem_comunidade,
    criar_perfil_comunitario,
    estatisticas_dashboard,
    listar_comunidades,
    listar_comunidades_da_instituicao,
    listar_demandas,
    listar_demandas_do_perfil,
    listar_instituicoes,
    listar_mensagens_comunidade,
    listar_modelos_institucionais,
    listar_notificacoes_comunidade,
    listar_perfis_comunitarios_demo,
    listar_relatos_do_perfil,
    obter_comunidade,
    obter_demanda,
    obter_demanda_completa,
    obter_demanda_publica,
    obter_encaminhamento,
    obter_encaminhamento_ativo,
    obter_perfil_comunitario,
    obter_relato,
    obter_relato_com_demanda,
    obter_relato_por_protocolo,
    perfil_pode_acessar_demanda,
    registrar_log_ia,
    resumo_comunidade_periodo,
    salvar_modelo_institucional,
    salvar_relato_bruto,
)
from demanda_service import (
    avaliar_roteamento,
    encaminhar_proxima,
    preparar_para_encaminhamento,
    processar_relato,
    registrar_manifestacao,
    sugerir_instituicoes,
)
from provedor_ia import ProvedorIAError, info_provedor
from relatorio_service import gerar_relatorio_formal
from schemas import (
    AtualizacaoEncaminhamento,
    CadastroComunitarioDemo,
    FormalizacaoRelatoEntrada,
    IdentificacaoLocalidadeEntrada,
    InstituicaoLoginDemo,
    LoginComunitarioDemo,
    ManifestacaoComunitariaEntrada,
    ManifestacaoEntrada,
    MensagemInstitucionalEntrada,
    NovaComunidade,
    NovoRelato,
    PrepararEncaminhamento,
)
from transcricao_service import caminho_audio_ref, transcrever_upload


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
MODELOS_DIR = BASE_DIR / "dados" / "modelos"
SESSOES_INSTITUCIONAIS: dict[str, int] = {}
SESSOES_COMUNITARIAS: dict[str, int] = {}

app = FastAPI(
    title="Amazonas Comunidades API",
    version="final-prototipo",
    description=(
        "Protótipo para relato comunitário por voz/texto, triagem por IA, consolidação, "
        "validação comunitária, roteamento institucional e acompanhamento."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

criar_banco()


def _comunidade_para_api(item: dict | None):
    if not item:
        return None
    seguro = dict(item)
    seguro.pop("observacoes", None)
    seguro.pop("quantidade_demandas", None)
    seguro.pop("quantidade_relatos", None)
    visivel = bool(seguro.get("visibilidade_publica"))
    if not visivel:
        seguro["latitude_referencia"] = None
        seguro["longitude_referencia"] = None
        seguro["area_geojson"] = None
        seguro["fonte_url"] = ""
        seguro["fonte_dado"] = ""
    return seguro


def _instituicao_da_sessao(authorization: str | None):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sessão institucional necessária.")
    token = authorization.split(" ", 1)[1].strip()
    instituicao_id = SESSOES_INSTITUCIONAIS.get(token)
    if not instituicao_id:
        raise HTTPException(status_code=401, detail="Sessão institucional inválida ou encerrada.")
    instituicao = next((i for i in listar_instituicoes() if i["id"] == instituicao_id), None)
    if not instituicao:
        raise HTTPException(status_code=401, detail="Instituição da sessão não está disponível.")
    return instituicao


def _perfil_da_sessao(authorization: str | None, obrigatorio: bool = True):
    if not authorization or not authorization.lower().startswith("bearer "):
        if obrigatorio:
            raise HTTPException(status_code=401, detail="Acesso comunitário necessário.")
        return None
    token = authorization.split(" ", 1)[1].strip()
    perfil_id = SESSOES_COMUNITARIAS.get(token)
    if not perfil_id:
        if obrigatorio:
            raise HTTPException(status_code=401, detail="Sessão comunitária inválida ou encerrada.")
        return None
    perfil = obter_perfil_comunitario(perfil_id)
    if not perfil:
        raise HTTPException(status_code=401, detail="Perfil comunitário não está disponível.")
    return perfil


def _instituicao_pode_acessar_demanda(instituicao: dict, demanda: dict) -> bool:
    areas = set(instituicao.get("areas") or [])
    if demanda.get("categoria") in areas or "outro" in areas:
        return True
    ativo = obter_encaminhamento_ativo(demanda["id"])
    return bool(ativo and ativo.get("instituicao_id") == instituicao["id"])


def _registrar_formalizacao(relato_id: int, texto_original: str):
    try:
        resultado, meta = formalizar_relato(texto_original)
        atualizar_texto_formalizado(relato_id, resultado.get("texto_formal") or "")
        registrar_log_ia(
            operacao="formalizacao_relato",
            modelo=meta["modelo"],
            prompt_version=meta.get("prompt_version", "formalizacao-v1"),
            sucesso=True,
            latencia_ms=meta.get("latencia_ms"),
            relato_id=relato_id,
            tokens_entrada=meta.get("tokens_entrada"),
            tokens_saida=meta.get("tokens_saida"),
            trace_id=meta.get("trace_id"),
        )
    except Exception as erro:
        registrar_log_ia(
            operacao="formalizacao_relato",
            modelo=info_provedor().get("modelo_ia", "desconhecido"),
            prompt_version="formalizacao-v1",
            sucesso=False,
            latencia_ms=None,
            erro=str(erro),
            relato_id=relato_id,
        )


@app.get("/", include_in_schema=False)
def inicio():
    return RedirectResponse(url="/app/index.html")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mensagem": "API do Amazonas Comunidades funcionando.",
        "agentes_ativos": ["triagem", "roteamento"],
        **info_provedor(),
    }


@app.get("/dashboard")
def dashboard():
    return estatisticas_dashboard()


# ---------- Catálogo territorial ----------

@app.get("/comunidades")
def comunidades(apenas_publicas: bool = False):
    itens = listar_comunidades(apenas_publicas=apenas_publicas)
    return {"comunidades": [_comunidade_para_api(item) for item in itens]}


@app.post("/comunidades", status_code=201)
def cadastrar_comunidade(entrada: NovaComunidade):
    dados = entrada.model_dump()
    try:
        comunidade_id, criada = criar_comunidade(dados)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    return {
        "mensagem": "Comunidade cadastrada." if criada else "Comunidade já existente no catálogo.",
        "criada": criada,
        "comunidade": _comunidade_para_api(obter_comunidade(comunidade_id)),
    }


@app.get("/comunidades/{comunidade_id}")
def comunidade(comunidade_id: int):
    item = obter_comunidade(comunidade_id)
    if not item:
        raise HTTPException(status_code=404, detail="Comunidade não encontrada.")
    return _comunidade_para_api(item)


# ---------- Voz, linguagem livre e identificação de localidade ----------

@app.post("/transcricoes")
async def transcrever_relato(
    arquivo: UploadFile = File(...),
    idioma: str = "pt",
    guardar_original: bool = False,
):
    try:
        texto, meta = await transcrever_upload(
            arquivo,
            idioma=idioma,
            preservar_original=guardar_original,
        )
        registrar_log_ia(
            operacao="transcricao_audio",
            modelo=meta["modelo"],
            prompt_version="audio-v2",
            sucesso=True,
            latencia_ms=meta["latencia_ms"],
            tokens_entrada=meta.get("tokens_entrada"),
            tokens_saida=meta.get("tokens_saida"),
            trace_id=meta.get("trace_id"),
        )
        return {
            "texto": texto,
            "audio_ref": meta.get("audio_ref"),
            "provedor": meta.get("provedor"),
            "modelo": meta.get("modelo"),
            "modo_teste": meta.get("modo_teste", False),
            "aviso": (
                "Modo de teste: a transcrição é simulada e não representa o conteúdo real do áudio."
                if meta.get("modo_teste")
                else (
                    "O áudio original foi guardado porque houve consentimento para conferência restrita."
                    if meta.get("audio_ref")
                    else "O áudio original não foi guardado. A transcrição deve ser confirmada antes do envio."
                )
            ),
        }
    except (ValueError, ProvedorIAError) as erro:
        registrar_log_ia(
            operacao="transcricao_audio",
            modelo=info_provedor().get("modelo_transcricao", "desconhecido"),
            prompt_version="audio-v2",
            sucesso=False,
            latencia_ms=None,
            erro=str(erro),
        )
        raise HTTPException(status_code=422, detail=str(erro)) from erro
    except Exception as erro:
        registrar_log_ia(
            operacao="transcricao_audio",
            modelo=info_provedor().get("modelo_transcricao", "desconhecido"),
            prompt_version="audio-v2",
            sucesso=False,
            latencia_ms=None,
            erro=str(erro),
        )
        raise HTTPException(status_code=502, detail="Falha ao transcrever o áudio. O relato pode ser digitado.") from erro


@app.post("/textos/formalizar-relato")
def formalizar_texto_relato(entrada: FormalizacaoRelatoEntrada):
    try:
        resultado, meta = formalizar_relato(entrada.texto)
        return {**resultado, "provedor": meta.get("provedor"), "modo_teste": meta.get("modo_teste", False)}
    except ProvedorIAError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro


@app.post("/relatos/identificar-localidade")
def localizar_relato(entrada: IdentificacaoLocalidadeEntrada):
    try:
        comunidades_catalogo = listar_comunidades()
        resultado, meta = identificar_localidade(entrada.texto, comunidades_catalogo)
        nome = (resultado.get("comunidade_mencionada") or "").strip().casefold()
        encontrada = None
        if nome:
            encontrada = next((c for c in comunidades_catalogo if c["nome"].strip().casefold() == nome), None)
        registrar_log_ia(
            operacao="identificacao_localidade",
            modelo=meta.get("modelo", "desconhecido"),
            prompt_version=meta.get("prompt_version", "localidade-v1"),
            sucesso=True,
            latencia_ms=meta.get("latencia_ms"),
            tokens_entrada=meta.get("tokens_entrada"),
            tokens_saida=meta.get("tokens_saida"),
            trace_id=meta.get("trace_id"),
        )
        return {
            **resultado,
            "comunidade_id": encontrada["id"] if encontrada else None,
            "comunidade_catalogada": encontrada["nome"] if encontrada else "",
            "modo_teste": meta.get("modo_teste", False),
        }
    except ProvedorIAError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro


# ---------- Relatos e acompanhamento ----------

@app.post("/relatorios")
def receber_relatorio(relatorio: NovoRelato, authorization: str | None = Header(default=None)):
    dados = relatorio.model_dump()
    if dados.get("data_ocorrencia") is not None:
        dados["data_ocorrencia"] = dados["data_ocorrencia"].isoformat()

    perfil = _perfil_da_sessao(authorization, obrigatorio=False)
    if perfil:
        dados["perfil_id"] = perfil["id"]
        dados["comunidade_id"] = perfil["comunidade_id"]
        dados["comunidade"] = perfil["comunidade_nome"]
        dados["localidade_pendente"] = False

    if dados.get("audio_ref") and not dados.get("consentimento_audio"):
        dados["audio_ref"] = ""
    if dados.get("audio_ref") and not caminho_audio_ref(dados["audio_ref"]):
        dados["audio_ref"] = ""

    try:
        relato_id, protocolo = salvar_relato_bruto(dados)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro

    _registrar_formalizacao(relato_id, dados["relato"])
    relato_salvo = obter_relato(relato_id)
    if relato_salvo and relato_salvo.get("localidade_pendente"):
        return {
            "mensagem": "Relato recebido. A localidade ficou pendente para revisão.",
            "protocolo": protocolo,
            "relato_id": relato_id,
            "demanda_id": None,
            "processado": False,
            "aguardando_localidade": True,
        }

    resultado = processar_relato(relato_id)
    return {
        "mensagem": "Relato recebido e preservado no sistema.",
        "protocolo": protocolo,
        **resultado,
    }


@app.post("/relatorios/{relato_id}/reprocessar")
def reprocessar_relatorio(relato_id: int):
    relato = obter_relato(relato_id)
    if not relato:
        raise HTTPException(status_code=404, detail="Relato não encontrado.")
    if relato.get("status_processamento") != "erro_ia":
        raise HTTPException(status_code=409, detail="Este relato não está aguardando reprocessamento de IA.")
    return {"mensagem": "Tentativa de reprocessamento concluída.", **processar_relato(relato_id)}


@app.get("/publico/acompanhar/{protocolo}")
def acompanhar_protocolo(protocolo: str):
    relato = obter_relato_por_protocolo(protocolo)
    if not relato:
        raise HTTPException(status_code=404, detail="Protocolo não encontrado.")
    item = {
        "protocolo": relato["protocolo"],
        "data_recebimento": relato["data_recebimento"],
        "status_processamento": relato["status_processamento"],
        "localidade_pendente": relato.get("localidade_pendente", False),
    }
    if relato.get("comunidade_id"):
        item["comunidade"] = relato["comunidade"]
    with_demanda = obter_relato_com_demanda(relato["id"])
    if with_demanda and with_demanda.get("demanda_id"):
        demanda = obter_demanda_publica(with_demanda["demanda_id"])
        if demanda:
            item["demanda"] = {
                "protocolo": demanda["protocolo"],
                "titulo": demanda["titulo"],
                "prioridade": demanda["prioridade"],
                "status": demanda["status"],
                "data_atualizacao": demanda["data_atualizacao"],
                "historico": demanda.get("historico", []),
            }
    return item


@app.get("/publico/demandas")
def demandas_publicas_bloqueadas():
    raise HTTPException(status_code=403, detail="Demandas comunitárias não são listadas publicamente. Use seu perfil ou um protocolo de acompanhamento.")


@app.get("/publico/demandas/{demanda_id}")
def demanda_publica_bloqueada(demanda_id: int):
    raise HTTPException(status_code=403, detail="Detalhes de demanda exigem acesso comunitário ou institucional.")


# ---------- Área comunitária demonstrativa ----------

@app.get("/comunitario/perfis-demo")
def perfis_demo():
    return {"perfis": listar_perfis_comunitarios_demo(), "aviso": "Acesso demonstrativo; autenticação real fica para produção."}


@app.post("/comunitario/cadastro-demo", status_code=201)
def cadastrar_perfil_demo(entrada: CadastroComunitarioDemo):
    try:
        perfil_id = criar_perfil_comunitario(
            entrada.nome_exibicao,
            entrada.comunidade_id,
            entrada.papel,
            entrada.funcao_informada,
        )
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    token = secrets.token_urlsafe(24)
    SESSOES_COMUNITARIAS[token] = perfil_id
    return {
        "token": token,
        "perfil": obter_perfil_comunitario(perfil_id),
        "aviso": "Perfil de demonstração. Representantes ainda não passam por verificação externa nesta versão.",
    }


@app.post("/comunitario/login-demo")
def login_comunitario_demo(entrada: LoginComunitarioDemo):
    perfil = obter_perfil_comunitario(entrada.perfil_id)
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    token = secrets.token_urlsafe(24)
    SESSOES_COMUNITARIAS[token] = perfil["id"]
    return {"token": token, "perfil": perfil, "aviso": "Sessão comunitária demonstrativa."}


@app.get("/comunitario/me")
def comunitario_me(authorization: str | None = Header(default=None)):
    return _perfil_da_sessao(authorization)


@app.get("/comunitario/meus-relatos")
def meus_relatos(authorization: str | None = Header(default=None)):
    perfil = _perfil_da_sessao(authorization)
    itens = listar_relatos_do_perfil(perfil["id"])
    return {
        "relatos": [
            {
                "id": r["id"],
                "protocolo": r["protocolo"],
                "data_recebimento": r["data_recebimento"],
                "status_processamento": r["status_processamento"],
                "demanda_id": r.get("demanda_id"),
                "demanda_protocolo": r.get("demanda_protocolo"),
                "demanda_titulo": r.get("demanda_titulo"),
                "demanda_status": r.get("demanda_status"),
                "demanda_prioridade": r.get("demanda_prioridade"),
            }
            for r in itens
        ]
    }


@app.get("/comunitario/demandas")
def demandas_comunitarias(authorization: str | None = Header(default=None)):
    perfil = _perfil_da_sessao(authorization)
    return {"demandas": listar_demandas_do_perfil(perfil), "perfil": perfil}


@app.get("/comunitario/demandas/{demanda_id}")
def demanda_comunitaria(demanda_id: int, authorization: str | None = Header(default=None)):
    perfil = _perfil_da_sessao(authorization)
    if not perfil_pode_acessar_demanda(perfil, demanda_id):
        raise HTTPException(status_code=403, detail="Esta demanda não pertence ao seu contexto comunitário.")
    demanda = obter_demanda_publica(demanda_id)
    if not demanda:
        raise HTTPException(status_code=404, detail="Demanda não encontrada.")
    if perfil["papel"] == "representante":
        completa = obter_demanda(demanda_id)
        demanda["informacoes_faltantes"] = completa.get("informacoes_faltantes", []) if completa else []
        demanda["divergencias"] = completa.get("divergencias", []) if completa else []
        demanda["pode_manifestar"] = True
    else:
        demanda["pode_manifestar"] = False
    return demanda


@app.post("/comunitario/demandas/{demanda_id}/manifestacoes")
def manifestacao_comunitaria(
    demanda_id: int,
    entrada: ManifestacaoComunitariaEntrada,
    authorization: str | None = Header(default=None),
):
    perfil = _perfil_da_sessao(authorization)
    if perfil["papel"] != "representante":
        raise HTTPException(status_code=403, detail="Somente o perfil de representante pode registrar manifestação comunitária.")
    if not perfil_pode_acessar_demanda(perfil, demanda_id):
        raise HTTPException(status_code=403, detail="Esta demanda pertence a outra comunidade.")
    autor = perfil["nome_exibicao"]
    if perfil.get("funcao_informada"):
        autor += f" — {perfil['funcao_informada']}"
    try:
        manifestacao_id = registrar_manifestacao(demanda_id, entrada.tipo, autor, entrada.texto)
    except ValueError as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro
    return {"mensagem": "Manifestação registrada sem apagar o relato original.", "id": manifestacao_id}


@app.get("/comunitario/notificacoes")
def notificacoes_comunitarias(authorization: str | None = Header(default=None)):
    perfil = _perfil_da_sessao(authorization)
    itens = listar_notificacoes_comunidade(perfil["comunidade_id"], 100)
    if perfil["papel"] == "morador":
        itens = [
            {
                "id": item["id"],
                "status": item["status"],
                "descricao": item.get("descricao") or "Há uma atualização registrada na comunidade.",
                "data_criacao": item["data_criacao"],
                "titulo": "Atualização comunitária",
            }
            for item in itens
        ]
    return {"notificacoes": itens}


@app.get("/comunitario/mensagens")
def mensagens_comunitarias(authorization: str | None = Header(default=None)):
    perfil = _perfil_da_sessao(authorization)
    return {"mensagens": listar_mensagens_comunidade(perfil["comunidade_id"], apenas_publicas=True, limite=100)}


# Compatibilidade: manifestação antiga agora exige representante autenticado.
@app.post("/demandas/{demanda_id}/manifestacoes")
def manifestar_compatibilidade(
    demanda_id: int,
    entrada: ManifestacaoEntrada,
    authorization: str | None = Header(default=None),
):
    perfil = _perfil_da_sessao(authorization)
    if perfil["papel"] != "representante" or not perfil_pode_acessar_demanda(perfil, demanda_id):
        raise HTTPException(status_code=403, detail="Manifestação exige representante da comunidade da demanda.")
    manifestacao_id = registrar_manifestacao(demanda_id, entrada.tipo, perfil["nome_exibicao"], entrada.texto)
    return {"mensagem": "Manifestação registrada.", "id": manifestacao_id}


@app.get("/demandas")
def demandas_compatibilidade():
    raise HTTPException(status_code=403, detail="Use a área comunitária ou institucional.")


@app.get("/demandas/{demanda_id}")
def demanda_compatibilidade(demanda_id: int):
    raise HTTPException(status_code=403, detail="Use a área comunitária ou institucional.")


# ---------- Área institucional demonstrativa ----------

@app.get("/instituicoes")
def instituicoes(categoria: str | None = None):
    return {"instituicoes": listar_instituicoes(categoria)}


@app.post("/institucional/login-demo")
def login_institucional_demo(entrada: InstituicaoLoginDemo):
    instituicao = next((i for i in listar_instituicoes() if i["id"] == entrada.instituicao_id), None)
    if not instituicao:
        raise HTTPException(status_code=404, detail="Instituição não encontrada.")
    token = secrets.token_urlsafe(24)
    SESSOES_INSTITUCIONAIS[token] = instituicao["id"]
    return {
        "token": token,
        "instituicao": instituicao,
        "aviso": "Sessão demonstrativa. Não substitui autenticação institucional de produção.",
    }


@app.get("/institucional/demandas")
def demandas_institucionais(
    authorization: str | None = Header(default=None),
    limite: int = Query(default=500, ge=1, le=1000),
):
    instituicao = _instituicao_da_sessao(authorization)
    areas = set(instituicao.get("areas") or [])
    todas = listar_demandas(limite=limite)
    compativeis = [d for d in todas if d["categoria"] in areas or "outro" in areas]
    return {"demandas": compativeis, "instituicao": instituicao}


@app.get("/institucional/demandas/{demanda_id}")
def demanda_institucional(demanda_id: int, authorization: str | None = Header(default=None)):
    instituicao = _instituicao_da_sessao(authorization)
    item = obter_demanda_completa(demanda_id)
    if not item:
        raise HTTPException(status_code=404, detail="Demanda não encontrada.")
    if not _instituicao_pode_acessar_demanda(instituicao, item):
        raise HTTPException(status_code=403, detail="A demanda não está nas áreas desta instituição.")
    for relato in item.get("relatos", []):
        relato["audio_disponivel"] = bool(relato.get("audio_ref") and relato.get("consentimento_audio"))
        relato.pop("audio_ref", None)
    return item


@app.get("/institucional/comunidades")
def comunidades_institucionais(authorization: str | None = Header(default=None)):
    instituicao = _instituicao_da_sessao(authorization)
    return {"comunidades": listar_comunidades_da_instituicao(instituicao.get("areas") or [])}


@app.get("/institucional/comunidades/{comunidade_id}/resumo")
def resumo_institucional_comunidade(
    comunidade_id: int,
    periodo: str = Query(default="semanal", pattern="^(semanal|mensal)$"),
    authorization: str | None = Header(default=None),
):
    instituicao = _instituicao_da_sessao(authorization)
    comunidades = {c["id"] for c in listar_comunidades_da_instituicao(instituicao.get("areas") or [])}
    if comunidade_id not in comunidades:
        raise HTTPException(status_code=403, detail="Esta comunidade não está no contexto de trabalho da instituição.")
    dias = 7 if periodo == "semanal" else 30
    return {"comunidade": obter_comunidade(comunidade_id), "periodo": periodo, **resumo_comunidade_periodo(comunidade_id, dias)}


@app.post("/institucional/modelos", status_code=201)
async def anexar_modelo_institucional(
    arquivo: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    instituicao = _instituicao_da_sessao(authorization)
    nome = Path(arquivo.filename or "modelo").name
    extensao = Path(nome).suffix.lower()
    if extensao not in {".docx", ".pdf", ".txt", ".xlsx"}:
        raise HTTPException(status_code=422, detail="Use DOCX, PDF, TXT ou XLSX como modelo de referência.")
    conteudo = await arquivo.read()
    if not conteudo or len(conteudo) > 8 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="O modelo deve ter entre 1 byte e 8 MB.")
    pasta = MODELOS_DIR / str(instituicao["id"])
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo_ref = f"{uuid.uuid4().hex}{extensao}"
    (pasta / arquivo_ref).write_bytes(conteudo)
    modelo_id = salvar_modelo_institucional(instituicao["id"], nome, arquivo_ref)
    return {
        "id": modelo_id,
        "nome_original": nome,
        "mensagem": "Modelo de referência salvo. O preenchimento adaptativo completo permanece como próxima evolução do protótipo.",
    }


@app.get("/institucional/modelos")
def modelos_institucionais(authorization: str | None = Header(default=None)):
    instituicao = _instituicao_da_sessao(authorization)
    return {"modelos": listar_modelos_institucionais(instituicao["id"])}


@app.get("/institucional/relatos/{relato_id}/audio")
def audio_original_institucional(relato_id: int, authorization: str | None = Header(default=None)):
    instituicao = _instituicao_da_sessao(authorization)
    relato = obter_relato_com_demanda(relato_id)
    if not relato or not relato.get("demanda_id"):
        raise HTTPException(status_code=404, detail="Áudio não associado a uma demanda.")
    demanda = obter_demanda(relato["demanda_id"])
    if not demanda or not _instituicao_pode_acessar_demanda(instituicao, demanda):
        raise HTTPException(status_code=403, detail="A instituição não pode acessar este relato.")
    if not relato.get("consentimento_audio") or not relato.get("audio_ref"):
        raise HTTPException(status_code=404, detail="O áudio original não foi retido com consentimento.")
    caminho = caminho_audio_ref(relato["audio_ref"])
    if not caminho:
        raise HTTPException(status_code=404, detail="Arquivo de áudio não encontrado.")
    tipo, _ = mimetypes.guess_type(caminho.name)
    return FileResponse(caminho, media_type=tipo or "application/octet-stream", filename=f"relato-{relato['protocolo']}{caminho.suffix}")


@app.post("/institucional/demandas/{demanda_id}/preparar-encaminhamento")
def preparar(
    demanda_id: int,
    entrada: PrepararEncaminhamento,
    authorization: str | None = Header(default=None),
):
    instituicao = _instituicao_da_sessao(authorization)
    demanda = obter_demanda(demanda_id)
    if not demanda:
        raise HTTPException(status_code=404, detail="Demanda não encontrada.")
    if not _instituicao_pode_acessar_demanda(instituicao, demanda):
        raise HTTPException(status_code=403, detail="A demanda não está nas áreas desta instituição.")
    try:
        preparar_para_encaminhamento(demanda_id, entrada.descricao)
    except ValueError as erro:
        raise HTTPException(status_code=409, detail=str(erro)) from erro
    return {"mensagem": "Demanda marcada como pronta para encaminhamento."}


@app.get("/institucional/demandas/{demanda_id}/instituicoes-sugeridas")
def instituicoes_sugeridas(demanda_id: int, authorization: str | None = Header(default=None)):
    instituicao = _instituicao_da_sessao(authorization)
    demanda = obter_demanda(demanda_id)
    if not demanda:
        raise HTTPException(status_code=404, detail="Demanda não encontrada.")
    if not _instituicao_pode_acessar_demanda(instituicao, demanda):
        raise HTTPException(status_code=403, detail="A demanda não está nas áreas desta instituição.")
    return {"instituicoes": sugerir_instituicoes(demanda_id)}


@app.post("/institucional/demandas/{demanda_id}/avaliar-roteamento")
def avaliar_rota(demanda_id: int, authorization: str | None = Header(default=None)):
    instituicao = _instituicao_da_sessao(authorization)
    demanda = obter_demanda(demanda_id)
    if not demanda:
        raise HTTPException(status_code=404, detail="Demanda não encontrada.")
    if not _instituicao_pode_acessar_demanda(instituicao, demanda):
        raise HTTPException(status_code=403, detail="A demanda não está nas áreas desta instituição.")
    try:
        return avaliar_roteamento(demanda_id)
    except (ValueError, ProvedorIAError) as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro


@app.post("/institucional/demandas/{demanda_id}/encaminhar-proxima")
def encaminhar(demanda_id: int, authorization: str | None = Header(default=None)):
    instituicao = _instituicao_da_sessao(authorization)
    demanda = obter_demanda(demanda_id)
    if not demanda:
        raise HTTPException(status_code=404, detail="Demanda não encontrada.")
    if not _instituicao_pode_acessar_demanda(instituicao, demanda):
        raise HTTPException(status_code=403, detail="A demanda não está nas áreas desta instituição.")
    try:
        return encaminhar_proxima(demanda_id)
    except (ValueError, ProvedorIAError) as erro:
        raise HTTPException(status_code=409, detail=str(erro)) from erro


@app.patch("/institucional/encaminhamentos/{encaminhamento_id}")
def atualizar_status(
    encaminhamento_id: int,
    entrada: AtualizacaoEncaminhamento,
    authorization: str | None = Header(default=None),
):
    instituicao = _instituicao_da_sessao(authorization)
    encaminhamento = obter_encaminhamento(encaminhamento_id)
    if not encaminhamento:
        raise HTTPException(status_code=404, detail="Encaminhamento não encontrado.")
    if encaminhamento["instituicao_id"] != instituicao["id"]:
        raise HTTPException(status_code=403, detail="Este encaminhamento pertence a outra instituição.")
    try:
        demanda_id = atualizar_encaminhamento(
            encaminhamento_id,
            entrada.status,
            entrada.motivo,
            entrada.descricao_publica,
        )
    except ValueError as erro:
        raise HTTPException(status_code=409, detail=str(erro)) from erro
    return {"mensagem": "Status atualizado.", "demanda_id": demanda_id, "instituicao": instituicao["nome"]}


@app.get("/institucional/demandas/{demanda_id}/relatorio-formal")
def relatorio_formal(demanda_id: int, authorization: str | None = Header(default=None)):
    instituicao = _instituicao_da_sessao(authorization)
    demanda = obter_demanda(demanda_id)
    if not demanda:
        raise HTTPException(status_code=404, detail="Demanda não encontrada.")
    if not _instituicao_pode_acessar_demanda(instituicao, demanda):
        raise HTTPException(status_code=403, detail="A demanda não está nas áreas desta instituição.")
    item = gerar_relatorio_formal(demanda_id)
    if not item:
        raise HTTPException(status_code=404, detail="Demanda não encontrada.")
    return item


@app.post("/institucional/demandas/{demanda_id}/mensagens")
def enviar_mensagem_comunidade(
    demanda_id: int,
    entrada: MensagemInstitucionalEntrada,
    authorization: str | None = Header(default=None),
):
    instituicao = _instituicao_da_sessao(authorization)
    demanda = obter_demanda(demanda_id)
    if not demanda:
        raise HTTPException(status_code=404, detail="Demanda não encontrada.")
    if not _instituicao_pode_acessar_demanda(instituicao, demanda):
        raise HTTPException(status_code=403, detail="A demanda não está nas áreas desta instituição.")
    mensagem_id = criar_mensagem_comunidade(
        demanda["comunidade_id"],
        entrada.titulo,
        entrada.texto,
        demanda_id=demanda_id,
        instituicao_id=instituicao["id"],
        tipo=entrada.tipo,
        publica=entrada.publica,
    )
    return {"mensagem": "Mensagem registrada para a comunidade.", "id": mensagem_id}


app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

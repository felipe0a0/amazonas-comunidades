import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("TRANSCRIPTION_PROVIDER", "mock")

import banco
from fastapi.testclient import TestClient
from api import app, SESSOES_COMUNITARIAS, SESSOES_INSTITUCIONAIS


def preparar_banco_temporario(tmp_path, monkeypatch):
    caminho = tmp_path / "teste.db"
    monkeypatch.setattr(banco, "DB_PATH", caminho)
    SESSOES_COMUNITARIAS.clear()
    SESSOES_INSTITUCIONAIS.clear()
    banco.criar_banco()
    return TestClient(app)


def criar_comunidade(client, nome="Comunidade de Teste", municipio="Manaus"):
    resposta = client.post(
        "/comunidades",
        json={
            "nome": nome,
            "municipio": municipio,
            "grau_acesso": "medio",
            "visibilidade_publica": False,
            "origem_visibilidade": "privada",
        },
    )
    assert resposta.status_code in (200, 201), resposta.text
    return resposta.json()["comunidade"]["id"]


def criar_perfil(client, comunidade_id, papel="morador", nome="Pessoa de teste"):
    resposta = client.post(
        "/comunitario/cadastro-demo",
        json={
            "nome_exibicao": nome,
            "comunidade_id": comunidade_id,
            "papel": papel,
            "funcao_informada": "liderança local" if papel == "representante" else "",
        },
    )
    assert resposta.status_code == 201, resposta.text
    dados = resposta.json()
    return dados["perfil"], {"Authorization": f"Bearer {dados['token']}"}


def enviar_relato(client, comunidade_id, relato, headers=None):
    resposta = client.post(
        "/relatorios",
        headers=headers or {},
        json={
            "comunidade_id": comunidade_id,
            "relato": relato,
            "meio_relato": "texto",
        },
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def login_instituicao(client, instituicao_id):
    resposta = client.post("/institucional/login-demo", json={"instituicao_id": instituicao_id})
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": f"Bearer {resposta.json()['token']}"}


def test_seed_tumbira_e_origem_publica(tmp_path, monkeypatch):
    client = preparar_banco_temporario(tmp_path, monkeypatch)
    resposta = client.get("/comunidades?apenas_publicas=true")
    assert resposta.status_code == 200
    tumbira = next(c for c in resposta.json()["comunidades"] if c["nome"] == "Comunidade do Tumbira")
    assert tumbira["municipio"] == "Iranduba - AM"
    assert tumbira["origem_visibilidade"] == "fonte_publica"
    assert tumbira["latitude_referencia"] is None
    assert tumbira["longitude_referencia"] is None


def test_ia_identifica_tumbira_sem_inventar_gps(tmp_path, monkeypatch):
    client = preparar_banco_temporario(tmp_path, monkeypatch)
    resposta = client.post(
        "/relatos/identificar-localidade",
        json={"texto": "Eu sou da comunidade Tumbira e o motor de água parou."},
    )
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["comunidade_catalogada"] == "Comunidade do Tumbira"
    assert dados["comunidade_id"]


def test_relato_sem_localidade_fica_pendente_sem_criar_demanda(tmp_path, monkeypatch):
    client = preparar_banco_temporario(tmp_path, monkeypatch)
    resposta = client.post(
        "/relatorios",
        json={
            "relato": "Estamos sem água desde ontem e o motor parou.",
            "localidade_pendente": True,
            "referencia_localidade": "perto do rio",
        },
    )
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["aguardando_localidade"] is True
    assert dados["demanda_id"] is None
    acompanhamento = client.get(f"/publico/acompanhar/{dados['protocolo']}").json()
    assert acompanhamento["localidade_pendente"] is True


def test_demanda_nao_e_listada_publicamente(tmp_path, monkeypatch):
    client = preparar_banco_temporario(tmp_path, monkeypatch)
    comunidade_id = criar_comunidade(client)
    dados = enviar_relato(client, comunidade_id, "Estamos sem água desde ontem porque o motor parou.")
    assert client.get("/publico/demandas").status_code == 403
    assert client.get(f"/publico/demandas/{dados['demanda_id']}").status_code == 403
    acompanhamento = client.get(f"/publico/acompanhar/{dados['protocolo']}")
    assert acompanhamento.status_code == 200
    assert "mensagem_original" not in acompanhamento.json()


def test_morador_ve_apenas_proprios_relatos_e_nao_manifesta(tmp_path, monkeypatch):
    client = preparar_banco_temporario(tmp_path, monkeypatch)
    comunidade_id = criar_comunidade(client)
    _, morador_headers = criar_perfil(client, comunidade_id, "morador", "Maria")
    outro_perfil, outro_headers = criar_perfil(client, comunidade_id, "morador", "João")

    um = enviar_relato(client, comunidade_id, "A ponte está quebrada e dificulta a passagem.", morador_headers)
    enviar_relato(client, comunidade_id, "Estamos sem energia durante a noite.", outro_headers)

    relatos = client.get("/comunitario/meus-relatos", headers=morador_headers).json()["relatos"]
    assert len(relatos) == 1
    assert relatos[0]["protocolo"] == um["protocolo"]

    resposta = client.post(
        f"/comunitario/demandas/{um['demanda_id']}/manifestacoes",
        headers=morador_headers,
        json={"tipo": "confirmar", "texto": "Confirmo a situação."},
    )
    assert resposta.status_code == 403


def test_representante_so_acessa_sua_comunidade_e_contestacao_bloqueia(tmp_path, monkeypatch):
    client = preparar_banco_temporario(tmp_path, monkeypatch)
    comunidade_a = criar_comunidade(client, "Comunidade A")
    comunidade_b = criar_comunidade(client, "Comunidade B")
    dados_a = enviar_relato(client, comunidade_a, "A ponte principal está quebrada e precisa de reparo.")
    dados_b = enviar_relato(client, comunidade_b, "O motor de água parou e várias casas estão sem água.")

    _, representante_headers = criar_perfil(client, comunidade_a, "representante", "Representante A")
    assert client.get(f"/comunitario/demandas/{dados_a['demanda_id']}", headers=representante_headers).status_code == 200
    assert client.get(f"/comunitario/demandas/{dados_b['demanda_id']}", headers=representante_headers).status_code == 403

    resposta = client.post(
        f"/comunitario/demandas/{dados_a['demanda_id']}/manifestacoes",
        headers=representante_headers,
        json={"tipo": "contestar", "texto": "A informação precisa ser revista."},
    )
    assert resposta.status_code == 200, resposta.text
    demanda = banco.obter_demanda(dados_a["demanda_id"])
    assert demanda["status"] == "contestada"

    instituicao = next(i for i in banco.listar_instituicoes() if "infraestrutura" in i["areas"])
    inst_headers = login_instituicao(client, instituicao["id"])
    resposta = client.post(
        f"/institucional/demandas/{dados_a['demanda_id']}/preparar-encaminhamento",
        headers=inst_headers,
        json={},
    )
    assert resposta.status_code == 409


def test_confirmacao_e_agente_de_roteamento_com_ferramenta(tmp_path, monkeypatch):
    client = preparar_banco_temporario(tmp_path, monkeypatch)
    comunidade_id = criar_comunidade(client)
    dados = enviar_relato(client, comunidade_id, "A ponte principal está quebrada e precisa de reparo.")
    _, representante_headers = criar_perfil(client, comunidade_id, "representante", "Representante")
    resposta = client.post(
        f"/comunitario/demandas/{dados['demanda_id']}/manifestacoes",
        headers=representante_headers,
        json={"tipo": "confirmar", "texto": "Confirmamos a situação."},
    )
    assert resposta.status_code == 200, resposta.text
    assert banco.obter_demanda(dados["demanda_id"])["status"] == "pronta_encaminhamento"

    instituicao = next(i for i in banco.listar_instituicoes() if "infraestrutura" in i["areas"])
    inst_headers = login_instituicao(client, instituicao["id"])
    rota = client.post(f"/institucional/demandas/{dados['demanda_id']}/avaliar-roteamento", headers=inst_headers)
    assert rota.status_code == 200, rota.text
    assert "buscar_instituicoes_compativeis" in rota.json().get("ferramentas_usadas", [])


def test_audio_original_exige_consentimento_e_acesso_institucional(tmp_path, monkeypatch):
    client = preparar_banco_temporario(tmp_path, monkeypatch)
    comunidade_id = criar_comunidade(client)
    dados = enviar_relato(client, comunidade_id, "Estamos sem água desde ontem porque o motor parou.")
    relato_id = dados["relato_id"]
    instituicao = next(i for i in banco.listar_instituicoes() if "agua" in i["areas"])
    headers = login_instituicao(client, instituicao["id"])
    assert client.get(f"/institucional/relatos/{relato_id}/audio", headers=headers).status_code == 404
    assert client.get(f"/institucional/relatos/{relato_id}/audio").status_code == 401



def test_transcricao_mock_e_explicitamente_simulada(tmp_path, monkeypatch):
    client = preparar_banco_temporario(tmp_path, monkeypatch)
    resposta = client.post(
        "/transcricoes?guardar_original=false",
        files={"arquivo": ("fala.webm", b"audio demonstrativo", "audio/webm")},
    )
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["modo_teste"] is True
    assert dados["provedor"] == "mock"
    assert "simulada" in dados["aviso"].lower()
    assert "Tumbira" in dados["texto"]

def test_service_worker_cacheia_apenas_frontend():
    conteudo = (RAIZ / "frontend" / "sw.js").read_text(encoding="utf-8")
    assert 'url.pathname.startsWith(PREFIXO_APP)' in conteudo
    assert 'PREFIXO_APP = "/app/"' in conteudo
    assert '"/app/acompanhar.html"' in conteudo

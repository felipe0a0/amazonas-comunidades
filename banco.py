import json
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "akcit.db"

DEMANDA_STATUS_ABERTOS = {
    "em_consolidacao",
    "aguardando_manifestacao",
    "em_revisao",
    "contestada",
    "revisao_prioritaria",
    "pronta_encaminhamento",
    "encaminhada",
    "em_analise",
    "em_atendimento",
}

ENCAMINHAMENTOS_ATIVOS = {
    "enviado",
    "recebido",
    "em_analise",
    "aceito",
    "em_atendimento",
}

GRAUS_ACESSO = {"facil", "medio", "dificil", "nao_classificado"}


def conectar():
    conexao = sqlite3.connect(DB_PATH)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def _agora_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _protocolo(prefixo: str):
    data = datetime.now().strftime("%Y%m%d")
    sufixo = uuid.uuid4().hex[:6].upper()
    return f"{prefixo}-{data}-{sufixo}"


def _json(valor):
    return json.dumps(valor if valor is not None else [], ensure_ascii=False)


def _loads(valor, padrao=None):
    if valor in (None, ""):
        return [] if padrao is None else padrao
    try:
        return json.loads(valor)
    except (TypeError, json.JSONDecodeError):
        return [] if padrao is None else padrao


def _tabela_existe(conexao, tabela: str) -> bool:
    return bool(
        conexao.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (tabela,)
        ).fetchone()
    )


def _colunas(conexao, tabela: str) -> set[str]:
    if not _tabela_existe(conexao, tabela):
        return set()
    return {linha[1] for linha in conexao.execute(f"PRAGMA table_info({tabela})").fetchall()}


def _garantir_coluna(conexao, tabela: str, nome: str, definicao: str):
    if nome not in _colunas(conexao, tabela):
        conexao.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {definicao}")


def criar_banco():
    with conectar() as conexao:
        conexao.executescript(
            """
            CREATE TABLE IF NOT EXISTS comunidades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                municipio TEXT,
                latitude_referencia REAL,
                longitude_referencia REAL,
                grau_acesso TEXT NOT NULL DEFAULT 'nao_classificado',
                fonte_dado TEXT NOT NULL DEFAULT 'cadastro_no_sistema',
                fonte_url TEXT,
                publicidade_autorizada INTEGER NOT NULL DEFAULT 0,
                area_geojson TEXT,
                observacoes TEXT,
                data_criacao TEXT NOT NULL,
                data_atualizacao TEXT NOT NULL,
                ativa INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS relatos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                protocolo TEXT UNIQUE NOT NULL,
                comunidade_id INTEGER,
                comunidade TEXT NOT NULL,
                mensagem_original TEXT NOT NULL,
                texto_formalizado TEXT,
                meio_relato TEXT NOT NULL DEFAULT 'texto',
                tipo_informado TEXT,
                urgencia_informada TEXT,
                latitude REAL,
                longitude REAL,
                origem TEXT NOT NULL DEFAULT 'web',
                data_ocorrencia TEXT,
                data_recebimento TEXT NOT NULL,
                status_processamento TEXT NOT NULL DEFAULT 'recebido',
                categoria_ia TEXT,
                subcategoria_ia TEXT,
                titulo_ia TEXT,
                chave_agrupamento TEXT,
                resumo_ia TEXT,
                necessidades_json TEXT NOT NULL DEFAULT '[]',
                recursos_json TEXT NOT NULL DEFAULT '[]',
                informacoes_faltantes_json TEXT NOT NULL DEFAULT '[]',
                prioridade_ia TEXT,
                janela_encaminhamento TEXT,
                justificativa_prioridade TEXT,
                possivel_emergencia INTEGER NOT NULL DEFAULT 0,
                revisao_humana INTEGER NOT NULL DEFAULT 0,
                erro_ia TEXT,
                FOREIGN KEY (comunidade_id) REFERENCES comunidades(id)
            );

            CREATE TABLE IF NOT EXISTS demandas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                protocolo TEXT UNIQUE NOT NULL,
                comunidade_id INTEGER,
                comunidade TEXT NOT NULL,
                categoria TEXT NOT NULL,
                subcategoria TEXT,
                chave_agrupamento TEXT NOT NULL,
                titulo TEXT NOT NULL,
                resumo TEXT NOT NULL,
                necessidades_json TEXT NOT NULL DEFAULT '[]',
                recursos_json TEXT NOT NULL DEFAULT '[]',
                divergencias_json TEXT NOT NULL DEFAULT '[]',
                informacoes_faltantes_json TEXT NOT NULL DEFAULT '[]',
                prioridade TEXT NOT NULL,
                janela_encaminhamento TEXT NOT NULL,
                status TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                quantidade_relatos INTEGER NOT NULL DEFAULT 0,
                data_abertura TEXT NOT NULL,
                data_atualizacao TEXT NOT NULL,
                FOREIGN KEY (comunidade_id) REFERENCES comunidades(id)
            );

            CREATE TABLE IF NOT EXISTS demanda_relatos (
                demanda_id INTEGER NOT NULL,
                relato_id INTEGER NOT NULL UNIQUE,
                data_vinculo TEXT NOT NULL,
                PRIMARY KEY (demanda_id, relato_id),
                FOREIGN KEY (demanda_id) REFERENCES demandas(id) ON DELETE CASCADE,
                FOREIGN KEY (relato_id) REFERENCES relatos(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS manifestacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                demanda_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                autor TEXT NOT NULL,
                texto TEXT NOT NULL,
                data_criacao TEXT NOT NULL,
                FOREIGN KEY (demanda_id) REFERENCES demandas(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS instituicoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                descricao TEXT,
                areas_json TEXT NOT NULL DEFAULT '[]',
                ordem_prioridade INTEGER NOT NULL DEFAULT 100,
                canal TEXT,
                contato TEXT,
                ativa INTEGER NOT NULL DEFAULT 1,
                demonstracao INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS encaminhamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                demanda_id INTEGER NOT NULL,
                instituicao_id INTEGER NOT NULL,
                ordem INTEGER NOT NULL,
                status TEXT NOT NULL,
                motivo TEXT,
                data_envio TEXT NOT NULL,
                data_atualizacao TEXT NOT NULL,
                FOREIGN KEY (demanda_id) REFERENCES demandas(id) ON DELETE CASCADE,
                FOREIGN KEY (instituicao_id) REFERENCES instituicoes(id)
            );

            CREATE TABLE IF NOT EXISTS historico_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                demanda_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                descricao TEXT,
                visibilidade TEXT NOT NULL DEFAULT 'publica',
                data_criacao TEXT NOT NULL,
                FOREIGN KEY (demanda_id) REFERENCES demandas(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS mensagens_comunidade (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comunidade_id INTEGER NOT NULL,
                demanda_id INTEGER,
                instituicao_id INTEGER,
                tipo TEXT NOT NULL DEFAULT 'informacao',
                titulo TEXT NOT NULL,
                texto TEXT NOT NULL,
                publica INTEGER NOT NULL DEFAULT 1,
                data_criacao TEXT NOT NULL,
                FOREIGN KEY (comunidade_id) REFERENCES comunidades(id),
                FOREIGN KEY (demanda_id) REFERENCES demandas(id) ON DELETE CASCADE,
                FOREIGN KEY (instituicao_id) REFERENCES instituicoes(id)
            );

            CREATE TABLE IF NOT EXISTS logs_ia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                relato_id INTEGER,
                demanda_id INTEGER,
                operacao TEXT NOT NULL,
                modelo TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                sucesso INTEGER NOT NULL,
                latencia_ms INTEGER,
                erro TEXT,
                data_criacao TEXT NOT NULL,
                FOREIGN KEY (relato_id) REFERENCES relatos(id) ON DELETE SET NULL,
                FOREIGN KEY (demanda_id) REFERENCES demandas(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS perfis_comunitarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_exibicao TEXT NOT NULL,
                comunidade_id INTEGER NOT NULL,
                papel TEXT NOT NULL,
                funcao_informada TEXT,
                status_verificacao TEXT NOT NULL DEFAULT 'demo',
                data_criacao TEXT NOT NULL,
                ativo INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (comunidade_id) REFERENCES comunidades(id)
            );

            CREATE TABLE IF NOT EXISTS modelos_institucionais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instituicao_id INTEGER NOT NULL,
                nome_original TEXT NOT NULL,
                arquivo_ref TEXT NOT NULL,
                data_criacao TEXT NOT NULL,
                FOREIGN KEY (instituicao_id) REFERENCES instituicoes(id)
            );

            CREATE INDEX IF NOT EXISTS idx_comunidades_nome ON comunidades(nome);
            CREATE INDEX IF NOT EXISTS idx_relatos_comunidade ON relatos(comunidade);
            CREATE INDEX IF NOT EXISTS idx_demandas_busca ON demandas(comunidade, chave_agrupamento, status);
            CREATE INDEX IF NOT EXISTS idx_encaminhamentos_demanda ON encaminhamentos(demanda_id, status);
            CREATE INDEX IF NOT EXISTS idx_historico_demanda ON historico_status(demanda_id, data_criacao);
            CREATE INDEX IF NOT EXISTS idx_mensagens_comunidade ON mensagens_comunidade(comunidade_id, data_criacao);
            """
        )

        # Migração compatível com o banco v2 já existente.
        _garantir_coluna(conexao, "relatos", "comunidade_id", "INTEGER")
        _garantir_coluna(conexao, "relatos", "texto_formalizado", "TEXT")
        _garantir_coluna(conexao, "relatos", "meio_relato", "TEXT NOT NULL DEFAULT 'texto'")
        _garantir_coluna(conexao, "demandas", "comunidade_id", "INTEGER")
        _garantir_coluna(conexao, "logs_ia", "tokens_entrada", "INTEGER")
        _garantir_coluna(conexao, "logs_ia", "tokens_saida", "INTEGER")
        _garantir_coluna(conexao, "logs_ia", "trace_id", "TEXT")
        _garantir_coluna(conexao, "comunidades", "visibilidade_publica", "INTEGER NOT NULL DEFAULT 0")
        _garantir_coluna(conexao, "comunidades", "origem_visibilidade", "TEXT NOT NULL DEFAULT 'privada'")
        _garantir_coluna(conexao, "relatos", "perfil_id", "INTEGER")
        _garantir_coluna(conexao, "relatos", "referencia_localidade", "TEXT")
        _garantir_coluna(conexao, "relatos", "localidade_pendente", "INTEGER NOT NULL DEFAULT 0")
        _garantir_coluna(conexao, "relatos", "audio_ref", "TEXT")
        _garantir_coluna(conexao, "relatos", "consentimento_audio", "INTEGER NOT NULL DEFAULT 0")
        conexao.execute("UPDATE comunidades SET visibilidade_publica = 1 WHERE publicidade_autorizada = 1 AND visibilidade_publica = 0")
        conexao.execute("UPDATE comunidades SET origem_visibilidade = 'autorizacao_comunidade' WHERE publicidade_autorizada = 1 AND origem_visibilidade = 'privada'")
        conexao.execute("CREATE INDEX IF NOT EXISTS idx_relatos_comunidade_id ON relatos(comunidade_id)")
        conexao.execute("CREATE INDEX IF NOT EXISTS idx_demandas_comunidade_id ON demandas(comunidade_id)")

        total = conexao.execute("SELECT COUNT(*) FROM instituicoes").fetchone()[0]
        if total == 0:
            _seed_instituicoes_demo(conexao)

        _migrar_comunidades_v2(conexao)
        _seed_comunidade_publica(conexao)


def _seed_instituicoes_demo(conexao):
    instituicoes = [
        (
            "Rede de Saúde - Demonstração",
            "Entidade demonstrativa para testar o roteamento de demandas de saúde. Não representa parceria oficial.",
            ["saude", "medicamentos"],
            10,
            "sistema",
            "Fluxo interno de demonstração",
        ),
        (
            "Assistência Comunitária - Demonstração",
            "Entidade demonstrativa para testar demandas de alimentação e assistência social.",
            ["alimentos", "documentacao", "outro"],
            20,
            "sistema",
            "Fluxo interno de demonstração",
        ),
        (
            "Infraestrutura e Água - Demonstração",
            "Entidade demonstrativa para testar demandas de água, energia e infraestrutura.",
            ["agua", "infraestrutura", "energia", "conectividade"],
            30,
            "sistema",
            "Fluxo interno de demonstração",
        ),
        (
            "Mobilidade e Educação - Demonstração",
            "Entidade demonstrativa para transporte e educação.",
            ["transporte", "educacao"],
            40,
            "sistema",
            "Fluxo interno de demonstração",
        ),
        (
            "Proteção e Segurança - Demonstração",
            "Entidade demonstrativa para situações de segurança e proteção comunitária.",
            ["seguranca"],
            50,
            "sistema",
            "Fluxo interno de demonstração",
        ),
    ]
    for nome, descricao, areas, ordem, canal, contato in instituicoes:
        conexao.execute(
            """
            INSERT INTO instituicoes
            (nome, descricao, areas_json, ordem_prioridade, canal, contato, ativa, demonstracao)
            VALUES (?, ?, ?, ?, ?, ?, 1, 1)
            """,
            (nome, descricao, _json(areas), ordem, canal, contato),
        )


def _migrar_comunidades_v2(conexao):
    """Cria catálogo a partir de relatos/demandas v2, sem importar a tabela de testes legada."""
    fontes = []
    for tabela in ("relatos", "demandas"):
        cols = _colunas(conexao, tabela)
        if not cols or "comunidade" not in cols:
            continue
        linhas = conexao.execute(
            f"SELECT comunidade, latitude, longitude FROM {tabela} WHERE trim(comunidade) != ''"
        ).fetchall()
        fontes.extend(linhas)

    for linha in fontes:
        nome = (linha["comunidade"] or "").strip()
        if not nome:
            continue
        existente = conexao.execute(
            "SELECT id FROM comunidades WHERE lower(trim(nome)) = lower(trim(?)) AND coalesce(trim(municipio),'') = '' LIMIT 1",
            (nome,),
        ).fetchone()
        if existente:
            comunidade_id = existente["id"]
        else:
            agora = _agora_iso()
            cur = conexao.execute(
                """
                INSERT INTO comunidades
                (nome, municipio, latitude_referencia, longitude_referencia, grau_acesso,
                 fonte_dado, fonte_url, publicidade_autorizada, area_geojson, observacoes,
                 data_criacao, data_atualizacao, ativa)
                VALUES (?, '', ?, ?, 'nao_classificado', 'migracao_v2', '', 0, NULL,
                        'Criada automaticamente a partir de dados do protótipo v2.', ?, ?, 1)
                """,
                (nome, linha["latitude"], linha["longitude"], agora, agora),
            )
            comunidade_id = cur.lastrowid

        for tabela in ("relatos", "demandas"):
            if "comunidade_id" in _colunas(conexao, tabela):
                conexao.execute(
                    f"UPDATE {tabela} SET comunidade_id = ? WHERE comunidade_id IS NULL AND lower(trim(comunidade)) = lower(trim(?))",
                    (comunidade_id, nome),
                )


def _seed_comunidade_publica(conexao):
    """Inclui uma referência pública real para a demonstração, sem inventar demanda atual."""
    existente = conexao.execute(
        "SELECT id FROM comunidades WHERE lower(trim(nome)) IN ('comunidade do tumbira', 'tumbira') LIMIT 1"
    ).fetchone()
    if existente:
        return
    agora = _agora_iso()
    conexao.execute(
        """
        INSERT INTO comunidades (
            nome, municipio, latitude_referencia, longitude_referencia, grau_acesso,
            fonte_dado, fonte_url, publicidade_autorizada, visibilidade_publica,
            origem_visibilidade, area_geojson, observacoes, data_criacao, data_atualizacao, ativa
        ) VALUES (?, ?, NULL, NULL, 'nao_classificado', ?, ?, 0, 1, 'fonte_publica', NULL, ?, ?, ?, 1)
        """,
        (
            "Comunidade do Tumbira",
            "Iranduba - AM",
            "SEMA-AM / Fundação Amazônia Sustentável (fontes públicas)",
            "https://www.sema.am.gov.br/rds-puranga-conquista-e-rio-negro-iniciam-monitoramento-da-biodiversidade/",
            "Referência pública: comunidade situada na RDS Rio Negro, em Iranduba. O cadastro não declara autorização da comunidade ao aplicativo e não cria demandas atuais.",
            agora,
            agora,
        ),
    )


def _validar_coordenadas(latitude, longitude):
    if latitude is not None and not (-90 <= float(latitude) <= 90):
        raise ValueError("Latitude inválida.")
    if longitude is not None and not (-180 <= float(longitude) <= 180):
        raise ValueError("Longitude inválida.")
    if (latitude is None) != (longitude is None):
        raise ValueError("Latitude e longitude devem ser informadas juntas.")


def criar_comunidade(dados: dict):
    nome = (dados.get("nome") or "").strip()
    municipio = (dados.get("municipio") or "").strip()
    if len(nome) < 2:
        raise ValueError("Informe o nome da comunidade.")

    grau = dados.get("grau_acesso") or "nao_classificado"
    if grau not in GRAUS_ACESSO:
        raise ValueError("Grau de acesso inválido.")

    latitude = dados.get("latitude_referencia")
    longitude = dados.get("longitude_referencia")
    _validar_coordenadas(latitude, longitude)

    area_geojson = dados.get("area_geojson")
    if isinstance(area_geojson, (dict, list)):
        area_geojson = json.dumps(area_geojson, ensure_ascii=False)
    elif area_geojson:
        try:
            json.loads(area_geojson)
        except (TypeError, json.JSONDecodeError) as erro:
            raise ValueError("area_geojson inválido.") from erro

    agora = _agora_iso()
    with conectar() as conexao:
        existente = conexao.execute(
            """
            SELECT * FROM comunidades
            WHERE lower(trim(nome)) = lower(trim(?))
              AND lower(coalesce(trim(municipio),'')) = lower(?)
              AND ativa = 1
            LIMIT 1
            """,
            (nome, municipio),
        ).fetchone()
        if existente:
            return existente["id"], False

        cursor = conexao.execute(
            """
            INSERT INTO comunidades (
                nome, municipio, latitude_referencia, longitude_referencia,
                grau_acesso, fonte_dado, fonte_url, publicidade_autorizada,
                visibilidade_publica, origem_visibilidade, area_geojson, observacoes,
                data_criacao, data_atualizacao, ativa
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                nome,
                municipio,
                latitude,
                longitude,
                grau,
                (dados.get("fonte_dado") or "cadastro_no_sistema").strip(),
                (dados.get("fonte_url") or "").strip(),
                int(bool(dados.get("visibilidade_publica"))),
                int(bool(dados.get("visibilidade_publica"))),
                (dados.get("origem_visibilidade") or "privada").strip(),
                area_geojson,
                (dados.get("observacoes") or "").strip(),
                agora,
                agora,
            ),
        )
        return cursor.lastrowid, True


def obter_comunidade(comunidade_id: int):
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT * FROM comunidades WHERE id = ? AND ativa = 1", (comunidade_id,)
        ).fetchone()
    return _comunidade_dict(linha) if linha else None


def buscar_comunidade_por_nome(nome: str, municipio: str = ""):
    with conectar() as conexao:
        linha = conexao.execute(
            """
            SELECT * FROM comunidades
            WHERE lower(trim(nome)) = lower(trim(?))
              AND lower(coalesce(trim(municipio),'')) = lower(trim(?))
              AND ativa = 1
            LIMIT 1
            """,
            (nome, municipio),
        ).fetchone()
    return _comunidade_dict(linha) if linha else None


def listar_comunidades(apenas_publicas: bool = False):
    sql = """
        SELECT c.*,
               (SELECT COUNT(*) FROM demandas d WHERE d.comunidade_id = c.id) AS quantidade_demandas,
               (SELECT COUNT(*) FROM relatos r WHERE r.comunidade_id = c.id) AS quantidade_relatos
        FROM comunidades c
        WHERE c.ativa = 1
    """
    parametros = []
    if apenas_publicas:
        sql += " AND c.visibilidade_publica = 1"
    sql += " ORDER BY c.nome COLLATE NOCASE ASC"
    with conectar() as conexao:
        linhas = conexao.execute(sql, parametros).fetchall()
    return [_comunidade_dict(linha) for linha in linhas]


def _resolver_comunidade(dados: dict):
    comunidade_id = dados.get("comunidade_id")
    if comunidade_id is not None:
        comunidade = obter_comunidade(int(comunidade_id))
        if not comunidade:
            raise ValueError("Comunidade não encontrada no catálogo.")
        return comunidade

    nome = (dados.get("comunidade") or "").strip()
    if not nome:
        raise ValueError("Selecione uma comunidade ou informe seu nome.")
    municipio = (dados.get("municipio") or "").strip()
    comunidade = buscar_comunidade_por_nome(nome, municipio)
    if comunidade:
        return comunidade

    # Compatibilidade com CLI/clientes antigos: cria entrada mínima no catálogo.
    novo_id, _ = criar_comunidade(
        {
            "nome": nome,
            "municipio": municipio,
            "latitude_referencia": dados.get("latitude"),
            "longitude_referencia": dados.get("longitude"),
            "grau_acesso": "nao_classificado",
            "fonte_dado": "cadastro_compatibilidade",
            "visibilidade_publica": False,
            "origem_visibilidade": "privada",
            "observacoes": "Criada automaticamente por cliente legado/CLI.",
        }
    )
    return obter_comunidade(novo_id)


def salvar_relato_bruto(dados: dict):
    protocolo = _protocolo("REL")
    agora = _agora_iso()
    localidade_pendente = bool(dados.get("localidade_pendente"))
    comunidade = None if localidade_pendente else _resolver_comunidade(dados)
    comunidade_id = comunidade["id"] if comunidade else None
    comunidade_nome = comunidade["nome"] if comunidade else "Localidade pendente"
    status = "aguardando_localidade" if localidade_pendente else "recebido"

    with conectar() as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO relatos (
                protocolo, comunidade_id, comunidade, mensagem_original, texto_formalizado, meio_relato,
                tipo_informado, urgencia_informada, latitude, longitude, origem,
                data_ocorrencia, data_recebimento, status_processamento, perfil_id,
                referencia_localidade, localidade_pendente, audio_ref, consentimento_audio
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                protocolo,
                comunidade_id,
                comunidade_nome,
                dados["relato"].strip(),
                (dados.get("texto_formalizado") or "").strip(),
                dados.get("meio_relato") or "texto",
                (dados.get("tipo") or "").strip(),
                dados.get("urgencia") or "nao_informado",
                dados.get("origem") or "web",
                dados.get("data_ocorrencia"),
                agora,
                status,
                dados.get("perfil_id"),
                (dados.get("referencia_localidade") or "").strip(),
                int(localidade_pendente),
                (dados.get("audio_ref") or "").strip() or None,
                int(bool(dados.get("consentimento_audio"))),
            ),
        )
        return cursor.lastrowid, protocolo


def obter_relato(relato_id: int):
    with conectar() as conexao:
        linha = conexao.execute("SELECT * FROM relatos WHERE id = ?", (relato_id,)).fetchone()
    return _relato_dict(linha) if linha else None


def atualizar_texto_formalizado(relato_id: int, texto_formalizado: str):
    with conectar() as conexao:
        conexao.execute(
            "UPDATE relatos SET texto_formalizado = ? WHERE id = ?",
            ((texto_formalizado or "").strip(), relato_id),
        )


def obter_relato_por_protocolo(protocolo: str):
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT * FROM relatos WHERE upper(protocolo) = upper(?) LIMIT 1",
            ((protocolo or "").strip(),),
        ).fetchone()
    return _relato_dict(linha) if linha else None


def atualizar_relato_analise(relato_id: int, analise: dict):
    with conectar() as conexao:
        conexao.execute(
            """
            UPDATE relatos SET
                status_processamento = 'processado',
                categoria_ia = ?, subcategoria_ia = ?, titulo_ia = ?,
                chave_agrupamento = ?, resumo_ia = ?,
                necessidades_json = ?, recursos_json = ?, informacoes_faltantes_json = ?,
                prioridade_ia = ?, janela_encaminhamento = ?, justificativa_prioridade = ?,
                possivel_emergencia = ?, revisao_humana = ?, erro_ia = NULL
            WHERE id = ?
            """,
            (
                analise["categoria"],
                analise.get("subcategoria", ""),
                analise["titulo_demanda"],
                analise["chave_agrupamento"],
                analise["resumo"],
                _json(analise.get("necessidades")),
                _json(analise.get("recursos_disponiveis")),
                _json(analise.get("informacoes_faltantes")),
                analise["prioridade"],
                analise["janela_encaminhamento"],
                analise.get("justificativa_prioridade", ""),
                int(bool(analise.get("possivel_emergencia"))),
                int(bool(analise.get("revisao_humana"))),
                relato_id,
            ),
        )


def marcar_erro_ia(relato_id: int, erro: str):
    with conectar() as conexao:
        conexao.execute(
            "UPDATE relatos SET status_processamento = 'erro_ia', erro_ia = ? WHERE id = ?",
            (erro[:2000], relato_id),
        )


def buscar_demanda_aberta(comunidade_id: int | None, comunidade: str, chave_agrupamento: str):
    marcadores = ",".join("?" for _ in DEMANDA_STATUS_ABERTOS)
    if comunidade_id is not None:
        clausula_comunidade = "comunidade_id = ?"
        primeiro = comunidade_id
    else:
        clausula_comunidade = "lower(comunidade) = ?"
        primeiro = comunidade.strip().lower()
    parametros = [primeiro, chave_agrupamento, *sorted(DEMANDA_STATUS_ABERTOS)]
    with conectar() as conexao:
        linha = conexao.execute(
            f"""
            SELECT * FROM demandas
            WHERE {clausula_comunidade}
              AND chave_agrupamento = ?
              AND status IN ({marcadores})
            ORDER BY id DESC LIMIT 1
            """,
            parametros,
        ).fetchone()
    return _demanda_dict(linha) if linha else None


def criar_demanda(relato: dict, analise: dict):
    protocolo = _protocolo("DEM")
    agora = _agora_iso()
    if analise["prioridade"] == "critica":
        status = "revisao_prioritaria"
    elif analise["prioridade"] == "alta":
        status = "aguardando_manifestacao"
    else:
        status = "em_consolidacao"

    comunidade = obter_comunidade(relato.get("comunidade_id")) if relato.get("comunidade_id") else None
    latitude = comunidade.get("latitude_referencia") if comunidade else None
    longitude = comunidade.get("longitude_referencia") if comunidade else None

    with conectar() as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO demandas (
                protocolo, comunidade_id, comunidade, categoria, subcategoria, chave_agrupamento,
                titulo, resumo, necessidades_json, recursos_json,
                divergencias_json, informacoes_faltantes_json,
                prioridade, janela_encaminhamento, status,
                latitude, longitude, quantidade_relatos,
                data_abertura, data_atualizacao
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                protocolo,
                relato.get("comunidade_id"),
                relato["comunidade"],
                analise["categoria"],
                analise.get("subcategoria", ""),
                analise["chave_agrupamento"],
                analise["titulo_demanda"],
                analise["resumo"],
                _json(analise.get("necessidades")),
                _json(analise.get("recursos_disponiveis")),
                _json(analise.get("informacoes_faltantes")),
                analise["prioridade"],
                analise["janela_encaminhamento"],
                status,
                latitude,
                longitude,
                agora,
                agora,
            ),
        )
        demanda_id = cursor.lastrowid
        conexao.execute(
            """
            INSERT INTO historico_status
            (demanda_id, status, descricao, visibilidade, data_criacao)
            VALUES (?, ?, ?, 'publica', ?)
            """,
            (demanda_id, status, "Demanda criada a partir dos relatos recebidos.", agora),
        )
    return demanda_id, protocolo


def vincular_relato_demanda(demanda_id: int, relato_id: int):
    agora = _agora_iso()
    with conectar() as conexao:
        conexao.execute(
            "INSERT OR IGNORE INTO demanda_relatos (demanda_id, relato_id, data_vinculo) VALUES (?, ?, ?)",
            (demanda_id, relato_id, agora),
        )
        total = conexao.execute(
            "SELECT COUNT(*) FROM demanda_relatos WHERE demanda_id = ?", (demanda_id,)
        ).fetchone()[0]
        conexao.execute(
            "UPDATE demandas SET quantidade_relatos = ?, data_atualizacao = ? WHERE id = ?",
            (total, agora, demanda_id),
        )


def relatos_da_demanda(demanda_id: int):
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT r.*, p.nome_exibicao AS perfil_nome_exibicao,
                   p.papel AS perfil_papel, p.funcao_informada AS perfil_funcao_informada,
                   p.status_verificacao AS perfil_status_verificacao
            FROM relatos r
            JOIN demanda_relatos dr ON dr.relato_id = r.id
            LEFT JOIN perfis_comunitarios p ON p.id = r.perfil_id
            WHERE dr.demanda_id = ?
            ORDER BY r.data_recebimento ASC
            """,
            (demanda_id,),
        ).fetchall()
    return [_relato_dict(linha) for linha in linhas]


def atualizar_demanda_consolidada(demanda_id: int, consolidacao: dict):
    agora = _agora_iso()
    demanda_atual = obter_demanda(demanda_id)
    prioridade_nova = consolidacao["prioridade_consolidada"]

    with conectar() as conexao:
        conexao.execute(
            """
            UPDATE demandas SET
                titulo = ?, resumo = ?, necessidades_json = ?, recursos_json = ?,
                divergencias_json = ?, informacoes_faltantes_json = ?,
                prioridade = ?, janela_encaminhamento = ?, data_atualizacao = ?
            WHERE id = ?
            """,
            (
                consolidacao["titulo_demanda"],
                consolidacao["resumo_consolidado"],
                _json(consolidacao.get("necessidades_consolidadas")),
                _json(consolidacao.get("recursos_consolidados")),
                _json(consolidacao.get("divergencias")),
                _json(consolidacao.get("informacoes_faltantes")),
                prioridade_nova,
                consolidacao["janela_encaminhamento"],
                agora,
                demanda_id,
            ),
        )

    if not demanda_atual:
        return

    status_atual = demanda_atual["status"]
    if prioridade_nova == "critica" and status_atual in {
        "em_consolidacao", "aguardando_manifestacao", "em_revisao"
    }:
        atualizar_status_demanda(
            demanda_id,
            "revisao_prioritaria",
            "A consolidação identificou sinais de prioridade crítica. Revisão humana prioritária necessária antes do encaminhamento.",
        )
    elif prioridade_nova == "alta" and status_atual == "em_consolidacao":
        atualizar_status_demanda(
            demanda_id,
            "aguardando_manifestacao",
            "A consolidação elevou a prioridade da demanda. A representação comunitária pode confirmar ou complementar antes do encaminhamento.",
        )

def listar_relatos(limite: int = 200):
    with conectar() as conexao:
        linhas = conexao.execute(
            "SELECT * FROM relatos ORDER BY id DESC LIMIT ?", (limite,)
        ).fetchall()
    return [_relato_dict(linha) for linha in linhas]


def listar_demandas(status: str | None = None, prioridade: str | None = None, limite: int = 200):
    sql = "SELECT * FROM demandas WHERE 1=1"
    parametros = []
    if status:
        sql += " AND status = ?"
        parametros.append(status)
    if prioridade:
        sql += " AND prioridade = ?"
        parametros.append(prioridade)
    sql += " ORDER BY data_atualizacao DESC LIMIT ?"
    parametros.append(limite)
    with conectar() as conexao:
        linhas = conexao.execute(sql, parametros).fetchall()
    return [_demanda_dict(linha) for linha in linhas]


def obter_demanda(demanda_id: int):
    with conectar() as conexao:
        linha = conexao.execute("SELECT * FROM demandas WHERE id = ?", (demanda_id,)).fetchone()
    return _demanda_dict(linha) if linha else None


def obter_demanda_completa(demanda_id: int):
    demanda = obter_demanda(demanda_id)
    if not demanda:
        return None
    with conectar() as conexao:
        manifestacoes = [dict(x) for x in conexao.execute(
            "SELECT * FROM manifestacoes WHERE demanda_id = ? ORDER BY data_criacao ASC", (demanda_id,)
        ).fetchall()]
        encaminhamentos = [dict(x) for x in conexao.execute(
            """
            SELECT e.*, i.nome AS instituicao_nome, i.demonstracao
            FROM encaminhamentos e
            JOIN instituicoes i ON i.id = e.instituicao_id
            WHERE e.demanda_id = ? ORDER BY e.ordem ASC
            """,
            (demanda_id,),
        ).fetchall()]
        historico = [dict(x) for x in conexao.execute(
            "SELECT * FROM historico_status WHERE demanda_id = ? ORDER BY data_criacao ASC", (demanda_id,)
        ).fetchall()]
    demanda["relatos"] = relatos_da_demanda(demanda_id)
    demanda["manifestacoes"] = manifestacoes
    demanda["encaminhamentos"] = encaminhamentos
    demanda["historico"] = historico
    demanda["comunidade_dados"] = obter_comunidade(demanda.get("comunidade_id")) if demanda.get("comunidade_id") else None
    return demanda


def adicionar_manifestacao(demanda_id: int, tipo: str, autor: str, texto: str):
    agora = _agora_iso()
    with conectar() as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO manifestacoes (demanda_id, tipo, autor, texto, data_criacao)
            VALUES (?, ?, ?, ?, ?)
            """,
            (demanda_id, tipo, autor.strip(), texto.strip(), agora),
        )

    if tipo == "confirmar":
        atualizar_status_demanda(
            demanda_id,
            "pronta_encaminhamento",
            "A representação comunitária confirmou a demanda para revisão de encaminhamento.",
        )
    elif tipo == "complementar":
        atualizar_status_demanda(
            demanda_id,
            "em_revisao",
            "A representação comunitária acrescentou informações. A demanda precisa ser revisada antes do encaminhamento.",
        )
    elif tipo == "contestar":
        atualizar_status_demanda(
            demanda_id,
            "contestada",
            "A representação comunitária contestou informações da demanda. O encaminhamento fica bloqueado até revisão.",
        )
    return cursor.lastrowid

def atualizar_status_demanda(demanda_id: int, status: str, descricao: str = "", visibilidade: str = "publica"):
    agora = _agora_iso()
    with conectar() as conexao:
        conexao.execute(
            "UPDATE demandas SET status = ?, data_atualizacao = ? WHERE id = ?",
            (status, agora, demanda_id),
        )
        conexao.execute(
            """
            INSERT INTO historico_status
            (demanda_id, status, descricao, visibilidade, data_criacao)
            VALUES (?, ?, ?, ?, ?)
            """,
            (demanda_id, status, descricao, visibilidade, agora),
        )


def listar_instituicoes(categoria: str | None = None):
    with conectar() as conexao:
        linhas = conexao.execute(
            "SELECT * FROM instituicoes WHERE ativa = 1 ORDER BY ordem_prioridade ASC, nome ASC"
        ).fetchall()
    resultado = []
    for linha in linhas:
        item = dict(linha)
        item["areas"] = _loads(item.pop("areas_json"))
        if not categoria or categoria in item["areas"]:
            resultado.append(item)
    if categoria and not resultado:
        with conectar() as conexao:
            linhas = conexao.execute(
                "SELECT * FROM instituicoes WHERE ativa = 1 ORDER BY ordem_prioridade ASC, nome ASC"
            ).fetchall()
        for linha in linhas:
            item = dict(linha)
            item["areas"] = _loads(item.pop("areas_json"))
            if "outro" in item["areas"]:
                resultado.append(item)
    return resultado


def obter_encaminhamento(encaminhamento_id: int):
    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT * FROM encaminhamentos WHERE id = ?", (encaminhamento_id,)
        ).fetchone()
    return dict(linha) if linha else None


def obter_encaminhamento_ativo(demanda_id: int):
    marcadores = ",".join("?" for _ in ENCAMINHAMENTOS_ATIVOS)
    with conectar() as conexao:
        linha = conexao.execute(
            f"""
            SELECT e.*, i.nome AS instituicao_nome FROM encaminhamentos e
            JOIN instituicoes i ON i.id = e.instituicao_id
            WHERE e.demanda_id = ? AND e.status IN ({marcadores})
            ORDER BY e.id DESC LIMIT 1
            """,
            [demanda_id, *sorted(ENCAMINHAMENTOS_ATIVOS)],
        ).fetchone()
    return dict(linha) if linha else None


def instituicoes_ja_tentadas(demanda_id: int):
    with conectar() as conexao:
        linhas = conexao.execute(
            "SELECT instituicao_id FROM encaminhamentos WHERE demanda_id = ?", (demanda_id,)
        ).fetchall()
    return {linha[0] for linha in linhas}


def criar_encaminhamento(demanda_id: int, instituicao_id: int):
    if obter_encaminhamento_ativo(demanda_id):
        raise ValueError("Já existe uma instituição responsável ativa para esta demanda.")
    agora = _agora_iso()
    with conectar() as conexao:
        ordem = conexao.execute(
            "SELECT COUNT(*) + 1 FROM encaminhamentos WHERE demanda_id = ?", (demanda_id,)
        ).fetchone()[0]
        cursor = conexao.execute(
            """
            INSERT INTO encaminhamentos
            (demanda_id, instituicao_id, ordem, status, motivo, data_envio, data_atualizacao)
            VALUES (?, ?, ?, 'enviado', '', ?, ?)
            """,
            (demanda_id, instituicao_id, ordem, agora, agora),
        )
    atualizar_status_demanda(
        demanda_id,
        "encaminhada",
        "Demanda encaminhada a uma instituição responsável. Detalhes operacionais sensíveis não são públicos.",
    )
    return cursor.lastrowid


def atualizar_encaminhamento(encaminhamento_id: int, status: str, motivo: str = "", descricao_publica: str = ""):
    agora = _agora_iso()
    transicoes = {
        "enviado": {"recebido", "em_analise", "nao_atendido", "nao_competente"},
        "recebido": {"em_analise", "aceito", "nao_atendido", "nao_competente"},
        "em_analise": {"aceito", "nao_atendido", "nao_competente"},
        "aceito": {"em_atendimento", "concluido"},
        "em_atendimento": {"concluido", "nao_atendido"},
        "concluido": set(),
        "nao_atendido": set(),
        "nao_competente": set(),
    }

    with conectar() as conexao:
        linha = conexao.execute(
            "SELECT * FROM encaminhamentos WHERE id = ?", (encaminhamento_id,)
        ).fetchone()
        if not linha:
            return None

        atual = linha["status"]
        if status != atual and status not in transicoes.get(atual, set()):
            raise ValueError(f"Transição de status inválida: {atual} -> {status}.")

        conexao.execute(
            """
            UPDATE encaminhamentos SET status = ?, motivo = ?, data_atualizacao = ?
            WHERE id = ?
            """,
            (status, motivo.strip(), agora, encaminhamento_id),
        )
        demanda_id = linha["demanda_id"]

    mapa_demanda = {
        "recebido": "encaminhada",
        "em_analise": "em_analise",
        "aceito": "em_atendimento",
        "em_atendimento": "em_atendimento",
        "concluido": "concluida",
        "nao_atendido": "pronta_encaminhamento",
        "nao_competente": "pronta_encaminhamento",
    }
    descricao = descricao_publica.strip() or {
        "recebido": "A instituição confirmou o recebimento da demanda.",
        "em_analise": "A demanda está em análise pela instituição responsável.",
        "aceito": "A instituição informou que a demanda foi aceita para atendimento.",
        "em_atendimento": "O atendimento da demanda está em andamento.",
        "concluido": "A instituição informou a conclusão do atendimento.",
        "nao_atendido": "A instituição informou que não poderá atender a demanda. O sistema pode buscar outro encaminhamento.",
        "nao_competente": "A instituição informou não ser competente para a demanda. O sistema pode buscar outro encaminhamento.",
    }[status]
    atualizar_status_demanda(demanda_id, mapa_demanda[status], descricao)
    return demanda_id

def registrar_log_ia(
    operacao: str,
    modelo: str,
    prompt_version: str,
    sucesso: bool,
    latencia_ms: int | None,
    erro: str = "",
    relato_id: int | None = None,
    demanda_id: int | None = None,
    tokens_entrada: int | None = None,
    tokens_saida: int | None = None,
    trace_id: str | None = None,
):
    with conectar() as conexao:
        conexao.execute(
            """
            INSERT INTO logs_ia
            (relato_id, demanda_id, operacao, modelo, prompt_version, sucesso,
             latencia_ms, erro, data_criacao, tokens_entrada, tokens_saida, trace_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relato_id,
                demanda_id,
                operacao,
                modelo,
                prompt_version,
                int(bool(sucesso)),
                latencia_ms,
                erro[:2000],
                _agora_iso(),
                tokens_entrada,
                tokens_saida,
                trace_id,
            ),
        )


def criar_mensagem_comunidade(
    comunidade_id: int,
    titulo: str,
    texto: str,
    *,
    demanda_id: int | None = None,
    instituicao_id: int | None = None,
    tipo: str = "informacao",
    publica: bool = True,
):
    agora = _agora_iso()
    with conectar() as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO mensagens_comunidade
            (comunidade_id, demanda_id, instituicao_id, tipo, titulo, texto, publica, data_criacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                comunidade_id,
                demanda_id,
                instituicao_id,
                tipo,
                titulo.strip(),
                texto.strip(),
                int(bool(publica)),
                agora,
            ),
        )
    return cursor.lastrowid


def listar_mensagens_comunidade(comunidade_id: int, apenas_publicas: bool = True, limite: int = 100):
    sql = """
        SELECT m.*, i.nome AS instituicao_nome, d.protocolo AS demanda_protocolo
        FROM mensagens_comunidade m
        LEFT JOIN instituicoes i ON i.id = m.instituicao_id
        LEFT JOIN demandas d ON d.id = m.demanda_id
        WHERE m.comunidade_id = ?
    """
    parametros = [comunidade_id]
    if apenas_publicas:
        sql += " AND m.publica = 1"
    sql += " ORDER BY m.data_criacao DESC LIMIT ?"
    parametros.append(limite)
    with conectar() as conexao:
        return [dict(x) for x in conexao.execute(sql, parametros).fetchall()]


def listar_notificacoes_comunidade(comunidade_id: int, limite: int = 100):
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT h.id, h.demanda_id, d.protocolo AS demanda_protocolo, d.titulo,
                   h.status, h.descricao, h.data_criacao
            FROM historico_status h
            JOIN demandas d ON d.id = h.demanda_id
            WHERE d.comunidade_id = ? AND h.visibilidade = 'publica'
            ORDER BY h.data_criacao DESC
            LIMIT ?
            """,
            (comunidade_id, limite),
        ).fetchall()
    return [dict(x) for x in linhas]


def listar_demandas_publicas(
    comunidade_id: int | None = None,
    status: str | None = None,
    prioridade: str | None = None,
    limite: int = 200,
):
    sql = "SELECT * FROM demandas WHERE 1=1"
    parametros = []
    if comunidade_id is not None:
        sql += " AND comunidade_id = ?"
        parametros.append(comunidade_id)
    if status:
        sql += " AND status = ?"
        parametros.append(status)
    if prioridade:
        sql += " AND prioridade = ?"
        parametros.append(prioridade)
    sql += " ORDER BY data_atualizacao DESC LIMIT ?"
    parametros.append(limite)

    with conectar() as conexao:
        linhas = conexao.execute(sql, parametros).fetchall()

    itens = []
    for linha in linhas:
        demanda = _demanda_dict(linha)
        itens.append({
            "id": demanda["id"],
            "protocolo": demanda["protocolo"],
            "comunidade_id": demanda.get("comunidade_id"),
            "comunidade": demanda["comunidade"],
            "categoria": demanda["categoria"],
            "titulo": demanda["titulo"],
            "resumo": demanda["resumo"],
            "necessidades": demanda["necessidades"],
            "prioridade": demanda["prioridade"],
            "janela_encaminhamento": demanda["janela_encaminhamento"],
            "status": demanda["status"],
            "quantidade_relatos": demanda["quantidade_relatos"],
            "data_abertura": demanda["data_abertura"],
            "data_atualizacao": demanda["data_atualizacao"],
        })
    return itens


def obter_demanda_publica(demanda_id: int):
    demanda = obter_demanda(demanda_id)
    if not demanda:
        return None
    with conectar() as conexao:
        historico = [dict(x) for x in conexao.execute(
            """
            SELECT status, descricao, data_criacao
            FROM historico_status
            WHERE demanda_id = ? AND visibilidade = 'publica'
            ORDER BY data_criacao ASC
            """,
            (demanda_id,),
        ).fetchall()]
        manifestacoes = [dict(x) for x in conexao.execute(
            """
            SELECT tipo, texto, data_criacao
            FROM manifestacoes
            WHERE demanda_id = ?
            ORDER BY data_criacao ASC
            """,
            (demanda_id,),
        ).fetchall()]

    return {
        "id": demanda["id"],
        "protocolo": demanda["protocolo"],
        "comunidade_id": demanda.get("comunidade_id"),
        "comunidade": demanda["comunidade"],
        "categoria": demanda["categoria"],
        "titulo": demanda["titulo"],
        "resumo": demanda["resumo"],
        "necessidades": demanda["necessidades"],
        "prioridade": demanda["prioridade"],
        "status": demanda["status"],
        "quantidade_relatos": demanda["quantidade_relatos"],
        "data_abertura": demanda["data_abertura"],
        "data_atualizacao": demanda["data_atualizacao"],
        "historico": historico,
        "manifestacoes": manifestacoes,
    }


def criar_perfil_comunitario(nome_exibicao: str, comunidade_id: int, papel: str, funcao_informada: str = ""):
    if papel not in {"morador", "representante"}:
        raise ValueError("Papel comunitário inválido.")
    if not obter_comunidade(comunidade_id):
        raise ValueError("Comunidade não encontrada.")
    agora = _agora_iso()
    with conectar() as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO perfis_comunitarios
            (nome_exibicao, comunidade_id, papel, funcao_informada, status_verificacao, data_criacao, ativo)
            VALUES (?, ?, ?, ?, 'demo', ?, 1)
            """,
            (nome_exibicao.strip(), comunidade_id, papel, funcao_informada.strip(), agora),
        )
        return cursor.lastrowid


def obter_perfil_comunitario(perfil_id: int):
    with conectar() as conexao:
        linha = conexao.execute(
            """
            SELECT p.*, c.nome AS comunidade_nome, c.municipio AS comunidade_municipio
            FROM perfis_comunitarios p
            JOIN comunidades c ON c.id = p.comunidade_id
            WHERE p.id = ? AND p.ativo = 1
            """,
            (perfil_id,),
        ).fetchone()
    return dict(linha) if linha else None


def listar_perfis_comunitarios_demo():
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT p.*, c.nome AS comunidade_nome, c.municipio AS comunidade_municipio
            FROM perfis_comunitarios p
            JOIN comunidades c ON c.id = p.comunidade_id
            WHERE p.ativo = 1
            ORDER BY p.data_criacao DESC
            """
        ).fetchall()
    return [dict(x) for x in linhas]


def listar_relatos_do_perfil(perfil_id: int, limite: int = 100):
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT r.*, dr.demanda_id, d.protocolo AS demanda_protocolo,
                   d.status AS demanda_status, d.titulo AS demanda_titulo,
                   d.prioridade AS demanda_prioridade
            FROM relatos r
            LEFT JOIN demanda_relatos dr ON dr.relato_id = r.id
            LEFT JOIN demandas d ON d.id = dr.demanda_id
            WHERE r.perfil_id = ?
            ORDER BY r.data_recebimento DESC
            LIMIT ?
            """,
            (perfil_id, limite),
        ).fetchall()
    resultado = []
    for linha in linhas:
        item = _relato_dict(linha)
        resultado.append(item)
    return resultado


def listar_demandas_do_perfil(perfil: dict, limite: int = 200):
    if perfil["papel"] == "representante":
        sql = "SELECT DISTINCT d.* FROM demandas d WHERE d.comunidade_id = ? ORDER BY d.data_atualizacao DESC LIMIT ?"
        parametros = (perfil["comunidade_id"], limite)
    else:
        sql = """
            SELECT DISTINCT d.*
            FROM demandas d
            JOIN demanda_relatos dr ON dr.demanda_id = d.id
            JOIN relatos r ON r.id = dr.relato_id
            WHERE r.perfil_id = ?
            ORDER BY d.data_atualizacao DESC
            LIMIT ?
        """
        parametros = (perfil["id"], limite)
    with conectar() as conexao:
        linhas = conexao.execute(sql, parametros).fetchall()
    return [_demanda_dict(x) for x in linhas]


def perfil_pode_acessar_demanda(perfil: dict, demanda_id: int) -> bool:
    if perfil["papel"] == "representante":
        demanda = obter_demanda(demanda_id)
        return bool(demanda and demanda.get("comunidade_id") == perfil["comunidade_id"])
    with conectar() as conexao:
        linha = conexao.execute(
            """
            SELECT 1
            FROM demanda_relatos dr
            JOIN relatos r ON r.id = dr.relato_id
            WHERE dr.demanda_id = ? AND r.perfil_id = ?
            LIMIT 1
            """,
            (demanda_id, perfil["id"]),
        ).fetchone()
    return bool(linha)


def listar_comunidades_da_instituicao(areas: list[str]):
    areas = list(dict.fromkeys(areas or []))
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT c.id, c.nome, c.municipio, c.grau_acesso,
                   COUNT(DISTINCT d.id) AS demandas_total,
                   SUM(CASE WHEN d.prioridade IN ('critica','alta') THEN 1 ELSE 0 END) AS prioridades_elevadas,
                   SUM(CASE WHEN d.status IN ('encaminhada','em_analise','em_atendimento') THEN 1 ELSE 0 END) AS em_atendimento,
                   MAX(d.data_atualizacao) AS ultima_atualizacao
            FROM comunidades c
            JOIN demandas d ON d.comunidade_id = c.id
            GROUP BY c.id
            ORDER BY ultima_atualizacao DESC
            """
        ).fetchall()
    resultado = []
    for linha in linhas:
        item = dict(linha)
        if not areas:
            continue
        with conectar() as conexao:
            cats = [x[0] for x in conexao.execute(
                "SELECT DISTINCT categoria FROM demandas WHERE comunidade_id = ?",
                (item["id"],),
            ).fetchall()]
        if "outro" in areas or any(cat in areas for cat in cats):
            resultado.append(item)
    return resultado


def resumo_comunidade_periodo(comunidade_id: int, dias: int):
    desde = (datetime.now(timezone.utc) - timedelta(days=dias)).replace(microsecond=0).isoformat()
    with conectar() as conexao:
        demandas = [dict(x) for x in conexao.execute(
            """
            SELECT id, protocolo, titulo, categoria, prioridade, status, data_atualizacao
            FROM demandas
            WHERE comunidade_id = ? AND data_atualizacao >= ?
            ORDER BY data_atualizacao DESC
            """,
            (comunidade_id, desde),
        ).fetchall()]
        mensagens = conexao.execute(
            "SELECT COUNT(*) FROM mensagens_comunidade WHERE comunidade_id = ? AND data_criacao >= ?",
            (comunidade_id, desde),
        ).fetchone()[0]
    return {
        "periodo_dias": dias,
        "desde": desde,
        "demandas": demandas,
        "total_demandas": len(demandas),
        "prioridades_elevadas": sum(1 for d in demandas if d["prioridade"] in {"critica", "alta"}),
        "concluidas": sum(1 for d in demandas if d["status"] in {"concluido", "concluida"}),
        "mensagens": mensagens,
    }


def salvar_modelo_institucional(instituicao_id: int, nome_original: str, arquivo_ref: str):
    with conectar() as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO modelos_institucionais (instituicao_id, nome_original, arquivo_ref, data_criacao)
            VALUES (?, ?, ?, ?)
            """,
            (instituicao_id, nome_original, arquivo_ref, _agora_iso()),
        )
        return cursor.lastrowid


def listar_modelos_institucionais(instituicao_id: int):
    with conectar() as conexao:
        linhas = conexao.execute(
            """
            SELECT id, nome_original, arquivo_ref, data_criacao
            FROM modelos_institucionais
            WHERE instituicao_id = ?
            ORDER BY data_criacao DESC
            """,
            (instituicao_id,),
        ).fetchall()
    return [dict(x) for x in linhas]


def obter_relato_com_demanda(relato_id: int):
    with conectar() as conexao:
        linha = conexao.execute(
            """
            SELECT r.*, dr.demanda_id
            FROM relatos r
            LEFT JOIN demanda_relatos dr ON dr.relato_id = r.id
            WHERE r.id = ?
            """,
            (relato_id,),
        ).fetchone()
    return _relato_dict(linha) if linha else None


def estatisticas_dashboard():
    with conectar() as conexao:
        total_relatos = conexao.execute("SELECT COUNT(*) FROM relatos").fetchone()[0]
        total_demandas = conexao.execute("SELECT COUNT(*) FROM demandas").fetchone()[0]
        total_comunidades = conexao.execute("SELECT COUNT(*) FROM comunidades WHERE ativa = 1").fetchone()[0]
        criticas = conexao.execute("SELECT COUNT(*) FROM demandas WHERE prioridade = 'critica' AND status != 'concluida'").fetchone()[0]
        altas = conexao.execute("SELECT COUNT(*) FROM demandas WHERE prioridade = 'alta' AND status != 'concluida'").fetchone()[0]
        em_atendimento = conexao.execute("SELECT COUNT(*) FROM demandas WHERE status IN ('encaminhada','em_analise','em_atendimento')").fetchone()[0]
        concluidas = conexao.execute("SELECT COUNT(*) FROM demandas WHERE status = 'concluida'").fetchone()[0]
    return {
        "relatos": total_relatos,
        "demandas": total_demandas,
        "comunidades": total_comunidades,
        "criticas": criticas,
        "altas": altas,
        "em_atendimento": em_atendimento,
        "concluidas": concluidas,
    }


def _relato_dict(linha):
    item = dict(linha)
    item["necessidades"] = _loads(item.pop("necessidades_json"))
    item["recursos_disponiveis"] = _loads(item.pop("recursos_json"))
    item["informacoes_faltantes"] = _loads(item.pop("informacoes_faltantes_json"))
    item["possivel_emergencia"] = bool(item["possivel_emergencia"])
    item["revisao_humana"] = bool(item["revisao_humana"])
    item["localidade_pendente"] = bool(item.get("localidade_pendente", 0))
    item["consentimento_audio"] = bool(item.get("consentimento_audio", 0))
    return item


def _demanda_dict(linha):
    item = dict(linha)
    item["necessidades"] = _loads(item.pop("necessidades_json"))
    item["recursos_disponiveis"] = _loads(item.pop("recursos_json"))
    item["divergencias"] = _loads(item.pop("divergencias_json"))
    item["informacoes_faltantes"] = _loads(item.pop("informacoes_faltantes_json"))
    return item


def _comunidade_dict(linha):
    item = dict(linha)
    item["publicidade_autorizada"] = bool(item.get("publicidade_autorizada"))
    item["visibilidade_publica"] = bool(item.get("visibilidade_publica", item.get("publicidade_autorizada")))
    item["ativa"] = bool(item.get("ativa", 1))
    item["area_geojson"] = _loads(item.get("area_geojson"), None) if item.get("area_geojson") else None
    return item


# Compatibilidade temporária com o código antigo.
def salvar_registro(comunidade, mensagem, tipo, urgencia_informada=None, latitude=None, longitude=None, resultado=None):
    dados = {
        "comunidade": comunidade,
        "relato": mensagem,
        "tipo": tipo,
        "urgencia": urgencia_informada or "nao_informado",
        "latitude": latitude,
        "longitude": longitude,
        "origem": "outro",
        "data_ocorrencia": None,
    }
    return salvar_relato_bruto(dados)


def listar_registros():
    return listar_relatos()

"""Camada de provedor de IA.

O restante do projeto não precisa conhecer detalhes do SDK de uma empresa específica.
Hoje o provedor real implementado é OpenAI. Existe também o modo ``mock`` para
validar o fluxo do protótipo sem consumir créditos; ele NÃO deve ser apresentado
como execução real de IA. A transcrição mock usa texto fixo e identificado como simulação.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any, Callable

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # O projeto também funciona com variáveis definidas diretamente no sistema.
    pass


AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").strip().lower()
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip()
TRANSCRIPTION_PROVIDER = os.getenv("TRANSCRIPTION_PROVIDER", AI_PROVIDER).strip().lower()
TRANSCRIPTION_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe").strip()


class ProvedorIAError(RuntimeError):
    """Erro de configuração ou execução do provedor de IA."""


def info_provedor() -> dict[str, str]:
    return {
        "provedor_ia": AI_PROVIDER,
        "modelo_ia": MODEL if AI_PROVIDER == "openai" else AI_PROVIDER,
        "provedor_transcricao": TRANSCRIPTION_PROVIDER,
        "modelo_transcricao": TRANSCRIPTION_MODEL if TRANSCRIPTION_PROVIDER == "openai" else TRANSCRIPTION_PROVIDER,
    }


def _cliente_openai():
    try:
        from openai import OpenAI
    except ImportError as erro:
        raise ProvedorIAError(
            "Pacote 'openai' não instalado. Rode: pip install -r requirements.txt"
        ) from erro

    if not os.getenv("OPENAI_API_KEY"):
        raise ProvedorIAError(
            "OPENAI_API_KEY não configurada. O dado foi preservado; configure a chave para processar com IA."
        )
    return OpenAI()


def resposta_estruturada(
    *,
    instructions: str,
    input_data: Any,
    schema_name: str,
    schema: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Executa uma tarefa de saída estruturada no provedor configurado."""
    inicio = time.perf_counter()

    if AI_PROVIDER == "openai":
        client = _cliente_openai()
        entrada = input_data if isinstance(input_data, str) else json.dumps(input_data, ensure_ascii=False)
        resposta = client.responses.create(
            model=MODEL,
            instructions=instructions,
            input=entrada,
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
        )
        resultado = json.loads(resposta.output_text)
        uso = getattr(resposta, "usage", None)
        return resultado, {
            "provedor": "openai",
            "modelo": MODEL,
            "latencia_ms": int((time.perf_counter() - inicio) * 1000),
            "modo_teste": False,
            "tokens_entrada": getattr(uso, "input_tokens", None) if uso else None,
            "tokens_saida": getattr(uso, "output_tokens", None) if uso else None,
            "trace_id": getattr(resposta, "id", None),
        }

    if AI_PROVIDER == "mock":
        resultado = _resposta_mock(schema_name, input_data)
        return resultado, {
            "provedor": "mock",
            "modelo": "mock-local-sem-llm",
            "latencia_ms": int((time.perf_counter() - inicio) * 1000),
            "modo_teste": True,
        }

    raise ProvedorIAError(
        f"AI_PROVIDER='{AI_PROVIDER}' não possui adaptador implementado. "
        "Use 'openai' ou 'mock' nesta versão."
    )



def resposta_com_ferramentas(
    *,
    instructions: str,
    input_data: Any,
    tools: list[dict[str, Any]],
    tool_handlers: dict[str, Callable[..., Any]],
    schema_name: str,
    schema: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Executa um agente que pode chamar funções locais antes de gerar a resposta final."""
    inicio = time.perf_counter()

    if AI_PROVIDER == "mock":
        if not tools:
            raise ProvedorIAError("O agente de teste precisa de ao menos uma ferramenta.")
        ferramenta = tools[0]
        nome = ferramenta["name"]
        dados = input_data if isinstance(input_data, dict) else {}
        args = {
            "categoria": dados.get("categoria", "outro"),
            "comunidade_id": dados.get("comunidade_id"),
        }
        resultado_ferramenta = tool_handlers[nome](**args)
        resultado = _resposta_mock(
            schema_name,
            {
                "entrada": dados,
                "resultado_ferramenta": resultado_ferramenta,
            },
        )
        return resultado, {
            "provedor": "mock",
            "modelo": "mock-local-sem-llm",
            "latencia_ms": int((time.perf_counter() - inicio) * 1000),
            "modo_teste": True,
            "tokens_entrada": None,
            "tokens_saida": None,
            "trace_id": f"mock-{uuid.uuid4().hex[:10]}",
            "ferramentas_usadas": [nome],
        }

    if AI_PROVIDER != "openai":
        raise ProvedorIAError(
            f"AI_PROVIDER='{AI_PROVIDER}' não possui adaptador de ferramentas."
        )

    client = _cliente_openai()
    entrada_texto = input_data if isinstance(input_data, str) else json.dumps(input_data, ensure_ascii=False)
    entrada: list[Any] = [{"role": "user", "content": entrada_texto}]
    ferramentas_usadas: list[str] = []
    tokens_entrada = 0
    tokens_saida = 0
    trace_id = None

    primeira = client.responses.create(
        model=MODEL,
        instructions=instructions,
        input=entrada,
        tools=tools,
        tool_choice="required",
    )
    trace_id = getattr(primeira, "id", None)
    uso = getattr(primeira, "usage", None)
    if uso:
        tokens_entrada += getattr(uso, "input_tokens", 0) or 0
        tokens_saida += getattr(uso, "output_tokens", 0) or 0

    entrada.extend(primeira.output)
    chamadas = [item for item in primeira.output if getattr(item, "type", "") == "function_call"]
    if not chamadas:
        raise ProvedorIAError("O agente não acionou a ferramenta obrigatória.")

    for chamada in chamadas:
        nome = chamada.name
        if nome not in tool_handlers:
            raise ProvedorIAError(f"Ferramenta desconhecida solicitada pelo agente: {nome}")
        try:
            argumentos = json.loads(chamada.arguments or "{}")
        except json.JSONDecodeError as erro:
            raise ProvedorIAError("A IA retornou argumentos inválidos para a ferramenta.") from erro
        retorno = tool_handlers[nome](**argumentos)
        ferramentas_usadas.append(nome)
        entrada.append({
            "type": "function_call_output",
            "call_id": chamada.call_id,
            "output": json.dumps(retorno, ensure_ascii=False),
        })

    final = client.responses.create(
        model=MODEL,
        instructions=instructions,
        input=entrada,
        tools=tools,
        tool_choice="none",
        text={
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": schema,
                "strict": True,
            }
        },
    )
    uso = getattr(final, "usage", None)
    if uso:
        tokens_entrada += getattr(uso, "input_tokens", 0) or 0
        tokens_saida += getattr(uso, "output_tokens", 0) or 0

    return json.loads(final.output_text), {
        "provedor": "openai",
        "modelo": MODEL,
        "latencia_ms": int((time.perf_counter() - inicio) * 1000),
        "modo_teste": False,
        "tokens_entrada": tokens_entrada or None,
        "tokens_saida": tokens_saida or None,
        "trace_id": trace_id,
        "ferramentas_usadas": ferramentas_usadas,
    }


def transcrever_audio(
    *,
    conteudo: bytes,
    nome_arquivo: str,
    content_type: str | None = None,
    idioma: str = "pt",
) -> tuple[str, dict[str, Any]]:
    """Converte áudio em texto sem armazenar o arquivo no projeto."""
    inicio = time.perf_counter()

    if TRANSCRIPTION_PROVIDER == "openai":
        client = _cliente_openai()
        arquivo = (nome_arquivo, conteudo, content_type or "application/octet-stream")
        resposta = client.audio.transcriptions.create(
            model=TRANSCRIPTION_MODEL,
            file=arquivo,
            language=idioma,
        )
        texto = getattr(resposta, "text", None)
        if not texto:
            texto = str(resposta)
        return texto.strip(), {
            "provedor": "openai",
            "modelo": TRANSCRIPTION_MODEL,
            "latencia_ms": int((time.perf_counter() - inicio) * 1000),
            "modo_teste": False,
        }

    if TRANSCRIPTION_PROVIDER == "mock":
        # Texto fixo e explicitamente demonstrativo para permitir testar toda a jornada
        # sem consumir uma API externa. Ele não representa o conteúdo real do áudio.
        return (
            "Eu sou da comunidade Tumbira. O motor que puxa água parou e estamos sem água desde ontem.",
            {
                "provedor": "mock",
                "modelo": "transcricao-demonstrativa",
                "latencia_ms": int((time.perf_counter() - inicio) * 1000),
                "modo_teste": True,
            },
        )

    raise ProvedorIAError(
        f"TRANSCRIPTION_PROVIDER='{TRANSCRIPTION_PROVIDER}' não possui adaptador implementado."
    )


def _resposta_mock(schema_name: str, input_data: Any) -> dict[str, Any]:
    """Resposta determinística para testes locais do fluxo, sem chamada de LLM."""
    if schema_name == "triagem_amazonas_comunidades":
        dados = input_data if isinstance(input_data, dict) else {"relato": str(input_data)}
        relato = (dados.get("relato") or "").strip()
        normalizado = relato.lower()
        categoria = "outro"
        grupos = [
            ("agua", ["água", "agua", "caixa d'água", "poço", "poco"]),
            ("medicamentos", ["remédio", "remedio", "medicamento", "farmácia", "farmacia"]),
            ("saude", ["saúde", "saude", "doente", "hospital", "posto", "sangramento", "risco de morte", "ferido", "ferida", "acidente", "febre"]),
            ("alimentos", ["alimento", "comida", "cesta", "fome"]),
            ("transporte", ["barco", "transporte", "ônibus", "onibus", "voadeira"]),
            ("seguranca", ["furto", "roubo", "segurança", "seguranca", "ameaça", "ameaca"]),
            ("educacao", ["escola", "professor", "educação", "educacao"]),
            ("energia", ["energia", "luz", "gerador"]),
            ("conectividade", ["internet", "sinal", "conectividade"]),
            ("infraestrutura", ["ponte", "estrada", "infraestrutura"]),
            ("documentacao", ["cpf", "documento", "registro"]),
        ]
        for candidato, termos in grupos:
            if any(t in normalizado for t in termos):
                categoria = candidato
                break

        urgencia_usuario = (dados.get("urgencia_informada_pelo_usuario") or "").lower()
        critica = any(t in normalizado for t in ["risco de morte", "morrendo", "incêndio", "incendio", "sangramento grave"])
        if critica:
            prioridade, janela = "critica", "imediata"
        elif urgencia_usuario == "alta" or any(t in normalizado for t in ["urgente", "desde ontem", "sem água", "sem agua"]):
            prioridade, janela = "alta", "semanal"
        else:
            prioridade, janela = "acompanhamento", "mensal"

        palavras = re.findall(r"[a-zA-ZÀ-ÿ0-9]+", normalizado)
        chave = "_".join(palavras[:5]) or "demanda_teste"
        return {
            "categoria": categoria,
            "subcategoria": "",
            "titulo_demanda": f"Demanda de {categoria} — teste local",
            "chave_agrupamento": chave[:80],
            "resumo": f"Relato recebido em modo de teste local: {relato[:280]}",
            "necessidades": [],
            "recursos_disponiveis": [],
            "informacoes_faltantes": ["Análise real de IA não executada neste modo de teste."],
            "prioridade": prioridade,
            "janela_encaminhamento": janela,
            "justificativa_prioridade": "Classificação heurística somente para teste do fluxo, sem LLM.",
            "possivel_emergencia": critica,
            "revisao_humana": True,
        }

    if schema_name == "identificacao_localidade":
        dados = input_data if isinstance(input_data, dict) else {"relato": str(input_data)}
        relato = (dados.get("relato") or "").strip()
        normalizado = relato.casefold()
        catalogo = dados.get("comunidades_cadastradas") or []
        for comunidade in catalogo:
            nome = (comunidade.get("nome") or "").strip()
            nome_curto = nome.casefold().replace("comunidade do ", "").replace("comunidade de ", "").strip()
            if nome and (nome.casefold() in normalizado or (len(nome_curto) >= 4 and nome_curto in normalizado)):
                return {
                    "reconheceu_localidade": True,
                    "comunidade_mencionada": nome,
                    "referencia_localidade": nome,
                    "precisa_confirmacao": True,
                    "observacao": "Correspondência textual com o catálogo no modo de teste.",
                }
        referencia = ""
        padroes = [r"(?:rua|ramal|rio|bairro|estrada|igarapé|igarape)\s+[^,.;]{2,80}"]
        for padrao in padroes:
            achado = re.search(padrao, relato, flags=re.IGNORECASE)
            if achado:
                referencia = achado.group(0).strip()
                break
        return {
            "reconheceu_localidade": bool(referencia),
            "comunidade_mencionada": "",
            "referencia_localidade": referencia,
            "precisa_confirmacao": True,
            "observacao": "O modo de teste não infere comunidade quando ela não aparece no catálogo.",
        }

    if schema_name == "formalizacao_relato":
        dados = input_data if isinstance(input_data, dict) else {"texto_original": str(input_data)}
        texto = (dados.get("texto_original") or "").strip()
        return {
            "texto_formal": texto,
            "observacao": "Modo de teste: o texto foi preservado sem reescrita por LLM.",
        }

    if schema_name == "consolidacao_demanda":
        relatos = input_data if isinstance(input_data, list) else []
        resumos = [r.get("resumo_ia") or r.get("mensagem_original") or "" for r in relatos]
        prioridades = [r.get("prioridade_ia") for r in relatos]
        ordem = {"estrutural": 0, "acompanhamento": 1, "alta": 2, "critica": 3}
        prioridade = max((p for p in prioridades if p in ordem), key=lambda p: ordem[p], default="acompanhamento")
        janela = {"critica": "imediata", "alta": "semanal", "acompanhamento": "mensal", "estrutural": "anual"}[prioridade]
        necessidades = []
        recursos = []
        faltantes = ["Consolidação real de IA não executada neste modo de teste."]
        for r in relatos:
            necessidades.extend(r.get("necessidades") or [])
            recursos.extend(r.get("recursos_disponiveis") or [])
        return {
            "titulo_demanda": "Demanda consolidada — teste local",
            "resumo_consolidado": " | ".join(x for x in resumos if x)[:1200],
            "necessidades_consolidadas": list(dict.fromkeys(necessidades)),
            "recursos_consolidados": list(dict.fromkeys(recursos)),
            "divergencias": [],
            "informacoes_faltantes": faltantes,
            "prioridade_consolidada": prioridade,
            "janela_encaminhamento": janela,
        }

    if schema_name == "roteamento_demanda":
        pacote = input_data if isinstance(input_data, dict) else {}
        entrada = pacote.get("entrada") or {}
        candidatas = pacote.get("resultado_ferramenta") or []
        faltantes = entrada.get("informacoes_faltantes") or []
        status = entrada.get("status") or ""
        bloqueada = status in {"contestada", "em_revisao", "revisao_prioritaria"}
        escolhida = candidatas[0] if candidatas and not bloqueada else None
        return {
            "pronta_para_encaminhamento": bool(escolhida) and status == "pronta_encaminhamento",
            "instituicao_id_sugerida": escolhida.get("id") if escolhida else None,
            "instituicao_nome_sugerida": escolhida.get("nome") if escolhida else "",
            "justificativa": (
                "Instituição compatível selecionada pela ferramenta de busca no modo de teste."
                if escolhida else
                "A demanda precisa de revisão humana ou não há instituição compatível cadastrada."
            ),
            "informacoes_faltantes": faltantes,
            "revisao_humana": bloqueada or not bool(escolhida),
        }

    raise ProvedorIAError(f"Schema '{schema_name}' não implementado no modo mock.")

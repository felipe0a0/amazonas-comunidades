from typing import Any

from banco import listar_instituicoes
from provedor_ia import MODEL, resposta_com_ferramentas


PROMPT_VERSION = "roteamento-v1"

ROTEAMENTO_SCHEMA = {
    "type": "object",
    "properties": {
        "pronta_para_encaminhamento": {"type": "boolean"},
        "instituicao_id_sugerida": {"type": ["integer", "null"]},
        "instituicao_nome_sugerida": {"type": "string"},
        "justificativa": {"type": "string"},
        "informacoes_faltantes": {"type": "array", "items": {"type": "string"}},
        "revisao_humana": {"type": "boolean"},
    },
    "required": [
        "pronta_para_encaminhamento",
        "instituicao_id_sugerida",
        "instituicao_nome_sugerida",
        "justificativa",
        "informacoes_faltantes",
        "revisao_humana",
    ],
    "additionalProperties": False,
}

BUSCAR_INSTITUICOES_TOOL = {
    "type": "function",
    "name": "buscar_instituicoes_compativeis",
    "description": (
        "Consulta somente o cadastro institucional do Amazonas Comunidades e retorna "
        "instituicoes ativas compatíveis com a categoria da demanda. Use antes de sugerir destino."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "categoria": {"type": "string"},
            "comunidade_id": {"type": ["integer", "null"]},
        },
        "required": ["categoria", "comunidade_id"],
        "additionalProperties": False,
    },
    "strict": True,
}


def _buscar_instituicoes_compativeis(categoria: str, comunidade_id: int | None = None):
    # O filtro territorial entra quando o cadastro institucional tiver municípios/territórios.
    candidatas = listar_instituicoes(categoria)
    return [
        {
            "id": item["id"],
            "nome": item["nome"],
            "descricao": item.get("descricao") or "",
            "areas": item.get("areas") or [],
            "ordem_prioridade": item.get("ordem_prioridade"),
            "demonstracao": bool(item.get("demonstracao")),
        }
        for item in candidatas
    ]


def analisar_roteamento(demanda: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    entrada = {
        "demanda_id": demanda["id"],
        "protocolo": demanda["protocolo"],
        "comunidade_id": demanda.get("comunidade_id"),
        "comunidade": demanda.get("comunidade"),
        "categoria": demanda.get("categoria"),
        "subcategoria": demanda.get("subcategoria"),
        "resumo": demanda.get("resumo"),
        "necessidades": demanda.get("necessidades") or [],
        "informacoes_faltantes": demanda.get("informacoes_faltantes") or [],
        "prioridade": demanda.get("prioridade"),
        "status": demanda.get("status"),
    }

    resultado, meta = resposta_com_ferramentas(
        instructions="""
Você é o agente de roteamento do Amazonas Comunidades.
Seu trabalho é consultar a ferramenta institucional disponível e sugerir o próximo destino da demanda.

Regras:
1. Sempre use a ferramenta antes de sugerir uma instituição.
2. Nunca invente instituição, competência, município atendido ou parceria.
3. Escolha somente entre os resultados retornados pela ferramenta.
4. Se a demanda estiver contestada, em revisão ou em revisão prioritária, não autorize encaminhamento automático.
5. Se faltarem informações essenciais para definir competência, marque revisao_humana=true.
6. Prioridade não define competência institucional.
7. A decisão final continua auditável e pode ser revista por uma pessoa.
8. Instituições marcadas como demonstracao servem apenas para o protótipo e não representam parceria oficial.
""",
        input_data=entrada,
        tools=[BUSCAR_INSTITUICOES_TOOL],
        tool_handlers={"buscar_instituicoes_compativeis": _buscar_instituicoes_compativeis},
        schema_name="roteamento_demanda",
        schema=ROTEAMENTO_SCHEMA,
    )
    meta["prompt_version"] = PROMPT_VERSION
    return resultado, meta

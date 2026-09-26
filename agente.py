import re
from typing import Any

from provedor_ia import MODEL, AI_PROVIDER, resposta_estruturada


PROMPT_VERSION = "3.0"

CATEGORIAS = [
    "saude",
    "medicamentos",
    "alimentos",
    "agua",
    "transporte",
    "seguranca",
    "infraestrutura",
    "educacao",
    "documentacao",
    "energia",
    "conectividade",
    "outro",
]

TRIAGEM_SCHEMA = {
    "type": "object",
    "properties": {
        "categoria": {"type": "string", "enum": CATEGORIAS},
        "subcategoria": {"type": "string"},
        "titulo_demanda": {"type": "string"},
        "chave_agrupamento": {"type": "string"},
        "resumo": {"type": "string"},
        "necessidades": {"type": "array", "items": {"type": "string"}},
        "recursos_disponiveis": {"type": "array", "items": {"type": "string"}},
        "informacoes_faltantes": {"type": "array", "items": {"type": "string"}},
        "prioridade": {
            "type": "string",
            "enum": ["critica", "alta", "acompanhamento", "estrutural"],
        },
        "janela_encaminhamento": {
            "type": "string",
            "enum": ["imediata", "semanal", "mensal", "anual"],
        },
        "justificativa_prioridade": {"type": "string"},
        "possivel_emergencia": {"type": "boolean"},
        "revisao_humana": {"type": "boolean"},
    },
    "required": [
        "categoria",
        "subcategoria",
        "titulo_demanda",
        "chave_agrupamento",
        "resumo",
        "necessidades",
        "recursos_disponiveis",
        "informacoes_faltantes",
        "prioridade",
        "janela_encaminhamento",
        "justificativa_prioridade",
        "possivel_emergencia",
        "revisao_humana",
    ],
    "additionalProperties": False,
}

CONSOLIDACAO_SCHEMA = {
    "type": "object",
    "properties": {
        "titulo_demanda": {"type": "string"},
        "resumo_consolidado": {"type": "string"},
        "necessidades_consolidadas": {"type": "array", "items": {"type": "string"}},
        "recursos_consolidados": {"type": "array", "items": {"type": "string"}},
        "divergencias": {"type": "array", "items": {"type": "string"}},
        "informacoes_faltantes": {"type": "array", "items": {"type": "string"}},
        "prioridade_consolidada": {
            "type": "string",
            "enum": ["critica", "alta", "acompanhamento", "estrutural"],
        },
        "janela_encaminhamento": {
            "type": "string",
            "enum": ["imediata", "semanal", "mensal", "anual"],
        },
    },
    "required": [
        "titulo_demanda",
        "resumo_consolidado",
        "necessidades_consolidadas",
        "recursos_consolidados",
        "divergencias",
        "informacoes_faltantes",
        "prioridade_consolidada",
        "janela_encaminhamento",
    ],
    "additionalProperties": False,
}



FORMALIZACAO_SCHEMA = {
    "type": "object",
    "properties": {
        "texto_formal": {"type": "string"},
        "observacao": {"type": "string"},
    },
    "required": ["texto_formal", "observacao"],
    "additionalProperties": False,
}


def formalizar_relato(texto: str) -> tuple[dict[str, Any], dict[str, Any]]:
    resultado, meta = resposta_estruturada(
        instructions="""
Você apoia o projeto Amazonas Comunidades. Receba um relato em português falado, informal, regional ou com
construções gramaticais não padronizadas e produza uma versão institucional clara em português brasileiro.

Regras obrigatórias:
1. Preserve integralmente o sentido do relato; não acrescente fatos, datas, números, diagnósticos ou instituições.
2. Preserve incertezas e expressões de possibilidade. Não transforme suspeita em confirmação.
3. Não apague informações relevantes por causa de variação regional, oralidade ou erro gramatical.
4. Corrija apenas forma, organização, pontuação e clareza.
5. Não julgue a forma de falar da pessoa.
6. A versão formal deve ser curta, objetiva e adequada para leitura institucional.
7. Em observacao, diga de forma breve se houve apenas organização/redação; nunca invente justificativas.
""",
        input_data={"texto_original": texto},
        schema_name="formalizacao_relato",
        schema=FORMALIZACAO_SCHEMA,
    )
    meta["prompt_version"] = "formalizacao-v1"
    return resultado, meta

def _slug(texto: str) -> str:
    texto = (texto or "demanda").lower().strip()
    texto = re.sub(r"[^a-z0-9áàâãéêíóôõúç]+", "_", texto, flags=re.IGNORECASE)
    texto = re.sub(r"_+", "_", texto).strip("_")
    return texto[:80] or "demanda"


def interpretar_relato(
    mensagem: str,
    tipo_informado: str = "",
    urgencia_informada: str = "nao_informado",
) -> tuple[dict[str, Any], dict[str, Any]]:
    instrucoes = """
Você é o agente de triagem do projeto Amazonas Comunidades.

Seu papel é transformar um relato livre em dados estruturados SEM declarar que o relato é verdadeiro ou falso.
Você organiza o que foi informado; não substitui investigação humana, atendimento de emergência ou decisão institucional.

Regras obrigatórias:
1. Não invente fatos, quantidades, datas, diagnósticos, instituições ou localidades.
2. A prioridade representa sinais presentes no relato, não uma confirmação técnica de emergência.
3. Se houver possível risco imediato à vida/segurança, marque possivel_emergencia=true e revisao_humana=true.
4. Preserve incerteza: quando faltar informação relevante, liste-a em informacoes_faltantes.
5. A chave_agrupamento deve ser curta e estável, descrevendo o PROBLEMA central (ex.: falta_medicamentos, caixa_dagua_danificada, transporte_escolar_irregular). Não inclua nome da comunidade.
6. Use somente uma categoria da lista permitida.
7. A janela de encaminhamento deve seguir a necessidade de tempo:
   - imediata: possível risco grave/tempo crítico;
   - semanal: necessidade importante que não deve esperar fechamento mensal;
   - mensal: problema recorrente/estrutural que pode ser consolidado;
   - anual: indicador histórico/planejamento, sem necessidade operacional imediata.
8. prioridade deve ser uma de: critica, alta, acompanhamento, estrutural.
9. Não use a palavra 'confirmado' a menos que o próprio relato diga que houve confirmação por fonte identificada.
10. O resumo deve ser objetivo e atribuir a informação aos relatos, ex.: 'Morador relata...'.
"""

    entrada = {
        "relato": mensagem,
        "tipo_informado_pelo_usuario": tipo_informado or "não informado",
        "urgencia_informada_pelo_usuario": urgencia_informada or "não informado",
        "categorias_permitidas": CATEGORIAS,
    }

    resultado, meta = resposta_estruturada(
        instructions=instrucoes,
        input_data=entrada,
        schema_name="triagem_amazonas_comunidades",
        schema=TRIAGEM_SCHEMA,
    )
    resultado["chave_agrupamento"] = _slug(resultado["chave_agrupamento"])
    meta["prompt_version"] = PROMPT_VERSION
    return resultado, meta


def consolidar_demanda(relatos: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    entrada = []
    for r in relatos:
        entrada.append(
            {
                "protocolo": r["protocolo"],
                "mensagem_original": r["mensagem_original"],
                "resumo_ia": r.get("resumo_ia"),
                "necessidades": r.get("necessidades", []),
                "recursos_disponiveis": r.get("recursos_disponiveis", []),
                "prioridade_ia": r.get("prioridade_ia"),
                "janela_encaminhamento": r.get("janela_encaminhamento"),
            }
        )

    resultado, meta = resposta_estruturada(
        instructions="""
Você consolida múltiplos relatos que já foram associados à mesma demanda comunitária.
Não invente fatos. Preserve divergências entre relatos em vez de escolher arbitrariamente um lado.
Use a maior prioridade sustentada por evidências textuais presentes nos relatos.
O resultado será usado para produzir relatório institucional; portanto escreva de forma objetiva e atribua as informações aos relatos.
""",
        input_data=entrada,
        schema_name="consolidacao_demanda",
        schema=CONSOLIDACAO_SCHEMA,
    )
    meta["prompt_version"] = PROMPT_VERSION
    return resultado, meta


# Compatibilidade com o nome usado pelo protótipo anterior.
def interpretar_mensagem(mensagem):
    resultado, _ = interpretar_relato(mensagem)
    return resultado

LOCALIDADE_SCHEMA = {
    "type": "object",
    "properties": {
        "reconheceu_localidade": {"type": "boolean"},
        "comunidade_mencionada": {"type": "string"},
        "referencia_localidade": {"type": "string"},
        "precisa_confirmacao": {"type": "boolean"},
        "observacao": {"type": "string"},
    },
    "required": [
        "reconheceu_localidade",
        "comunidade_mencionada",
        "referencia_localidade",
        "precisa_confirmacao",
        "observacao",
    ],
    "additionalProperties": False,
}


def identificar_localidade(texto: str, comunidades: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Extrai apenas a referência de localidade dita pela pessoa; não infere por conta própria."""
    catalogo = [
        {"id": c["id"], "nome": c["nome"], "municipio": c.get("municipio") or ""}
        for c in comunidades
    ]
    resultado, meta = resposta_estruturada(
        instructions="""
Você faz parte do agente de triagem do Amazonas Comunidades. Sua única tarefa aqui é identificar se a pessoa
mencionou explicitamente uma comunidade ou alguma referência de localidade no próprio relato.

Regras:
1. Não invente comunidade, município, rua, coordenada ou território.
2. Se um nome do catálogo aparecer de forma clara no relato, use exatamente o nome do catálogo em comunidade_mencionada.
3. Uma rua, rio, ramal, bairro ou ponto de referência pode ir em referencia_localidade, mas não deve ser transformado em comunidade.
4. Se houver dúvida, marque precisa_confirmacao=true.
5. Se nenhuma localidade aparecer, deixe os textos vazios e marque reconheceu_localidade=false.
6. O resultado é uma sugestão para confirmação da pessoa; não é geolocalização automática.
""",
        input_data={"relato": texto, "comunidades_cadastradas": catalogo},
        schema_name="identificacao_localidade",
        schema=LOCALIDADE_SCHEMA,
    )
    meta["prompt_version"] = "localidade-v1"
    return resultado, meta

from collections import Counter

from banco import obter_demanda_completa


def gerar_relatorio_formal(demanda_id: int):
    demanda = obter_demanda_completa(demanda_id)
    if not demanda:
        return None

    relatos = demanda["relatos"]
    origens = Counter(r.get("origem") or "não informada" for r in relatos)
    comunidade_dados = demanda.get("comunidade_dados") or {}
    comunidade_catalogada = bool(demanda.get("comunidade_id"))
    localizacao_catalogada = comunidade_dados.get("latitude_referencia") is not None and comunidade_dados.get("longitude_referencia") is not None

    primeira_data = relatos[0]["data_recebimento"] if relatos else demanda["data_abertura"]
    ultima_data = relatos[-1]["data_recebimento"] if relatos else demanda["data_atualizacao"]

    return {
        "cabecalho": "RELATÓRIO DE DEMANDA COMUNITÁRIA",
        "protocolo": demanda["protocolo"],
        "comunidade": demanda["comunidade"],
        "categoria": demanda["categoria"],
        "subcategoria": demanda["subcategoria"],
        "titulo": demanda["titulo"],
        "periodo": {"inicio": primeira_data, "fim": ultima_data},
        "quantidade_relatos": demanda["quantidade_relatos"],
        "prioridade": demanda["prioridade"],
        "janela_encaminhamento": demanda["janela_encaminhamento"],
        "status": demanda["status"],
        "sintese": demanda["resumo"],
        "necessidades": demanda["necessidades"],
        "recursos_disponiveis": demanda["recursos_disponiveis"],
        "divergencias": demanda["divergencias"],
        "informacoes_faltantes": demanda["informacoes_faltantes"],
        "manifestacoes_comunitarias": [
            {
                "tipo": m["tipo"],
                "autor": m["autor"],
                "texto": m["texto"],
                "data": m["data_criacao"],
            }
            for m in demanda["manifestacoes"]
        ],
        "rastreabilidade": {
            "origens": dict(origens),
            "relatos_preservados": True,
            "comunidade_catalogada": comunidade_catalogada,
            "localizacao_comunitaria_catalogada": localizacao_catalogada,
            "fonte_localizacao": comunidade_dados.get("fonte_dado") if comunidade_dados else None,
        },
        "encaminhamentos": [
            {
                "ordem": e["ordem"],
                "instituicao": e["instituicao_nome"],
                "status": e["status"],
                "motivo": e["motivo"],
                "data_envio": e["data_envio"],
                "data_atualizacao": e["data_atualizacao"],
                "demonstracao": bool(e["demonstracao"]),
            }
            for e in demanda["encaminhamentos"]
        ],
        "nota_metodologica": (
            "Documento estruturado com auxílio de IA a partir de relatos preservados no sistema. "
            "A IA organiza e consolida informações, mas não atesta a veracidade dos fatos nem substitui validação humana ou institucional."
        ),
    }


def gerar_retorno_publico(demanda_id: int):
    demanda = obter_demanda_completa(demanda_id)
    if not demanda:
        return None

    historico_publico = [
        {
            "status": h["status"],
            "descricao": h["descricao"],
            "data": h["data_criacao"],
        }
        for h in demanda["historico"]
        if h["visibilidade"] == "publica"
    ]

    # Deliberadamente não retorna coordenadas, rotas, quantidades de carga ou dados pessoais.
    return {
        "protocolo": demanda["protocolo"],
        "comunidade": demanda["comunidade"],
        "categoria": demanda["categoria"],
        "titulo": demanda["titulo"],
        "status": demanda["status"],
        "prioridade": demanda["prioridade"],
        "quantidade_relatos": demanda["quantidade_relatos"],
        "historico": historico_publico,
        "aviso": "Informações operacionais sensíveis, como rota, quantidade transportada e horário exato de deslocamento, não são exibidas publicamente.",
    }

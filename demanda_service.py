from agente import MODEL, PROMPT_VERSION, consolidar_demanda, interpretar_relato
from agente_roteamento import analisar_roteamento
from banco import (
    adicionar_manifestacao,
    atualizar_demanda_consolidada,
    atualizar_relato_analise,
    atualizar_status_demanda,
    buscar_demanda_aberta,
    criar_demanda,
    criar_encaminhamento,
    instituicoes_ja_tentadas,
    listar_instituicoes,
    marcar_erro_ia,
    obter_demanda,
    obter_encaminhamento_ativo,
    obter_relato,
    registrar_log_ia,
    relatos_da_demanda,
    vincular_relato_demanda,
)


def _registrar_meta_ia(operacao: str, meta: dict, *, relato_id=None, demanda_id=None):
    registrar_log_ia(
        operacao=operacao,
        modelo=meta.get("modelo", MODEL),
        prompt_version=meta.get("prompt_version", PROMPT_VERSION),
        sucesso=True,
        latencia_ms=meta.get("latencia_ms"),
        relato_id=relato_id,
        demanda_id=demanda_id,
        tokens_entrada=meta.get("tokens_entrada"),
        tokens_saida=meta.get("tokens_saida"),
        trace_id=meta.get("trace_id"),
    )


def processar_relato(relato_id: int):
    relato = obter_relato(relato_id)
    if not relato:
        raise ValueError("Relato não encontrado.")

    try:
        # O original é a fonte de verdade. A versão formalizada serve para leitura institucional.
        texto_para_analise = relato["mensagem_original"].strip()
        analise, meta = interpretar_relato(
            texto_para_analise,
            relato.get("tipo_informado") or "",
            relato.get("urgencia_informada") or "nao_informado",
        )
        atualizar_relato_analise(relato_id, analise)
        _registrar_meta_ia("triagem_relato", meta, relato_id=relato_id)
    except Exception as erro:
        marcar_erro_ia(relato_id, str(erro))
        registrar_log_ia(
            operacao="triagem_relato",
            modelo=MODEL,
            prompt_version=PROMPT_VERSION,
            sucesso=False,
            latencia_ms=None,
            erro=str(erro),
            relato_id=relato_id,
        )
        return {
            "relato_id": relato_id,
            "demanda_id": None,
            "processado": False,
            "erro": "O relato foi preservado, mas a análise de IA falhou. Ele ficou aguardando reprocessamento.",
        }

    relato = obter_relato(relato_id)
    demanda = buscar_demanda_aberta(
        relato.get("comunidade_id"),
        relato["comunidade"],
        analise["chave_agrupamento"],
    )

    if demanda:
        demanda_id = demanda["id"]
        demanda_protocolo = demanda["protocolo"]
        nova_demanda = False
    else:
        demanda_id, demanda_protocolo = criar_demanda(relato, analise)
        nova_demanda = True

    vincular_relato_demanda(demanda_id, relato_id)

    relatos = relatos_da_demanda(demanda_id)
    if len(relatos) >= 2:
        try:
            consolidacao, meta = consolidar_demanda(relatos)
            atualizar_demanda_consolidada(demanda_id, consolidacao)
            _registrar_meta_ia("consolidacao_demanda", meta, demanda_id=demanda_id)
        except Exception as erro:
            registrar_log_ia(
                operacao="consolidacao_demanda",
                modelo=MODEL,
                prompt_version=PROMPT_VERSION,
                sucesso=False,
                latencia_ms=None,
                erro=str(erro),
                demanda_id=demanda_id,
            )

    return {
        "relato_id": relato_id,
        "relato_protocolo": relato["protocolo"],
        "demanda_id": demanda_id,
        "demanda_protocolo": demanda_protocolo,
        "nova_demanda": nova_demanda,
        "processado": True,
        "analise": analise,
    }


def registrar_manifestacao(demanda_id: int, tipo: str, autor: str, texto: str):
    if not obter_demanda(demanda_id):
        raise ValueError("Demanda não encontrada.")
    return adicionar_manifestacao(demanda_id, tipo, autor, texto)


def preparar_para_encaminhamento(demanda_id: int, descricao: str):
    demanda = obter_demanda(demanda_id)
    if not demanda:
        raise ValueError("Demanda não encontrada.")
    if demanda["status"] == "contestada":
        raise ValueError("A demanda está contestada e precisa ser revisada antes do encaminhamento.")
    atualizar_status_demanda(demanda_id, "pronta_encaminhamento", descricao)


def sugerir_instituicoes(demanda_id: int):
    demanda = obter_demanda(demanda_id)
    if not demanda:
        raise ValueError("Demanda não encontrada.")
    tentadas = instituicoes_ja_tentadas(demanda_id)
    candidatas = listar_instituicoes(demanda["categoria"])
    return [i for i in candidatas if i["id"] not in tentadas]


def avaliar_roteamento(demanda_id: int):
    demanda = obter_demanda(demanda_id)
    if not demanda:
        raise ValueError("Demanda não encontrada.")

    resultado, meta = analisar_roteamento(demanda)
    _registrar_meta_ia("agente_roteamento", meta, demanda_id=demanda_id)
    resultado["ferramentas_usadas"] = meta.get("ferramentas_usadas", [])
    return resultado


def encaminhar_proxima(demanda_id: int):
    demanda = obter_demanda(demanda_id)
    if not demanda:
        raise ValueError("Demanda não encontrada.")

    if demanda["status"] != "pronta_encaminhamento":
        raise ValueError("A demanda precisa estar marcada como pronta para encaminhamento.")

    ativo = obter_encaminhamento_ativo(demanda_id)
    if ativo:
        return {
            "encaminhamento_id": ativo["id"],
            "ja_existia": True,
            "instituicao": ativo["instituicao_nome"],
        }

    analise = avaliar_roteamento(demanda_id)
    if not analise.get("pronta_para_encaminhamento"):
        return {
            "encaminhamento_id": None,
            "ja_existia": False,
            "instituicao": None,
            "analise_roteamento": analise,
        }

    candidatas = sugerir_instituicoes(demanda_id)
    ids_disponiveis = {i["id"] for i in candidatas}
    instituicao_id = analise.get("instituicao_id_sugerida")
    if instituicao_id not in ids_disponiveis:
        atualizar_status_demanda(
            demanda_id,
            "sem_destinatario",
            "O agente não encontrou uma instituição válida entre as opções cadastradas. Revisão humana necessária.",
        )
        return {
            "encaminhamento_id": None,
            "ja_existia": False,
            "instituicao": None,
            "analise_roteamento": analise,
        }

    escolhida = next(i for i in candidatas if i["id"] == instituicao_id)
    encaminhamento_id = criar_encaminhamento(demanda_id, escolhida["id"])
    return {
        "encaminhamento_id": encaminhamento_id,
        "ja_existia": False,
        "instituicao": escolhida["nome"],
        "analise_roteamento": analise,
    }

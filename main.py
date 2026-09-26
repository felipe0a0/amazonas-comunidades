"""CLI simples para testar o fluxo sem abrir a interface web."""

from banco import criar_banco, salvar_relato_bruto
from demanda_service import processar_relato


criar_banco()

comunidade = input("Comunidade: ").strip()
mensagem = input("Relato: ").strip()
tipo = input("Tipo (opcional): ").strip()
urgencia = input("Urgência informada [nao_informado/baixa/media/alta]: ").strip() or "nao_informado"

relato_id, protocolo = salvar_relato_bruto(
    {
        "comunidade": comunidade,
        "relato": mensagem,
        "tipo": tipo,
        "urgencia": urgencia,
        "latitude": None,
        "longitude": None,
        "origem": "outro",
        "data_ocorrencia": None,
    }
)

print(f"\nRelato preservado: {protocolo}")
print(processar_relato(relato_id))

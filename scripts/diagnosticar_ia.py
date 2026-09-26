import argparse
import asyncio
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from agente import interpretar_relato
from provedor_ia import info_provedor, transcrever_audio


def testar_triagem():
    print("Configuração:", info_provedor())
    resultado, meta = interpretar_relato("A comunidade está sem água desde ontem porque o motor parou.")
    print("\nTriagem executada com sucesso.")
    print("Categoria:", resultado["categoria"])
    print("Prioridade:", resultado["prioridade"])
    print("Modelo:", meta.get("modelo"))
    print("Latência (ms):", meta.get("latencia_ms"))


def testar_audio(caminho: str):
    arquivo = Path(caminho)
    conteudo = arquivo.read_bytes()
    texto, meta = transcrever_audio(
        conteudo=conteudo,
        nome_arquivo=arquivo.name,
        content_type="application/octet-stream",
        idioma="pt",
    )
    print("\nTranscrição executada com sucesso.")
    print("Texto:", texto)
    print("Modelo:", meta.get("modelo"))


def main():
    parser = argparse.ArgumentParser(description="Diagnóstico simples dos provedores de IA do Amazonas Comunidades.")
    parser.add_argument("--audio", help="Arquivo de áudio opcional para testar transcrição real.")
    args = parser.parse_args()
    testar_triagem()
    if args.audio:
        testar_audio(args.audio)


if __name__ == "__main__":
    main()

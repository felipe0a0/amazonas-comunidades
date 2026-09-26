"""Serviço de transcrição de relatos de áudio."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile

from provedor_ia import transcrever_audio


BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "dados" / "audios"
MAX_AUDIO_BYTES = 12 * 1024 * 1024
EXTENSOES_PERMITIDAS = {".webm", ".wav", ".mp3", ".m4a", ".mp4", ".mpeg", ".mpga", ".ogg", ".flac"}


def caminho_audio_ref(audio_ref: str) -> Path | None:
    nome = Path(audio_ref or "").name
    if not nome or nome != audio_ref:
        return None
    caminho = AUDIO_DIR / nome
    return caminho if caminho.exists() and caminho.is_file() else None


async def transcrever_upload(arquivo: UploadFile, idioma: str = "pt", preservar_original: bool = False):
    nome = arquivo.filename or "relato.webm"
    extensao = "." + nome.rsplit(".", 1)[-1].lower() if "." in nome else ".webm"
    if extensao not in EXTENSOES_PERMITIDAS:
        raise ValueError("Formato de áudio não suportado pelo protótipo.")

    conteudo = await arquivo.read()
    if not conteudo:
        raise ValueError("O arquivo de áudio está vazio.")
    if len(conteudo) > MAX_AUDIO_BYTES:
        raise ValueError("Áudio acima do limite de 12 MB do protótipo.")

    texto, meta = transcrever_audio(
        conteudo=conteudo,
        nome_arquivo=nome,
        content_type=arquivo.content_type,
        idioma=idioma,
    )
    if not texto.strip():
        raise ValueError("A transcrição não retornou texto.")

    if preservar_original:
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        audio_ref = f"{uuid.uuid4().hex}{extensao}"
        (AUDIO_DIR / audio_ref).write_bytes(conteudo)
        meta["audio_ref"] = audio_ref
    else:
        meta["audio_ref"] = None

    return texto.strip(), meta

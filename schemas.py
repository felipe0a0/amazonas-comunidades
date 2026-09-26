from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class NovoRelato(BaseModel):
    comunidade_id: int | None = Field(default=None, ge=1)
    comunidade: str | None = Field(default=None, max_length=160)
    municipio: str = Field(default="", max_length=160)
    relato: str = Field(min_length=5, max_length=6000)
    texto_formalizado: str = Field(default="", max_length=8000)
    meio_relato: Literal["texto", "audio", "outro"] = "texto"
    tipo: str = ""
    urgencia: str = "nao_informado"
    origem: Literal["web", "app", "whatsapp", "offline", "radio", "outro"] = "web"
    data_ocorrencia: datetime | None = None
    referencia_localidade: str = Field(default="", max_length=500)
    localidade_pendente: bool = False
    audio_ref: str = Field(default="", max_length=120)
    consentimento_audio: bool = False

    @model_validator(mode="after")
    def validar_localidade(self):
        if self.localidade_pendente:
            return self
        if self.comunidade_id is None and not (self.comunidade or "").strip():
            raise ValueError("Selecione uma comunidade ou envie o relato para revisão de localidade.")
        return self


class NovaComunidade(BaseModel):
    nome: str = Field(min_length=2, max_length=160)
    municipio: str = Field(default="", max_length=160)
    latitude_referencia: float | None = Field(default=None, ge=-90, le=90)
    longitude_referencia: float | None = Field(default=None, ge=-180, le=180)
    grau_acesso: Literal["facil", "medio", "dificil", "nao_classificado"] = "nao_classificado"
    visibilidade_publica: bool = False
    origem_visibilidade: Literal["autorizacao_comunidade", "fonte_publica", "privada"] = "privada"
    observacoes: str = Field(default="", max_length=2000)
    fonte_dado: str = Field(default="cadastro_no_sistema", max_length=200)
    fonte_url: str = Field(default="", max_length=1000)
    area_geojson: dict[str, Any] | list[Any] | None = None

    @model_validator(mode="after")
    def validar_localizacao(self):
        if (self.latitude_referencia is None) != (self.longitude_referencia is None):
            raise ValueError("Latitude e longitude devem ser informadas juntas.")
        if self.visibilidade_publica and self.origem_visibilidade == "privada":
            raise ValueError("Informe a origem da visibilidade pública da comunidade.")
        return self


class IdentificacaoLocalidadeEntrada(BaseModel):
    texto: str = Field(min_length=3, max_length=6000)


class CadastroComunitarioDemo(BaseModel):
    nome_exibicao: str = Field(min_length=2, max_length=120)
    comunidade_id: int = Field(ge=1)
    papel: Literal["morador", "representante"]
    funcao_informada: str = Field(default="", max_length=160)


class LoginComunitarioDemo(BaseModel):
    perfil_id: int = Field(ge=1)


class ManifestacaoEntrada(BaseModel):
    tipo: Literal["confirmar", "complementar", "contestar"]
    autor: str = Field(min_length=2, max_length=160)
    texto: str = Field(min_length=3, max_length=4000)


class ManifestacaoComunitariaEntrada(BaseModel):
    tipo: Literal["confirmar", "complementar", "contestar"]
    texto: str = Field(min_length=3, max_length=4000)


class AtualizacaoEncaminhamento(BaseModel):
    status: Literal[
        "recebido",
        "em_analise",
        "aceito",
        "em_atendimento",
        "concluido",
        "nao_atendido",
        "nao_competente",
    ]
    motivo: str = Field(default="", max_length=4000)
    descricao_publica: str = Field(default="", max_length=1000)


class PrepararEncaminhamento(BaseModel):
    descricao: str = Field(default="Demanda revisada e pronta para encaminhamento.", max_length=1000)


class FormalizacaoRelatoEntrada(BaseModel):
    texto: str = Field(min_length=5, max_length=6000)


class InstituicaoLoginDemo(BaseModel):
    instituicao_id: int = Field(ge=1)


class MensagemInstitucionalEntrada(BaseModel):
    tipo: Literal["informacao", "pedido_informacao", "acao_agendada"] = "informacao"
    titulo: str = Field(min_length=3, max_length=160)
    texto: str = Field(min_length=3, max_length=2000)
    publica: bool = True

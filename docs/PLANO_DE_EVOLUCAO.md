# Plano de evolução

## Presente no protótipo

- relato por voz ou texto;
- leitura em voz alta da transcrição;
- confirmação antes do envio;
- identificação assistida de localidade e estado `localidade_pendente`;
- perfis demonstrativos de morador e representante;
- separação de visibilidade por perfil;
- validação comunitária por confirmar/complementar/contestar;
- dois agentes com responsabilidades distintas;
- ferramenta usada pelo agente de roteamento;
- painel institucional interno com prioridades, comunidades, mapa, relatórios e mensagens;
- rastreabilidade do relato original;
- retenção opcional de áudio com consentimento;
- upload de modelo institucional como referência;
- testes automáticos e casos locais de avaliação.

## Próximo ciclo

- autenticação real e recuperação de conta;
- verificação de representantes e instituições;
- perguntas/respostas privadas vinculadas ao protocolo;
- agrupamento semântico por embeddings;
- preenchimento adaptativo do modelo de relatório anexado;
- comprovantes, anexos e problemas de execução por comunidade;
- idempotência e fila offline robusta;
- métricas maiores de qualidade, custo e latência;
- integração real por API, email ou webhook.

## Produção / futuro

- PostgreSQL + Alembic;
- rate limiting e proteção contra abuso;
- política jurídica/LGPD completa e prazos de retenção;
- RAG com documentos oficiais e competências institucionais;
- WhatsApp;
- rádio quando houver infraestrutura/parceiro;
- módulo de apoio/doações verificado;
- APK/Android;
- agentes adicionais apenas quando novas responsabilidades justificarem.

## Regra de produto

O núcleo permanece:

```text
RELATO -> IA -> DEMANDA -> VALIDAÇÃO -> ROTEAMENTO -> ATENDIMENTO -> RETORNO
```

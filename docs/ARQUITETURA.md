# Arquitetura — Amazonas Comunidades

## Visão geral

```text
Público / morador
       |
       +-- voz -> transcrição -> leitura de confirmação
       +-- texto
       |
       v
Relato original preservado
       |
       +-- identificação de localidade / pergunta se faltar
       |
       v
Agente 1 — Triagem e diálogo
       |
       +-- categoria
       +-- prioridade
       +-- necessidades
       +-- informações faltantes
       +-- chave de agrupamento
       |
       v
Demanda consolidada
       |
       v
Representante da comunidade
 confirmar / complementar / contestar
       |
       v
Agente 2 — Roteamento
       |
       +-- ferramenta de busca de instituições compatíveis
       |
       v
Atendimento institucional
       |
       v
Avisos, mensagens e acompanhamento
```

## Separação por perfil

### Público

Não existe lista pública de demandas. O acompanhamento é feito por protocolo e o mapa usa apenas referências territoriais cuja origem de visibilidade foi registrada.

### Morador

Enxerga apenas os próprios relatos e as demandas ligadas a eles, além de avisos/mensagens públicas da sua comunidade.

### Representante

Enxerga demandas consolidadas da própria comunidade e pode confirmar, complementar ou contestar. O perfil é demonstrativo no protótipo e precisa de verificação real em produção.

### Instituição

Enxerga demandas compatíveis com suas áreas demonstrativas, rastreabilidade dos relatos, comunidades relacionadas, resumo semanal/mensal, relatórios e mensagens. Áudio original só pode ser consultado quando foi retido com consentimento e o perfil institucional tem acesso à demanda.

## Fonte de verdade

O relato original é usado pela triagem. A formalização profissional é uma segunda representação para leitura institucional e não substitui a fala original.

## Localidade

O Agente 1 tenta reconhecer uma comunidade já cadastrada pelo nome mencionado. Quando não encontra evidência suficiente, retorna referência de localidade ou pede confirmação. Relatos também podem ser enviados como `localidade_pendente`.

## Dados e migração

SQLite é usado no protótipo. `criar_banco()` aplica migrações leves por coluna/tabela para preservar bancos anteriores. PostgreSQL e Alembic fazem parte da evolução de produção.

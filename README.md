# Amazonas Comunidades

Protótipo web/PWA para receber relatos comunitários por voz ou texto, preservar a fala original, transformar relatos em demandas estruturadas e apoiar validação e roteamento institucional com IA.

## Fluxo principal

```text
RELATO -> TRIAGEM IA -> DEMANDA -> VALIDAÇÃO COMUNITÁRIA -> ROTEAMENTO IA -> ATENDIMENTO -> RETORNO
```

## Dois agentes implementados

### 1. Agente de triagem e diálogo

Trabalha a partir do relato original. Extrai categoria, prioridade, necessidades, informações faltantes, chave de agrupamento e possível situação crítica. Também ajuda a identificar a comunidade mencionada no relato sem inventar uma localidade quando não há evidência suficiente.

A versão formalizada é apenas auxiliar para leitura institucional; o original continua sendo a fonte de verdade.

### 2. Agente de roteamento

Recebe uma demanda estruturada e consulta uma ferramenta local que retorna instituições compatíveis. O agente só pode sugerir destinos presentes nessa consulta e registra quais ferramentas usou.

## Perfis do protótipo

- **Público:** conhece o serviço, consulta o mapa territorial seguro, envia relato e acompanha pelo protocolo.
- **Morador:** acessa os próprios relatos, avisos e mensagens.
- **Representante comunitário:** acompanha demandas consolidadas da própria comunidade e pode confirmar, complementar ou contestar.
- **Instituição:** analisa demandas compatíveis, comunidades no seu contexto, prioridades, rastreabilidade, relatórios e mensagens.

Os cadastros e logins comunitário/institucional são **demonstrativos**. Verificação de identidade e autenticação de produção permanecem como evolução.

## Voz e acessibilidade

O envio por voz permite:

1. gravar o relato;
2. transcrever;
3. ouvir em voz alta o texto entendido pelo sistema;
4. confirmar ou regravar;
5. identificar ou complementar a localidade;
6. enviar.

Se a comunidade não puder ser identificada, o relato pode ficar com **localidade pendente** para revisão. GPS é usado somente como sugestão de comunidade quando existem referências públicas adequadas; ele não determina automaticamente a comunidade do usuário.

O áudio original só é preservado quando a pessoa marca consentimento. Nesse caso, o acesso é restrito à área institucional compatível com a demanda.

## Comunidade pública de demonstração

O banco cria uma referência da **Comunidade do Tumbira, Iranduba - AM**, identificada como informação de **fonte pública**. O cadastro não afirma autorização da comunidade para este aplicativo, não inclui coordenada inventada e não cria uma demanda atual fictícia.

## Estrutura principal

```text
api.py                    rotas HTTP e controle das visões
banco.py                  SQLite, migrações e acesso aos dados
agente.py                 triagem, localização, consolidação e formalização
agente_roteamento.py      segundo agente e ferramenta institucional
provedor_ia.py            OpenAI e modo mock
transcricao_service.py    transcrição e retenção opcional de áudio
demanda_service.py        regras de demanda e orquestração
relatorio_service.py      relatório institucional
schemas.py                contratos Pydantic
frontend/                  interface web/PWA
tests/                     testes de fluxo e casos de IA
scripts/                   diagnóstico e avaliação
docs/                      documentação para estudo
```

## Atualizar sem perder seus dados

O pacote não inclui `akcit.db`.

Para manter seus dados atuais:

1. pare o servidor;
2. faça uma cópia de segurança do `akcit.db` atual;
3. mantenha esse arquivo na raiz de `Amazonas comunidade`;
4. substitua apenas os arquivos do patch final;
5. inicie o servidor.

As novas tabelas e colunas são criadas automaticamente. A migração foi testada sobre um banco criado pela versão anterior.

## Iniciar em modo de demonstração

Se sua `.venv` já existe, basta usar:

```powershell
.\iniciar-mock.bat
```

Ou manualmente:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
$env:AI_PROVIDER="mock"
$env:TRANSCRIPTION_PROVIDER="mock"
python -m uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Abra:

```text
http://127.0.0.1:8000/app/index.html
```

## IA real

Use `.env.example` como referência e nunca publique sua chave.

```powershell
$env:AI_PROVIDER="openai"
$env:TRANSCRIPTION_PROVIDER="openai"
$env:OPENAI_API_KEY="sua_chave"
python scripts\diagnosticar_ia.py
```

Para avaliar os 10 casos de triagem:

```powershell
python scripts\avaliar_ia.py
```

## O que continua demonstrativo

- login e verificação de identidade;
- instituições fictícias usadas para simular competência;
- encaminhamento interno, sem integração oficial com órgão/ONG;
- upload de modelo institucional guarda o arquivo como referência; preenchimento automático no modelo é evolução futura;
- modo `mock` é heurístico e não representa a qualidade de um LLM real; a transcrição de áudio nesse modo usa uma frase fixa e é marcada na interface como simulação;
- PostgreSQL, RAG, WhatsApp, rádio, APK e agentes adicionais ficam para ciclos posteriores.

## Antes da apresentação

```powershell
pytest -q
python scripts\avaliar_ia.py
```

Depois teste manualmente: relato por voz, confirmação falada, cadastro de morador, cadastro de representante, manifestação comunitária, acesso institucional e agente de roteamento.

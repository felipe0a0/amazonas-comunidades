# Testes antes da demonstração

## Testes automáticos

```powershell
$env:AI_PROVIDER="mock"
$env:TRANSCRIPTION_PROVIDER="mock"
pytest -q
```

A suíte final cobre:

- comunidade pública de demonstração e origem da visibilidade;
- identificação de Tumbira no modo mock;
- relato com localidade pendente;
- bloqueio da lista pública de demandas;
- privacidade do morador;
- escopo do representante;
- contestação;
- segundo agente e uso da ferramenta de roteamento;
- proteção do áudio original;
- cache PWA limitado ao frontend.

## Avaliação local da triagem

```powershell
python scripts\avaliar_ia.py
```

No modo mock da versão final, os 10 casos atuais passam nos critérios configurados de categoria, prioridade aceita e sinal de emergência. Isso valida a lógica de teste local; não deve ser apresentado como acurácia de um modelo real. A transcrição em mock também é simulada com uma frase fixa e aparece identificada como demonstração na interface.

## Checklist manual

1. abrir a home;
2. gravar um relato e transcrever;
3. usar “Ouvir o que entendemos”;
4. confirmar a transcrição;
5. testar identificação de “Comunidade do Tumbira”;
6. criar um perfil de morador e conferir apenas seus relatos;
7. criar um representante e registrar confirmar/complementar/contestar;
8. entrar na área institucional;
9. abrir uma demanda e usar o agente de roteamento;
10. conferir Comunidades, Mapa, Relatórios e Mensagens sem sair do painel.

## IA real

A validação real depende de chave e internet no notebook:

```powershell
$env:AI_PROVIDER="openai"
$env:TRANSCRIPTION_PROVIDER="openai"
$env:OPENAI_API_KEY="sua_chave"
python scripts\diagnosticar_ia.py
```

Transcrição real:

```powershell
python scripts\diagnosticar_ia.py --audio caminho\para\audio.m4a
```

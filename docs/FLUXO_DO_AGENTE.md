# Fluxo dos agentes

## Agente 1 — Triagem e diálogo

### Entrada

- relato original em linguagem livre;
- tipo/urgência informados apenas quando existirem;
- catálogo de comunidades quando a tarefa é identificar localidade.

### Ações

- identifica uma comunidade mencionada sem inventar nome;
- estrutura o relato;
- classifica categoria e prioridade;
- identifica necessidades, recursos mencionados e informações faltantes;
- sinaliza possível situação crítica para revisão;
- produz chave de agrupamento;
- consolida relatos vinculados à mesma demanda.

### Saída

JSON estruturado e validado pelo schema do sistema.

## Agente 2 — Roteamento

### Entrada

Demanda já estruturada, com categoria, prioridade, necessidades, estado e informações faltantes.

### Ferramenta

O agente usa uma ferramenta equivalente a:

```text
buscar_instituicoes_compativeis(categoria)
```

A ferramenta consulta o cadastro local. O agente não pode sugerir uma instituição que não tenha sido devolvida pela ferramenta.

### Saída

- se a demanda está pronta para encaminhamento;
- instituição sugerida, quando houver;
- justificativa;
- informações faltantes;
- necessidade de revisão humana;
- ferramentas usadas.

## Guardrails implementados

- relato original preservado;
- schemas estruturados;
- comunidade não inventada quando a identificação é incerta;
- contestação bloqueia encaminhamento;
- complemento devolve a demanda para revisão;
- prioridade crítica gera revisão prioritária;
- destino institucional precisa vir da ferramenta;
- morador não recebe demandas de outros perfis;
- representante só acessa a própria comunidade;
- área institucional verifica compatibilidade;
- áudio exige consentimento e autorização de acesso;
- logs registram operação, modelo, latência, tokens quando disponíveis e trace id.

## Por que dois agentes

A separação representa responsabilidades diferentes: o primeiro interpreta linguagem comunitária e organiza o problema; o segundo trabalha sobre uma demanda estruturada e usa ferramenta para decidir o próximo destino possível. Agentes adicionais só devem ser criados quando houver uma responsabilidade autônoma clara.

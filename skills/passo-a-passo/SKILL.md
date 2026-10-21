---
name: passo-a-passo
description: >-
  Estrutura as respostas do agente em formato passo a passo (resumo do feito, foco no passo atual, prévia do que pode vir). Use quando o usuário estiver no ask mode, pedir para ir compreendendo e executando sugestões manualmente, ou pedir explicitamente uma condução passo a passo.

metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Passo a passo

Em algumas situações vou preferir usar o ask mode pra ir compreendendo a situação e executando as sugestões manualmente. Nestes casos, pra maior clareza, a estrutura das suas mensagens deve ser:

## Status atual

### Hipóteses adotadas / confirmadas / refutadas / pendentes

### Passos realizados

### Conclusões obtidas até o momento

## Passo atual

Foco detalhado no passo atual, não só pra executar mas também pra compreender. O foco aqui precisa ser uma ação ÚNICA.

NÃO tem: "faça X depois faça Y, se acontecer B você faz A, se acontecer D você faz M..."

TEM: "faça X, dessa forma, por causa disso"

## Prognóstico

Aqui você pode abordar de forma bem sucinta o que está enxergando para os próximos passos:

- Se o resultado de X for Y, seguiremos pelo caminho A
- Se o resultado de X for Z, seguiremos pelo caminho B

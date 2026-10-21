---
description: Modo somente leitura — responde, explica e analisa sem alterar nada. Use quando o usuário quiser apenas perguntas, revisão ou explicação.
mode: primary
permission:
  edit: deny
  bash:
    "*": deny
    "ls*": allow
    "git status*": allow
    "git log*": allow
    "git diff*": allow
    "git show*": allow
  task: deny
  webfetch: allow
  websearch: allow
---
Você está no modo ask (somente leitura). Responda perguntas, explique código e analise o projeto, mas nunca crie, altere ou apague arquivos — nem rode comandos que modifiquem o sistema.

Se a tarefa exigir mudanças, descreva o que precisa ser feito e sugira que o usuário troque para o modo build (Tab).

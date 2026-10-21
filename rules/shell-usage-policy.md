# Uso de shell

O shell está restrito para impedir alterações fora do repositório de trabalho, não para impedir o trabalho dentro dele. Comandos de shell pedem aprovação do usuário, então use-os somente quando não houver outro caminho.

Para ler, buscar e editar arquivos, prefira as ferramentas read, glob, grep e edit: elas já estão liberadas e não geram aprovação. Na grande maioria das tarefas, elas bastam para concluir o trabalho dentro do repo.

Use shell apenas quando a tarefa exigir de fato um comando que as ferramentas não cobrem, como rodar testes ou executar um commit. Os comandos que já estão na allowlist (git status, diff, log, show, add, commit, checkout, switch, merge, pytest, unittest, npm test, jest, vitest) podem ser usados normalmente quando necessários; qualquer outro comando vai pedir aprovação.

Nunca use shell para escrever ou apagar arquivos fora do repositório de trabalho, nem para contornar essa restrição (por exemplo, redirecionando saída para outro caminho ou chamando um script que grave fora do repo).

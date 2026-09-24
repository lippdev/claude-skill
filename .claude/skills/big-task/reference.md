# Big Task: referência

## Como estimar o que cada parte exige

| Sinal na parte | Leitura | Raciocínio | Agente |
|---|---|---|---|
| "onde fica", "quem usa", "liste" | alta | baixo | `scout` |
| "como funciona", "qual o fluxo" | alta | médio | `researcher` |
| "o que fazer", "qual o melhor jeito", "ideias" | baixa | alto | `ideator` |
| "implemente", "corrija", "adicione" | média | médio | `implementer` |
| mesma parte falhou 2× | média | alto | `implementer-high` |
| falhou 2× no high | média | muito alto | `implementer-fable` |
| "rode os testes", "confira" | baixa | baixo | `verifier` |

Leitura alta vai para modelo barato. Raciocínio alto com entrada pequena pode ir para
modelo caro, porque o custo depende do tamanho da entrada.

## O que conta como falha

- `Status: FALHOU` na resposta do implementer;
- `verifier` reporta FALHOU no mesmo teste que a parte devia resolver;
- o implementer devolveu OK mas a verificação mostra o mesmo erro de antes.

Erro novo e diferente, mostrando progresso, não conta como segunda falha: registre e
tente de novo no mesmo nível.

## Memória externa

O brief em `.token-pilot/brief.md` é a memória padrão. Para usar um app de memória
global no lugar dele:

1. Exponha o app como servidor MCP (ou CLI) com duas operações: ler o contexto de uma
   tarefa e gravar o contexto de uma tarefa.
2. Defina `TOKEN_PILOT_MEMORY` com o nome do servidor MCP ou o comando da CLI.
3. A coordenadora grava ali o mesmo conteúdo do brief, com a chave
   `token-pilot/<nome-curto-da-tarefa>`, e passa essa chave aos subagentes.
4. Os subagentes leem pela mesma operação no lugar do arquivo.

Sem `TOKEN_PILOT_MEMORY`, use o arquivo.

---
name: token-pilot
description: Coordena o trabalho delegando cada parte ao subagente e modelo mais baratos que dão conta (Haiku 5.5, Sonnet 5.5, Opus 5.5). Use ao começar uma tarefa, quando algo travar, ao delegar busca, logs ou testes, em conversa longa, ou quando o usuário falar de tokens, custo, /usage, /compact ou /clear.
---

# Token Pilot

Você é a coordenadora da sessão. O usuário escolhe o modelo e o effort da sessão principal
(Fable, Opus ou outro); você não muda isso. Seu trabalho é dividir cada tarefa e mandar cada
parte ao subagente mais barato que resolve bem, recebendo só resumos.

A política completa (níveis, sinais e mensagens prontas) está em [policy.md](policy.md).
Leia-a quando precisar decidir algo que não está resumido abaixo.

## Regras

- **Não troque o modelo nem o effort da sessão principal**, e não peça ao usuário para trocar.
- **Não edite código na sessão principal.** Divida a tarefa por área (tela, API, banco,
  testes...) e delegue:
  - `implementer` (Opus 5.5, medium): implementar ou corrigir uma parte.
  - `quick-edit` (Haiku 5.5): mudança mecânica (renomear, trocar texto, ajustar imports).
  - `scout` (Haiku 5.5, low): localizar arquivos, símbolos, grep amplo.
  - `log-reader` (Haiku 5.5, low): ler e resumir logs, saídas de CI, stack traces.
  - `verifier` (Haiku 5.5, low): rodar testes, build ou lint e resumir. Teste de poucos
    segundos, rode você mesmo com a saída filtrada.
  - `researcher` (Sonnet 5.5, medium): entender um fluxo lendo vários arquivos.
  - `ideator` (Opus 5.5, high): comparar opções antes de implementar.
  - `implementer-high` (Opus 5.5, high): parte que falhou 2 vezes no `implementer`.
- **Partes que não tocam os mesmos arquivos vão em paralelo**, na mesma mensagem.
- **Passe a cada subagente só a parte dele** e o caminho do brief; traga só a conclusão.
- **Siga a disciplina de resposta** que o hook injeta: a menor mudança que resolve a tarefa
  inteira e respostas curtas.
- **Tarefa grande (analisar + decidir + implementar)?** Siga a skill `big-task` por conta
  própria, sem esperar o usuário digitar `/big-task`.

## Quando algo travar

Conte as tentativas no **mesmo** problema (mesmo erro, mesmo teste falhando, mesmo
comportamento errado):

1. Primeira falha no `implementer`: mande de novo, com o que falhou.
2. Segunda falha: mande ao `implementer-high`, com o que já foi tentado.
3. Duas falhas no `implementer-high`: pare, resuma o que falhou e peça ajuda ao usuário.
4. Resolvido: a próxima parte volta para o `implementer`.

O hook `token_pilot.py` conta esses sinais e injeta no contexto a ação a tomar. Execute-a
sem pedir confirmação ao usuário, depois de conferir pelo histórico real da conversa (o
hook usa heurística de palavras e pode errar).

## Durante a sessão

- Tarefa nova sem relação com a anterior → sugira `/clear`.
- Conversa longa, num intervalo natural → sugira `/compact` **com uma nota do que manter**,
  e escreva a nota para o usuário copiar, por exemplo:
  `/compact manter: objetivo X, arquivos A e B alterados, teste T ainda falhando por Y`.
- Quando o usuário quiser medir, sugira comparar o `/usage` da mesma tarefa com e sem o pacote.

## Estilo das recomendações

- Uma recomendação por vez, no fim da resposta, numa linha começando com `💡 Token Pilot:`.
- Só recomende quando algo mudar. Não repita a mesma sugestão se o usuário ignorou.

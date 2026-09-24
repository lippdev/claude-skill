---
name: token-pilot
description: Escolhe o modelo e o nível de esforço (effort) certos para cada momento da sessão para gastar menos tokens. Use no início de uma tarefa nova, quando o usuário travar no mesmo problema, quando for delegar busca ou leitura de logs, quando a conversa estiver longa, ou quando o usuário perguntar como economizar tokens, qual modelo ou effort usar, ou mencionar /model, /effort, /usage, /compact ou /clear.
---

# Token Pilot

Você é o "piloto" de custo da sessão. Seu trabalho é manter a sessão no modelo e no
effort mais baratos que ainda resolvem bem a tarefa, subir só quando houver sinal
de que é preciso, e descer de novo assim que o problema for resolvido.

A política completa (tabela de decisão, sinais e mensagens prontas) está em
[policy.md](policy.md). Leia-a quando precisar decidir algo que não está resumido abaixo.

## O que você consegue e o que não consegue mudar

- **Você não troca o modelo nem o effort da sessão principal sozinho.** Só o usuário faz isso
  com `/model <nome>` e `/effort <nível>`. Quando a troca for recomendada, diga o comando
  exato em uma linha, e explique o motivo em no máximo uma frase.
- **Você escolhe o modelo dos subagentes.** Use os agentes deste pacote, ou passe `model`
  na ferramenta Agent:
  - `scout` (Haiku, effort low): localizar arquivos, símbolos, grep amplo.
  - `log-reader` (Haiku, effort low): ler e resumir logs, saídas de CI, stack traces.
  - `researcher` (Sonnet, effort medium): pesquisa que exige ler e comparar vários arquivos.
  - Edição de código fica na sessão principal (Opus 5.5). Nunca delegue edições para Haiku.
- **As skills `/boost` e `/escalate` mudam o modelo/effort só enquanto estão ativas**
  (frontmatter `model`/`effort`). Isso é o jeito mais barato de "subir e voltar": a sessão
  volta sozinha ao padrão quando a skill termina.

## Fluxo

### 1. Antes de começar (tarefa nova)

Classifique a tarefa e recomende o ponto de partida:

| Tarefa | Modelo | Effort | Extra |
|---|---|---|---|
| Bem delimitada, 1–2 arquivos, rotina do dia a dia | Opus 5.5 | `medium` | — |
| Mexe em vários arquivos | Opus 5.5 | `medium` | sugerir `plan mode` (Shift+Tab) |
| Pergunta rápida, formatação, renomear | Opus 5.5 ou Sonnet | `low` | — |
| Só busca/leitura | subagente `scout` / `log-reader` | `low` | — |

Sempre garanta uma forma de verificar o trabalho (teste, build, lint, script de
reprodução). Se não existir, proponha uma antes de editar.

Se o effort atual (`${CLAUDE_EFFORT}`) já é o recomendado, não diga nada sobre isso.

### 2. Quando o usuário bater numa parede

Conte as tentativas no **mesmo** problema (mesmo erro, mesmo teste falhando, mesmo
comportamento errado):

1. Primeira falha no `medium`: tente de novo normalmente.
2. Segunda falha no `medium`: recomende subir para `high`, **num intervalo** (entre
   tarefas, não no meio de uma edição), porque mudar o effort gera uma nova escrita de
   cache. Ofereça `/boost` como alternativa que volta sozinha ao normal.
3. Duas falhas no `high`: recomende `/escalate` (Fable 5.1, só durante a skill) ou
   `/model fable`.
4. Problema resolvido depois de subir: recomende voltar (`/model opus`, `/effort medium`)
   na mesma mensagem que confirma a solução.

O hook `token_pilot.py`, se instalado, conta esses sinais e injeta um lembrete no
contexto. Siga o lembrete, mas confirme pelo histórico real da conversa: o hook
usa heurística de palavras e pode errar.

### 3. Durante a sessão

- Busca e leitura de logs → subagentes `scout`/`log-reader` (Haiku) ou `researcher`
  (Sonnet). Traga só a conclusão para a sessão principal.
- Tarefa nova sem relação com a anterior → sugira `/clear`.
- Conversa longa, num intervalo natural → sugira `/compact` **com uma nota do que manter**,
  e escreva a nota para o usuário copiar, por exemplo:
  `/compact manter: objetivo X, arquivos A e B alterados, teste T ainda falhando por Y`.

### 4. Medir

Quando o usuário quiser comparar, sugira rodar a mesma tarefa real em cada modelo e
comparar o que `/usage` mostra. Os números dele valem mais que qualquer regra geral.

## Estilo das recomendações

- Uma recomendação por vez, no fim da resposta, numa linha começando com `💡 Token Pilot:`.
- Só recomende quando algo mudar. Não repita a mesma sugestão se o usuário ignorou.
- Nunca interrompa um trabalho em andamento só para recomendar troca de effort.

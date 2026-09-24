# Token Pilot

Pacote para Claude Code que escolhe o modelo e o effort certos para cada momento da
sessão, para gastar menos tokens. Segue o guia "Making Opus 5.5 your daily driver":

1. **Antes de começar:** Opus 5.5 com effort `medium`. Plan mode para mudanças em vários arquivos.
2. **Quando travar:** `medium` → `high` (num intervalo, porque a troca gera escrita de cache).
   Se o `high` travar duas vezes → Fable 5.1. Volte ao padrão quando resolver.
3. **Durante a sessão:** busca e logs em subagentes Sonnet/Haiku, edição no Opus 5.5.
   `/clear` entre tarefas sem relação, `/compact` com nota nos intervalos.
4. **Meça:** compare o `/usage` de cada modelo numa tarefa real.

## O que vem no pacote

| Arquivo | O que faz |
|---|---|
| `.claude/skills/token-pilot/` | Skill principal. O Claude a usa sozinho para recomendar modelo, effort, `/clear`, `/compact` e delegação. |
| `.claude/skills/boost/` | `/boost <problema>`: roda a tarefa com effort `high` e volta ao normal ao terminar. |
| `.claude/skills/escalate/` | `/escalate <problema>`: roda a tarefa no Fable 5.1 e volta ao modelo da sessão ao terminar. |
| `.claude/agents/scout.md` | Subagente Haiku (effort low) para localizar código. |
| `.claude/agents/log-reader.md` | Subagente Haiku (effort low) para resumir logs e saídas de CI. |
| `.claude/agents/researcher.md` | Subagente Sonnet (effort medium) para pesquisa em vários arquivos. |
| `.claude/hooks/token_pilot.py` | Hook que mede o uso da sessão e avisa quando vale trocar. |
| `.claude/settings.json` | Padrão Opus 5.5 + `medium` e registro do hook. |

## Como a troca funciona

O Claude não consegue trocar o modelo ou o effort da sessão principal sozinho. O pacote
usa três caminhos:

- **Automático e temporário:** `/boost` e `/escalate` definem `effort`/`model` no
  frontmatter da skill, então a troca vale só enquanto a skill roda e depois volta.
- **Automático para subagentes:** busca e leitura de logs vão para Haiku/Sonnet pelo
  frontmatter dos agentes.
- **Recomendado:** para a sessão principal, o Claude (e o hook) dizem o comando exato:
  `/effort high`, `/model fable`, `/model opus`, `/effort medium`, `/clear`, `/compact ...`.

## Como o hook mede o uso

A cada prompt, `token_pilot.py` atualiza um estado por sessão em `~/.claude/token-pilot/`:

| Sinal no prompt | Efeito |
|---|---|
| "ainda não funciona", "mesmo erro", "de novo", "still failing"… | conta uma falha no mesmo problema |
| 2 falhas seguidas | sugere `/effort high` ou `/boost` |
| 4 falhas seguidas | sugere `/escalate` ou `/model fable` |
| "funcionou", "resolvido", "works", "fixed"… depois de subir | sugere voltar para `/model opus` + `/effort medium` |
| "nova tarefa", "agora…", "next task"… | sugere `/clear` |
| primeiro prompt com "refatorar", "vários arquivos", "migrar"… | sugere plan mode |
| 30 prompts desde o último `/compact`, ou transcript acima de 2 MB | sugere `/compact` com nota |

A mesma dica não é repetida em seguida. A detecção é por palavras-chave, então o hook
pede ao Claude para confirmar pelo histórico real antes de repetir a recomendação.

Ajuste os limiares por variável de ambiente:

| Variável | Padrão |
|---|---|
| `TOKEN_PILOT_STALLS_TO_BOOST` | `2` |
| `TOKEN_PILOT_STALLS_TO_ESCALATE` | `4` |
| `TOKEN_PILOT_PROMPTS_TO_COMPACT` | `30` |
| `TOKEN_PILOT_TRANSCRIPT_MB` | `2` |
| `TOKEN_PILOT_STATE_DIR` | `~/.claude/token-pilot` |

## Instalação

**Num projeto:** copie a pasta `.claude/` para a raiz do projeto. Se o projeto já tiver
`.claude/settings.json`, junte a seção `hooks` em vez de sobrescrever.

**Em todos os projetos:** copie `skills/` e `agents/` para `~/.claude/`, copie o hook para
`~/.claude/hooks/token_pilot.py` e registre em `~/.claude/settings.json` com
`"command": "python3 ~/.claude/hooks/token_pilot.py"`.

Requer Python 3.

## Testar o hook

```bash
echo '{"session_id":"teste","prompt":"continua dando o mesmo erro"}' | python3 .claude/hooks/token_pilot.py
echo '{"session_id":"teste","prompt":"ainda não funcionou"}' | python3 .claude/hooks/token_pilot.py
```

A segunda chamada deve sugerir `/effort high` ou `/boost`.

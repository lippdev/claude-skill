# Token Pilot

Pacote para Claude Code que manda cada parte do trabalho para o modelo e o effort mais
baratos que dão conta dela, para gastar menos tokens. Segue o guia "Making Opus 5.5 your
daily driver":

1. **Antes de começar:** Opus 5.5 com effort `medium`. Plan mode para mudanças em vários arquivos.
2. **Quando travar:** `medium` → `high`; se o `high` travar duas vezes → Fable 5.1. Volta ao padrão quando resolver.
3. **Durante a sessão:** busca e logs no Sonnet/Haiku, edição no Opus 5.5. `/clear` entre tarefas, `/compact` com nota.
4. **Meça:** compare o `/usage` de cada modelo numa tarefa real.

## Como funciona

O Claude não consegue trocar o modelo da sessão principal sozinho, mas consegue escolher
o modelo de cada **subagente**. Então a sessão principal vira uma coordenadora que nunca
troca de modelo (o cache dela não é refeito) e manda cada parte para o agente certo:

```
/big-task <tarefa>          (sessão principal: Opus 5.5, medium, contexto pequeno)
│
├─ Análise     scout ×N (Haiku, low) em paralelo + researcher (Sonnet, medium)
├─ Brainstorm  ideator (Opus 5.5, high), recebe só o resumo      ⏸ você escolhe
├─ Execução    implementer (Opus 5.5, medium) por parte
│              ├─ 2 falhas → implementer-high (Opus 5.5, high)
│              └─ 2 falhas → implementer-fable (Fable 5.1, high)
└─ Conferência verifier (Haiku, low)
```

Os subagentes não veem a conversa. A memória compartilhada deles é o brief em
`.token-pilot/brief.md`, que só a coordenadora escreve (objetivo, mapa do código,
decisão, plano, falhas, comando de verificação).

## O que vem no pacote

| Arquivo | O que faz |
|---|---|
| `.claude/skills/big-task/` | `/big-task <tarefa> [--auto]`: a coordenadora. `--auto` pula as pausas. |
| `.claude/skills/token-pilot/` | Regras gerais. O Claude a usa sozinho para delegar, escalar e sugerir `/clear`/`/compact`. |
| `.claude/skills/boost/` | `/boost <problema>`: effort `high` na sessão principal só durante a tarefa (manual). |
| `.claude/skills/escalate/` | `/escalate <problema>`: Fable 5.1 na sessão principal só durante a tarefa (manual). |
| `.claude/agents/` | 8 agentes, cada um com modelo e effort fixos (tabela abaixo). |
| `.claude/hooks/token_pilot.py` | Hook que detecta travas e conversa longa e avisa. |
| `.claude/settings.json` | Padrão Opus 5.5 + `medium` e registro do hook. |
| `tests/` | Validação do pacote e testes do hook, sem chamar modelo. |
| `examples/demo-loja/` | Projeto de demonstração com bug proposital e roteiro de teste. |

| Agente | Modelo | Effort | Edita? | Para |
|---|---|---|---|---|
| `scout` | Haiku | low | não | localizar código |
| `log-reader` | Haiku | low | não | resumir logs e CI |
| `verifier` | Haiku | low | não | rodar testes e resumir |
| `researcher` | Sonnet | medium | não | entender fluxos |
| `ideator` | Opus 5.5 | high | não | brainstorm |
| `implementer` | Opus 5.5 | medium | sim | editar (padrão) |
| `implementer-high` | Opus 5.5 | high | sim | 2 falhas no implementer |
| `implementer-fable` | Fable 5.1 | high | sim | 2 falhas no implementer-high |

O effort de um subagente só pode ser definido no arquivo dele, por isso há um agente por
nível de execução.

## O hook

A cada prompt, `token_pilot.py` atualiza um estado por sessão em `~/.claude/token-pilot/`:

| Sinal no prompt | Efeito |
|---|---|
| 2 mensagens seguidas tipo "ainda não funciona", "mesmo erro", "de novo" | a próxima tentativa vai para `implementer-high` |
| 4 mensagens seguidas | a próxima tentativa vai para `implementer-fable` |
| "funcionou", "resolvido", "works" depois de subir | aviso de volta ao nível padrão |
| "nova tarefa", "agora…", "next task" | sugere `/clear` |
| primeiro prompt com "refatorar", "vários arquivos", "migrar" | sugere plan mode |
| 30 prompts sem `/compact`, ou transcript acima de 2 MB | sugere `/compact` com nota |

A detecção é por palavras-chave, então o Claude confere o histórico real antes de agir.
Limiares ajustáveis: `TOKEN_PILOT_STALLS_TO_BOOST` (2), `TOKEN_PILOT_STALLS_TO_ESCALATE` (4),
`TOKEN_PILOT_PROMPTS_TO_COMPACT` (30), `TOKEN_PILOT_TRANSCRIPT_MB` (2),
`TOKEN_PILOT_STATE_DIR` (`~/.claude/token-pilot`).

## Integração com um app de memória

O brief em arquivo é a memória padrão. Para trocar por um app de memória global, exponha
o app como servidor MCP (ou CLI) com "ler contexto" e "gravar contexto" e defina
`TOKEN_PILOT_MEMORY`. O contrato está em
[`.claude/skills/big-task/reference.md`](.claude/skills/big-task/reference.md#memória-externa).

## Instalação

**Num projeto:** copie a pasta `.claude/` para a raiz do projeto e adicione `.token-pilot/`
ao `.gitignore`. Se o projeto já tiver `.claude/settings.json`, junte a seção `hooks` em
vez de sobrescrever. Abra uma sessão nova: agentes e skills são carregados no início.

**Em todos os projetos:** copie `skills/` e `agents/` para `~/.claude/`, o hook para
`~/.claude/hooks/token_pilot.py`, e registre-o em `~/.claude/settings.json` com
`"command": "python3 ~/.claude/hooks/token_pilot.py"`.

Requer Python 3.

## Testar

Sem gastar tokens:

```bash
python3 tests/validate_package.py   # modelos/efforts dos agentes, skills, links, hook registrado
python3 tests/test_hook.py          # simula uma sessão contra o hook
```

Com o Claude, no projeto de demonstração: siga
[`examples/demo-loja/CENARIO.md`](examples/demo-loja/CENARIO.md).

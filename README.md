# Token Pilot

Pacote para Claude Code que transforma a sessão principal numa **coordenadora**: ela divide
cada tarefa por área (tela, API, banco, testes...) e manda cada parte ao subagente e ao
modelo mais baratos que dão conta dela, recebendo só resumos.

- **A sessão principal fica no modelo que você escolher** (Fable, Opus ou outro). O pacote
  nunca troca nem pede para trocar `/model` ou `/effort`.
- **Os subagentes usam só Haiku 5.5, Sonnet 5.5 e Opus 5.5**, que estão em todos os planos,
  desde o Pro.
- **Quanto mais cara a sessão principal, maior a economia**, porque a leitura e a edição
  acontecem fora dela.

## Como funciona

Tudo roda sozinho, sem comandos:

- **Ao abrir a sessão**, o hook injeta as regras de delegação no contexto do Claude.
- **A cada mensagem**, o hook classifica o pedido e detecta tarefa grande ou trava, e diz ao
  Claude o que fazer. Você só vê um aviso curto `💡 Token Pilot` quando algo muda.
- **Os agentes** têm descrições "use proativamente", então o Claude delega por conta própria.

O comando `/big-task` continua existindo para forçar o fluxo completo.

```
sessão principal (modelo à sua escolha): divide, despacha, junta, responde
│
├─ Análise     scout ×N (Haiku 5.5, low) em paralelo + researcher (Sonnet 5.5, medium)
├─ Decisão     ideator (Opus 5.5, high), recebe só o resumo        ⏸ você escolhe
├─ Execução    um implementer (Opus 5.5, medium) por área, em paralelo quando não
│              tocam os mesmos arquivos; mudança mecânica no quick-edit (Haiku 5.5)
│              └─ 2 falhas → implementer-high (Opus 5.5, high)
│                 └─ 2 falhas → a coordenadora para e pede sua ajuda
└─ Conferência verifier (Haiku 5.5, low)
```

Os subagentes não veem a conversa. A memória compartilhada deles é o brief em
`.token-pilot/brief.md`, que só a coordenadora escreve (objetivo, mapa do código,
decisão, plano, falhas, comando de verificação).

### Por tipo de pedido

A cada mensagem, o hook classifica o pedido e passa ao Claude uma instrução silenciosa:

| Pedido | Exemplo | O que acontece |
|---|---|---|
| Mecânico | "renomeia X para Y", "corrige o typo", "troca A por B", "remove os prints" | O `quick-edit` (Haiku 5.5) edita e confere; a coordenadora só despacha e responde em uma linha. |
| Curto | "por que o teste de frete falha?" | Pergunta: resposta direta, curta. Mudança de código: vai para o `implementer`. |
| Médio ou grande | pedidos longos, com várias etapas | A disciplina da coordenadora e o mapa do código entram uma vez na sessão; tarefa grande segue o `big-task`. |

A abertura de toda sessão leva só um núcleo curto de regras (~900 caracteres). Ajuste o
limite de pedido curto com `TOKEN_PILOT_SHORT_PROMPT_CHARS` (padrão 160).

### Disciplina de resposta e mapa do código

- **Disciplina de resposta** (`.claude/hooks/disciplina.md`): a menor mudança que resolve a
  tarefa inteira, sem código "para depois", e uma resposta curta que diz o que ficou de fora.
  Nunca corta validação, tratamento de erro, segurança, acessibilidade nem o que foi pedido.
  Tem três versões: a da coordenadora (sessão principal), a de edição (`implementer`,
  `implementer-high`) e uma mais curta para os agentes de leitura, entregue pelo hook
  `SubagentStart`.
- **Mapa do código:** até 2 mil caracteres com as funções, classes e exports de cada pasta,
  gerado sem modelo em até 2 s. Ajuda a dividir a tarefa e a reutilizar o que existe.
  Desligue com `TOKEN_PILOT_MAP=0` ou ajuste o teto com `TOKEN_PILOT_MAP_CHARS`.
- Ambas foram inspiradas no [ponytail](https://github.com/dietrichgebert/ponytail) (MIT),
  com texto e código próprios.

## O que vem no pacote

| Arquivo | O que faz |
|---|---|
| `.claude/skills/big-task/` | `/big-task <tarefa> [--auto]`: a coordenadora. `--auto` pula as pausas. |
| `.claude/skills/token-pilot/` | Regras gerais. O Claude a usa sozinho para delegar, escalar e sugerir `/clear`/`/compact`. |
| `.claude/agents/` | 8 agentes, cada um com modelo e effort fixos (tabela abaixo). |
| `.claude/hooks/token_pilot.py` | Hook que injeta as regras, classifica pedidos e detecta travas e conversa longa. |
| `.claude/settings.json` | Registro do hook. Não define modelo nem effort. |
| `tests/` | Validação do pacote e testes do hook, sem chamar modelo. |
| `examples/` | Projetos de demonstração e de benchmark. |

| Agente | Modelo | Effort | Edita? | Para |
|---|---|---|---|---|
| `scout` | Haiku 5.5 | low | não | localizar código |
| `log-reader` | Haiku 5.5 | low | não | resumir logs e CI |
| `verifier` | Haiku 5.5 | low | não | rodar testes e resumir |
| `researcher` | Sonnet 5.5 | medium | não | entender fluxos |
| `ideator` | Opus 5.5 | high | não | comparar opções |
| `quick-edit` | Haiku 5.5 | medium | sim | mudança mecânica: renomear, trocar texto, typo, import |
| `implementer` | Opus 5.5 | medium | sim | implementar ou corrigir uma parte |
| `implementer-high` | Opus 5.5 | high | sim | parte que falhou 2 vezes no implementer |

O effort de um subagente só pode ser definido no arquivo dele, por isso há um agente por
nível de execução.

Os agentes usam os apelidos `haiku`, `sonnet` e `opus`, que o Claude Code liga ao modelo
mais novo de cada família. O `tests/session_report.py` mostra a versão que rodou de fato.

O Haiku 5.5 custa 5 vezes mais quando o pedido passa de 100 mil tokens, então `scout`,
`log-reader` e `verifier` filtram arquivos e saídas grandes com `grep`, `head` e `tail`.
Ele também não tem fallback automático para recusas: se um agente no Haiku 5.5 recusar ou
voltar vazio, o Claude refaz a parte no Sonnet 5.5.

## O hook

No início da sessão, `token_pilot.py` injeta as regras de delegação. A cada prompt, atualiza um estado por sessão em `~/.claude/token-pilot/`:

| Sinal no prompt | Efeito |
|---|---|
| 2 mensagens seguidas tipo "ainda não funciona", "mesmo erro", "de novo" | a próxima tentativa vai para `implementer-high` |
| 4 mensagens seguidas | o Claude para, resume o que falhou e pede sua ajuda |
| "funcionou", "resolvido", "works" depois de subir | as próximas partes voltam para o `implementer` |
| "nova tarefa", "agora…", "next task" | sugere `/clear` |
| tarefa grande: 2 etapas no mesmo pedido ("analisa… e implementa", "ideias… e cria"), "refatorar", "vários arquivos", ou pedido longo | o Claude segue o `big-task` sozinho |
| 30 prompts sem `/compact`, ou transcript acima de 2 MB | sugere `/compact` com nota |

A detecção é por palavras-chave, então o Claude confere o histórico real antes de agir.
Limiares ajustáveis: `TOKEN_PILOT_STALLS_TO_BOOST` (2), `TOKEN_PILOT_STALLS_TO_STOP` (4),
`TOKEN_PILOT_PROMPTS_TO_COMPACT` (30), `TOKEN_PILOT_TRANSCRIPT_MB` (2),
`TOKEN_PILOT_BIG_PROMPT_CHARS` (600), `TOKEN_PILOT_STATE_DIR` (`~/.claude/token-pilot`).

## Integração com um app de memória

O brief em arquivo é a memória padrão. Para trocar por um app de memória global, exponha
o app como servidor MCP (ou CLI) com "ler contexto" e "gravar contexto" e defina
`TOKEN_PILOT_MEMORY`. O contrato está em
[`.claude/skills/big-task/reference.md`](.claude/skills/big-task/reference.md#memória-externa).

## Instalação

**Como plugin (recomendado):** dentro do Claude Code,

```
/plugin marketplace add lippdev/claude-skill
/plugin install token-pilot@token-pilot
```

ou, no Claude Code 2.1.275 ou mais novo, numa linha só:

```
/plugin install token-pilot --marketplace lippdev/claude-skill
```

Como plugin, os agentes aparecem com o prefixo `token-pilot:` (por exemplo,
`token-pilot:scout`). O plugin não muda o modelo nem o effort da sessão principal: use o que
você preferir.

**Copiando a pasta, num projeto:** copie `.claude/` para a raiz do projeto e adicione
`.token-pilot/` ao `.gitignore`. Se o projeto já tiver `.claude/settings.json`, junte a seção
`hooks` em vez de sobrescrever. Abra uma sessão nova: agentes e skills são carregados no início.

**Testar sem instalar:** `claude --plugin-dir <pasta deste repositório>`.

Requer Python 3.

## Testar

Sem gastar tokens:

```bash
python3 tests/validate_package.py   # modelos/efforts dos agentes, skills, links, hook registrado
python3 tests/test_hook.py          # simula uma sessão contra o hook
```

Com o Claude, no projeto de demonstração: siga
[`examples/demo-loja/CENARIO.md`](examples/demo-loja/CENARIO.md).

Teste completo, com os agentes rodando de verdade num projeto fictício de estoque, e um
relatório de quais agentes rodaram, em qual modelo e com quantos tokens: siga
[`examples/estoque/PLANO-DE-TESTE.md`](examples/estoque/PLANO-DE-TESTE.md). O relatório vem de

```bash
python3 tests/session_report.py --dir <pasta do projeto> --last 3
```

que lê os registros locais do Claude Code sem mostrar o conteúdo das respostas.

Estimativa de custo, tempo e diferenças funcionais entre usar o pacote e não usar nada:
[`docs/BENCHMARK.md`](docs/BENCHMARK.md), gerada por `python3 tests/benchmark_estimate.py`.

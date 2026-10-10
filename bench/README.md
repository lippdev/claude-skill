# Benchmark real: Opus 5.5 medium x Token Pilot

O objetivo, as hipóteses e os critérios de sucesso estão em [`OBJETIVO.md`](OBJETIVO.md).

Roda as mesmas tarefas no Claude Code sem interface (`claude -p`), cada uma numa cópia limpa
de `examples/estoque`, e compara custo, tempo, turnos e se a verificação da tarefa passa.

| Braço | O que roda |
|---|---|
| `opus-medium` | Sessão única no Opus 5.5 com effort `medium`, sem o pacote |
| `token-pilot` | Opus 5.5 com effort `low` na sessão principal, que só coordena, com a pasta `.claude/` do pacote: o trabalho vai para os subagentes (Haiku 5.5, Sonnet 5.5 e Opus 5.5). Mude o effort com `--pilot-effort`. |
| `ponytail` (opcional) | Sem o pacote, com o plugin do ponytail (`--ponytail <pasta>`) |

As tarefas estão em `bench/tasks.json`, em três tamanhos. Cada uma tem um pedido, uma
verificação que só passa se o trabalho foi feito e conferências de qualidade.

| Tamanho | Tarefa | Projeto | Verificação |
|---|---|---|---|
| pequena | `renomear` | estoque | a função nova existe e o nome antigo sumiu |
| pequena | `pequena-renomear-loja` | loja-grande | idem, em `loja/utils/dinheiro.py` |
| pequena | `pequena-milhar` | loja-grande | testes ocultos do separador de milhar |
| media | `corrigir-testes` | estoque | `python3 -m unittest` passa |
| media | `simulador` | estoque | `python3 simular.py` roda até o fim |
| media | `grande-bug` | loja-grande | `python3 -m unittest` passa |
| media | `grande-sincronizar` | loja-grande | os 300 produtos do export sincronizam |
| pesada | `reposicao` | estoque | testes passam e o comando `reposicao` lista o CAF-001 |
| pesada | `grande-reembolso` | loja-grande | testes ocultos do reembolso parcial |
| pesada | `pesada-limite-cupom` | loja-grande | testes ocultos do limite de uso de cupom |

**Qualidade.** Além da verificação, cada rodada confere:

- **Sem regressão:** a suíte visível não tem mais falhas do que antes da tarefa.
- **Regras do pedido:** testes intactos quando o pedido proíbe mudá-los, dados intactos,
  testes novos quando o pedido pede.
- **Testes ocultos:** nas tarefas com `hidden`, entram só depois do trabalho.

A nota de qualidade é a fração dessas conferências que passou. Cada rodada também registra
os tokens por modelo (entrada, cache lido, cache escrito e saída).

## Rodar

```bash
python3 bench/run.py run --dry-run                 # mostra os comandos, sem gastar nada
python3 bench/run.py run --fake --runs 2           # testa o pipeline com respostas simuladas
python3 bench/run.py run --runs 3                 # benchmark de verdade
python3 bench/run.py run --runs 3 --ponytail ~/ponytail   # com o terceiro braço
python3 bench/run.py run --runs 3 --tiers pesada --jobs 4 # só um tamanho, 4 sessões em paralelo
python3 bench/run.py compare bench/results/<arquivo>.jsonl
```

**Custo:** a rodada completa (10 tarefas × 2 braços × 3 rodadas = 60 sessões) deve ficar
entre US$ 15 e US$ 35 em preço de API, ou o equivalente no limite de uso do plano. Cada sessão
tem teto de US$ 3 (`--max-budget`). Para começar barato, use `--tasks corrigir-testes --runs 1`.

## Como funciona

- **Isolamento:** cada rodada é uma pasta temporária nova com `git init`, e as configurações do
  usuário não são carregadas (`--setting-sources project,local`).
- **Permissões:** só a edição de arquivos e alguns comandos de leitura e teste (`python3`,
  `git`, `grep`...) são liberados.
- **Ordem:** os braços são intercalados, para que mudanças de carga no servidor afetem os
  dois por igual.
- **Resultado:** cada sessão vira uma linha em `bench/results/<data>.jsonl`, com o custo por
  modelo.
- **Comparação:** para cada tarefa, usa a mediana das rodadas; entre tarefas, a média
  geométrica das razões contra o `opus-medium`. É o mesmo método do benchmark do ponytail.

## Limites

- **Custo informado:** `total_cost_usd` é a estimativa do próprio Claude Code, não a cobrança.
- **Pausa do brainstorm:** no modo sem interface ninguém responde, então os pedidos das tarefas
  grandes dizem para o Claude decidir sozinho.
- **O que não é isolado:** um `CLAUDE.md` ou agentes em `~/.claude/` ainda podem ser
  carregados. Rode numa máquina sem eles, ou confira com `tests/session_report.py`.
- **Poucas tarefas:** 4 tarefas num projeto pequeno dão uma direção, não um número definitivo.

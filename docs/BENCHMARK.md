# Benchmark estimado: Opus 5.5 medium (uso normal) x Token Pilot

> **Estimativa, não medição.** Os números vêm de `tests/benchmark_estimate.py`, um modelo
> turno a turno com premissas explícitas no código. A medição real vem de `bench/run.py`
> (seção "Medir de verdade" abaixo).

**O que está sendo comparado:**

- **Opus 5.5 medium (uso normal):** uma sessão só, no Opus 5.5 com effort `medium`, que lê,
  pensa, edita e testa tudo sozinha. Ninguém troca `/model` nem `/effort`.
- **Token Pilot:** a mesma sessão principal (Opus 5.5 `medium`) delega o que é barato de
  delegar e edita ela mesma:

| Função | Quem faz no Token Pilot |
|---|---|
| Análise | `scout` e `log-reader` (Haiku 5.5, `low`) e `researcher` (Sonnet 5.5, `medium`) |
| Brainstorm | `ideator` (Opus 5.5, `high`) |
| Execução | a própria sessão principal, que fica com contexto pequeno porque só recebe resumos; mudança mecânica vai para o `quick-edit` (Haiku 5.5) |
| Verificação | `verifier` (Haiku 5.5, `low`) |
| Escalada, se travar | `implementer-high` (Opus 5.5, `high`) e depois `implementer-fable` |

Todos seguem a disciplina de resposta, que pede a menor mudança que resolve a tarefa
inteira, e recebem um mapa do código.

Recalcule com:

```bash
python3 tests/benchmark_estimate.py          # tabelas
python3 tests/benchmark_estimate.py --json   # dados
```

Custo em dólares equivalentes à API (em planos Pro/Max, o mesmo consumo pesa no limite de uso). Tempo é o de espera do usuário, sem contar quanto ele demora para responder.

## Cenário esperado

| Situação | Opus 5.5 medium | Token Pilot | Custo | Tempo |
|---|---|---|---|---|
| Pedido mecânico (renomear uma função) | $0.204 · 0.8 min | $0.133 · 0.9 min | -35% | +11% |
| Pedido curto que exige investigar | $0.244 · 1.2 min | $0.252 · 1.2 min | +3% | +0% |
| Tarefa grande (analisar, corrigir, propor e implementar) | $1.369 · 6.8 min | $0.889 · 5.6 min | -35% | -17% |
| Log de CI longo + 10 turnos de trabalho seguinte | $0.695 · 2.4 min | $0.348 · 1.9 min | -50% | -20% |
| Bug difícil que o medium demora a resolver | $1.287 · 6.1 min | $0.950 · 3.9 min | -26% | -35% |
| **Dia típico** (4x simples, 4x curta, 2x grande, 2x log, 1x trava) | $7.20 · 32 min | $4.96 · 27 min | -31% | -16% |

## Tarefa grande: custo por função (cenário esperado)

| Função | Opus 5.5 medium | Token Pilot | Quem faz no Token Pilot |
|---|---|---|---|
| Análise | $0.578 | $0.305 | 3 scouts (Haiku 5.5) + researcher (Sonnet 5.5) |
| Brainstorm | $0.084 | $0.191 | ideator (Opus 5.5, high) |
| Execução | $0.572 | $0.328 | sessão principal, com a disciplina de resposta |
| Verificação | $0.082 | $0.043 | 2 verifiers (Haiku 5.5) |
| Coordenação | $0.052 | $0.021 | sessão principal (resumo final) |

## Faixa (pessimista · esperado · otimista para o Token Pilot)

| Situação | Variação de custo | Variação de tempo |
|---|---|---|
| Pedido mecânico (renomear uma função) | -36% · -35% · -34% | +11% · +11% · +11% |
| Pedido curto que exige investigar | +4% · +3% · +3% | +0% · +0% · +0% |
| Tarefa grande (analisar, corrigir, propor e implementar) | -19% · -35% · -46% | -9% · -17% · -24% |
| Log de CI longo + 10 turnos de trabalho seguinte | -38% · -50% · -58% | -13% · -20% · -25% |
| Bug difícil que o medium demora a resolver | +2% · -26% · -44% | -2% · -35% · -55% |
| Dia típico | -18% · -31% · -40% | -5% · -16% · -25% |

## De onde vem cada parte do ganho

| Tarefa grande (esperado) | Custo | Tempo |
|---|---|---|
| Só a estrutura (delegar leitura, editar na sessão principal) | −16% | +18% |
| Estrutura + disciplina de resposta | −35% | −17% |

| Dia típico (esperado) | Custo | Tempo |
|---|---|---|
| Só a estrutura | −13% | +10% |
| Estrutura + disciplina de resposta | −31% | −16% |

- **A estrutura economiza na leitura e na verificação.** O Haiku 5.5 lê no lugar do Opus,
  e a sessão principal recebe só resumos. Sozinha, porém, ela deixa o trabalho mais lento:
  cada subagente tem a própria espera até o primeiro token.
- **A disciplina de resposta corta o que o Opus escreve.** No Opus 5.5, as respostas e o
  raciocínio são o custo principal e o que mais demora. É ela que transforma o tempo extra
  em ganho.
- **A redução de saída da disciplina não foi medida por nós.** O fator usado (−35% a −54%
  de tokens de saída) vem do benchmark do ponytail no Opus 5.5 (39 tarefas, 5 rodadas;
  `benchmarks/results/2026-10-07-agentic.md` naquele repositório). A nossa disciplina é um
  texto próprio, mais curto, e pode render menos.

## Parte funcional

| Aspecto | Opus 5.5 medium (uso normal) | Token Pilot |
|---|---|---|
| Pedido mecânico | O Opus lê, edita e confere | O `quick-edit` (Haiku 5.5) edita e confere; o Opus só despacha e responde |
| Pedido curto que exige investigar | Resolve direto | Igual, com a instrução de resolver direto; ~3% mais caro pelo contexto fixo |
| Análise de código | O Opus lê tudo e tem os detalhes à mão | O Haiku 5.5 resume e há um mapa do código; risco de um resumo deixar passar um detalhe |
| Brainstorm | No meio da conversa, em `medium`, sem pausa | O `ideator` compara opções em `high` e você escolhe antes da edição |
| Edição | Opus com todo o contexto, que cresce | Opus com contexto pequeno; segue a menor mudança completa |
| Verificação | Quando o Claude lembra | O `verifier` roda depois de cada parte |
| Bug difícil | Continua no `medium`; pode não resolver | Sobe para `high` e depois Fable, se o plano tiver |
| Tamanho da mudança | O que o modelo achar melhor | Menor diff completo; nunca corta validação, segurança ou o que foi pedido |

**Riscos funcionais:**
- **Resumos do Haiku 5.5:** podem perder detalhes.
- **Disciplina de resposta:** pode deixar de fora algo útil que ninguém pediu. Ela lista no
  fim o que ficou de fora.
- **Pausa do brainstorm:** exige uma resposta sua.

## Medir de verdade

`bench/run.py` roda as mesmas tarefas no Claude Code sem interface (`claude -p`), em pastas
limpas, com e sem o pacote, e compara custo, tempo, turnos e se os testes passam. Veja
`bench/README.md`.

**Rodadas reais até agora** (09/10/2026, Claude Code 2.1.295; ainda é pouco para tirar
números firmes, mas já mostra a direção):

| Tarefa | Opus 5.5 medium | Token Pilot | Custo | Tempo | Acertou? |
|---|---|---|---|---|---|
| `renomear`, primeira versão (2 rodadas) | $0.168 e $0.139 · 26 e 22 s | $0.178 e $0.177 | +6% e +27% | −9% e +11% | sim |
| `renomear`, versão final com `quick-edit` (2 rodadas) | mesma base | $0.093 e $0.085 · 26 e 18 s | **cerca de −40%** | igual ou menor | sim |
| `corrigir-testes` (pedido curto, 2 rodadas) | $0.188 · 25 s | $0.202 e $0.215 | +7% e +14% | +60% e +8% | sim |

O que isso mostra:

- **Pedido mecânico agora economiza.** O hook reconhece "renomear", "trocar texto",
  "corrigir typo", "ajustar import", e a mudança vai para o `quick-edit` (Haiku 5.5). O Opus
  só despacha e responde em uma linha: foram 2 turnos do Opus contra 6 a 7 sem o pacote.
- **Dois ajustes fizeram a diferença nessas rodadas.** O Opus parou de refazer a conferência
  que o `quick-edit` já tinha feito, e o `quick-edit` passou a separar sozinho os testes que já
  falhavam antes da mudança; sem isso, o Opus gastava 6 turnos investigando.
- **Pedido curto que exige investigar fica perto do neutro.** O Opus precisa investigar de
  qualquer jeito; o pacote só acrescenta ~1,3 mil tokens de contexto fixo. A diferença medida
  (+7% e +14%) está dentro da variação entre rodadas iguais do próprio Opus (US$ 0,139 a
  US$ 0,168 na mesma tarefa).
- **A economia nas tarefas grandes ainda é estimada.** Ela precisa ser medida num projeto
  maior, com leitura de verdade.

## Premissas principais

- **Preços:** API da Anthropic por milhão de tokens.
  - Haiku 5.5: $0,10 de entrada e $0,50 de saída (pedidos de até 100 mil tokens).
  - Sonnet 5.5: $2 e $10.
  - Opus 5.5: $4 e $20.
  - Fable 5.1: $10 e $50.
  - Cache: leitura a ~0,1× da entrada ($0,20 no Opus 5.5) e escrita a 1,25×.
- **Planos Pro e Max:** não há cobrança por token, mas o consumo pesa no limite de uso de
  forma parecida. As porcentagens valem como ordem de grandeza.
- **Tokenizador:** o Haiku 5.5 conta ~30% mais tokens para o mesmo texto.
- **Contextos iniciais:** a sessão principal começa com 18 a 22 mil tokens, mais ~2,5 mil
  do pacote; cada subagente, com 7 a 12 mil, mais ~400 de disciplina e mapa.
- **Tamanho da tarefa grande:** 14 leituras de ~3,5 mil tokens, 3 partes de edição e
  2 execuções da suíte de testes.
- **Bug difícil:** o Opus 5.5 `medium` leva de 3 a 5 tentativas; o `high` resolve na primeira.
- **Saída do Opus com a disciplina:** 65% / 55% / 46% da saída normal, nos cenários
  pessimista, esperado e otimista.
- **Velocidade de saída:** Haiku 5.5 a 250 tokens/s, Sonnet 5.5 a 120, Opus 5.5 a 70 e
  Fable 5.1 a 45. A espera até o primeiro token vai de 0,8 a 4 s.

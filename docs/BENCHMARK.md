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
| Execução | a própria sessão principal, que fica com contexto pequeno porque só recebe resumos |
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
| Pedido simples (renomear uma função) | $0.204 · 0.8 min | $0.219 · 0.8 min | +7% | +0% |
| Tarefa grande (analisar, corrigir, propor e implementar) | $1.369 · 6.8 min | $0.892 · 5.6 min | -35% | -17% |
| Log de CI longo + 10 turnos de trabalho seguinte | $0.695 · 2.4 min | $0.357 · 1.9 min | -49% | -20% |
| Bug difícil que o medium demora a resolver | $1.287 · 6.1 min | $0.959 · 3.9 min | -26% | -35% |
| **Dia típico** (8x simples, 2x grande, 2x log, 1x trava) | $7.04 · 31 min | $5.21 · 25 min | -26% | -18% |

## Tarefa grande: custo por função (cenário esperado)

| Função | Opus 5.5 medium | Token Pilot | Quem faz no Token Pilot |
|---|---|---|---|
| Análise | $0.578 | $0.307 | 3 scouts (Haiku 5.5) + researcher (Sonnet 5.5) |
| Brainstorm | $0.084 | $0.191 | ideator (Opus 5.5, high) |
| Execução | $0.572 | $0.329 | sessão principal, com a disciplina de resposta |
| Verificação | $0.082 | $0.043 | 2 verifiers (Haiku 5.5) |
| Coordenação | $0.052 | $0.021 | sessão principal (resumo final) |

## Faixa (pessimista · esperado · otimista para o Token Pilot)

| Situação | Variação de custo | Variação de tempo |
|---|---|---|
| Pedido simples (renomear uma função) | +8% · +7% · +7% | +0% · +0% · +0% |
| Tarefa grande (analisar, corrigir, propor e implementar) | -19% · -35% · -46% | -9% · -17% · -24% |
| Log de CI longo + 10 turnos de trabalho seguinte | -36% · -49% · -57% | -13% · -20% · -25% |
| Bug difícil que o medium demora a resolver | +3% · -26% · -43% | -2% · -35% · -55% |
| Dia típico | -12% · -26% · -36% | -7% · -18% · -27% |

## De onde vem cada parte do ganho

| Tarefa grande (esperado) | Custo | Tempo |
|---|---|---|
| Só a estrutura (delegar leitura, editar na sessão principal) | −16% | +18% |
| Estrutura + disciplina de resposta | −35% | −17% |

| Dia típico (esperado) | Custo | Tempo |
|---|---|---|
| Só a estrutura | −13% | +10% |
| Estrutura + disciplina de resposta | −26% | −18% |

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
| Pedido simples | Resolve direto | Igual; ~7% mais caro pelo contexto extra do pacote |
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

**Rodadas reais até agora** (09/10/2026, Claude Code 2.1.295, 1 rodada por braço; ainda é
pouco para tirar números, mas já mostra a direção):

| Tarefa | Opus 5.5 medium | Token Pilot | Custo | Tempo | Os dois acertaram? |
|---|---|---|---|---|---|
| `renomear` (2 rodadas) | $0.168 e $0.139 | $0.178 e $0.177 | +6% e +27% | −9% e +11% | sim |
| `corrigir-testes` | $0.188 · 25 s | $0.202 · 40 s | +7% | +60% | sim |

O que isso mostra:

- **Num projeto pequeno, o pacote ainda não economiza.** As tarefas custaram US$ 0,14 a
  US$ 0,20, bem menos que a "tarefa grande" da estimativa (US$ 1,37). Não há leitura grande
  para tirar do Opus, e sobra o custo fixo de ~2,5 mil tokens de contexto.
- **A chamada ao `verifier` atrasou a correção em ~15 s** para rodar um teste de menos de um
  segundo. Depois disso, testes curtos passaram a rodar na própria sessão, e o `verifier`
  ficou para suítes longas ou lentas.
- **A economia estimada depende de tarefas maiores.** Ela ainda precisa ser medida num
  projeto maior, com leitura de verdade, antes de ser tratada como fato.

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

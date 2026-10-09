# Benchmark estimado: Opus 5.5 medium (uso normal) x Token Pilot

> **Estimativa, não medição.** Os números vêm de `tests/benchmark_estimate.py`, um modelo
> turno a turno com premissas explícitas no código. A medição real vem do plano em
> `examples/estoque/PLANO-DE-TESTE.md` e do relatório de `tests/session_report.py`.

**O que está sendo comparado:**

- **Opus 5.5 medium (uso normal):** uma sessão só, no Opus 5.5 com effort `medium`, que lê,
  pensa, edita e testa tudo sozinha. Ninguém troca `/model` nem `/effort`.
- **Token Pilot:** a mesma sessão principal (Opus 5.5 `medium`) coordena e delega cada função
  a um subagente:

| Função | Subagente |
|---|---|
| Análise | `scout` e `log-reader` (Haiku 5.5, `low`) e `researcher` (Sonnet 5.5, `medium`) |
| Brainstorm | `ideator` (Opus 5.5, `high`) |
| Execução | `implementer` (Opus 5.5, `medium`), um por parte |
| Verificação | `verifier` (Haiku 5.5, `low`) |
| Escalada, se travar | `implementer-high` (Opus 5.5, `high`) |

Recalcule com:

```bash
python3 tests/benchmark_estimate.py          # tabelas
python3 tests/benchmark_estimate.py --json   # dados
```


Custo em dólares equivalentes à API (em planos Pro/Max, o mesmo consumo pesa no limite de uso). Tempo é o de espera do usuário, sem contar quanto ele demora para responder.

## Cenário esperado

| Situação | Opus 5.5 medium | Token Pilot | Custo | Tempo |
|---|---|---|---|---|
| Pedido simples (renomear uma função) | $0.204 · 0.8 min | $0.213 · 0.8 min | +4% | +0% |
| Tarefa grande (analisar, corrigir, propor e implementar) | $1.369 · 6.8 min | $1.355 · 9.3 min | -1% | +38% |
| Log de CI longo + 10 turnos de trabalho seguinte | $0.695 · 2.4 min | $0.425 · 2.6 min | -39% | +9% |
| Bug difícil que o medium demora a resolver | $1.287 · 6.1 min | $1.175 · 6.3 min | -9% | +4% |
| **Dia típico** (8x simples, 2x grande, 2x log, 1x trava) | $7.04 · 31 min | $6.44 · 37 min | -9% | +19% |

## Tarefa grande: custo por função (cenário esperado)

| Função | Opus 5.5 medium | Token Pilot | Quem faz no Token Pilot |
|---|---|---|---|
| Análise | $0.578 | $0.327 | 3 scouts (Haiku 5.5) + researcher (Sonnet 5.5) |
| Brainstorm | $0.084 | $0.271 | ideator (Opus 5.5, high) |
| Execução | $0.572 | $0.699 | 3 implementers (Opus 5.5, medium) |
| Verificação | $0.082 | $0.034 | 2 verifiers (Haiku 5.5) |
| Coordenação | $0.052 | $0.024 | sessão principal (resumo final) |

## Faixa (pessimista · esperado · otimista para o Token Pilot)

| Situação | Variação de custo | Variação de tempo |
|---|---|---|
| Pedido simples (renomear uma função) | +5% · +4% · +4% | +0% · +0% · +0% |
| Tarefa grande (analisar, corrigir, propor e implementar) | +21% · -1% · -15% | +38% · +38% · +38% |
| Log de CI longo + 10 turnos de trabalho seguinte | -27% · -39% · -47% | +9% · +9% · +9% |
| Bug difícil que o medium demora a resolver | +23% · -9% · -28% | +40% · +4% · -17% |
| Dia típico | +8% · -9% · -20% | +25% · +19% · +13% |

## Leitura dos resultados

**Onde a delegação economiza:**
- **Leitura grande (log, muitos arquivos):** −39% no log. A leitura vai para o Haiku 5.5,
  e a sessão principal recebe só um resumo, em vez de carregar o log nos turnos seguintes.
- **Análise e verificação na tarefa grande:** −43% e −59%.
- **Bug difícil:** −9% no esperado. O high resolve com menos tentativas do que o medium
  insistindo numa sessão de contexto grande. Isso depende muito de quantas tentativas o
  medium leva: no cenário pessimista (3 tentativas), o Token Pilot sai 23% mais caro; no
  otimista (5 tentativas), 28% mais barato.

**Onde a delegação custa mais:**
- **Brainstorm:** mais de três vezes o custo. O `ideator` roda em `high`, com mais
  raciocínio, e abre um contexto novo no Opus. É uma escolha de qualidade, não de economia.
- **Execução:** +22%. Cada `implementer` abre um contexto novo no Opus, paga a gravação
  dele e relê arquivos que a análise já tinha lido.
- **Pedido simples:** +4%, pelas regras do hook e as descrições dos agentes no contexto.

**Saldo:**
- **Tarefa grande:** quase empata no custo (−1%, de +21% a −15%).
- **Dia típico:** −9% (de +8% a −20%).

## Tempo

- **Tarefa grande:** o Token Pilot fica ~38% mais lento. Cada subagente tem a própria
  espera até o primeiro token e começa sem contexto. Os scouts rodam em paralelo, mas os
  implementers rodam um depois do outro.
- **Log e bug difícil:** quase o mesmo tempo.
- **Dia típico:** +19%, sem contar o tempo que você leva para responder a pausa do
  brainstorm.

## Parte funcional

| Aspecto | Opus 5.5 medium (uso normal) | Token Pilot |
|---|---|---|
| Pedido simples | Resolve direto | Igual |
| Análise de código | O Opus lê tudo e tem todos os detalhes à mão | O Haiku 5.5 resume; risco de um resumo deixar passar um detalhe |
| Brainstorm | No meio da conversa, em `medium`, sem pausa | O `ideator` compara opções em `high` e você escolhe antes da edição |
| Edição | Opus com todo o contexto da conversa | Opus, mas o `implementer` só vê o brief; risco de perder contexto |
| Verificação | Quando o Claude lembra de rodar os testes | O `verifier` roda depois de cada parte |
| Bug difícil | Continua no `medium`; pode não resolver | Sobe para `high` e depois Fable, se o plano tiver |
| Contexto longo | A sessão cresce e pede `/compact` mais cedo | A sessão principal cresce devagar, porque recebe só resumos |

**Ganhos funcionais:** brainstorm mais cuidadoso, verificação sistemática e escalada
automática.

**Riscos funcionais:** resumos do Haiku 5.5 que perdem detalhes, o implementer sem a
conversa e mais espera. A Sessão 2 do plano de teste mede esses riscos.

## O que dá para melhorar no Token Pilot

O modelo aponta a execução como o maior custo extra. Executar as partes na sessão principal,
que com o pacote tem contexto pequeno, e deixar os implementers só para a escalada levaria
a tarefa grande de −1% para cerca de −17% (de −3% a −27%) e diminuiria a espera. Isso muda
o desenho de "um subagente por função" e ainda não foi feito.

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
- **Contextos iniciais:** a sessão principal começa com 18 a 22 mil tokens; cada
  subagente, com 7 a 12 mil.
- **Tamanho da tarefa grande:** 14 leituras de ~3,5 mil tokens, 3 partes de edição e
  2 execuções da suíte de testes.
- **Bug difícil:** o Opus 5.5 `medium` leva de 3 a 5 tentativas; o `high` resolve na primeira.
- **Velocidade de saída:** Haiku 5.5 a 250 tokens/s, Sonnet 5.5 a 120, Opus 5.5 a 70 e
  Fable 5.1 a 45. A espera até o primeiro token vai de 0,8 a 4 s.

# Benchmark estimado: Token Pilot x Claude Code puro

> **Estimativa, não medição.** Os números vêm de `tests/benchmark_estimate.py`, um modelo
> turno a turno com premissas explícitas no código. Eles servem para comparar os dois
> jeitos de trabalhar e mostrar de onde vem a economia. A medição real vem do plano em
> `examples/estoque/PLANO-DE-TESTE.md` e do relatório de `tests/session_report.py`.

Recalcule com:

```bash
python3 tests/benchmark_estimate.py          # tabelas
python3 tests/benchmark_estimate.py --json   # dados
```


Custo em dólares equivalentes à API (em planos Pro/Max, o mesmo consumo pesa no limite de uso). Tempo é o de espera do usuário, sem contar quanto ele demora para responder.

## Cenário esperado

| Situação | Sem o pacote | Com o Token Pilot | Custo | Tempo |
|---|---|---|---|---|
| Pedido simples (renomear uma função) | $0.204 · 0.8 min | $0.213 · 0.8 min | +4% | +0% |
| Tarefa grande (analisar, corrigir, propor e implementar) | $1.369 · 6.8 min | $1.355 · 9.3 min | -1% | +38% |
| Tarefa grande, variante: execução na sessão principal | $1.369 · 6.8 min | $1.135 · 8.0 min | -17% | +18% |
| Log de CI longo + 10 turnos de trabalho seguinte | $0.695 · 2.4 min | $0.425 · 2.6 min | -39% | +9% |
| Bug que trava no medium e só sai no high | $1.572 · 6.1 min | $1.175 · 6.3 min | -25% | +4% |

**Dia típico** (8x simples, 2x grande, 2x log, 1x trava): $7.33 sem o pacote, $6.44 com ele (-12%); $6.00 com a variante na tarefa grande (-18%).

## Faixa (pessimista · esperado · otimista)

| Situação | Variação de custo |
|---|---|
| Pedido simples (renomear uma função) | +5% · +4% · +4% |
| Tarefa grande (analisar, corrigir, propor e implementar) | +21% · -1% · -15% |
| Tarefa grande, variante: execução na sessão principal | -3% · -17% · -27% |
| Log de CI longo + 10 turnos de trabalho seguinte | -27% · -39% · -47% |
| Bug que trava no medium e só sai no high | -21% · -25% · -28% |
| Dia típico | -1% · -12% · -20% |
| Dia típico, com a variante | -10% · -18% · -24% |

## De onde vem (e de onde não vem) a economia

- **Leitura grande fora do Opus.** É onde o pacote mais economiza. Um log de 40 mil tokens
  lido na sessão principal fica no contexto e é relido a cada turno seguinte; no `log-reader`
  (Haiku 5.5) ele é filtrado com `grep`/`tail` e só um resumo de ~450 tokens chega à sessão.
- **Escalada em contexto novo.** Quando algo trava, trocar `/effort high` no meio da sessão
  regrava o cache da conversa inteira. O `implementer-high` começa com um contexto pequeno.
- **A leitura do Opus 5.5 já é barata.** O cache sai a $0,20 por milhão de tokens. Por isso,
  tirar a análise da sessão principal economiza menos do que parece.
- **O que pesa no Opus são saídas e gravações de cache.** Cada subagente no Opus
  (`ideator`, `implementer`) começa um contexto novo e paga a gravação dele, e o `implementer`
  relê arquivos que a análise já tinha lido. Na tarefa grande, isso quase anula a economia
  da análise.
- **Pedidos simples ficam ~4% mais caros.** É o custo das regras do hook e das descrições
  dos agentes no contexto de toda sessão.

## Tempo

- **Subagentes no caminho crítico atrasam.** Cada um tem a própria espera até o primeiro
  token e começa sem contexto. Os scouts rodam em paralelo, mas os implementers rodam um
  depois do outro.
- **Tarefa grande:** +38% de tempo no fluxo atual e +18% na variante com a execução na
  sessão principal.
- **Log e trava:** quase o mesmo tempo (+4% a +9%).
- **Fora da conta:** o tempo que você leva para responder a pausa do brainstorm.

## Parte funcional

| Aspecto | Sem o pacote | Com o Token Pilot |
|---|---|---|
| Pedido simples | Resolve direto | Igual; o pacote não deve interferir |
| Análise de código | O Opus lê tudo e decide sozinho o que importa | O Haiku 5.5 resume; risco de um resumo deixar passar um detalhe |
| Brainstorm | Feito no meio da conversa, sem pausa | O `ideator` (Opus, high) compara opções e você escolhe antes da edição |
| Edição | Opus 5.5 com todo o contexto da conversa | Opus 5.5, mas o `implementer` só vê o brief; risco de perder contexto entre etapas |
| Verificação | Quando o Claude lembra de rodar os testes | O `verifier` roda depois de cada parte |
| Trava | Você percebe e troca `/effort` ou `/model` | Sobe sozinho (high e depois Fable, se o plano tiver) |
| Contexto longo | A sessão cresce e pede `/compact` mais cedo | A sessão principal cresce devagar, porque recebe só resumos |
| Plano sem Fable | Nada muda | A escada para no high e pede ajuda |

**Ganho funcional esperado:** a verificação sistemática, a escalada automática e a pausa
para decidir antes de editar.

**Riscos funcionais:**
- **Resumos do Haiku 5.5:** podem perder detalhes.
- **Implementer sem a conversa:** depende do brief, então pode perder contexto.
- **Mais pausas e esperas:** o fluxo grande é mais lento.

A Sessão 2 do plano de teste mede esses três riscos.

## Recomendação que sai do modelo

Executar as partes na sessão principal, que com o pacote tem contexto pequeno, em vez de
um `implementer` por parte. Os implementers ficam para a escalada (`implementer-high`,
`implementer-fable`) e para partes grandes e independentes que possam rodar em paralelo.

| Tarefa grande | Custo | Tempo |
|---|---|---|
| Fluxo atual | +21% · −1% · −15% | +38% |
| Execução na sessão principal | −3% · −17% · −27% | +18% |

No dia típico, a variante leva a economia esperada de −12% para −18%.

## Premissas principais

- **Preços:** API da Anthropic por milhão de tokens.
  - Haiku 5.5: $0,10 de entrada e $0,50 de saída (pedidos de até 100 mil tokens).
  - Sonnet 5.5: $2 e $10.
  - Opus 5.5: $4 e $20.
  - Fable 5.1: $10 e $50.
  - Cache: leitura a ~0,1× da entrada ($0,20 no Opus 5.5) e escrita a 1,25×.
- **Planos Pro e Max:** não há cobrança por token, mas o consumo pesa no limite de uso de
  forma parecida. As porcentagens valem como ordem de grandeza para o limite.
- **Tokenizador:** o Haiku 5.5 conta ~30% mais tokens para o mesmo texto.
- **Contextos iniciais:** a sessão principal começa com 18 a 22 mil tokens (prompt de
  sistema, ferramentas e CLAUDE.md); cada subagente, com 7 a 12 mil.
- **Tamanho da tarefa grande:** 14 leituras de ~3,5 mil tokens, 3 partes de edição e
  2 execuções da suíte de testes.
- **Velocidade de saída:** Haiku 5.5 a 250 tokens/s, Sonnet 5.5 a 120, Opus 5.5 a 70 e
  Fable 5.1 a 45. A espera até o primeiro token vai de 0,8 a 4 s.
- **Dia típico:** 8 pedidos simples, 2 tarefas grandes, 2 leituras de log e 1 trava.

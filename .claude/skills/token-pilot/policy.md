# Política do Token Pilot

A sessão principal roda no modelo que o usuário escolheu e só coordena. O trabalho vai para
subagentes em três modelos, todos disponíveis desde o plano Pro:

- Haiku 5.5 ($0,10/$0,50 por milhão de tokens de entrada/saída): busca, logs, testes,
  mudança mecânica.
- Sonnet 5.5 ($2/$10): pesquisa que exige ler e comparar vários arquivos.
- Opus 5.5 ($4/$20): implementação e decisão.

Quanto mais cara a sessão principal (por exemplo, Fable 5.1 a $10/$50), maior a economia de
manter a leitura e a edição fora dela.

## Níveis dos subagentes

| Nível | Agente | Modelo | Effort | Quando |
|---|---|---|---|---|
| 0 – Leitura | `scout`, `log-reader`, `verifier` | Haiku 5.5 | `low` | Busca, logs, testes |
| 0 – Leitura | `researcher` | Sonnet 5.5 | `medium` | Entender um fluxo |
| 0 – Mecânico | `quick-edit` | Haiku 5.5 | `medium` | Renomear, trocar texto, imports |
| 1 – Padrão | `implementer` | Opus 5.5 | `medium` | Implementar ou corrigir uma parte |
| 1 – Decisão | `ideator` | Opus 5.5 | `high` | Comparar opções |
| 2 – Reforço | `implementer-high` | Opus 5.5 | `high` | 2 falhas no mesmo problema no nível 1 |
| — | a coordenadora pede ajuda | — | — | 2 falhas no nível 2 |

## Sinais de "parede"

Conte como falha no mesmo problema quando:

- o mesmo teste/comando continua falhando com o mesmo erro depois de uma correção;
- o usuário diz que ainda não funciona ("ainda", "de novo", "continua", "mesmo erro",
  "still", "again", "same error");
- o subagente propôs a mesma abordagem duas vezes;
- a correção de um erro gerou outro no mesmo ponto e voltou ao erro original.

Não conte como falha: erro novo e diferente que mostra progresso, pedido de ajuste de
estilo, ou tarefa nova.

## Sinais de "resolvido"

Teste passando, usuário confirma ("funcionou", "resolvido", "deu certo", "works",
"fixed"), ou o usuário muda de assunto. Ao ver isso depois de subir de nível, a próxima
parte volta para o `implementer`.

## Por que a sessão principal não troca de modelo

Trocar modelo ou effort invalida o cache do prompt e força uma nova escrita de cache. Os
subagentes resolvem a necessidade de outro modelo sem tocar no cache da sessão principal.

## Mensagens prontas

- Parede: `💡 Token Pilot: segunda falha no mesmo erro. Passando a parte para o implementer-high (Opus 5.5, high).`
- Parede no high: `💡 Token Pilot: o high também travou duas vezes. Parando para você decidir: <resumo>.`
- Resolvido: `💡 Token Pilot: resolvido. A próxima parte volta para o implementer (Opus 5.5, medium).`
- Nova tarefa: `💡 Token Pilot: assunto novo, /clear evita carregar o contexto antigo.`
- Conversa longa: `💡 Token Pilot: bom momento para /compact manter: <resumo>.`

# Política do Token Pilot

Baseada no guia "Making Opus 5.5 your daily driver". Opus 5.5 custa 20% menos por
token que o Opus 5 e 60% menos em leituras de cache, então a regra geral é: fique no
Opus 5.5 com effort `medium` e só saia disso com motivo.

## Níveis

| Nível | Modelo | Effort | Quando | Como entrar | Como sair |
|---|---|---|---|---|---|
| 0 – Leve | Haiku / Sonnet (subagente) | `low`/`medium` | Busca, logs, testes, pesquisa | `scout`, `log-reader`, `verifier`, `researcher` | termina sozinho |
| 1 – Padrão | Opus 5.5 | `medium` | Trabalho diário bem delimitado | `/model opus` + `/effort medium` | — |
| 2 – Reforço | Opus 5.5 | `high` | 2 falhas no mesmo problema no nível 1 | subagente `implementer-high` (manual: `/boost`) | automático ao terminar |
| 3 – Escalada | Fable 5.1 | `high` | 2 falhas no mesmo problema no nível 2 | subagente `implementer-fable` (manual: `/escalate`) | automático ao terminar |

## Sinais de "parede"

Conte como falha no mesmo problema quando:

- o mesmo teste/comando continua falhando com o mesmo erro depois de uma correção;
- o usuário diz que ainda não funciona ("ainda", "de novo", "continua", "mesmo erro",
  "still", "again", "same error");
- você propôs a mesma abordagem duas vezes;
- a correção de um erro gerou outro no mesmo ponto e voltou ao erro original.

Não conte como falha: erro novo e diferente que mostra progresso, pedido de ajuste de
estilo, ou tarefa nova.

## Sinais de "resolvido"

Teste passando, usuário confirma ("funcionou", "resolvido", "deu certo", "works",
"fixed"), ou o usuário muda de assunto. Ao ver isso depois de subir de nível,
recomende voltar ao nível 1.

## Por que trocar só em intervalos

Trocar modelo ou effort invalida o cache do prompt e força uma nova escrita de cache.
Por isso:

- não recomende troca no meio de uma sequência de edições;
- prefira `/boost` e `/escalate`, que valem só para uma tarefa e evitam esquecer o
  nível alto ligado;
- junte a troca com um `/compact` quando os dois forem úteis, já que ambos custam uma
  escrita de cache.

## Mensagens prontas

- Início: `💡 Token Pilot: tarefa bem delimitada, /effort medium basta.`
- Multi-arquivo: `💡 Token Pilot: vai mexer em vários arquivos, vale entrar em plan mode (Shift+Tab) antes.`
- Parede 1: `💡 Token Pilot: segunda falha no mesmo erro. Passando a correção para o implementer-high (Opus 5.5, high).`
- Parede 2: `💡 Token Pilot: o high também travou duas vezes. Passando para o implementer-fable (Fable 5.1).`
- Resolvido: `💡 Token Pilot: resolvido. A próxima parte volta ao implementer (Opus 5.5, medium).`
- Nova tarefa: `💡 Token Pilot: assunto novo, /clear evita carregar o contexto antigo.`
- Conversa longa: `💡 Token Pilot: bom momento para /compact manter: <resumo>.`
- Medição: `💡 Token Pilot: rode a mesma tarefa em cada modelo e compare o /usage.`

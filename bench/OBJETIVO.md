# Objetivo do benchmark

Este benchmark responde a duas perguntas sobre o Token Pilot, em tarefas pequenas, médias e
pesadas:

1. **O resultado fica melhor, ou pelo menos igual?** O pacote muda como o Claude trabalha:
   ele delega a leitura a modelos baratos, segue a disciplina de resposta, recebe o mapa do
   código e manda as mudanças mecânicas para o `quick-edit`. Tudo isso só vale se o trabalho
   continuar certo.
2. **Ele gasta menos tokens?** A promessa do pacote é economia. Ela precisa aparecer em
   medição real, e não só na estimativa de `tests/benchmark_estimate.py`.

A resposta esperada é uma tabela por tamanho de tarefa. Ela mostra onde o pacote economiza,
onde fica neutro e onde piora, e se a qualidade se mantém em cada caso.

## O que está sendo comparado

| Braço | O que roda |
|---|---|
| `opus-medium` | Claude Code no Opus 5.5, effort `medium`, sem o pacote. É o uso normal. |
| `token-pilot` | A mesma sessão, com a pasta `.claude/` do pacote: hook, skills, agentes e disciplina. |

A sessão principal é igual nos dois braços: mesmo modelo, mesmo effort, mesmo pedido e o
mesmo projeto de partida. Assim, qualquer diferença vem do pacote.

## O que cada parte do pacote deveria trazer

| Parte do pacote | Benefício esperado | Onde aparece no benchmark |
|---|---|---|
| `quick-edit` (Haiku 5.5) para pedidos mecânicos | Menos custo e menos turnos do Opus | Tarefas pequenas |
| Instrução de tarefa curta (resolver direto) | Ficar perto do neutro, sem custo extra de subagentes | `corrigir-testes` e `simulador` |
| Disciplina de resposta | Menos tokens de saída do Opus, diffs menores e completos | Todas, sobretudo as médias |
| Delegação de leitura e de logs (`scout`, `log-reader`, `researcher`) | Contexto menor na sessão principal | Médias com log, pesadas |
| `big-task` com `ideator` e `verifier` | Desenho melhor e verificação sistemática | Pesadas |
| Mapa do código | Menos releituras e reuso do que já existe | Médias e pesadas |

## Tarefas

São 10 tarefas, em dois projetos de exemplo: `examples/estoque`, pequeno, e
`examples/loja-grande`, com 45 arquivos e cerca de 2.200 linhas. A coluna "Como o hook
classifica" mostra o caminho que o pacote escolhe para cada pedido.

| Tamanho | Tarefa | O que pede | Como o hook classifica |
|---|---|---|---|
| pequena | `renomear` | Renomear uma função e os usos dela | mecânica → `quick-edit` |
| pequena | `pequena-renomear-loja` | Idem, no projeto maior | mecânica → `quick-edit` |
| pequena | `pequena-milhar` | Corrigir o separador de milhar e o teste da função | mecânica → `quick-edit` |
| media | `corrigir-testes` | Achar e corrigir a causa dos testes que falham | curta |
| media | `simulador` | Rodar um script que quebra no fim de um log longo e corrigir | curta |
| media | `grande-bug` | Bug de cupom com promoção que atravessa módulos | média |
| media | `grande-sincronizar` | Sincronização que quebra no meio de ~2.000 linhas de log | média |
| pesada | `reposicao` | Corrigir os testes e criar um comando novo, com testes | grande → `big-task` |
| pesada | `grande-reembolso` | Reembolso parcial de pedidos, com testes ocultos | grande → `big-task` |
| pesada | `pesada-limite-cupom` | Limite de uso de cupons, total e por cliente, com testes ocultos | grande → `big-task` |

A `pequena-milhar` é de propósito um caso limite: o hook a manda para o Haiku, mas ela exige
uma pequena correção de lógica. Ela mede se a economia do `quick-edit` custa qualidade.

## Como o resultado é medido

**Qualidade (pergunta 1)**

- **Acerto:** a verificação da tarefa passa. Pode ser um comando que roda, a suíte de testes
  ou testes ocultos, que só entram no projeto depois que o Claude termina.
- **Sem regressão:** a suíte visível não termina com mais falhas do que tinha no começo.
- **Regras do pedido:** testes intactos quando o pedido proíbe mudá-los, dados intactos e
  testes novos quando o pedido pede.
- **Nota de qualidade:** a fração dessas conferências que passou, em média entre as rodadas.
- **Tamanho do diff:** linhas mudadas. Serve para ver se a disciplina deixa a mudança menor
  sem deixar de fazer o pedido.

**Economia (pergunta 2)**

- **Tokens totais:** entrada, cache lido, cache escrito e saída, somados entre os modelos. É
  o que pesa no limite de uso dos planos Pro e Max.
- **Tokens de saída:** a parte mais cara e mais lenta no Opus 5.5, e a que a disciplina de
  resposta deveria cortar.
- **Custo equivalente em US$:** a estimativa do próprio Claude Code. Ela pondera cada modelo
  pelo preço, então um token do Haiku pesa menos que um do Opus.
- **Tempo e turnos:** o custo de espera para quem usa.

Os tokens vêm do `modelUsage` do `claude -p --output-format json`, separados por modelo.
Esse dado aparece também quando a sessão usa a assinatura, e não só com chave de API.

## Como ler o resultado

- Para cada tarefa e braço, o relatório usa a **mediana das rodadas que passaram**. Assim, um
  braço que não terminou o trabalho não parece mais barato.
- Por tamanho, e no total, ele mostra a **média geométrica da razão** `token-pilot /
  opus-medium`. Valor negativo é economia.
- O pacote **cumpre o objetivo** num tamanho de tarefa quando duas coisas valem juntas:
  - O acerto e a nota de qualidade ficam iguais ou acima da base.
  - Os tokens e o custo ficam abaixo dela, por uma margem maior que a variação entre rodadas
    iguais do próprio `opus-medium`. Nas rodadas de 09/10/2026, essa variação chegou a ~20%.
- Se a economia vier com perda de qualidade, o resultado conta como piora, e não como ganho.

## Rodar

Veja `bench/README.md`. Sem chave de API, rode na sua máquina, com o Claude Code logado no
plano. O consumo sai do limite de uso, e os tokens são registrados do mesmo jeito:

```bash
python3 bench/run.py run --runs 1 --tiers pequena   # teste rápido, 6 sessões
python3 bench/run.py run --runs 3 --jobs 2          # completo, 60 sessões
python3 bench/run.py compare bench/results/<arquivo>.jsonl
```

## Limites

- **Poucas tarefas:** são 10, em projetos de exemplo. O resultado mostra uma direção, não um
  número para qualquer projeto.
- **Pausas:** no modo sem interface ninguém responde as pausas do `big-task`, então os
  pedidos das tarefas pesadas dizem para o Claude decidir sozinho.
- **Configuração do usuário:** um `CLAUDE.md` ou agentes em `~/.claude/` podem influenciar as
  rodadas. O harness carrega só as configurações do projeto, mas vale rodar numa máquina
  limpa.
- **Custo estimado:** o custo em US$ é estimado pelo Claude Code e não é a cobrança real.

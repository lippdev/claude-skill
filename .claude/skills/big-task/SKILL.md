---
name: big-task
description: Coordena uma tarefa grande dividindo-a em análise, brainstorm e execução, e manda cada parte para um subagente com o modelo e o effort adequados (Haiku, Sonnet, Opus 5.5 ou Fable 5.1). Use quando o usuário pedir uma tarefa que exige entender o código, decidir o que fazer e depois implementar, ou quando ele digitar /big-task.
argument-hint: "<tarefa> [--auto]"
---

# Big Task: coordenadora

Tarefa: $ARGUMENTS

Você é a **coordenadora**. Você não lê código em volume nem edita arquivos: você divide a
tarefa, escolhe o agente de cada parte, mantém o brief e junta os resultados. Assim a
sessão principal fica pequena, nunca troca de modelo (o cache dela não é refeito) e cada
parte roda no modelo mais barato que dá conta dela.

Se `$ARGUMENTS` contiver `--auto`, não pare para o usuário escolher: siga a recomendação
do ideator. Sem `--auto`, pare nos pontos marcados com ⏸.

## Agentes disponíveis

O effort vem do arquivo do agente, então escolha o agente pela combinação que a parte exige.

| Agente | Modelo | Effort | Use para |
|---|---|---|---|
| `scout` | Haiku | low | localizar arquivos, símbolos, usos |
| `log-reader` | Haiku | low | resumir logs, CI, stack traces |
| `verifier` | Haiku | low | rodar testes/build/lint e resumir |
| `researcher` | Sonnet | medium | entender um fluxo lendo vários arquivos |
| `ideator` | Opus 5.5 | high | brainstorm e comparação de opções |
| `implementer` | Opus 5.5 | medium | editar código (nível padrão) |
| `implementer-high` | Opus 5.5 | high | parte que falhou 2× no implementer |
| `implementer-fable` | Fable 5.1 | high | parte que falhou 2× no implementer-high |

### Plano do usuário

Nem todo plano tem todos os modelos (o Pro não tem Fable, por exemplo). O hook informa no
início da sessão a linha `Modelos do plano do usuário` e, se preciso, quais agentes devem
ser chamados com o parâmetro `model` trocado. Siga essa linha:

- Agente cujo modelo não está no plano → chame-o passando o `model` substituto indicado.
- Sem Fable → a escada termina no `implementer-high`. Depois de 2 falhas nele, pare,
  resuma o que foi tentado e peça ajuda ao usuário.
- Um subagente falhou porque o modelo não está disponível → trate esse modelo como
  indisponível pelo resto da sessão e aplique a mesma regra.

Regra de escolha para cada parte:

- **Só achar coisas** → `scout`. **Entender como coisas se ligam** → `researcher`.
- **Decidir entre caminhos** → `ideator`.
- **Mudar código** → sempre começa no `implementer`. Nunca comece no high ou no Fable.
- **Conferir** → `verifier`. **Log grande** → `log-reader`.
- Nunca mande edição para Haiku ou Sonnet.

## Brief: a memória compartilhada

Subagentes não veem esta conversa. A memória deles é o arquivo `.token-pilot/brief.md`
na raiz do projeto. Você é a única que escreve nele. Mantenha-o com no máximo ~60 linhas:

```markdown
# Brief: <tarefa>
## Objetivo
## Mapa do código        (da análise: arquivo:linha + 1 frase)
## Decisão               (opção escolhida no brainstorm)
## Plano                 (partes numeradas, status: pendente/ok/falhou)
## Falhas                (parte, nível, o que foi tentado, por que falhou)
## Comando de verificação
```

Crie o brief no início e atualize depois de cada etapa. Se existir um app ou servidor de
memória configurado (ver seção "Memória externa" em [reference.md](reference.md)), use-o
no lugar do arquivo, com o mesmo conteúdo.

## Fluxo

### 1. Análise (barata, em paralelo)

1. Escreva o brief só com o Objetivo.
2. Divida a análise em 2–4 perguntas independentes e dispare um `scout` para cada uma
   **na mesma mensagem** (em paralelo). Se uma pergunta exigir entender um fluxo, use
   `researcher` para ela.
3. Junte as respostas no "Mapa do código" do brief. Descubra também o comando de
   verificação (peça ao scout, se não souber).

Se a tarefa for pequena (1–2 arquivos já conhecidos), pule o brainstorm e vá para a
execução com um único `implementer`.

### 2. Brainstorm (caro, mas com entrada pequena)

1. Chame o `ideator` passando o Objetivo e o Mapa do código, não o código.
2. ⏸ Mostre as opções ao usuário em até 10 linhas e pergunte quais entram.
   Com `--auto`, use a recomendação do ideator e diga qual escolheu.
3. Registre a Decisão no brief.

### 3. Execução (partes em sequência)

1. Quebre a decisão em partes pequenas e verificáveis e escreva o Plano no brief.
   Se forem mais de 3 arquivos, ⏸ mostre o plano e peça aprovação (com `--auto`, siga).
2. Para cada parte, em ordem:
   1. Chame `implementer` com: número da parte, o que fazer, arquivos prováveis e o
      comando de verificação.
   2. Se voltar `OK`, chame `verifier` para confirmar (pule se o implementer já mostrou
      os testes passando).
   3. Se falhar, registre em Falhas e aplique a escada:
      - 2 falhas no `implementer` → `implementer-high`
      - 2 falhas no `implementer-high` → `implementer-fable` (só se o plano tiver Fable;
        sem Fable, pare aqui e explique ao usuário o que falta)
      - 2 falhas no `implementer-fable` → pare e explique ao usuário o que falta.
   4. Voltou OK depois de subir? A próxima parte começa de novo no `implementer`.
3. Partes que não tocam os mesmos arquivos podem rodar em paralelo com
   `isolation: "worktree"`. Na dúvida, rode em sequência.

### 4. Fechamento

Responda ao usuário em até 15 linhas:

- o que foi feito (partes e arquivos),
- resultado da verificação final,
- quais níveis foram usados, por exemplo `scout×3, ideator×1, implementer×3, implementer-high×1`,
- pendências, se houver.

Termine com `💡 Token Pilot: tarefa concluída. Se o próximo pedido não tiver relação, use /clear.`

## Regras de economia

- Passe para cada subagente só o que ele precisa: a parte dele e o caminho do brief.
- Nunca cole o resultado bruto de um subagente no próximo; resuma no brief.
- Não releia arquivos que um subagente já resumiu.
- Um subagente por pergunta. Não peça ao scout para "analisar tudo".

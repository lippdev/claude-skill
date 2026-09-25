# Plano de teste: Token Pilot num projeto real

Um controle de estoque em Python (só biblioteca padrão) com problemas plantados para
acionar cada agente. Você roda 4 sessões no seu terminal, gera um relatório e me manda.

## O que está plantado no projeto

| Problema | Onde | Para testar |
|---|---|---|
| Datas `dd/mm/aaaa` ordenadas como texto: o saldo sai errado quando os movimentos cruzam meses | `estoque/movimentos.py` | análise, execução e, se travar, a escada |
| Relatório usa `<` em vez de `<=` no estoque mínimo | `estoque/relatorios.py` | correção simples |
| Simulador imprime 281 linhas e quebra no fim com um SKU fora do cadastro | `simular.py` | `log-reader` |
| Nenhum alerta de reposição | todo o projeto | brainstorm no `ideator` |

Estado inicial: `python3 -m unittest -q` mostra `FAILED (failures=3)`.

## Preparar (uma vez)

```bash
cd ~ && (git clone -q https://github.com/lippdev/claude-skill.git || git -C claude-skill pull -q origin main)
rm -rf ~/tp-estoque && cp -r ~/claude-skill/examples/estoque ~/tp-estoque && cp -r ~/claude-skill/.claude ~/tp-estoque/
cd ~/tp-estoque && git init -q && git add -A && git commit -qm "estado inicial"
python3 .claude/hooks/token_pilot.py --plan pro     # troque pelo seu plano: pro, max, team...
python3 -m unittest -q                              # deve mostrar FAILED (failures=3)
```

Abra cada sessão com `claude` dentro de `~/tp-estoque`. Na primeira, rode `/agents` e confira
se aparecem os 8 agentes do pacote.

Responda às perguntas do Claude como faria normalmente. Não precisa acompanhar os detalhes:
o relatório do final registra quais agentes rodaram e em qual modelo.

## Sessão 1: pedido simples (controle)

```
Renomeia a função valor_total para valor_total_estoque e atualiza onde ela é usada.
```

Esperado: nenhum aviso de tarefa grande, nenhum `ideator` e nenhum `implementer`. A sessão
principal resolve sozinha, com no máximo um `scout`. Serve para ver se o pacote atrapalha
pedidos pequenos.

Saia com `/exit`.

## Sessão 2: tarefa grande, sem comandos

```
Analisa o projeto de estoque, corrige os testes que estão falhando e me dá ideias de alertas de reposição. Depois implementa a que você recomendar.
```

Esperado:

1. Aviso `💡 Token Pilot: Tarefa grande detectada`.
2. **Análise:** 2 a 4 `scout` (Haiku) em paralelo, talvez um `researcher` (Sonnet). Aparece
   `.token-pilot/brief.md`.
3. **Brainstorm:** um `ideator` (Opus, high) e uma pausa para você escolher. Responda
   `vai com a recomendada`.
4. **Execução:** `implementer` (Opus, medium) por parte e `verifier` (Haiku) conferindo.
5. **Fechamento:** resumo com a contagem de agentes e os testes passando.

Saia com `/exit`.

## Sessão 3: log longo

```
Roda python3 simular.py e me explica por que ele quebra. Não corrige nada ainda.
```

Esperado: um `log-reader` ou `verifier` (Haiku) lê a saída. A sessão principal recebe só o
resumo: o SKU `FIL-009` não existe no cadastro.

Continue na mesma sessão para a Sessão 4.

## Sessão 4: trava e escada

Mande:

```
Agora corrige o simulador.
```

Depois da resposta, mande **duas vezes seguidas**, mesmo que tenha funcionado:

```
ainda não funciona, continua dando o mesmo erro
```

Esperado na segunda mensagem: aviso `💡 Token Pilot: 2 falhas seguidas...implementer-high`.
Aqui há duas reações corretas, e o relatório mostra qual aconteceu:

- o Claude roda o simulador de novo, vê que funciona e pergunta qual erro você está vendo
  (o hook manda conferir antes de agir); ou
- delega ao `implementer-high` (Opus, high) com o histórico da falha.

Reação errada: subir de nível sem conferir nada, ou pedir para você trocar `/model` ou `/effort`.

Por fim, mande:

```
nova tarefa: escreve um README curto para o projeto
```

Esperado: sugestão de `/clear`.

Saia com `/exit`.

## Gerar o relatório

```bash
cd ~/tp-estoque
python3 -m unittest -q 2>&1 | tail -1 > relatorio.md
git diff --stat >> relatorio.md
python3 ~/claude-skill/tests/session_report.py --last 3 >> relatorio.md
```

O relatório mostra, para cada sessão, os seus pedidos (só o começo), os avisos do Token Pilot,
os subagentes com o modelo que de fato rodou e o esperado, o effort, os tokens por modelo, o
tempo e os erros. Ele não inclui o conteúdo das respostas nem das ferramentas.

## O que me mandar

1. O conteúdo de `relatorio.md`.
2. Se puder, a saída de `/usage` no fim da Sessão 2.
3. Suas impressões em poucas linhas: alguma pausa incomodou? Algo pareceu lento ou confuso?
   O Claude pediu para você trocar modelo ou effort?

## Como vou avaliar

| Critério | Certo | Errado |
|---|---|---|
| Pedido simples | Resolve na sessão principal | Aciona o fluxo grande ou o ideator |
| Leitura | `scout` e `log-reader` no Haiku | Sessão principal lendo muitos arquivos ou o log inteiro |
| Brainstorm | Um `ideator` com entrada pequena e uma pausa | Brainstorm na sessão principal ou sem pausa |
| Edição | Só `implementer*` no Opus | Edição no Haiku ou no Sonnet |
| Modelo real | Igual ao esperado no relatório | Diferente (⚠️ no relatório) |
| Trava | Confere antes de subir; sobe para o high se a falha for real | Sobe sem conferir; pede `/model` ou `/effort` |
| Custo | A maior parte da leitura nos modelos baratos | Opus com a maior parte dos tokens de leitura |
| Resultado | 6 testes passando e simulador rodando | Testes ainda falhando |

# Cenário de teste: Loja demo

Um projeto Python pequeno (carrinho, catálogo, frete) com um bug proposital e 2 testes
falhando. Serve para testar o Token Pilot gastando pouco.

Requisitos: Python 3. Sem dependências.

## Preparar

Copie a demo para fora do repositório, junto com o pacote, e abra o Claude Code ali:

```bash
cp -r examples/demo-loja /tmp/demo-loja
cp -r .claude /tmp/demo-loja/
cd /tmp/demo-loja
python3 -m unittest -q     # deve mostrar FAILED (failures=2)
claude
```

Confira com `/agents` se aparecem os 8 agentes (scout, log-reader, verifier, researcher,
ideator, implementer, implementer-high, implementer-fable).

## Teste 0: sem comandos (o fluxo nativo)

Peça normalmente, sem `/`:

```
Analisa o carrinho, corrige os testes que falham e me dá ideias de cupons de desconto para implementar
```

O esperado: aparece `💡 Token Pilot: Tarefa grande detectada...` e o Claude segue sozinho
o mesmo fluxo do Teste 1 (scouts, ideator, implementer, verifier).

## Teste 1: tarefa grande com pausa, forçando pelo comando

```
/big-task Corrigir os testes que falham e adicionar cupons de desconto ao carrinho
```

O esperado:

1. **Análise:** 2–4 `scout` (Haiku) em paralelo e talvez um `researcher` (Sonnet).
   Aparece `.token-pilot/brief.md`.
2. **Brainstorm:** 1 `ideator` (Opus, high) com opções de cupom (percentual, valor fixo,
   frete grátis, validade...). ⏸ Ele para e pergunta quais entram.
3. **Execução:** `implementer` (Opus, medium) por parte, com `verifier` (Haiku) depois.
4. **Fechamento:** resumo com a contagem de cada agente usado.

Depois rode `/usage` e anote os números.

## Teste 2: tarefa grande sem pausa

```
/big-task Adicionar cupons de desconto ao carrinho --auto
```

Deve seguir direto com a recomendação do ideator.

## Teste 3: escada de escalada (hook)

Numa conversa normal, sem `/big-task`, mande em sequência:

```
o teste de frete ainda não passa
continua dando o mesmo erro
```

Na segunda, deve aparecer `💡 Token Pilot: ... implementer-high ...`, e o Claude deve
delegar a próxima tentativa a esse agente. Depois mande `funcionou!` e confira o aviso
de volta ao nível padrão.

## Teste 4: comparar custo

Rode a mesma tarefa do Teste 2 numa sessão nova **sem** o pacote (apague `.claude/`) e
compare o `/usage` das duas.

## Voltar ao início

```bash
rm -rf /tmp/demo-loja
```

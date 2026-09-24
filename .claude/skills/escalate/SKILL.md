---
name: escalate
description: Resolve um problema que travou até no effort high trocando para Fable 5.1 só durante esta tarefa, e depois volta ao modelo da sessão.
model: fable
effort: high
disable-model-invocation: true
argument-hint: "<problema>"
---

# Escalate (Fable 5.1)

O problema resistiu ao Opus 5.5 em `medium` e em `high`. Você está rodando no Fable 5.1
só enquanto esta skill estiver ativa. Quando terminar, a sessão volta ao modelo anterior.

Problema: $ARGUMENTS

1. Leia o histórico da conversa e liste as abordagens que já falharam e a evidência de cada falha.
2. Questione as premissas: o erro está mesmo onde todos procuraram? Leia o código real
   em vez de confiar em resumos anteriores.
3. Encontre a causa raiz, corrija com a menor mudança possível e verifique.
4. Escreva uma nota curta com a causa raiz e a correção, para a sessão principal continuar
   sem precisar do Fable.
5. Termine com: `💡 Token Pilot: resolvido no Fable 5.1. Volte ao padrão com /model opus e /effort medium.`
   Se não resolveu, diga o que falta descobrir e não sugira voltar ainda.

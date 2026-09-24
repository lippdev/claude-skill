---
name: boost
description: Resolve um problema travado com Opus 5.5 em effort high só durante esta tarefa, e depois a sessão volta ao effort normal.
effort: high
disable-model-invocation: true
argument-hint: "<problema>"
---

# Boost (Opus 5.5, effort high)

O usuário travou duas vezes no mesmo problema com effort `medium`. Você está rodando
com effort `high` só enquanto esta skill estiver ativa.

Problema: $ARGUMENTS

1. Resuma em até 3 linhas o que já foi tentado nesta conversa e por que falhou.
2. Levante hipóteses para a causa raiz antes de editar. Não repita uma abordagem que já falhou.
3. Corrija, depois verifique com o teste, build ou comando de reprodução.
4. No fim, diga numa linha se resolveu:
   - Resolvido: `💡 Token Pilot: resolvido no high. A sessão volta ao effort normal.`
   - Não resolvido: `💡 Token Pilot: o high também não resolveu. Próximo passo: /escalate <problema>.`

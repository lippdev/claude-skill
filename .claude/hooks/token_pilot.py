#!/usr/bin/env python3
"""Token Pilot hook: acompanha o uso da sessão e sugere trocas de modelo/effort.

Registrado em UserPromptSubmit. Lê o JSON do hook pela entrada padrão, atualiza um
estado por sessão e, quando algo muda, devolve um lembrete para o Claude
(additionalContext) e um aviso curto para o usuário (systemMessage).

Nunca bloqueia o prompt: qualquer erro sai com código 0 e sem saída.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# Limiares ajustáveis por variável de ambiente.
STALLS_TO_BOOST = int(os.environ.get("TOKEN_PILOT_STALLS_TO_BOOST", "2"))
STALLS_TO_ESCALATE = int(os.environ.get("TOKEN_PILOT_STALLS_TO_ESCALATE", "4"))
PROMPTS_TO_COMPACT = int(os.environ.get("TOKEN_PILOT_PROMPTS_TO_COMPACT", "30"))
TRANSCRIPT_MB_TO_COMPACT = float(os.environ.get("TOKEN_PILOT_TRANSCRIPT_MB", "2"))

STALL_PATTERNS = [
    r"\bainda (n[aã]o|d[aá]|est[aá]|falha|quebra)",
    r"\bde novo\b",
    r"\bcontinua (dando|falhando|com|quebrando|o mesmo)",
    r"\bmesmo (erro|problema|bug)\b",
    r"\bn[aã]o (funcionou|resolveu|deu certo|mudou nada)",
    r"\bnada mudou\b",
    r"\bn[aã]o passou\b",
    r"\bstill (fails?|failing|broken|not|doesn'?t|the same)",
    r"\bsame (error|issue|problem|bug)\b",
    r"\b(didn'?t|doesn'?t|does not|did not) (work|help|fix)",
    r"\bagain\b",
]
RESOLVED_PATTERNS = [
    r"\bfuncionou\b",
    r"\bresolv(eu|ido|ida)\b",
    r"\bdeu certo\b",
    r"\bpassou\b",
    r"\bperfeito\b",
    r"\b(it )?works( now)?\b",
    r"\bfixed\b",
    r"\bsolved\b",
    r"\ball (tests )?pass(ing)?\b",
]
NEW_TASK_PATTERNS = [
    r"^\s*(agora|pr[oó]xima tarefa|nova tarefa|outra coisa|mudando de assunto)\b",
    r"^\s*(now|next task|new task|unrelated|switching gears)\b",
]
MULTI_FILE_PATTERNS = [
    r"\brefator",
    r"\brefactor",
    r"\bmigra",
    r"\bv[aá]rios arquivos\b",
    r"\bmultiple files\b",
    r"\b(todo o|toda a|em todo) (projeto|c[oó]digo|repo)",
    r"\bacross the (codebase|repo)\b",
]


def matches(patterns, text):
    return any(re.search(p, text, re.IGNORECASE | re.MULTILINE) for p in patterns)


def state_path(session_id):
    base = Path(os.environ.get("TOKEN_PILOT_STATE_DIR", Path.home() / ".claude" / "token-pilot"))
    base.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "default")
    return base / f"{safe}.json"


def load_state(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {"prompts": 0, "stalls": 0, "level": 1, "last_hint": "", "since_compact": 0}


def transcript_mb(transcript_path):
    try:
        return os.path.getsize(transcript_path) / (1024 * 1024)
    except (OSError, TypeError):
        return 0.0


def decide(state, prompt, transcript_path):
    """Atualiza o estado e devolve (chave_da_dica, texto) ou (None, None)."""
    state["prompts"] += 1
    state["since_compact"] += 1

    if prompt.strip().startswith("/compact") or prompt.strip().startswith("/clear"):
        state["since_compact"] = 0
        state["stalls"] = 0
        return None, None

    if matches(RESOLVED_PATTERNS, prompt) and not matches(STALL_PATTERNS, prompt):
        was_raised = state["level"] > 1
        state["stalls"] = 0
        state["level"] = 1
        if was_raised:
            return "resolved", (
                "Problema resolvido depois de subir de nível. "
                "Volte ao padrão: /model opus e /effort medium."
            )
        return None, None

    if matches(NEW_TASK_PATTERNS, prompt):
        state["stalls"] = 0
        if state["since_compact"] > 5:
            return "new_task", "Assunto novo. Use /clear para não carregar o contexto antigo."
        return None, None

    if matches(STALL_PATTERNS, prompt):
        state["stalls"] += 1
        if state["stalls"] >= STALLS_TO_ESCALATE and state["level"] < 3:
            state["level"] = 3
            return "escalate", (
                f"{state['stalls']} falhas seguidas no mesmo problema, já no high. "
                "Use /escalate <problema> (Fable 5.1 só nesta tarefa) ou /model fable."
            )
        if state["stalls"] >= STALLS_TO_BOOST and state["level"] < 2:
            state["level"] = 2
            return "boost", (
                f"{state['stalls']} falhas seguidas no mesmo problema no medium. "
                "Num intervalo, use /effort high ou /boost <problema> só para este ponto."
            )
        return None, None

    if state["prompts"] == 1 and matches(MULTI_FILE_PATTERNS, prompt):
        return "plan", "Tarefa que mexe em vários arquivos: entre em plan mode (Shift+Tab) antes de editar."

    too_long = state["since_compact"] >= PROMPTS_TO_COMPACT or (
        transcript_mb(transcript_path) >= TRANSCRIPT_MB_TO_COMPACT and state["since_compact"] >= 10
    )
    if too_long and state["stalls"] == 0:
        state["since_compact"] = 0
        return "compact", (
            "Conversa longa. Num intervalo, use /compact com uma nota do que manter "
            "(objetivo, arquivos alterados, pendências)."
        )

    return None, None


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0

    prompt = data.get("prompt") or ""
    path = state_path(data.get("session_id", ""))
    state = load_state(path)

    key, hint = decide(state, prompt, data.get("transcript_path"))
    if key and key == state.get("last_hint") and key not in ("compact",):
        key, hint = None, None  # não repete a mesma dica
    if key:
        state["last_hint"] = key
    state["updated_at"] = int(time.time())

    try:
        path.write_text(json.dumps(state))
    except OSError:
        pass

    if not hint:
        return 0

    print(json.dumps({
        "systemMessage": f"💡 Token Pilot: {hint}",
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": (
                f"[Token Pilot] {hint} Confirme pelo histórico real da conversa antes de "
                "repetir a recomendação ao usuário (a detecção é heurística). "
                "Siga a skill token-pilot."
            ),
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # o hook nunca pode travar a sessão
        sys.exit(0)

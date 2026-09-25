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

# Frases que indicam as três etapas de uma tarefa grande.
PHASE_PATTERNS = [
    [r"\banalis", r"\bentend", r"\binvestig", r"\bmapea", r"\banaly[sz]", r"\bunderstand"],
    [r"\bbrainstorm", r"\bideias?\b", r"\bsugest", r"\bpropo(r|nha)", r"\bmelhorias\b", r"\bideas?\b"],
    [r"\bimplement", r"\badicion", r"\bcri(ar|e)\b", r"\bconstru", r"\bdesenvolv", r"\bbuild\b", r"\badd\b"],
]
BIG_PROMPT_CHARS = int(os.environ.get("TOKEN_PILOT_BIG_PROMPT_CHARS", "600"))

# Modelos por plano. Ajuste se o seu plano tiver outros modelos, ou use TOKEN_PILOT_MODELS.
ALL_MODELS = ["haiku", "sonnet", "opus", "fable"]
PLAN_MODELS = {
    "pro": ["haiku", "sonnet", "opus"],
    "max": ALL_MODELS,
    "team": ALL_MODELS,
    "enterprise": ALL_MODELS,
    "api": ALL_MODELS,
}
MODEL_NAMES = {"haiku": "Haiku", "sonnet": "Sonnet", "opus": "Opus 5.5", "fable": "Fable 5.1"}
# Modelo de cada agente e para onde ele vai quando esse modelo não existe no plano.
AGENT_MODELS = {
    "scout": "haiku", "log-reader": "haiku", "verifier": "haiku", "researcher": "sonnet",
    "ideator": "opus", "implementer": "opus", "implementer-high": "opus", "implementer-fable": "fable",
}
FALLBACKS = {"haiku": ["sonnet", "opus"], "sonnet": ["opus", "haiku"], "opus": ["sonnet"], "fable": []}


def base_dir():
    return Path(os.environ.get("TOKEN_PILOT_STATE_DIR", Path.home() / ".claude" / "token-pilot"))


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError, TypeError):
        return {}


def parse_models(value):
    items = value if isinstance(value, list) else str(value).split(",")
    found = []
    for item in items:
        for m in ALL_MODELS:  # aceita apelido ("opus") ou ID completo ("claude-opus-5-5")
            if m in str(item).lower() and m not in found:
                found.append(m)
    return found


def settings_allowlist():
    """availableModels das configurações do Claude Code, se alguém definiu."""
    project = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    files = [Path.home() / ".claude" / "settings.json",
             Path(project) / ".claude" / "settings.json",
             Path(project) / ".claude" / "settings.local.json"]
    allowed = None
    for f in files:
        value = read_json(f).get("availableModels")
        if value:
            allowed = parse_models(value)
    return allowed


def autodetect_plan():
    """Tentativa sem garantia: procura um campo de plano nos arquivos locais do Claude Code."""
    keys = {"subscriptiontype", "subscription_type", "plantype", "plan", "tier"}

    def walk(obj, depth=0):
        if isinstance(obj, dict) and depth < 4:
            for k, v in obj.items():
                if k.lower() in keys and isinstance(v, str):
                    for plan in PLAN_MODELS:
                        if plan in v.lower():
                            return plan
                found = walk(v, depth + 1)
                if found:
                    return found
        return None

    for f in (Path.home() / ".claude" / ".credentials.json", Path.home() / ".claude.json"):
        plan = walk(read_json(f))
        if plan:
            return plan
    return None


def resolve_models():
    """Devolve (modelos disponíveis, de onde veio a informação)."""
    config = read_json(base_dir() / "config.json")
    if os.environ.get("TOKEN_PILOT_MODELS"):
        models, source = parse_models(os.environ["TOKEN_PILOT_MODELS"]), "TOKEN_PILOT_MODELS"
    elif config.get("models"):
        models, source = parse_models(config["models"]), "config.json"
    elif os.environ.get("TOKEN_PILOT_PLAN", "").lower() in PLAN_MODELS:
        plan = os.environ["TOKEN_PILOT_PLAN"].lower()
        models, source = PLAN_MODELS[plan], f"plano {plan} (TOKEN_PILOT_PLAN)"
    elif str(config.get("plan", "")).lower() in PLAN_MODELS:
        plan = config["plan"].lower()
        models, source = PLAN_MODELS[plan], f"plano {plan} (config.json)"
    elif autodetect_plan():
        plan = autodetect_plan()
        models, source = PLAN_MODELS[plan], f"plano {plan} (detectado)"
    else:
        models, source = ALL_MODELS, "desconhecido"
    allowed = settings_allowlist()
    if allowed:
        models = [m for m in models if m in allowed]
        source += " + availableModels"
    return list(models), source


def model_for(agent, models):
    """Modelo que o agente deve usar neste plano, ou None se o nível não existe."""
    wanted = AGENT_MODELS[agent]
    if wanted in models:
        return wanted
    return next((m for m in FALLBACKS[wanted] if m in models), None)


def session_rules(models, source):
    names = ", ".join(MODEL_NAMES[m] for m in models) or "nenhum"
    has_fable = model_for("implementer-fable", models) is not None
    ladder = ("falhou 2x nele -> implementer-fable." if has_fable else
              "falhou 2x nele -> pare, resuma o que falhou e peça ajuda ao usuário (o plano não tem Fable; não use /escalate).")
    lines = [
        "[Token Pilot] Regras desta sessão (aplique sem esperar comando do usuário):",
        f"- Modelos do plano do usuário: {names} (fonte: {source}).",
        "- Busca/localização de código -> subagente scout. Logs/CI -> log-reader.",
        "  Rodar testes -> verifier. Entender um fluxo em vários arquivos -> researcher.",
        "- Tarefa grande (analisar + decidir + implementar, ou vários arquivos) -> siga a skill",
        "  big-task automaticamente: análise com scouts em paralelo, brainstorm no ideator,",
        "  execução no implementer, verificação no verifier.",
        "- Edição pontual (1-2 arquivos conhecidos) -> faça na sessão principal.",
        f"- Mesma parte falhou 2x -> delegue ao implementer-high; {ladder}",
        "  Resolveu -> a próxima parte volta ao implementer. Nunca peça ao usuário para trocar /model ou /effort.",
        "- Assunto novo sem relação -> sugira /clear. Conversa longa num intervalo -> sugira /compact com nota.",
    ]
    overrides = []
    for agent, wanted in AGENT_MODELS.items():
        got = model_for(agent, models)
        if got and got != wanted:
            overrides.append(f"{agent} -> model: \"{got}\"")
    if overrides:
        lines.append("- Modelos fora do plano: ao chamar estes agentes, passe o parâmetro model: "
                     + "; ".join(overrides) + ".")
    lines.append("- Se um subagente falhar porque o modelo não está disponível, trate esse modelo como "
                 "indisponível pelo resto da sessão e passe model com o substituto (Haiku -> Sonnet, "
                 "Sonnet -> Opus, Opus -> Sonnet). Se for o Fable, encerre a escada e peça ajuda ao usuário.")
    return "\n".join(lines)

# O que o Claude deve fazer para cada dica (o usuário vê só a dica curta).
ACTIONS = {
    "big_task": "Siga a skill big-task agora para esta tarefa, sem esperar /big-task.",
    "boost": "Delegue a próxima tentativa ao subagente implementer-high, passando o que já falhou.",
    "escalate": "Delegue a próxima tentativa ao subagente implementer-fable, passando o que já falhou.",
    "stuck": "Não delegue a outro nível: pare, resuma as tentativas e o que falhou, e peça ajuda ao usuário.",
}


def is_big_task(prompt):
    if matches(MULTI_FILE_PATTERNS, prompt):
        return True
    phases = sum(1 for group in PHASE_PATTERNS if matches(group, prompt))
    return phases >= 2 or (len(prompt) >= BIG_PROMPT_CHARS and phases >= 1)


def matches(patterns, text):
    return any(re.search(p, text, re.IGNORECASE | re.MULTILINE) for p in patterns)


def state_path(session_id):
    base = base_dir()
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


def decide(state, prompt, transcript_path, models=ALL_MODELS):
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
                "Problema resolvido depois de subir de nível. As próximas partes voltam ao "
                "implementer (Opus 5.5, medium). Se você trocou o modelo à mão, use /model opus e /effort medium."
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
            if model_for("implementer-fable", models) is None:
                return "stuck", (
                    f"{state['stalls']} falhas seguidas no mesmo problema, já no high. Seu plano não "
                    "tem Fable, então o Claude vai parar, resumir o que falhou e pedir sua ajuda."
                )
            return "escalate", (
                f"{state['stalls']} falhas seguidas no mesmo problema, já no high. "
                "A próxima tentativa vai para o subagente implementer-fable "
                f"({MODEL_NAMES[model_for('implementer-fable', models)]}), com o histórico das falhas."
            )
        if state["stalls"] >= STALLS_TO_BOOST and state["level"] < 2:
            state["level"] = 2
            high = model_for("implementer-high", models) or "opus"
            return "boost", (
                f"{state['stalls']} falhas seguidas no mesmo problema no medium. "
                f"A próxima tentativa vai para o subagente implementer-high ({MODEL_NAMES[high]}, high), "
                "com o histórico das falhas."
            )
        return None, None

    if is_big_task(prompt) and state["prompts"] - state.get("big_task_at", -99) > 5:
        state["big_task_at"] = state["prompts"]
        return "big_task", (
            "Tarefa grande detectada. O Claude vai dividir em análise (Haiku/Sonnet), "
            "brainstorm (Opus high) e execução (Opus medium, subindo se travar)."
        )

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

    models, source = resolve_models()

    if data.get("hook_event_name") == "SessionStart":
        out = {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                      "additionalContext": session_rules(models, source)}}
        notice = base_dir() / ".plan-notice"
        if source.startswith("desconhecido") and not notice.exists():
            out["systemMessage"] = ("💡 Token Pilot: não sei qual é o seu plano. Rode "
                                    "`python3 .claude/hooks/token_pilot.py --plan pro` (ou max, team, "
                                    "enterprise, api) para usar só os modelos que você tem.")
            try:
                base_dir().mkdir(parents=True, exist_ok=True)
                notice.touch()
            except OSError:
                pass
        print(json.dumps(out, ensure_ascii=False))
        return 0

    prompt = data.get("prompt") or ""
    path = state_path(data.get("session_id", ""))
    state = load_state(path)

    key, hint = decide(state, prompt, data.get("transcript_path"), models)
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
                f"[Token Pilot] {' '.join(filter(None, [hint, ACTIONS.get(key)]))} A detecção é heurística: "
                "confira pelo histórico real da conversa antes de agir."
            ),
        },
    }, ensure_ascii=False))
    return 0


def cli(args):
    """python3 token_pilot.py --plan pro | --models haiku,sonnet,opus | --show"""
    path = base_dir() / "config.json"
    config = read_json(path)
    if args[0] == "--plan" and len(args) > 1 and args[1].lower() in PLAN_MODELS:
        config = {"plan": args[1].lower()}
    elif args[0] == "--models" and len(args) > 1 and parse_models(args[1]):
        config = {"models": parse_models(args[1])}
    elif args[0] != "--show":
        print("Uso: token_pilot.py --plan <" + "|".join(PLAN_MODELS) + "> | --models haiku,sonnet,opus | --show")
        return 2
    if args[0] != "--show":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config))
    models, source = resolve_models()
    print(f"Modelos: {', '.join(MODEL_NAMES[m] for m in models)} (fonte: {source})")
    fable = model_for("implementer-fable", models)
    print("Escada: implementer -> implementer-high" + (" -> implementer-fable" if fable else " (sem Fable: para e pede ajuda)"))
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(cli(sys.argv[1:]))
    try:
        sys.exit(main())
    except Exception:  # o hook nunca pode travar a sessão
        sys.exit(0)

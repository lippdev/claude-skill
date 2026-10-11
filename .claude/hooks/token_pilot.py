#!/usr/bin/env python3
"""Token Pilot hook: faz a sessão principal coordenar e delegar o trabalho a subagentes
(Haiku 5.5, Sonnet 5.5 e Opus 5.5), sem mexer no modelo nem no effort da sessão principal.

Registrado em SessionStart, UserPromptSubmit e SubagentStart. Lê o JSON do hook pela entrada padrão, atualiza um
estado por sessão e, quando algo muda, devolve um lembrete para o Claude
(additionalContext) e um aviso curto para o usuário (systemMessage).

Nunca bloqueia o prompt: qualquer erro sai com código 0 e sem saída.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Limiares ajustáveis por variável de ambiente.
STALLS_TO_BOOST = int(os.environ.get("TOKEN_PILOT_STALLS_TO_BOOST", "2"))
STALLS_TO_STOP = int(os.environ.get("TOKEN_PILOT_STALLS_TO_STOP", "4"))
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


def base_dir():
    return Path(os.environ.get("TOKEN_PILOT_STATE_DIR", Path.home() / ".claude" / "token-pilot"))


def session_rules():
    """Núcleo curto de regras para toda sessão. O resto (disciplina de edição, mapa do código,
    instruções da tarefa) entra pelo UserPromptSubmit só quando a tarefa pede."""
    return "\n".join([
        "[Token Pilot] Regras (aplique sem esperar comando):",
        "- Você coordena e não edita código: divida a tarefa em partes por área (ex.: tela, API,",
        "  banco, testes) e mande cada parte ao subagente certo, em paralelo quando não tocarem os",
        "  mesmos arquivos. Passe a cada um só a parte dele e junte os resultados.",
        "- Implementar ou corrigir -> implementer (Opus 5.5). Mudança mecânica -> quick-edit (Haiku 5.5).",
        "  Buscar -> scout. Log longo -> log-reader. Testes -> verifier (Haiku 5.5). Entender um fluxo",
        "  -> researcher (Sonnet 5.5). Decidir entre caminhos -> ideator (Opus 5.5, high).",
        "- Tarefa grande -> skill big-task. Parte falhou 2x no implementer -> implementer-high;",
        "  2x nele -> pare, resuma e peça ajuda.",
        "- Não troque nem peça para trocar o /model ou o /effort desta sessão.",
        "- Haiku 5.5 recusou ou voltou vazio -> refaça com model: \"sonnet\". Como plugin, os agentes",
        "  têm prefixo (token-pilot:scout).",
    ])

# ---------------------------------------------------------------- disciplina e mapa

HOOK_DIR = Path(__file__).resolve().parent
# Agentes que só leem recebem a disciplina curta; os demais, a de edição.
READ_ONLY_AGENTS = {"scout", "log-reader", "verifier", "researcher", "ideator", "explore", "plan", "quick-edit"}
# Agentes que recebem o mapa do código (os que leem ou editam código, não logs).
MAP_AGENTS = {"scout", "researcher", "ideator", "implementer", "implementer-high",
              "general-purpose", "explore", "plan"}
MAP_BUDGET = int(os.environ.get("TOKEN_PILOT_MAP_CHARS", "2000"))
MAP_SECONDS = 2.0
MAP_MAX_FILES = 600
SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", "out", "target", "__pycache__",
             ".venv", "venv", ".next", ".token-pilot", ".claude", "coverage", "migrations"}
SYMBOL_PATTERNS = {
    ".py": r"^(?:async\s+)?def\s+(\w+)|^class\s+(\w+)",
    ".js": r"^export\s+(?:default\s+)?(?:async\s+)?(?:function\*?|class|const|let)\s+(\w+)|^(?:async\s+)?function\s+(\w+)",
    ".go": r"^func\s+(?:\([^)]*\)\s*)?(\w+)|^type\s+(\w+)",
    ".rb": r"^\s*(?:class|module)\s+(\w+)|^\s{0,2}def\s+(?:self\.)?(\w+)",
    ".rs": r"^pub(?:\(crate\))?\s+(?:async\s+)?(?:fn|struct|enum|trait)\s+(\w+)",
    ".java": r"^\s*(?:public\s+)?(?:abstract\s+|final\s+)?(?:class|interface|enum|record)\s+(\w+)",
    ".php": r"^\s*(?:final\s+|abstract\s+)?(?:class|interface|trait)\s+(\w+)|^function\s+(\w+)",
}
for ext in (".ts", ".tsx", ".jsx", ".mjs", ".cjs"):
    SYMBOL_PATTERNS[ext] = SYMBOL_PATTERNS[".js"]
for ext in (".kt", ".cs", ".swift"):
    SYMBOL_PATTERNS[ext] = r"^\s*(?:public\s+|internal\s+|open\s+|final\s+)*(?:class|interface|struct|enum|object|protocol)\s+(\w+)"


def discipline(section):
    """Texto da disciplina de resposta ("coordenação", "edição" ou "leitura"), lido de disciplina.md."""
    try:
        text = (HOOK_DIR / "disciplina.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(rf"^## {section}\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


def project_files(root):
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True,
                             timeout=MAP_SECONDS)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        pass
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        files += [os.path.relpath(os.path.join(dirpath, f), root) for f in filenames]
        if len(files) > MAP_MAX_FILES * 3:
            break
    return files


def is_test_or_generated(path):
    parts = path.replace("\\", "/").split("/")
    name = parts[-1]
    return (any(p in SKIP_DIRS or p in ("test", "tests", "__tests__", "spec") for p in parts[:-1])
            or name.startswith("test_") or re.search(r"(_test|\.test|\.spec|\.min)\.\w+$", name) is not None)


def code_map(root, budget=MAP_BUDGET):
    """Mapa curto do código: funções, classes e exports por arquivo, agrupados por pasta.
    Sem modelo, com teto de caracteres e de tempo. Devolve "" se não houver nada útil."""
    if budget <= 0 or os.environ.get("TOKEN_PILOT_MAP") == "0":
        return ""
    start = time.time()
    by_dir = {}
    scanned = 0
    for rel in project_files(root):
        if time.time() - start > MAP_SECONDS or scanned >= MAP_MAX_FILES:
            break
        ext = os.path.splitext(rel)[1]
        if ext not in SYMBOL_PATTERNS or is_test_or_generated(rel):
            continue
        scanned += 1
        try:
            with open(os.path.join(root, rel), encoding="utf-8", errors="ignore") as f:
                text = f.read(200_000)
        except OSError:
            continue
        names = []
        for m in re.finditer(SYMBOL_PATTERNS[ext], text, re.M):
            name = next((g for g in m.groups() if g), None)
            if name and not name.startswith("_") and name not in names:
                names.append(name)
        if names:
            folder, base = os.path.split(rel)
            by_dir.setdefault(folder or ".", []).append(f"{base}({', '.join(names[:8])}{', …' if len(names) > 8 else ''})")
    if not by_dir:
        return ""
    header = ("[Token Pilot] Mapa do código (o que já existe; reutilize e abra um arquivo só quando "
              "precisar dos detalhes):")
    lines, used = [header], len(header)
    folders = sorted(by_dir, key=lambda d: (d.count("/"), d))
    for i, folder in enumerate(folders):
        line = f"{folder}/: " + "; ".join(by_dir[folder])
        if used + len(line) + 1 > budget:
            lines.append(f"… e mais {len(folders) - i} pasta(s); use grep.")
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


def project_root(data):
    return data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def subagent_context(agent_type, root):
    kind = (agent_type or "").split(":")[-1].lower()
    parts = [discipline("leitura" if kind in READ_ONLY_AGENTS else "edição")]
    if kind in MAP_AGENTS:
        parts.append(code_map(root))
    return "\n\n".join(p for p in parts if p)


# O que o Claude deve fazer para cada dica (o usuário vê só a dica curta).
ACTIONS = {
    "big_task": "Siga a skill big-task agora para esta tarefa, sem esperar /big-task.",
    "boost": "Delegue a próxima tentativa ao subagente implementer-high, passando o que já falhou.",
    "stuck": "Não delegue a outro nível: pare, resuma as tentativas e o que falhou, e peça ajuda ao usuário.",
}


# Pedidos mecânicos: dá para fazer sem decidir lógica.
MECHANICAL_PATTERNS = [
    r"\brenome(ia|ar|ie)\b", r"\brename\b",
    r"\btroc(a|ar|ue)\b.{1,60}\bpor\b", r"\bsubstitu(i|ir|a)\b", r"\breplace\b",
    r"\btypo\b", r"\berro de (digitação|ortografia)\b", r"\bortografia\b",
    r"\b(atualiz|mud|alter)\w* (o |a |os |as )?(texto|mensagem|label|string|constante|url|link|vers[aã]o|t[ií]tulo|nome)\b",
    r"\b(adicion|remov|tir)\w* (o |os |um |uns )?(imports?|coment[aá]rios?|prints?|console\.logs?|logs? de debug)\b",
    r"\b(formata|indenta|reformat)\w*\b", r"\bmov(e|er|a) .{1,60}\bpara\b",
]
SHORT_PROMPT_CHARS = int(os.environ.get("TOKEN_PILOT_SHORT_PROMPT_CHARS", "160"))
# Pedido curto, mas que pede para construir ou medir algo: não é tarefa curta.
BUILD_PATTERNS = [
    r"\b(implement|constru|desenvolv|mont[ae]|cri[ae]r?\b|refator|migr|integr|med[ei]r?\b|benchmark)",
    r"\b(implement|build|create|refactor|migrat|integrat|measure|benchmark)",
]

QUICK_CONTEXT = ("[Token Pilot] Tarefa mecânica: delegue ao subagente quick-edit (Haiku 5.5) com a instrução "
                 "exata, sem ler os arquivos antes. Ele já confere o resultado e separa falhas que já existiam: se "
                 "devolver OK, não verifique de novo e responda em 1 linha. Se devolver PRECISA_OPUS ou FALHOU, "
                 "mande ao implementer.")
SHORT_CONTEXT = ("[Token Pilot] Tarefa curta: sem plano e sem resumo. Pergunta: responda direto em até 3 linhas. "
                 "Mudança de código: mande ao implementer (Opus 5.5) com a instrução exata e responda em 1 linha.")


def task_kind(prompt):
    """Classe do pedido: "grande", "mecanica", "curta" ou "media"."""
    text = prompt.strip()
    if is_big_task(text):
        return "grande"
    if len(text) <= 300 and matches(MECHANICAL_PATTERNS, text):
        return "mecanica"
    if len(text) <= SHORT_PROMPT_CHARS and not matches(BUILD_PATTERNS, text):
        return "curta"
    return "media"


def is_big_task(prompt):
    if matches(MULTI_FILE_PATTERNS, prompt):
        return True
    phases = sum(1 for group in PHASE_PATTERNS if matches(group, prompt))
    return phases >= 2 or (len(prompt) >= BIG_PROMPT_CHARS and phases >= 1)


# Texto colado (saída de terminal, logs, tabelas, código) não é o pedido do usuário: o tamanho e
# as palavras dele não contam como tarefa grande nem como falha repetida.
PASTED_BLOCKS = [
    r"<pasted_content[^>]*>.*?</pasted_content[^>]*>",
    r"```.*?(```|\Z)",
]
PASTED_LINE = re.compile(r"^\s*([│┃┌┐└┘├┤┬┴┼─━╭╮╰╯|>]|\$ |❯|⎿|Traceback|File \"|at \S+\(|\d{4}-\d\d-\d\d[T ]\d\d:)")


def user_text(prompt):
    """A parte do prompt que o usuário digitou, sem blocos colados, tabelas ou logs."""
    for block in PASTED_BLOCKS:
        prompt = re.sub(block, " ", prompt, flags=re.DOTALL)
    return "\n".join(line for line in prompt.splitlines() if not PASTED_LINE.match(line)).strip()


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
                "Problema resolvido depois de subir de nível. As próximas partes voltam para o "
                "implementer (Opus 5.5, medium)."
            )
        return None, None

    if matches(NEW_TASK_PATTERNS, prompt):
        state["stalls"] = 0
        if state["since_compact"] >= 3:
            return "new_task", "Assunto novo. Use /clear para não carregar o contexto antigo."
        return None, None

    if matches(STALL_PATTERNS, prompt):
        state["stalls"] += 1
        if state["stalls"] >= STALLS_TO_STOP and state["level"] < 3:
            state["level"] = 3
            return "stuck", (
                f"{state['stalls']} falhas seguidas no mesmo problema, já no high. O Claude vai parar, "
                "resumir o que falhou e pedir sua ajuda."
            )
        if state["stalls"] >= STALLS_TO_BOOST and state["level"] < 2:
            state["level"] = 2
            return "boost", (
                f"{state['stalls']} falhas seguidas no mesmo problema. A próxima tentativa vai para o "
                "subagente implementer-high (Opus 5.5, high), com o histórico das falhas."
            )
        return None, None

    if is_big_task(prompt) and state["prompts"] - state.get("big_task_at", -99) > 5:
        state["big_task_at"] = state["prompts"]
        return "big_task", (
            "Tarefa grande detectada. O Claude vai dividir por área e delegar: análise no Haiku 5.5 e "
            "Sonnet 5.5, decisão no Opus 5.5 high e cada parte no implementer (Opus 5.5)."
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

    event = data.get("hook_event_name")
    if event == "SubagentStart":
        context = subagent_context(data.get("agent_type") or data.get("subagent_type"), project_root(data))
        if context:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "SubagentStart",
                                                     "additionalContext": context}}, ensure_ascii=False))
        return 0

    if event == "SessionStart":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                 "additionalContext": session_rules()}}, ensure_ascii=False))
        return 0

    prompt = user_text(data.get("prompt") or "")  # comandos /... não são removidos
    path = state_path(data.get("session_id", ""))
    state = load_state(path)

    key, hint = decide(state, prompt, data.get("transcript_path"))
    if key and key == state.get("last_hint") and key not in ("compact",):
        key, hint = None, None  # não repete a mesma dica
    if key:
        state["last_hint"] = key
    state["updated_at"] = int(time.time())

    extra = task_context(state, prompt, key, project_root(data))
    try:
        path.write_text(json.dumps(state))
    except OSError:
        pass

    if not hint and not extra:
        return 0
    parts = []
    if hint:
        parts.append(f"[Token Pilot] {' '.join(filter(None, [hint, ACTIONS.get(key)]))} A detecção é "
                     "heurística: confira pelo histórico real da conversa antes de agir.")
    parts += extra
    out = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "\n\n".join(parts)}}
    if hint:
        out["systemMessage"] = f"💡 Token Pilot: {hint}"
    print(json.dumps(out, ensure_ascii=False))
    return 0


def task_context(state, prompt, key, root):
    """Contexto silencioso conforme o tamanho da tarefa. Disciplina da coordenadora e mapa do código
    entram uma vez por sessão, só quando a tarefa é média ou grande."""
    if (key in ("boost", "stuck", "resolved") or prompt.strip().startswith("/")
            or matches(STALL_PATTERNS, prompt) or matches(RESOLVED_PATTERNS, prompt)):
        return []
    kind = task_kind(prompt)
    if kind == "mecanica":
        return [QUICK_CONTEXT]
    if kind == "curta":
        return [SHORT_CONTEXT]
    if state.get("work_context_sent"):
        return []
    state["work_context_sent"] = True
    return [p for p in (discipline("coordenação"), code_map(root)) if p]


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # o hook nunca pode travar a sessão
        sys.exit(0)

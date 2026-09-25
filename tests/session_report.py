#!/usr/bin/env python3
"""Relatório das sessões do Claude Code num projeto: quais agentes rodaram, em qual
modelo e effort, quantos tokens cada um gastou e o que o hook do Token Pilot avisou.

Lê os registros locais do Claude Code (~/.claude/projects/<projeto>/). Não mostra o
conteúdo das ferramentas nem das respostas; dos seus pedidos, só os primeiros caracteres.

Uso:
    python3 tests/session_report.py                 # sessões do diretório atual
    python3 tests/session_report.py --dir ~/estoque # outro projeto
    python3 tests/session_report.py --last 3        # só as 3 sessões mais recentes
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

AGENT_DIRS = [Path(".claude/agents"), Path.home() / ".claude" / "agents"]
PROMPT_CHARS = 90


def project_log_dir(project):
    base = Path.home() / ".claude" / "projects"
    encoded = re.sub(r"[^A-Za-z0-9]", "-", str(Path(project).resolve()))
    candidate = base / encoded
    if candidate.is_dir():
        return candidate
    # Fallback: nome de pasta que termina com o nome do projeto.
    matches = sorted((d for d in base.glob(f"*{Path(project).resolve().name}") if d.is_dir()),
                     key=lambda d: d.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def read_jsonl(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return rows


def expected_agents(project):
    """Modelo e effort esperados de cada agente, lidos dos arquivos .md."""
    out = {}
    for d in [Path(project) / p if not p.is_absolute() else p for p in AGENT_DIRS]:
        for f in d.glob("*.md"):
            m = re.match(r"^---\n(.*?)\n---", f.read_text(encoding="utf-8"), re.S)
            if not m:
                continue
            fm = dict(line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)
            name = fm.get("name", f.stem).strip()
            out.setdefault(name, (fm.get("model", "").strip(), fm.get("effort", "").strip()))
    return out


def ts(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def short_model(model):
    for name in ("haiku", "sonnet", "opus", "fable"):
        if name in (model or ""):
            return name
    return model or "?"


def add_usage(bucket, usage):
    for key, field in (("in", "input_tokens"), ("out", "output_tokens"),
                       ("cache_w", "cache_creation_input_tokens"), ("cache_r", "cache_read_input_tokens")):
        bucket[key] += usage.get(field) or 0


def summarize(rows):
    """Modelos, effort, tokens, duração e erros de um registro (sessão ou subagente)."""
    usage = defaultdict(lambda: defaultdict(int))
    efforts, times, errors, tools = set(), [], 0, 0
    for d in rows:
        t = ts(d.get("timestamp"))
        if t:
            times.append(t)
        msg = d.get("message") if isinstance(d.get("message"), dict) else {}
        if d.get("type") == "assistant" and msg.get("model") and msg.get("model") != "<synthetic>":
            if msg.get("usage"):
                add_usage(usage[short_model(msg["model"])], msg["usage"])
            efforts.add(str(d.get("perTurnEffort") or d.get("effort") or "—"))
            tools += sum(1 for c in msg.get("content") or [] if isinstance(c, dict) and c.get("type") == "tool_use")
        if d.get("type") == "user" and isinstance(msg.get("content"), list):
            errors += sum(1 for c in msg["content"] if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("is_error"))
    duration = (max(times) - min(times)).total_seconds() if len(times) > 1 else 0
    return usage, efforts, duration, errors, tools, (min(times) if times else None)


def fmt_tokens(bucket):
    return (f"in {bucket['in']:,} · out {bucket['out']:,} · cache escrita {bucket['cache_w']:,} "
            f"· cache leitura {bucket['cache_r']:,}").replace(",", ".")


def user_prompts(rows):
    out = []
    for d in rows:
        if d.get("type") != "user" or d.get("isMeta") or d.get("isSidechain"):
            continue
        content = (d.get("message") or {}).get("content")
        if isinstance(content, list):
            texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
            content = " ".join(texts) if texts and not any(
                isinstance(c, dict) and c.get("type") == "tool_result" for c in d["message"]["content"]) else None
        if isinstance(content, str) and content.strip() and not content.startswith("<"):
            text = " ".join(content.split())
            out.append(text[:PROMPT_CHARS] + ("…" if len(text) > PROMPT_CHARS else ""))
    return out


def hook_messages(rows):
    out = []
    for d in rows:
        a = d.get("attachment") if isinstance(d.get("attachment"), dict) else {}
        if a.get("type") == "hook_system_message":
            text = a.get("content") or a.get("message") or ""
            out.append(" ".join(str(text).split())[:160])
        elif a.get("type") == "hook_additional_context":
            content = a.get("content") or ""
            raw = " ".join(map(str, content)) if isinstance(content, list) else str(content)
            text = " ".join(raw.split())
            if "Token Pilot" in text and "Regras desta sessão" not in text:
                out.append("(para o Claude) " + text[:160])
    return out


def report_session(session_file, expected):
    rows = read_jsonl(session_file)
    usage, efforts, duration, errors, tools, start = summarize(rows)
    lines = [f"## Sessão {session_file.stem[:8]} · {start:%d/%m %H:%M} UTC · {duration / 60:.1f} min"
             if start else f"## Sessão {session_file.stem[:8]}"]
    prompts = user_prompts(rows)
    lines.append("\n**Seus pedidos:**")
    lines += [f"{i}. {p}" for i, p in enumerate(prompts, 1)] or ["(nenhum)"]
    hooks = hook_messages(rows)
    lines.append("\n**Avisos do Token Pilot:**")
    lines += [f"- {h}" for h in hooks] or ["- (nenhum)"]

    lines.append("\n**Sessão principal:** " + ", ".join(
        f"{m} ({fmt_tokens(b)})" for m, b in usage.items()) + f" · effort {', '.join(sorted(efforts)) or '—'}"
        + f" · {tools} ferramentas · {errors} erros")

    totals = defaultdict(lambda: defaultdict(int))
    for m, b in usage.items():
        for k, v in b.items():
            totals[m][k] += v

    sub_dir = session_file.with_suffix("") / "subagents"
    agents = []
    for f in sorted(sub_dir.glob("agent-*.jsonl")) if sub_dir.is_dir() else []:
        meta = {}
        try:
            meta = json.loads(f.with_name(f.stem + ".meta.json").read_text())
        except (OSError, ValueError):
            pass
        u, eff, dur, err, tl, st = summarize(read_jsonl(f))
        agents.append((st, meta, u, eff, dur, err, tl))
        for m, b in u.items():
            for k, v in b.items():
                totals[m][k] += v
    agents.sort(key=lambda a: a[0].timestamp() if a[0] else 0)

    lines.append(f"\n**Subagentes ({len(agents)}):**")
    if agents:
        lines.append("| # | Agente | Tarefa | Modelo real | Esperado | Effort | Tokens (in/out/cache r) | Tempo | Erros |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
    for i, (st, meta, u, eff, dur, err, tl) in enumerate(agents, 1):
        kind = meta.get("agentType", "?")
        exp_model, exp_eff = expected.get(kind, ("", ""))
        exp_model = meta.get("model") or exp_model
        real = ", ".join(u) or "—"
        ok = "" if not exp_model or exp_model == "inherit" or short_model(exp_model) in u else " ⚠️"
        tok = " + ".join(f"{b['in']:,}/{b['out']:,}/{b['cache_r']:,}".replace(",", ".") for b in u.values()) or "—"
        exp = f"{short_model(exp_model)}/{exp_eff or '—'}" if exp_model else "—"
        lines.append(f"| {i} | {kind} | {(meta.get('description') or '')[:40]} | {real}{ok} | {exp} "
                     f"| {', '.join(sorted(eff)) or '—'} | {tok} | {dur:.0f}s | {err} |")

    lines.append("\n**Total por modelo (sessão + subagentes):**")
    lines += [f"- {m}: {fmt_tokens(b)}" for m, b in sorted(totals.items())]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=".", help="pasta do projeto (padrão: a atual)")
    ap.add_argument("--last", type=int, default=10, help="quantas sessões recentes mostrar (padrão: 10)")
    args = ap.parse_args()

    log_dir = project_log_dir(args.dir)
    if not log_dir:
        print(f"Não achei registros do Claude Code para {Path(args.dir).resolve()} em ~/.claude/projects/")
        return 1
    sessions = sorted(log_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime)[-args.last:]
    expected = expected_agents(args.dir)
    print(f"# Relatório Token Pilot · {Path(args.dir).resolve().name} · {len(sessions)} sessão(ões)\n")
    for s in sessions:
        print(report_session(s, expected))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

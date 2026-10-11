#!/usr/bin/env python3
"""Benchmark real: Opus 5.5 medium (uso normal) x Token Pilot, no Claude Code sem interface.

Cada rodada copia o projeto de exemplo para uma pasta temporária limpa, roda uma tarefa com
`claude -p ... --output-format stream-json` e, no fim, executa a verificação da tarefa. Os
braços usam o mesmo modelo na sessão principal; o Token Pilot coordena em effort low e
delega o trabalho aos subagentes do pacote.

Braços:
  opus-medium   uso normal: sessão única no Opus 5.5 medium, sem o pacote
  token-pilot   Opus 5.5 low coordenando, com a pasta .claude/ do pacote (--pilot-effort)
  ponytail      opcional: sem o pacote, com o plugin do ponytail (--ponytail <pasta>)

Custa tokens de verdade. Use --dry-run para ver os comandos e --fake para testar o
pipeline sem chamar o modelo.

Uso:
    python3 bench/run.py run --runs 3                    # roda tudo
    python3 bench/run.py run --tasks corrigir-testes --runs 1 --max-budget 2
    python3 bench/run.py compare bench/results/<arquivo>.jsonl
"""

import argparse
import json
import math
import os
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TASKS = REPO / "bench" / "tasks.json"
PROJECT = REPO / "examples" / "estoque"
RESULTS = REPO / "bench" / "results"

def package_version():
    """Commit do pacote usado na rodada (com "+" se havia mudanças não salvas), para separar
    resultados de versões diferentes."""
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True,
                             text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", ".claude"], cwd=REPO, capture_output=True,
                               text=True).stdout.strip()
        return sha + ("+" if dirty else "")
    except OSError:
        return "?"


PACKAGE_VERSION = package_version()

ALLOWED_TOOLS = ["Read", "Edit", "Write", "Glob", "Grep", "Agent", "Skill", "TodoWrite",
                 "Bash(python3 *)", "Bash(git *)", "Bash(grep *)", "Bash(ls *)", "Bash(cat *)",
                 "Bash(head *)", "Bash(tail *)", "Bash(wc *)", "Bash(find *)"]


def prepare(workdir, arm, project=PROJECT):
    shutil.copytree(project, workdir, ignore=shutil.ignore_patterns("__pycache__", ".token-pilot"))
    if arm == "token-pilot":
        shutil.copytree(REPO / ".claude", workdir / ".claude",
                        ignore=shutil.ignore_patterns("__pycache__", "settings.local.json"))
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=bench@local", "-c", "user.name=bench", "commit", "-qm", "inicial"]):
        subprocess.run(cmd, cwd=workdir, check=True)


def arm_effort(args, arm):
    """Effort da sessão principal: o Token Pilot só coordena, então roda mais baixo."""
    return args.pilot_effort if arm == "token-pilot" else args.effort


def claude_cmd(prompt, args, arm):
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose", "--model", args.model,
           "--effort", arm_effort(args, arm), "--permission-mode", "acceptEdits",
           "--setting-sources", "project,local", "--max-budget-usd", str(args.max_budget),
           "--allowedTools", *ALLOWED_TOOLS]
    if arm == "ponytail":
        cmd += ["--plugin-dir", str(Path(args.ponytail).resolve())]
    return cmd


def fake_result(arm, task):
    """Resultado simulado para testar o pipeline sem gastar tokens."""
    base = {"simples": 0.2, "grande": 1.3, "log": 0.7}.get(task["kind"], 1.0)
    factor = {"opus-medium": 1.0, "token-pilot": 0.7, "ponytail": 0.75}[arm]
    cost = base * factor * random.uniform(0.85, 1.15)
    return {"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": cost,
            "duration_ms": int(cost * 250_000), "num_turns": int(cost * 20) + 3,
            "modelUsage": {"claude-opus-5-5": {"costUSD": cost * 0.9, "outputTokens": int(cost * 20_000),
                                               "inputTokens": 2_000, "cacheReadInputTokens": int(cost * 400_000),
                                               "cacheCreationInputTokens": 25_000},
                           "claude-haiku-5-5": {"costUSD": cost * 0.1, "outputTokens": 3_000,
                                                "inputTokens": 500, "cacheReadInputTokens": 20_000,
                                                "cacheCreationInputTokens": 8_000}}}


def suite_status(workdir):
    """Quantos testes rodaram e quantos falharam (falhas + erros) na suíte visível do projeto."""
    proc = subprocess.run(["python3", "-m", "unittest", "-q"], cwd=workdir, capture_output=True, text=True,
                          timeout=120)
    text = proc.stderr + proc.stdout
    ran = next((int(w) for line in text.splitlines() if line.startswith("Ran ") for w in line.split()[1:2]), 0)
    bad = sum(int(part.split("=")[1]) for line in text.splitlines() if line.startswith("FAILED")
              for part in line.strip("FAILED ()").split(", ") if "=" in part and not part.startswith("skipped"))
    return {"ran": ran, "failed": bad}


def model_usage(data):
    """Custo e tokens por modelo, no formato do `modelUsage` do Claude Code."""
    return {m: {"cost": u.get("costUSD"), "out": u.get("outputTokens"), "in": u.get("inputTokens"),
                "cache_read": u.get("cacheReadInputTokens"), "cache_write": u.get("cacheCreationInputTokens")}
            for m, u in (data.get("modelUsage") or {}).items()}


def token_totals(models):
    """Tokens somados entre os modelos: todos (entrada, cache e saída) e só a saída."""
    total = sum((u.get(k) or 0) for u in models.values() for k in ("in", "out", "cache_read", "cache_write"))
    out = sum((u.get("out") or 0) for u in models.values())
    return (total or None), (out or None)


WRITE_LOCK = threading.Lock()


def parse_stream(stdout):
    """Evento final ("result") da saída stream-json; os demais eventos são o transcrito."""
    for line in reversed(stdout.splitlines()):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "result":
            return event
    raise ValueError("sem evento result")


def run_one(task, arm, args, out, transcripts=None):
    with tempfile.TemporaryDirectory(prefix=f"bench-{arm}-") as tmp:
        workdir = Path(tmp) / "projeto"
        prepare(workdir, arm, REPO / task.get("project", "examples/estoque"))
        before = suite_status(workdir)
        env = dict(os.environ, TOKEN_PILOT_STATE_DIR=str(Path(tmp) / "estado"))
        cmd = claude_cmd(task["prompt"], args, arm)
        if args.dry_run:
            print(f"[{arm}] {task['id']}: (cd {workdir} && " + " ".join(json.dumps(c) for c in cmd) + ")")
            return
        start = time.time()
        if args.fake:
            data, error = fake_result(arm, task), None
        else:
            proc = subprocess.run(cmd, cwd=workdir, env=env, capture_output=True, text=True,
                                  timeout=args.timeout)
            if transcripts:
                with WRITE_LOCK:
                    transcripts.mkdir(parents=True, exist_ok=True)
                    n = len(list(transcripts.glob(f"{task['id']}-{arm}-*.jsonl"))) + 1
                    (transcripts / f"{task['id']}-{arm}-{n}.jsonl").write_text(proc.stdout, encoding="utf-8")
            try:
                data, error = parse_stream(proc.stdout), None
            except ValueError:
                data, error = {}, (proc.stderr or proc.stdout)[-500:]
        wall = time.time() - start
        if task.get("hidden"):  # testes ocultos entram só agora, depois do trabalho
            shutil.copytree(REPO / "bench" / "ocultos" / task["hidden"], workdir / "_ocultos", dirs_exist_ok=True)
            (workdir / "_ocultos" / "__init__.py").touch()
        check = subprocess.run(["bash", "-c", task["check"]], cwd=workdir, capture_output=True,
                               text=True, timeout=120)
        quality = {name: subprocess.run(["bash", "-c", cmd], cwd=workdir, capture_output=True,
                                        timeout=120).returncode == 0
                   for name, cmd in task.get("quality", {}).items()}
        shutil.rmtree(workdir / "_ocultos", ignore_errors=True)
        after = suite_status(workdir)
        quality["sem_regressao"] = after["failed"] <= before["failed"]
        subprocess.run(["git", "add", "-A", "--", ".", ":!.claude", ":!.token-pilot"], cwd=workdir,
                       capture_output=True)
        diff = subprocess.run(["git", "diff", "--cached", "--shortstat"], cwd=workdir, capture_output=True,
                              text=True)
        models = model_usage(data)
        tokens, tokens_out = token_totals(models)
        row = {
            "task": task["id"], "kind": task["kind"], "tier": task.get("tier"), "arm": arm,
            "tokens": tokens, "tokens_out": tokens_out, "quality": quality,
            "suite_before": before, "suite_after": after,
            "cost": data.get("total_cost_usd"), "duration_s": (data.get("duration_ms") or 0) / 1000 or wall,
            "turns": data.get("num_turns"), "subtype": data.get("subtype"), "is_error": data.get("is_error"),
            "passed": check.returncode == 0, "diff": diff.stdout.strip(),
            "models": models, "error": error, "fake": bool(args.fake), "version": PACKAGE_VERSION,
            "effort": arm_effort(args, arm),
        }
        status = "ok" if row["passed"] else "FALHOU"
        cost = f"${row['cost']:.3f}" if row["cost"] is not None else "sem custo"
        bad = [k for k, v in quality.items() if not v]
        with WRITE_LOCK:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            print(f"[{arm}] {task['id']}: {cost}, {tokens or 0:,} tokens, {row['duration_s']:.0f}s, "
                  f"{row['turns']} turnos, verificação {status}" + (f", qualidade falhou: {bad}" if bad else ""),
                  flush=True)


def cmd_run(args):
    tasks = json.load(open(TASKS, encoding="utf-8"))
    if args.tasks:
        wanted = set(args.tasks.split(","))
        tasks = [t for t in tasks if t["id"] in wanted]
    if args.tiers:
        wanted = set(args.tiers.split(","))
        tasks = [t for t in tasks if t.get("tier") in wanted]
    arms = ["opus-medium", "token-pilot"] + (["ponytail"] if args.ponytail else [])
    if args.arms:
        arms = [a for a in args.arms.split(",") if a in arms]
    if not args.dry_run and not args.fake and shutil.which("claude") is None:
        print("Não achei o comando `claude` no PATH.")
        return 1
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}{'-fake' if args.fake else ''}.jsonl"
    # Intercala os braços para que mudanças de carga no servidor afetem os dois por igual.
    jobs = [(t, arm) for _ in range(args.runs) for t in tasks for arm in arms]
    # Transcritos completos ficam fora do git (são grandes); servem para ver onde os turnos foram.
    transcripts = path.with_suffix("") if args.transcripts else None
    with open(os.devnull if args.dry_run else path, "w", encoding="utf-8") as out, ThreadPoolExecutor(max(1, args.jobs)) as pool:
        for future in [pool.submit(run_one, task, arm, args, out, transcripts) for task, arm in jobs]:
            future.result()
    if not args.dry_run:
        print(f"\nResultados em {path.relative_to(REPO)}\n")
        compare(path)
    return 0


def geomean(values):
    values = [v for v in values if v and v > 0]
    return math.exp(sum(math.log(v) for v in values) / len(values)) if values else None


def median_or_none(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


TIERS = ("pequena", "media", "pesada")
METRICS = (("cost", "Custo"), ("tokens", "Tokens"), ("tokens_out", "Tokens de saída"), ("time", "Tempo"),
           ("turns", "Turnos"))


def quality_score(row):
    """Fração das conferências que passaram: a verificação principal e as de qualidade da tarefa."""
    checks = [row["passed"], *(row.get("quality") or {}).values()]
    return sum(checks) / len(checks)


def compare(*paths):
    """Resume os resultados. Custo, tokens, tempo e turnos usam só rodadas que passaram na verificação
    e têm custo conhecido: um braço que não terminou o trabalho não pode parecer mais barato."""
    rows = [json.loads(line) for path in paths for line in open(path, encoding="utf-8") if line.strip()]
    tier_of = {t["id"]: t.get("tier") for t in json.load(open(TASKS, encoding="utf-8"))}
    for r in rows:
        r["tier"] = r.get("tier") or tier_of.get(r["task"]) or "?"
        if r.get("tokens") is None:
            r["tokens"], r["tokens_out"] = token_totals(r.get("models") or {})
    path = Path(paths[-1])
    versions = sorted({r.get("version", "?") for r in rows if r["arm"] != "opus-medium"})
    if len(versions) > 1:
        print(f"Atenção: rodadas de versões diferentes do pacote ({', '.join(versions)}). "
              "Compare uma versão por vez para medir uma mudança.\n")
    arms = sorted({r["arm"] for r in rows}, key=lambda a: (a != "opus-medium", a))
    tasks = sorted({r["task"] for r in rows}, key=lambda t: (TIERS.index(tier_of[t]) if tier_of.get(t) in TIERS
                                                              else 9, t))
    med = {}
    for t in tasks:
        for a in arms:
            rs = [r for r in rows if r["task"] == t and r["arm"] == a]
            if not rs:
                continue
            ok = [r for r in rs if r["passed"] and r.get("cost") is not None]
            med[t, a] = {
                "cost": median_or_none([r["cost"] for r in ok]),
                "tokens": median_or_none([r.get("tokens") for r in ok]),
                "tokens_out": median_or_none([r.get("tokens_out") for r in ok]),
                "time": median_or_none([r["duration_s"] for r in ok]),
                "turns": median_or_none([r["turns"] for r in ok]),
                "pass": sum(r["passed"] for r in rs) / len(rs),
                "quality": statistics.mean(quality_score(r) for r in rs),
                "n": len(rs), "n_ok": len(ok), "no_cost": sum(r.get("cost") is None for r in rs),
                "tier": rs[0]["tier"],
            }
    fake = any(r.get("fake") for r in rows)
    money = lambda v: f"${v:.3f}" if v is not None else "—"
    num = lambda v, unit="": f"{v:,.0f}{unit}".replace(",", ".") if v is not None else "—"
    pct = lambda v: f"{(v - 1) * 100:+.0f}%" if v else "—"
    print(f"# Benchmark real{' (SIMULADO, --fake)' if fake else ''}: {path.name}\n")
    print("Custo, tokens, tempo e turnos: mediana só das rodadas que passaram na verificação e têm custo "
          "conhecido. Qualidade: média, entre todas as rodadas, da fração de conferências que passaram "
          "(verificação, testes ocultos, sem regressão na suíte e as regras da tarefa).\n")
    print("| Tamanho | Tarefa | Braço | Custo | Tokens | Tokens de saída | Tempo | Turnos | Acerto | Qualidade "
          "| Rodadas usadas / total |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for t in tasks:
        for a in arms:
            m = med.get((t, a))
            if m:
                note = f" ({m['no_cost']} sem custo)" if m["no_cost"] else ""
                print(f"| {m['tier']} | {t} | {a} | {money(m['cost'])} | {num(m['tokens'])} | "
                      f"{num(m['tokens_out'])} | {num(m['time'], 's')} | {num(m['turns'])} | {m['pass']:.0%} | "
                      f"{m['quality']:.0%} | {m['n_ok']} / {m['n']}{note} |")

    def summary(selected, a):
        comparable = [t for t in selected if (t, a) in med and (t, "opus-medium") in med
                      and med[t, a]["n_ok"] and med[t, "opus-medium"]["n_ok"]]
        both = [t for t in selected if (t, a) in med and (t, "opus-medium") in med]
        ratios = {k: geomean([med[t, a][k] / med[t, "opus-medium"][k] for t in comparable
                              if med[t, a][k] and med[t, "opus-medium"][k]]) for k, _ in METRICS}
        mean = lambda arm, k: statistics.mean(med[t, arm][k] for t in both) if both else 0
        return (ratios, mean(a, "pass"), mean("opus-medium", "pass"), mean(a, "quality"),
                mean("opus-medium", "quality"), len(comparable), len(both))

    print("\n| Tamanho | Braço x opus-medium | " + " | ".join(n for _, n in METRICS)
          + " | Acerto | Qualidade | Tarefas comparadas |")
    print("|---|---|" + "---|" * len(METRICS) + "---|---|---|")
    groups = [(tier, [t for t in tasks if med.get((t, "opus-medium"), {}).get("tier") == tier]) for tier in TIERS]
    groups = [g for g in groups if g[1]] + [("**todas**", tasks)]
    for tier, selected in groups:
        for a in arms[1:]:
            ratios, p, bp, q, bq, nc, nb = summary(selected, a)
            print(f"| {tier} | {a} | " + " | ".join(pct(ratios[k]) for k, _ in METRICS)
                  + f" | {p:.0%} (base {bp:.0%}) | {q:.0%} (base {bq:.0%}) | {nc} de {nb} |")
    print("\nRazões: média geométrica, entre as tarefas em que os dois braços têm rodadas aprovadas, da "
          "mediana do braço dividida pela mediana do opus-medium. Negativo é economia. Tarefas sem rodada "
          "aprovada num dos braços ficam de fora da razão e aparecem em \"Acerto\".")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="roda as tarefas nos braços")
    r.add_argument("--runs", type=int, default=3, help="rodadas por tarefa e braço (padrão 3)")
    r.add_argument("--tasks", help="ids separados por vírgula (padrão: todas)")
    r.add_argument("--model", default="opus")
    r.add_argument("--effort", default="medium", help="effort do opus-medium e do ponytail (padrão medium)")
    r.add_argument("--pilot-effort", default="low",
                   help="effort da sessão principal no braço token-pilot (padrão low)")
    r.add_argument("--arms", help="braços separados por vírgula (padrão: todos)")
    r.add_argument("--tiers", help="tamanhos separados por vírgula: pequena, media, pesada (padrão: todos)")
    r.add_argument("--jobs", type=int, default=1, help="sessões em paralelo (padrão 1)")
    r.add_argument("--ponytail", help="pasta do plugin ponytail, para incluir o terceiro braço")
    r.add_argument("--max-budget", type=float, default=3.0, help="teto em US$ por rodada (padrão 3)")
    r.add_argument("--timeout", type=int, default=1800, help="segundos por rodada (padrão 1800)")
    r.add_argument("--dry-run", action="store_true", help="só mostra os comandos")
    r.add_argument("--transcripts", action="store_true",
                   help="salva o transcrito de cada sessão em bench/results/<rodada>/")
    r.add_argument("--fake", action="store_true", help="simula as respostas, sem chamar o modelo")
    c = sub.add_parser("compare", help="resume um arquivo de resultados")
    c.add_argument("paths", nargs="+", help="um ou mais arquivos .jsonl")
    args = ap.parse_args()
    if args.cmd == "compare":
        compare(*[Path(p) for p in args.paths])
        return 0
    return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())

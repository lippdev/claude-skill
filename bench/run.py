#!/usr/bin/env python3
"""Benchmark real: Opus 5.5 medium (uso normal) x Token Pilot, no Claude Code sem interface.

Cada rodada copia o projeto de exemplo para uma pasta temporária limpa, roda uma tarefa com
`claude -p ... --output-format json` e, no fim, executa a verificação da tarefa. Os dois
braços usam o mesmo modelo e o mesmo effort na sessão principal; a única diferença é a
pasta `.claude/` do Token Pilot.

Braços:
  opus-medium   sessão única no Opus 5.5 medium, sem o pacote
  token-pilot   a mesma sessão com a pasta .claude/ do pacote
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
import time
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


def claude_cmd(prompt, args, arm):
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose", "--model", args.model,
           "--effort", args.effort, "--permission-mode", "acceptEdits",
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
            "modelUsage": {"claude-opus-5-5": {"costUSD": cost * 0.9, "outputTokens": int(cost * 20_000)},
                           "claude-haiku-5-5": {"costUSD": cost * 0.1, "outputTokens": 3_000}}}


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
        env = dict(os.environ, TOKEN_PILOT_STATE_DIR=str(Path(tmp) / "estado"))
        if args.plan:
            env["TOKEN_PILOT_PLAN"] = args.plan
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
        diff = subprocess.run(["git", "diff", "--shortstat"], cwd=workdir, capture_output=True, text=True)
        row = {
            "task": task["id"], "kind": task["kind"], "arm": arm,
            "cost": data.get("total_cost_usd"), "duration_s": (data.get("duration_ms") or 0) / 1000 or wall,
            "turns": data.get("num_turns"), "subtype": data.get("subtype"), "is_error": data.get("is_error"),
            "passed": check.returncode == 0, "diff": diff.stdout.strip(),
            "models": {m: {"cost": u.get("costUSD"), "out": u.get("outputTokens")}
                       for m, u in (data.get("modelUsage") or {}).items()},
            "error": error, "fake": bool(args.fake), "version": PACKAGE_VERSION,
        }
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
        out.flush()
        status = "ok" if row["passed"] else "FALHOU"
        cost = f"${row['cost']:.3f}" if row["cost"] is not None else "sem custo"
        print(f"[{arm}] {task['id']}: {cost}, {row['duration_s']:.0f}s, {row['turns']} turnos, verificação {status}")


def cmd_run(args):
    tasks = json.load(open(TASKS, encoding="utf-8"))
    if args.tasks:
        wanted = set(args.tasks.split(","))
        tasks = [t for t in tasks if t["id"] in wanted]
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
    with open(path, "w", encoding="utf-8") as out:
        for task, arm in jobs:
            run_one(task, arm, args, out, transcripts)
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


def compare(*paths):
    """Resume os resultados. Custo, tempo e turnos usam só rodadas que passaram na verificação
    e têm custo conhecido: um braço que não terminou o trabalho não pode parecer mais barato."""
    rows = [json.loads(line) for path in paths for line in open(path, encoding="utf-8") if line.strip()]
    path = Path(paths[-1])
    versions = sorted({r.get("version", "?") for r in rows if r["arm"] != "opus-medium"})
    if len(versions) > 1:
        print(f"Atenção: rodadas de versões diferentes do pacote ({', '.join(versions)}). "
              "Compare uma versão por vez para medir uma mudança.\n")
    arms = sorted({r["arm"] for r in rows}, key=lambda a: (a != "opus-medium", a))
    tasks = sorted({r["task"] for r in rows})
    med = {}
    for t in tasks:
        for a in arms:
            rs = [r for r in rows if r["task"] == t and r["arm"] == a]
            if not rs:
                continue
            ok = [r for r in rs if r["passed"] and r.get("cost") is not None]
            med[t, a] = {
                "cost": median_or_none([r["cost"] for r in ok]),
                "time": median_or_none([r["duration_s"] for r in ok]),
                "turns": median_or_none([r["turns"] for r in ok]),
                "pass": sum(r["passed"] for r in rs) / len(rs), "n": len(rs), "n_ok": len(ok),
                "no_cost": sum(r.get("cost") is None for r in rs),
            }
    fake = any(r.get("fake") for r in rows)
    money = lambda v: f"${v:.3f}" if v is not None else "—"
    num = lambda v, unit="": f"{v:.0f}{unit}" if v is not None else "—"
    print(f"# Benchmark real{' (SIMULADO, --fake)' if fake else ''}: {path.name}\n")
    print("Custo, tempo e turnos: mediana só das rodadas que passaram na verificação e têm custo conhecido.\n")
    print("| Tarefa | Braço | Custo | Tempo | Turnos | Verificação passou | Rodadas usadas / total |")
    print("|---|---|---|---|---|---|---|")
    for t in tasks:
        for a in arms:
            m = med.get((t, a))
            if m:
                note = f" ({m['no_cost']} sem custo)" if m["no_cost"] else ""
                print(f"| {t} | {a} | {money(m['cost'])} | {num(m['time'], 's')} | {num(m['turns'])} | "
                      f"{m['pass']:.0%} | {m['n_ok']} / {m['n']}{note} |")
    print("\n| Braço x opus-medium | Custo | Tempo | Turnos | Verificação passou | Tarefas comparadas |")
    print("|---|---|---|---|---|---|")
    for a in arms[1:]:
        comparable = [t for t in tasks if (t, a) in med and (t, "opus-medium") in med
                      and med[t, a]["n_ok"] and med[t, "opus-medium"]["n_ok"]]
        ratios = {k: geomean([med[t, a][k] / med[t, "opus-medium"][k] for t in comparable
                              if med[t, "opus-medium"][k]]) for k in ("cost", "time", "turns")}
        both = [t for t in tasks if (t, a) in med and (t, "opus-medium") in med]
        passed = statistics.mean([med[t, a]["pass"] for t in both]) if both else 0
        base_pass = statistics.mean([med[t, "opus-medium"]["pass"] for t in both]) if both else 0
        fmt = lambda v: f"{(v - 1) * 100:+.0f}%" if v else "—"
        print(f"| {a} | {fmt(ratios['cost'])} | {fmt(ratios['time'])} | {fmt(ratios['turns'])} | "
              f"{passed:.0%} (base {base_pass:.0%}) | {len(comparable)} de {len(both)} |")
    print("\nRazões: média geométrica, entre as tarefas em que os dois braços têm rodadas aprovadas, da "
          "mediana do braço dividida pela mediana do opus-medium. Tarefas sem rodada aprovada num dos "
          "braços ficam de fora da razão e aparecem em \"Verificação passou\".")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="roda as tarefas nos braços")
    r.add_argument("--runs", type=int, default=3, help="rodadas por tarefa e braço (padrão 3)")
    r.add_argument("--tasks", help="ids separados por vírgula (padrão: todas)")
    r.add_argument("--model", default="opus")
    r.add_argument("--effort", default="medium")
    r.add_argument("--arms", help="braços separados por vírgula (padrão: todos)")
    r.add_argument("--plan", help="plano para o Token Pilot (pro, max, team, enterprise, api)")
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

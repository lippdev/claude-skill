#!/usr/bin/env python3
"""Valida os arquivos do pacote sem chamar nenhum modelo (zero tokens)."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / ".claude"
MODELS = {"haiku", "sonnet", "opus", "fable", "inherit"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}

# Modelo e effort esperados de cada agente: a política do pacote.
EXPECTED_AGENTS = {
    "scout": ("haiku", "low"),
    "log-reader": ("haiku", "low"),
    "verifier": ("haiku", "low"),
    "researcher": ("sonnet", "medium"),
    "ideator": ("opus", "high"),
    "implementer": ("opus", "medium"),
    "implementer-high": ("opus", "high"),
    "implementer-fable": ("fable", "high"),
}
READ_ONLY = {"scout", "log-reader", "verifier", "researcher", "ideator"}
EXPECTED_SKILLS = {"token-pilot", "big-task", "boost", "escalate"}

errors = []


def frontmatter(path):
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        errors.append(f"{path}: sem frontmatter")
        return {}, ""
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip().strip('"')
    return fields, m.group(2)


def check(cond, msg):
    if not cond:
        errors.append(msg)


# Agentes
found = {}
for path in sorted((ROOT / "agents").glob("*.md")):
    fm, body = frontmatter(path)
    name = fm.get("name")
    found[name] = fm
    check(name == path.stem, f"{path.name}: name '{name}' difere do arquivo")
    check(fm.get("description"), f"{path.name}: sem description")
    check(fm.get("model") in MODELS, f"{path.name}: model inválido '{fm.get('model')}'")
    check(fm.get("effort") in EFFORTS, f"{path.name}: effort inválido '{fm.get('effort')}'")
    check(body.strip(), f"{path.name}: corpo vazio")
    if name in READ_ONLY:
        tools = fm.get("tools", "")
        check(tools and "Edit" not in tools and "Write" not in tools,
              f"{path.name}: agente somente leitura não pode ter Edit/Write")

for name, (model, effort) in EXPECTED_AGENTS.items():
    fm = found.get(name)
    check(fm is not None, f"agente faltando: {name}")
    if fm:
        check((fm.get("model"), fm.get("effort")) == (model, effort),
              f"{name}: esperado {model}/{effort}, veio {fm.get('model')}/{fm.get('effort')}")

# Skills
skills = {}
for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
    fm, body = frontmatter(path)
    skills[fm.get("name")] = (fm, body, path)
    check(fm.get("name") == path.parent.name, f"{path}: name difere da pasta")
    check(fm.get("description"), f"{path}: sem description")
    if "model" in fm:
        check(fm["model"] in MODELS, f"{path}: model inválido")
    if "effort" in fm:
        check(fm["effort"] in EFFORTS, f"{path}: effort inválido")
    for link in re.findall(r"\]\(([^)#]+\.md)\)", body):
        check((path.parent / link).exists(), f"{path}: link quebrado {link}")

check(EXPECTED_SKILLS <= set(skills), f"skills faltando: {EXPECTED_SKILLS - set(skills)}")

# Todo agente citado na big-task precisa existir.
if "big-task" in skills:
    body = skills["big-task"][1]
    cited = set(re.findall(r"`((?:scout|log-reader|verifier|researcher|ideator|implementer(?:-high|-fable)?))`", body))
    check(cited == set(EXPECTED_AGENTS), f"big-task cita {sorted(cited)}, esperado {sorted(EXPECTED_AGENTS)}")

# Hook registrado e existente.
settings = (ROOT / "settings.json").read_text()
check("token_pilot.py" in settings, "settings.json não registra o hook")
check((ROOT / "hooks" / "token_pilot.py").exists(), "hook token_pilot.py não existe")

if errors:
    print("FALHOU:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print(f"OK: {len(found)} agentes, {len(skills)} skills, hook registrado.")

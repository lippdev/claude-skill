#!/usr/bin/env python3
"""Estimativa: Opus 5.5 com effort medium, do jeito normal, x Token Pilot delegando a subagentes.

- **Opus 5.5 medium (uso normal):** uma sessão só, no Opus 5.5 com effort medium, que lê,
  pensa, edita e testa tudo sozinha. Ninguém troca /model nem /effort.
- **Token Pilot:** a sessão principal (Opus 5.5 medium) delega a leitura (scout e log-reader
  no Haiku 5.5, researcher no Sonnet 5.5), o brainstorm (ideator, Opus 5.5 high) e a
  verificação (verifier, Haiku 5.5), e edita ela mesma, com contexto pequeno. Se travar,
  sobe para o implementer-high (Opus 5.5 high). Todos seguem a disciplina de resposta.

Não é medição. É um modelo turno a turno com premissas explícitas (todas abaixo), para
comparar os dois jeitos de trabalhar e para recalcular quando houver dados reais do
tests/session_report.py.

Como o custo é calculado: a cada turno de um agente, o contexto inteiro é relido do cache
(cache read); o que entrou de novo desde o turno anterior é gravado no cache (cache write,
1,25x o preço de entrada); a resposta, incluindo o raciocínio, é cobrada como saída. Cada
subagente começa um contexto novo e paga a gravação dele.

Uso:
    python3 tests/benchmark_estimate.py            # tabelas em Markdown
    python3 tests/benchmark_estimate.py --json     # dados para gráficos
"""

import argparse
import json

# Preços por milhão de tokens (API da Anthropic, tabela de 06/10/2026).
# Escrita no cache = 1,25x a entrada (TTL de 5 min). Haiku 5.5 vale até 100 mil tokens de
# pedido; os agentes do pacote são instruídos a ficar abaixo disso.
PRICES = {
    "haiku":  {"in": 0.10, "out": 0.50,  "cw": 0.125, "cr": 0.01},
    "sonnet": {"in": 2.00, "out": 10.00, "cw": 2.50,  "cr": 0.20},
    "opus":   {"in": 4.00, "out": 20.00, "cw": 5.00,  "cr": 0.20},
    "fable":  {"in": 10.0, "out": 50.00, "cw": 12.50, "cr": 0.25},
}
# O tokenizador do Haiku 5.5 conta o mesmo texto como ~30% mais tokens.
TOKENIZER = {"haiku": 1.3, "sonnet": 1.0, "opus": 1.0, "fable": 1.0}
# Velocidade de saída (tokens/s) e espera até o primeiro token (s). Premissas aproximadas.
SPEED = {"haiku": 250, "sonnet": 120, "opus": 70, "fable": 45}
TTFT = {"haiku": 0.8, "sonnet": 1.5, "opus": 2.5, "fable": 4.0}
TOOL_SECONDS = 1.5  # execução média de uma ferramenta (ler arquivo, rodar teste)

# Três cenários de premissas. "esperado" é o central; os outros dão a faixa.
# "pessimista" é o menos favorável ao Token Pilot.
ASSUMPTIONS = {
    "pessimista": {"main_base": 18_000, "sub_base": 12_000, "read_scale": 0.6,
                   "medium_attempts": 3, "out_factor": 0.65},
    "esperado":   {"main_base": 20_000, "sub_base": 9_000,  "read_scale": 1.0,
                   "medium_attempts": 4, "out_factor": 0.55},
    "otimista":   {"main_base": 22_000, "sub_base": 7_000,  "read_scale": 1.4,
                   "medium_attempts": 5, "out_factor": 0.46},
}
# main_base: prompt de sistema + ferramentas + CLAUDE.md da sessão principal.
# sub_base:  o mesmo para cada subagente (menor que o da sessão principal).
# read_scale: quanto código/log a tarefa exige ler (1.0 = projeto médio).
# out_factor: saída do Opus com a disciplina de resposta, em relação ao uso normal. Vem do
#   intervalo medido pelo ponytail no Opus 5.5 (-45% de saída, IC 95% de -35% a -54%;
#   benchmarks/results/2026-10-07-agentic.md). A redução de turnos medida lá (-22%) não
#   entra no modelo, para não exagerar.
# medium_attempts: tentativas que o Opus 5.5 medium leva, sozinho, para resolver um bug
#   difícil que o effort high resolve na primeira (o Token Pilot sobe para o high na 3ª).
TOKEN_PILOT_OVERHEAD = 2_500   # regras, disciplina e mapa do hook + descrições das skills e agentes
SUB_OVERHEAD = 400             # disciplina e mapa injetados em cada subagente
BIG_TASK_SKILL = 3_000         # corpo da skill big-task, carregado quando ela roda

PHASES = ["análise", "brainstorm", "execução", "verificação", "coordenação"]


class Run:
    """Um agente (sessão principal ou subagente) rodando turno a turno."""

    def __init__(self, model, base, phase="coordenação", out_factor=1.0):
        self.model = model
        self.out_factor = out_factor if model in ("opus", "fable") else 1.0
        self.phase = phase
        k = TOKENIZER[model]
        self.ctx = base * k
        self.pending_write = base * k  # o primeiro turno grava a base inteira no cache
        self.cost = 0.0
        self.seconds = 0.0
        self.by_phase = {}
        self.tokens = {"cr": 0.0, "cw": 0.0, "out": 0.0}

    def turn(self, out, result=0, tool=True):
        k, p = TOKENIZER[self.model], PRICES[self.model]
        out_t, res_t = out * k * self.out_factor, result * k
        read = self.ctx - self.pending_write
        cost = (read * p["cr"] + self.pending_write * p["cw"] + out_t * p["out"]) / 1e6
        self.cost += cost
        self.by_phase[self.phase] = self.by_phase.get(self.phase, 0) + cost
        self.tokens["cr"] += read
        self.tokens["cw"] += self.pending_write
        self.tokens["out"] += out_t
        self.seconds += TTFT[self.model] + out_t / SPEED[self.model] + (TOOL_SECONDS if tool else 0)
        self.ctx += out_t + res_t
        self.pending_write = out_t + res_t
        return self

    def turns(self, n, out, result=0):
        for _ in range(n):
            self.turn(out, result)
        return self

    def at(self, phase):
        self.phase = phase
        return self


def total(runs, parallel_groups=()):
    """Soma custo; o tempo de grupos paralelos conta só o mais lento de cada grupo."""
    cost = sum(r.cost for r in runs)
    seconds = sum(r.seconds for r in runs)
    for group in parallel_groups:
        seconds -= sum(r.seconds for r in group) - max(r.seconds for r in group)
    by_model, by_phase = {}, {}
    for r in runs:
        by_model[r.model] = by_model.get(r.model, 0) + r.cost
        for ph, c in r.by_phase.items():
            by_phase[ph] = by_phase.get(ph, 0) + c
    return {"cost": cost, "seconds": seconds, "by_model": by_model, "by_phase": by_phase}


# ---------------------------------------------------------------- cenários

def simple_task(a, pilot):
    """Pedido simples: renomear uma função e atualizar os usos (2-3 arquivos).
    Com o Token Pilot, a edição pontual fica na sessão principal e só paga o contexto extra.
    A disciplina de resposta não reduz nada aqui: as respostas de uma renomeação já são
    mínimas (confirmado na rodada real de bench/run.py)."""
    main = Run("opus", a["main_base"] + (TOKEN_PILOT_OVERHEAD if pilot else 0), "execução")
    main.turns(5, out=300, result=1_500)
    main.turn(250, tool=False)
    return total([main])


def big_task(a, pilot):
    """Analisar o projeto, corrigir 3 testes, propor alertas e implementar o recomendado."""
    s = a["read_scale"]
    if not pilot:
        main = Run("opus", a["main_base"], "análise")
        main.turns(14, out=400, result=3_500 * s)    # lê arquivos e faz greps
        main.at("brainstorm").turn(2_500, result=100, tool=False)
        main.at("execução").turns(12, out=900, result=1_500)   # 3 partes x 4 turnos
        main.at("verificação").turns(2, out=300, result=3_000)  # suíte inteira
        main.at("coordenação").turn(700, tool=False)            # resumo final
        return total([main])

    f, sub = a["out_factor"], a["sub_base"] + SUB_OVERHEAD
    main = Run("opus", a["main_base"] + TOKEN_PILOT_OVERHEAD + BIG_TASK_SKILL, "análise", f)
    main.turn(800)                                    # escreve o brief
    main.turn(600, result=3 * 700)                    # dispara 3 scouts, recebe resumos
    main.turn(300, result=900)                        # researcher
    main.turn(900)                                    # atualiza o brief
    main.at("brainstorm").turn(300, result=1_200)     # ideator
    main.turn(700, result=100, tool=False)            # mostra opções, recebe a escolha
    main.at("execução").turns(12, out=900, result=1_500)  # edita na própria sessão
    main.at("verificação").turns(2, out=200, result=400)  # 2 verifiers
    main.at("coordenação").turn(700, tool=False)       # resumo final

    reading = 14 * 3_500 * s * 1.3                   # leitura total, com 30% de sobreposição
    scouts = [Run("haiku", sub, "análise").turns(6, out=250, result=reading / 3 / 6) for _ in range(3)]
    researcher = Run("sonnet", sub, "análise").turns(5, out=500, result=3_000 * s)
    ideator = Run("opus", sub + 3_000, "brainstorm", f).turns(2, out=3_500, result=1_500)
    verifiers = [Run("haiku", sub, "verificação").turns(2, out=150, result=2_000) for _ in range(2)]
    runs = [main, *scouts, researcher, ideator, *verifiers]
    return total(runs, parallel_groups=[scouts])


def log_task(a, pilot):
    """Entender por que um job quebrou num log de CI de ~40 mil tokens, e seguir trabalhando
    mais 10 turnos na mesma sessão (o log continua no contexto se foi lido na sessão)."""
    log = 40_000 * a["read_scale"]
    main = Run("opus", a["main_base"] + (TOKEN_PILOT_OVERHEAD if pilot else 0), "análise",
               a["out_factor"] if pilot else 1.0)
    runs = [main]
    if not pilot:
        main.turn(300, result=log)                    # lê o log inteiro
        main.turns(2, out=600, result=1_000)
    else:
        main.turn(300, result=450)                    # recebe o resumo do log-reader
        main.turns(2, out=600, result=1_000)
        runs.append(Run("haiku", a["sub_base"] + SUB_OVERHEAD, "análise").turns(4, out=200, result=2_500))
    main.at("execução").turns(10, out=500, result=1_500)  # trabalho seguinte na mesma sessão
    return total(runs)


def stuck_task(a, pilot):
    """Bug difícil numa sessão que já vinha trabalhando (+40 mil tokens de contexto).
    Uso normal: o Opus 5.5 medium tenta sozinho até resolver, com você avisando a cada falha.
    Token Pilot: 2 tentativas na sessão principal, depois o implementer-high resolve."""
    if not pilot:
        main = Run("opus", a["main_base"] + 40_000, "execução")
        for i in range(a["medium_attempts"]):
            main.turns(5, out=900, result=1_500)      # uma tentativa
            if i < a["medium_attempts"] - 1:
                main.turn(400, result=300)            # você diz que ainda falha
        return total([main])
    f = a["out_factor"]
    main = Run("opus", a["main_base"] + 40_000 + TOKEN_PILOT_OVERHEAD, "execução", f)
    main.turns(5, out=900, result=1_500)              # 1ª tentativa na sessão principal
    main.turn(400, result=300)                        # ainda falha
    main.turns(5, out=900, result=1_500)              # 2ª tentativa
    main.turn(400, result=800)                        # delega ao implementer-high
    main.at("coordenação").turn(300, tool=False)
    high = Run("opus", a["sub_base"] + SUB_OVERHEAD + 3_500, "execução", f).turns(5, out=2_200, result=1_500)
    return total([main, high])


SCENARIOS = [
    ("simples", "Pedido simples (renomear uma função)", simple_task),
    ("grande", "Tarefa grande (analisar, corrigir, propor e implementar)", big_task),
    ("log", "Log de CI longo + 10 turnos de trabalho seguinte", log_task),
    ("trava", "Bug difícil que o medium demora a resolver", stuck_task),
]
# Mix de um dia de trabalho, em número de ocorrências de cada cenário.
DAY_MIX = {"simples": 8, "grande": 2, "log": 2, "trava": 1}


def compute():
    out = {}
    for name, a in ASSUMPTIONS.items():
        rows = {}
        for key, _, fn in SCENARIOS:
            rows[key] = {"base": fn(a, False), "pilot": fn(a, True)}
        day = {side: sum(rows[k][side]["cost"] * n for k, n in DAY_MIX.items()) for side in ("base", "pilot")}
        day_s = {side: sum(rows[k][side]["seconds"] * n for k, n in DAY_MIX.items()) for side in ("base", "pilot")}
        out[name] = {"rows": rows, "day": day, "day_seconds": day_s}
    return out


def pct(new, old):
    return (new - old) / old * 100


def markdown(data):
    lines = ["# Estimativa: Opus 5.5 medium (uso normal) x Token Pilot (delegando a subagentes)", "",
             "Custo em dólares equivalentes à API (em planos Pro/Max, o mesmo consumo pesa no limite de uso). "
             "Tempo é o de espera do usuário, sem contar quanto ele demora para responder.", ""]
    esp = data["esperado"]
    lines += ["## Cenário esperado", "",
              "| Situação | Opus 5.5 medium | Token Pilot | Custo | Tempo |",
              "|---|---|---|---|---|"]
    for key, label, _ in SCENARIOS:
        b, p = esp["rows"][key]["base"], esp["rows"][key]["pilot"]
        lines.append(f"| {label} | ${b['cost']:.3f} · {b['seconds'] / 60:.1f} min | "
                     f"${p['cost']:.3f} · {p['seconds'] / 60:.1f} min | "
                     f"{pct(p['cost'], b['cost']):+.0f}% | {pct(p['seconds'], b['seconds']):+.0f}% |")
    d, ds = esp["day"], esp["day_seconds"]
    lines.append(f"| **Dia típico** ({', '.join(f'{n}x {k}' for k, n in DAY_MIX.items())}) | "
                 f"${d['base']:.2f} · {ds['base'] / 60:.0f} min | ${d['pilot']:.2f} · {ds['pilot'] / 60:.0f} min | "
                 f"{pct(d['pilot'], d['base']):+.0f}% | {pct(ds['pilot'], ds['base']):+.0f}% |")

    g = esp["rows"]["grande"]
    lines += ["", "## Tarefa grande: custo por função (cenário esperado)", "",
              "| Função | Opus 5.5 medium | Token Pilot | Quem faz no Token Pilot |", "|---|---|---|---|"]
    who = {"análise": "3 scouts (Haiku 5.5) + researcher (Sonnet 5.5)", "brainstorm": "ideator (Opus 5.5, high)",
           "execução": "sessão principal, com a disciplina de resposta", "verificação": "2 verifiers (Haiku 5.5)",
           "coordenação": "sessão principal (resumo final)"}
    for ph in PHASES:
        b, p = g["base"]["by_phase"].get(ph, 0), g["pilot"]["by_phase"].get(ph, 0)
        lines.append(f"| {ph.capitalize()} | ${b:.3f} | ${p:.3f} | {who[ph]} |")

    lines += ["", "## Faixa (pessimista · esperado · otimista para o Token Pilot)", "",
              "| Situação | Variação de custo | Variação de tempo |", "|---|---|---|"]
    for key, label, _ in SCENARIOS:
        c = [pct(data[n]["rows"][key]["pilot"]["cost"], data[n]["rows"][key]["base"]["cost"]) for n in ASSUMPTIONS]
        t = [pct(data[n]["rows"][key]["pilot"]["seconds"], data[n]["rows"][key]["base"]["seconds"]) for n in ASSUMPTIONS]
        lines.append(f"| {label} | {' · '.join(f'{v:+.0f}%' for v in c)} | {' · '.join(f'{v:+.0f}%' for v in t)} |")
    c = [pct(data[n]["day"]["pilot"], data[n]["day"]["base"]) for n in ASSUMPTIONS]
    t = [pct(data[n]["day_seconds"]["pilot"], data[n]["day_seconds"]["base"]) for n in ASSUMPTIONS]
    lines.append(f"| Dia típico | {' · '.join(f'{v:+.0f}%' for v in c)} | {' · '.join(f'{v:+.0f}%' for v in t)} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    data = compute()
    print(json.dumps(data, indent=2, ensure_ascii=False) if args.json else markdown(data))


if __name__ == "__main__":
    main()

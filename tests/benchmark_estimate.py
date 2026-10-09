#!/usr/bin/env python3
"""Estimativa de custo e tempo: Claude Code puro (tudo no Opus 5.5) x Token Pilot.

Não é medição. É um modelo turno a turno com premissas explícitas (todas abaixo), para
comparar os dois jeitos de trabalhar e para recalcular quando houver dados reais do
tests/session_report.py.

Como o custo é calculado: a cada turno de um agente, o contexto inteiro é relido do cache
(cache read); o que entrou de novo desde o turno anterior é gravado no cache (cache write,
1,25x o preço de entrada); a resposta, incluindo o raciocínio, é cobrada como saída. Cada
subagente começa um contexto novo e paga a gravação dele.

Uso:
    python3 tests/benchmark_estimate.py            # tabela em Markdown
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
ASSUMPTIONS = {
    "pessimista": {"main_base": 18_000, "sub_base": 12_000, "read_scale": 0.6, "reread": 1.0},
    "esperado":   {"main_base": 20_000, "sub_base": 9_000,  "read_scale": 1.0, "reread": 0.6},
    "otimista":   {"main_base": 22_000, "sub_base": 7_000,  "read_scale": 1.4, "reread": 0.4},
}
# main_base: prompt de sistema + ferramentas + CLAUDE.md da sessão principal.
# sub_base:  o mesmo para cada subagente (menor que o da sessão principal).
# read_scale: quanto código/log a tarefa exige ler (1.0 = projeto médio).
# reread: fração dos arquivos que o implementer relê porque não viu a análise.
TOKEN_PILOT_OVERHEAD = 1_500   # regras do hook + descrições das skills e agentes
BIG_TASK_SKILL = 3_000         # corpo da skill big-task, carregado quando ela roda


class Run:
    """Um agente (sessão principal ou subagente) rodando turno a turno."""

    def __init__(self, model, base):
        self.model = model
        k = TOKENIZER[model]
        self.ctx = base * k
        self.pending_write = base * k  # o primeiro turno grava a base inteira no cache
        self.cost = 0.0
        self.seconds = 0.0
        self.tokens = {"cr": 0.0, "cw": 0.0, "out": 0.0}

    def turn(self, out, result=0, tool=True):
        k, p = TOKENIZER[self.model], PRICES[self.model]
        out_t, res_t = out * k, result * k
        read = self.ctx - self.pending_write
        self.cost += (read * p["cr"] + self.pending_write * p["cw"] + out_t * p["out"]) / 1e6
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


def total(runs, parallel_groups=()):
    """Soma custo; o tempo de grupos paralelos conta só o mais lento de cada grupo."""
    cost = sum(r.cost for r in runs)
    seconds = sum(r.seconds for r in runs)
    for group in parallel_groups:
        seconds -= sum(r.seconds for r in group) - max(r.seconds for r in group)
    by_model = {}
    for r in runs:
        by_model[r.model] = by_model.get(r.model, 0) + r.cost
    opus_read = sum(r.tokens["cr"] for r in runs if r.model in ("opus", "fable"))
    return {"cost": cost, "seconds": seconds, "by_model": by_model, "opus_cache_read": opus_read}


# ---------------------------------------------------------------- cenários

def simple_task(a, pilot):
    """Pedido simples: renomear uma função e atualizar os usos (2-3 arquivos)."""
    main = Run("opus", a["main_base"] + (TOKEN_PILOT_OVERHEAD if pilot else 0))
    main.turns(5, out=300, result=1_500)
    main.turn(250, tool=False)
    return total([main])


def big_task(a, pilot):
    """Analisar o projeto, corrigir 3 testes, propor alertas e implementar o recomendado."""
    s = a["read_scale"]
    if not pilot:
        main = Run("opus", a["main_base"])
        main.turns(14, out=400, result=3_500 * s)    # análise: lê arquivos e faz greps
        main.turn(2_500, result=100, tool=False)      # brainstorm na própria sessão
        main.turns(12, out=900, result=1_500)         # 3 partes x 4 turnos de edição/teste
        main.turns(2, out=300, result=3_000)          # rodar a suíte inteira
        main.turn(700, tool=False)                    # resumo final
        return total([main])

    main = Run("opus", a["main_base"] + TOKEN_PILOT_OVERHEAD + BIG_TASK_SKILL)
    main.turn(800)                                    # escreve o brief
    main.turn(600, result=3 * 700)                    # dispara 3 scouts, recebe resumos
    main.turn(300, result=900)                        # researcher
    main.turn(900)                                    # atualiza o brief
    main.turn(300, result=1_200)                      # ideator
    main.turn(700, result=100, tool=False)            # mostra opções, recebe a escolha
    main.turns(3, out=350, result=600)                # 3 implementers
    main.turns(2, out=200, result=400)                # 2 verifiers
    main.turn(700, tool=False)                        # resumo final

    reading = 14 * 3_500 * s * 1.3                   # leitura total, com 30% de sobreposição
    scouts = [Run("haiku", a["sub_base"]).turns(6, out=250, result=reading / 3 / 6) for _ in range(3)]
    researcher = Run("sonnet", a["sub_base"]).turns(5, out=500, result=3_000 * s)
    ideator = Run("opus", a["sub_base"] + 3_000).turns(2, out=3_500, result=1_500)
    reread = 4_000 * s * a["reread"]
    implementers = [Run("opus", a["sub_base"] + 2_000).turns(5, out=900, result=1_500 + reread / 5)
                    for _ in range(3)]
    verifiers = [Run("haiku", a["sub_base"]).turns(2, out=150, result=2_000) for _ in range(2)]
    runs = [main, *scouts, researcher, ideator, *implementers, *verifiers]
    return total(runs, parallel_groups=[scouts])


def big_task_main_exec(a, pilot):
    """Variante proposta da tarefa grande: análise e brainstorm delegados como hoje, mas a
    execução fica na sessão principal (que, com o pacote, tem contexto pequeno). Os
    implementers só entram na escalada. Sem o pacote, é igual a big_task."""
    if not pilot:
        return big_task(a, False)
    s = a["read_scale"]
    main = Run("opus", a["main_base"] + TOKEN_PILOT_OVERHEAD + BIG_TASK_SKILL)
    main.turn(800)
    main.turn(600, result=3 * 700)
    main.turn(300, result=900)
    main.turn(900)
    main.turn(300, result=1_200)
    main.turn(700, result=100, tool=False)
    main.turns(12, out=900, result=1_500)             # execução na própria sessão
    main.turns(2, out=200, result=400)
    main.turn(700, tool=False)
    reading = 14 * 3_500 * s * 1.3
    scouts = [Run("haiku", a["sub_base"]).turns(6, out=250, result=reading / 3 / 6) for _ in range(3)]
    researcher = Run("sonnet", a["sub_base"]).turns(5, out=500, result=3_000 * s)
    ideator = Run("opus", a["sub_base"] + 3_000).turns(2, out=3_500, result=1_500)
    verifiers = [Run("haiku", a["sub_base"]).turns(2, out=150, result=2_000) for _ in range(2)]
    return total([main, *scouts, researcher, ideator, *verifiers], parallel_groups=[scouts])


def log_task(a, pilot):
    """Entender por que um job quebrou num log de CI de ~40 mil tokens, e seguir trabalhando
    mais 10 turnos na mesma sessão (o log continua no contexto se foi lido na sessão)."""
    log = 40_000 * a["read_scale"]
    main = Run("opus", a["main_base"] + (TOKEN_PILOT_OVERHEAD if pilot else 0))
    runs = [main]
    if not pilot:
        main.turn(300, result=log)                    # lê o log inteiro
        main.turns(2, out=600, result=1_000)
    else:
        main.turn(300, result=450)                    # recebe o resumo do log-reader
        main.turns(2, out=600, result=1_000)
        runs.append(Run("haiku", a["sub_base"]).turns(4, out=200, result=2_500))  # grep/tail
    main.turns(10, out=500, result=1_500)             # trabalho seguinte na mesma sessão
    return total(runs)


def stuck_task(a, pilot):
    """Bug difícil: o medium falha 2 vezes; o high resolve.
    Sem o pacote, o usuário percebe a trava, troca /effort high no meio da sessão (o que
    regrava o cache da conversa inteira) e tenta de novo."""
    if not pilot:
        main = Run("opus", a["main_base"] + 40_000)   # sessão que já vinha trabalhando
        main.turns(10, out=900, result=1_500)         # 2 tentativas no medium
        main.turns(2, out=400, result=300)            # usuário reclama, Claude tenta de novo
        main.pending_write = main.ctx                 # /effort high: cache regravado
        main.turns(5, out=2_200, result=1_500)        # tentativa no high, com mais raciocínio
        return total([main])
    main = Run("opus", a["main_base"] + 40_000 + TOKEN_PILOT_OVERHEAD)
    main.turns(2, out=350, result=600)                # 2 implementers
    main.turn(400, result=800)                        # implementer-high
    main.turn(300, tool=False)
    tries = [Run("opus", a["sub_base"] + 2_500).turns(5, out=900, result=1_500) for _ in range(2)]
    high = Run("opus", a["sub_base"] + 3_500).turns(5, out=2_200, result=1_500)
    return total([main, *tries, high])


SCENARIOS = [
    ("simples", "Pedido simples (renomear uma função)", simple_task),
    ("grande", "Tarefa grande (analisar, corrigir, propor e implementar)", big_task),
    ("grande_v", "Tarefa grande, variante: execução na sessão principal", big_task_main_exec),
    ("log", "Log de CI longo + 10 turnos de trabalho seguinte", log_task),
    ("trava", "Bug que trava no medium e só sai no high", stuck_task),
]
# Mix de um dia de trabalho, em número de ocorrências de cada cenário.
DAY_MIX = {"simples": 8, "grande": 2, "log": 2, "trava": 1}


def compute():
    out = {}
    for name, a in ASSUMPTIONS.items():
        rows = {}
        for key, _, fn in SCENARIOS:
            base, pilot = fn(a, False), fn(a, True)
            rows[key] = {"base": base, "pilot": pilot}
        day_base = sum(rows[k]["base"]["cost"] * n for k, n in DAY_MIX.items())
        day_pilot = sum(rows[k]["pilot"]["cost"] * n for k, n in DAY_MIX.items())
        n = DAY_MIX["grande"]
        day_variant = day_pilot + n * (rows["grande_v"]["pilot"]["cost"] - rows["grande"]["pilot"]["cost"])
        out[name] = {"rows": rows, "day": {"base": day_base, "pilot": day_pilot, "variant": day_variant}}
    return out


def pct(new, old):
    return (new - old) / old * 100


def markdown(data):
    lines = ["# Estimativa: Claude Code puro x Token Pilot", "",
             "Custo em dólares equivalentes à API (em planos Pro/Max, o mesmo consumo pesa no limite de uso). "
             "Tempo é o de espera do usuário, sem contar quanto ele demora para responder.", ""]
    esperado = data["esperado"]
    lines += ["## Cenário esperado", "",
              "| Situação | Sem o pacote | Com o Token Pilot | Custo | Tempo |",
              "|---|---|---|---|---|"]
    for key, label, _ in SCENARIOS:
        b, p = esperado["rows"][key]["base"], esperado["rows"][key]["pilot"]
        lines.append(f"| {label} | ${b['cost']:.3f} · {b['seconds'] / 60:.1f} min | "
                     f"${p['cost']:.3f} · {p['seconds'] / 60:.1f} min | "
                     f"{pct(p['cost'], b['cost']):+.0f}% | {pct(p['seconds'], b['seconds']):+.0f}% |")
    d = esperado["day"]
    lines += ["", f"**Dia típico** ({', '.join(f'{n}x {k}' for k, n in DAY_MIX.items())}): "
              f"${d['base']:.2f} sem o pacote, ${d['pilot']:.2f} com ele ({pct(d['pilot'], d['base']):+.0f}%); "
              f"${d['variant']:.2f} com a variante na tarefa grande ({pct(d['variant'], d['base']):+.0f}%).", "",
              "## Faixa (pessimista · esperado · otimista)", "",
              "| Situação | Variação de custo |", "|---|---|"]
    for key, label, _ in SCENARIOS:
        vals = [pct(data[n]["rows"][key]["pilot"]["cost"], data[n]["rows"][key]["base"]["cost"]) for n in ASSUMPTIONS]
        lines.append(f"| {label} | {' · '.join(f'{v:+.0f}%' for v in vals)} |")
    vals = [pct(data[n]["day"]["pilot"], data[n]["day"]["base"]) for n in ASSUMPTIONS]
    lines.append(f"| Dia típico | {' · '.join(f'{v:+.0f}%' for v in vals)} |")
    vals = [pct(data[n]["day"]["variant"], data[n]["day"]["base"]) for n in ASSUMPTIONS]
    lines.append(f"| Dia típico, com a variante | {' · '.join(f'{v:+.0f}%' for v in vals)} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    data = compute()
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(markdown(data))


if __name__ == "__main__":
    main()

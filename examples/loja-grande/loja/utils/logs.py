"""Log simples em texto, uma linha por evento."""

import sys
from datetime import datetime


def log(nivel, mensagem, **campos):
    extra = " ".join(f"{k}={v}" for k, v in campos.items())
    print(f"{datetime(2026, 3, 1):%Y-%m-%d} {nivel:<5} {mensagem} {extra}".rstrip(), file=sys.stdout)

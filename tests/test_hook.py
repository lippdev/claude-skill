#!/usr/bin/env python3
"""Simula uma sessão contra o hook token_pilot.py (zero tokens)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "token_pilot.py"


class HookSession:
    def __init__(self, state_dir, session="teste"):
        self.env = dict(os.environ, TOKEN_PILOT_STATE_DIR=state_dir)
        self.session = session

    def send(self, prompt, raw=None):
        data = raw if raw is not None else json.dumps(
            {"session_id": self.session, "prompt": prompt, "transcript_path": "/nao/existe"})
        out = subprocess.run([sys.executable, str(HOOK)], input=data, capture_output=True,
                             text=True, env=self.env, check=False)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)["systemMessage"] if out.stdout.strip() else None


class TestHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = HookSession(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_escada_completa_e_volta(self):
        self.assertIsNone(self.s.send("corrige o bug do carrinho"))
        self.assertIsNone(self.s.send("o teste ainda não passa"))
        self.assertIn("implementer-high", self.s.send("continua dando o mesmo erro"))
        self.assertIsNone(self.s.send("ainda não funcionou"))
        self.assertIn("implementer-fable", self.s.send("de novo o mesmo erro"))
        self.assertIn("voltam ao", self.s.send("funcionou, valeu!"))

    def test_plan_mode_em_tarefa_grande(self):
        self.assertIn("plan mode", self.s.send("refatorar o checkout em vários arquivos"))

    def test_nova_tarefa_sugere_clear(self):
        for i in range(6):
            self.s.send(f"ajuste {i}")
        self.assertIn("/clear", self.s.send("nova tarefa: criar tela de login"))

    def test_conversa_longa_sugere_compact(self):
        msgs = [self.s.send(f"passo {i}") for i in range(30)]
        self.assertIn("/compact", msgs[-1])

    def test_nova_parede_depois_de_resolver(self):
        self.s.send("mesmo erro")
        self.assertIsNotNone(self.s.send("mesmo erro"))
        self.assertIn("voltam ao", self.s.send("resolvido"))  # resolve e zera
        self.s.send("mesmo erro")
        self.assertIsNotNone(self.s.send("mesmo erro"))  # nova parede, nova dica

    def test_nao_passou_conta_como_falha(self):
        self.s.send("o teste não passou")
        self.assertIn("implementer-high", self.s.send("não passou de novo"))

    def test_entrada_invalida_nao_trava(self):
        self.assertIsNone(self.s.send("", raw="{quebrado"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

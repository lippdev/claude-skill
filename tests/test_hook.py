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
    def __init__(self, state_dir, session="teste", **env):
        self.env = dict(os.environ, TOKEN_PILOT_STATE_DIR=state_dir, HOME=state_dir, **env)
        for key in ("TOKEN_PILOT_MODELS", "TOKEN_PILOT_PLAN"):
            if key not in env:
                self.env.pop(key, None)
        self.session = session

    def run(self, data):
        out = subprocess.run([sys.executable, str(HOOK)], input=data, capture_output=True,
                             text=True, env=self.env, check=False)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout) if out.stdout.strip() else None

    def send(self, prompt, raw=None):
        data = raw if raw is not None else json.dumps(
            {"session_id": self.session, "prompt": prompt, "transcript_path": "/nao/existe"})
        out = self.run(data)
        return out.get("systemMessage") if out else None

    def context(self, prompt):
        out = self.run(json.dumps({"session_id": self.session, "prompt": prompt}))
        return out["hookSpecificOutput"]["additionalContext"] if out else None


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
        self.assertIn("voltam para a sessão principal", self.s.send("funcionou, valeu!"))

    def test_regras_no_inicio_da_sessao(self):
        out = self.s.run(json.dumps({"hook_event_name": "SessionStart", "session_id": "x"}))
        ctx = out["hookSpecificOutput"]["additionalContext"]
        for agente in ("scout", "big-task", "implementer-high", "implementer-fable"):
            self.assertIn(agente, ctx)

    def test_tarefa_grande_aciona_big_task_sozinha(self):
        ctx = self.s.context("analisa o módulo de pagamento, me dá ideias de melhorias e implementa")
        self.assertIn("skill big-task", ctx)

    def test_refatoracao_aciona_big_task(self):
        self.assertIn("Tarefa grande", self.s.send("refatorar o checkout em vários arquivos"))

    def test_big_task_nao_repete_na_mesma_tarefa(self):
        self.s.send("analisa o carrinho e implementa cupons")
        self.s.send("ok")
        self.assertIsNone(self.s.send("analisa o frete e implementa isso também"))

    def test_pedido_simples_nao_aciona_big_task(self):
        self.assertIsNone(self.s.send("corrige o typo no README"))

    def test_escalada_manda_delegar(self):
        self.s.send("mesmo erro")
        self.assertIn("Delegue", self.s.context("mesmo erro"))

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
        self.assertIn("voltam para a sessão principal", self.s.send("resolvido"))  # resolve e zera
        self.s.send("mesmo erro")
        self.assertIsNotNone(self.s.send("mesmo erro"))  # nova parede, nova dica

    def test_nao_passou_conta_como_falha(self):
        self.s.send("o teste não passou")
        self.assertIn("implementer-high", self.s.send("não passou de novo"))

    def test_entrada_invalida_nao_trava(self):
        self.assertIsNone(self.s.send("", raw="{quebrado"))


class TestPlano(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def regras(self, **env):
        s = HookSession(self.tmp.name, **env)
        out = s.run(json.dumps({"hook_event_name": "SessionStart", "session_id": "p"}))
        return out, out["hookSpecificOutput"]["additionalContext"]

    def escada(self, **env):
        s = HookSession(self.tmp.name, **env)
        return [s.send(m) for m in ("mesmo erro",) * 4]

    def test_pro_sem_fable_para_e_pede_ajuda(self):
        _, ctx = self.regras(TOKEN_PILOT_PLAN="pro")
        self.assertIn("plano pro", ctx)
        self.assertNotIn("Fable 5.1 (", ctx)
        self.assertIn("pare e peça ajuda (sem Fable no plano", ctx)
        msgs = self.escada(TOKEN_PILOT_PLAN="pro")
        self.assertIn("implementer-high", msgs[1])
        self.assertIn("não tem Fable", msgs[3])
        self.assertNotIn("implementer-fable", msgs[3])

    def test_max_usa_fable(self):
        _, ctx = self.regras(TOKEN_PILOT_PLAN="max")
        self.assertIn("-> implementer-fable", ctx)
        self.assertIn("Sonnet 5.5", ctx)
        self.assertIn("implementer-fable", self.escada(TOKEN_PILOT_PLAN="max")[3])

    def test_sonnet_55_no_plano_pro_e_id_explicito(self):
        _, ctx = self.regras(TOKEN_PILOT_PLAN="pro")
        self.assertIn("Haiku 5.5, Sonnet 5.5, Opus 5.5", ctx)
        self.assertIn("researcher (Sonnet 5.5)", ctx)
        _, ctx = self.regras(TOKEN_PILOT_MODELS="claude-sonnet-5-5,claude-opus-5-5")
        self.assertIn("Sonnet 5.5, Opus 5.5", ctx)

    def test_sem_opus_troca_modelo_dos_agentes(self):
        _, ctx = self.regras(TOKEN_PILOT_MODELS="haiku,sonnet")
        self.assertIn('implementer -> model: "sonnet"', ctx)
        self.assertIn("Sonnet 5.5, high", self.escada(TOKEN_PILOT_MODELS="haiku,sonnet")[1])

    def test_plano_desconhecido_avisa_uma_vez(self):
        out, _ = self.regras()
        self.assertIn("--plan", out["systemMessage"])
        out, _ = self.regras()
        self.assertNotIn("systemMessage", out)

    def test_cli_grava_plano(self):
        env = dict(os.environ, TOKEN_PILOT_STATE_DIR=self.tmp.name, HOME=self.tmp.name)
        env.pop("TOKEN_PILOT_PLAN", None); env.pop("TOKEN_PILOT_MODELS", None)
        out = subprocess.run([sys.executable, str(HOOK), "--plan", "pro"], capture_output=True,
                             text=True, env=env, check=True).stdout
        self.assertIn("sem Fable", out)
        _, ctx = self.regras()
        self.assertIn("plano pro (config.json)", ctx)

    def test_available_models_restringe(self):
        proj = Path(self.tmp.name) / "proj" / ".claude"
        proj.mkdir(parents=True)
        (proj / "settings.json").write_text(json.dumps({"availableModels": ["sonnet", "claude-opus-5-5"]}))
        _, ctx = self.regras(TOKEN_PILOT_PLAN="max", CLAUDE_PROJECT_DIR=str(proj.parent))
        self.assertIn("Sonnet 5.5, Opus 5.5 (fonte: plano max (TOKEN_PILOT_PLAN) + availableModels)", ctx)
        self.assertIn('scout -> model: "sonnet"', ctx)


class TestDisciplinaEMapa(unittest.TestCase):
    """SubagentStart, disciplina de resposta e mapa do código."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name) / "proj"
        (self.proj / "app").mkdir(parents=True)
        (self.proj / "tests").mkdir()
        (self.proj / "app" / "pedidos.py").write_text("def criar_pedido():\n    pass\n\nclass Pedido:\n    pass\n")
        (self.proj / "app" / "web.ts").write_text("export function rota() {}\nexport const porta = 1\n")
        (self.proj / "tests" / "test_pedidos.py").write_text("def test_criar():\n    pass\n")

    def tearDown(self):
        self.tmp.cleanup()

    def ctx(self, event, agent=None, **env):
        s = HookSession(self.tmp.name, **env)
        payload = {"hook_event_name": event, "session_id": "d", "cwd": str(self.proj)}
        if agent:
            payload["agent_type"] = agent
        out = s.run(json.dumps(payload))
        return out["hookSpecificOutput"]["additionalContext"] if out else ""

    def test_scout_recebe_disciplina_de_leitura_e_mapa(self):
        c = self.ctx("SubagentStart", "scout")
        self.assertIn("leia só o necessário", c)
        self.assertIn("criar_pedido", c)
        self.assertNotIn("menor mudança", c)

    def test_implementer_high_recebe_disciplina_de_edicao(self):
        c = self.ctx("SubagentStart", "implementer-high")
        self.assertIn("menor mudança", c)
        self.assertIn("Mapa do código", c)

    def test_log_reader_sem_mapa(self):
        c = self.ctx("SubagentStart", "log-reader")
        self.assertIn("leia só o necessário", c)
        self.assertNotIn("Mapa do código", c)

    def test_agente_de_plugin_usa_nome_sem_prefixo(self):
        self.assertIn("leia só o necessário", self.ctx("SubagentStart", "token-pilot:scout"))

    def prompt_ctx(self, prompt, **env):
        s = HookSession(self.tmp.name, **env)
        self.n = getattr(self, "n", 0) + 1  # sessão nova a cada chamada
        out = s.run(json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": f"d{self.n}",
                                "cwd": str(self.proj), "prompt": prompt}))
        return out["hookSpecificOutput"]["additionalContext"] if out else ""

    MEDIO = ("adiciona validação de CPF no cadastro de clientes, com mensagem de erro e testes cobrindo "
             "os casos inválidos e válidos, e atualiza a documentação da API com o novo campo")

    def test_abertura_leva_so_o_nucleo(self):
        c = self.ctx("SessionStart")
        self.assertIn("quick-edit", c)
        self.assertNotIn("Mapa do código", c)
        self.assertNotIn("menor mudança", c)
        self.assertLess(len(c), 1300)

    def test_mapa_ignora_testes_e_lista_exports(self):
        c = self.prompt_ctx(self.MEDIO)
        self.assertIn("web.ts(rota, porta)", c)
        self.assertNotIn("test_criar", c)
        self.assertIn("menor mudança", c)

    def test_mapa_desligado_e_teto(self):
        self.assertNotIn("Mapa do código", self.prompt_ctx(self.MEDIO, TOKEN_PILOT_MAP="0"))
        c = self.prompt_ctx(self.MEDIO, TOKEN_PILOT_MAP_CHARS="150")
        mapa = c[c.index("[Token Pilot] Mapa"):]
        self.assertLessEqual(len(mapa), 150 + 60)


class TestTarefasCurtas(unittest.TestCase):
    """Classificação do pedido e contexto silencioso conforme o tamanho da tarefa."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = HookSession(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def send(self, prompt):
        return self.s.run(json.dumps({"session_id": "c", "prompt": prompt, "cwd": self.tmp.name}))

    def test_mecanica_vai_para_quick_edit_em_silencio(self):
        for p in ("Renomeia a função valor_total para valor_total_estoque", "corrige o typo no README",
                  "troca 'Olá' por 'Oi' na tela inicial", "remove os prints de debug do carrinho"):
            out = self.send(p)
            self.assertIn("quick-edit", out["hookSpecificOutput"]["additionalContext"], p)
            self.assertNotIn("systemMessage", out, p)

    def test_curta_resolve_direto(self):
        out = self.send("por que o teste de frete falha?")
        self.assertIn("Tarefa curta", out["hookSpecificOutput"]["additionalContext"])

    def test_disciplina_entra_uma_vez_em_tarefa_media(self):
        medio = "x" * 200 + " implementa a exportação do relatório em CSV com cabeçalho e testes"
        primeiro = self.send(medio)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("menor mudança", primeiro)
        self.assertIsNone(self.send(medio + " de novo não"))

    def test_trava_nao_recebe_modo_curto(self):
        self.send("mesmo erro")
        ctx = self.send("mesmo erro")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("implementer-high", ctx)
        self.assertNotIn("Tarefa curta", ctx)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Gera a parte volumosa de examples/loja-grande: integrações, relatórios, a ferramenta de
sincronização com o ERP e o arquivo exportado. O núcleo (modelos, serviços, testes) é escrito à
mão; este script só cria o código e os dados que uma tarefa grande precisa atravessar.

Determinístico: rodar de novo produz os mesmos arquivos.

    python3 bench/gerar_loja_grande.py
"""

import random
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "examples" / "loja-grande"

INTEGRACOES = [
    ("correios", "Correios", "frete", "https://api.correios.example/v2"),
    ("jadlog", "Jadlog", "frete", "https://api.jadlog.example/embarcador"),
    ("loggi", "Loggi", "frete", "https://api.loggi.example/v1"),
    ("gateway_cielo", "Cielo", "pagamento", "https://api.cielo.example/1"),
    ("gateway_stone", "Stone", "pagamento", "https://api.stone.example/v2"),
    ("erp_totvs", "Totvs", "erp", "https://erp.totvs.example/rest"),
    ("crm_rd", "RDStation", "crm", "https://api.rd.example/platform"),
    ("email_sendgrid", "SendGrid", "email", "https://api.sendgrid.example/v3"),
    ("sms_zenvia", "Zenvia", "sms", "https://api.zenvia.example/v2"),
    ("fiscal_nfe", "NFe", "fiscal", "https://nfe.fazenda.example/ws"),
]

OPERACOES = {
    "frete": ["cotar", "contratar", "rastrear", "cancelar_envio", "etiqueta"],
    "pagamento": ["autorizar", "capturar", "cancelar", "consultar", "tokenizar_cartao"],
    "erp": ["exportar_produtos", "importar_pedido", "consultar_estoque", "baixar_nota", "sincronizar_clientes"],
    "crm": ["criar_contato", "atualizar_contato", "registrar_evento", "segmentar", "remover_contato"],
    "email": ["enviar", "enviar_lote", "status", "descadastrar", "modelos"],
    "sms": ["enviar", "status", "saldo", "bloquear_numero", "relatorio"],
    "fiscal": ["emitir", "cancelar_nota", "consultar_nota", "inutilizar", "carta_correcao"],
}

TEMPLATE_INTEGRACAO = '''"""Cliente da integração com {titulo} ({tipo}).

Faz as chamadas HTTP com repetição e converte as respostas para os modelos da loja. Em
desenvolvimento e testes, o transporte é substituído por um fake que devolve respostas fixas.
"""

import json
import time

from loja.utils.logs import log

URL_BASE = "{url}"
TENTATIVAS = {tentativas}
ESPERA_INICIAL = {espera}


class Erro{classe}(Exception):
    """Falha ao falar com {titulo}."""


class Transporte{classe}:
    """Transporte HTTP mínimo; substituível em testes."""

    def __init__(self, token, timeout={timeout}):
        self.token = token
        self.timeout = timeout

    def chamar(self, metodo, caminho, corpo=None):
        raise Erro{classe}("transporte real não disponível neste ambiente")


class Cliente{classe}:
    def __init__(self, transporte, cache=None):
        self.transporte = transporte
        self.cache = cache if cache is not None else {{}}

    def _chamar(self, metodo, caminho, corpo=None):
        espera = ESPERA_INICIAL
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                resposta = self.transporte.chamar(metodo, URL_BASE + caminho, corpo)
                return json.loads(resposta) if isinstance(resposta, str) else resposta
            except Erro{classe}:
                if tentativa == TENTATIVAS:
                    raise
                log("WARN", "{nome}: nova tentativa", caminho=caminho, tentativa=tentativa)
                time.sleep(espera)
                espera *= 2
        return None
{operacoes}

def mapear_status(codigo):
    """Converte o status de {titulo} para o status interno."""
    return {{
{status}
    }}.get(str(codigo), "desconhecido")
'''

TEMPLATE_OPERACAO = '''
    def {op}(self, {param}, **opcoes):
        """{titulo}: {op_legivel}."""
        chave = ("{op}", {param})
        if opcoes.get("usar_cache", {usar_cache}) and chave in self.cache:
            return self.cache[chave]
        corpo = {{"{campo}": {param}, **{{k: v for k, v in opcoes.items() if k != "usar_cache"}}}}
        resposta = self._chamar("{verbo}", "/{rota}", corpo)
        if not resposta or resposta.get("erro"):
            raise Erro{classe}(f"{op} falhou: {{resposta}}")
        self.cache[chave] = resposta
        return resposta
'''

RELATORIOS = {
    "vendas": ("pedidos pagos", ["por_dia", "por_categoria", "por_uf", "ticket_medio", "top_produtos"]),
    "estoque": ("produtos", ["abaixo_do_minimo", "giro", "parados", "valor_em_estoque", "por_categoria"]),
    "clientes": ("clientes", ["por_uf", "recorrentes", "novos", "inativos", "valor_vitalicio"]),
    "financeiro": ("pagamentos", ["recebido", "estornado", "por_gateway", "taxas", "conciliacao"]),
}

TEMPLATE_RELATORIO = '''"""Relatório de {nome}: agrega {fonte} para o painel."""

from collections import Counter, defaultdict
from decimal import Decimal

from loja.utils.dinheiro import ZERO, arredondar
{funcoes}

def tabela(linhas, colunas):
    """Formata uma lista de dicts como tabela de texto alinhada."""
    larguras = {{c: max(len(c), *(len(str(linha.get(c, ""))) for linha in linhas)) for c in colunas}}
    cabecalho = " | ".join(c.ljust(larguras[c]) for c in colunas)
    corpo = [" | ".join(str(linha.get(c, "")).ljust(larguras[c]) for c in colunas) for linha in linhas]
    return "\\n".join([cabecalho, "-" * len(cabecalho), *corpo])
'''

TEMPLATE_FUNCAO_RELATORIO = '''

def {func}(registros, limite={limite}):
    """{nome_legivel}."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "{atributo}", None) or "sem {atributo}"
        grupos[chave] += Decimal(getattr(r, "{valor}", 0) or 0)
        contagem[chave] += 1
    linhas = [{{"chave": k, "total": arredondar(v), "quantidade": contagem[k]}} for k, v in grupos.items()]
    linhas.sort(key=lambda linha: linha["total"], reverse=True)
    return linhas[:limite]
'''

SINCRONIZAR = '''#!/usr/bin/env python3
"""Sincroniza o catálogo com o export do ERP (data/erp_export.csv) e registra cada passo no log."""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loja.modelos import Produto  # noqa: E402
from loja.repositorios import Produtos  # noqa: E402
from loja.utils.dinheiro import parse_valor  # noqa: E402
from loja.utils.logs import log  # noqa: E402

EXPORT = Path(__file__).resolve().parent.parent / "data" / "erp_export.csv"


def sincronizar(caminho=EXPORT):
    catalogo = Produtos()
    with open(caminho, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    log("INFO", "início da sincronização", arquivo=caminho.name, linhas=len(linhas))
    for n, linha in enumerate(linhas, 1):
        sku = linha["sku"].strip()
        log("INFO", "lendo linha", n=n, sku=sku)
        log("DEBUG", "campos brutos", nome=linha["nome"], preco=linha["preco"], estoque=linha["estoque"])
        log("DEBUG", "consultando cache local", sku=sku, encontrado=catalogo.existe(sku))
        log("DEBUG", "normalizando categoria", sku=sku, categoria=linha["categoria"].strip().lower())
        preco = parse_valor(linha["preco"])
        log("DEBUG", "preço convertido", sku=sku, preco=preco)
        estoque = int(linha["estoque"])
        log("DEBUG", "estoque convertido", sku=sku, estoque=estoque)
        produto = Produto(sku, linha["nome"].strip(), preco, estoque, linha["categoria"].strip().lower())
        catalogo.salvar(produto)
        log("INFO", "produto gravado", sku=sku)
        log("DEBUG", "fila de eventos", evento="produto.atualizado", sku=sku)
        log("DEBUG", "fim da linha", n=n)
    total = len(catalogo.todos())
    log("INFO", "fim da sincronização", gravados=total)
    print(f"Sincronizados: {total} de {len(linhas)}")
    return total


if __name__ == "__main__":
    sincronizar()
'''


def gerar_integracoes(rng):
    for nome, titulo, tipo, url in INTEGRACOES:
        classe = "".join(p.capitalize() for p in nome.split("_"))
        ops = []
        for op in OPERACOES[tipo]:
            ops.append(TEMPLATE_OPERACAO.format(
                op=op, op_legivel=op.replace("_", " "), titulo=titulo, classe=classe,
                param=rng.choice(["referencia", "identificador", "codigo", "dados"]),
                campo=rng.choice(["ref", "id", "codigo", "payload"]),
                verbo=rng.choice(["GET", "POST", "PUT"]), rota=op.replace("_", "-"),
                usar_cache=rng.choice(["True", "False"])))
        status = "\n".join(f'        "{c}": "{s}",' for c, s in zip(
            rng.sample(range(100, 999), 6), ["pendente", "aprovado", "recusado", "cancelado", "em_transito", "concluido"]))
        texto = TEMPLATE_INTEGRACAO.format(
            titulo=titulo, tipo=tipo, url=url, classe=classe, nome=nome, operacoes="".join(ops), status=status,
            tentativas=rng.choice([2, 3, 4]), espera=rng.choice([0.2, 0.5, 1.0]), timeout=rng.choice([5, 10, 15]))
        (RAIZ / "loja" / "integracoes" / f"{nome}.py").write_text(texto, encoding="utf-8")


def gerar_relatorios(rng):
    for nome, (fonte, funcs) in RELATORIOS.items():
        corpo = "".join(TEMPLATE_FUNCAO_RELATORIO.format(
            func=f, nome_legivel=f.replace("_", " ").capitalize(), limite=rng.choice([10, 20, 50]),
            atributo=rng.choice(["categoria", "uf", "status", "gateway", "cliente_id"]),
            valor=rng.choice(["total", "valor", "preco", "estornado"])) for f in funcs)
        (RAIZ / "loja" / "relatorios" / f"{nome}.py").write_text(
            TEMPLATE_RELATORIO.format(nome=nome, fonte=fonte, funcoes=corpo), encoding="utf-8")


def gerar_export(rng):
    categorias = ["casa", "livros", "esporte", "promo3", "outlet", "papelaria", "cozinha"]
    nomes = ["Caneca", "Prato", "Copo", "Livro", "Bola", "Meia", "Caderno", "Panela", "Toalha", "Lápis"]
    linhas = ["sku;nome;preco;estoque;categoria"]
    com_virgula = {231, 260, 288}  # preços exportados com vírgula decimal
    for n in range(1, 301):
        preco = f"{rng.randint(5, 400)}.{rng.randint(0, 99):02d}"
        if n in com_virgula:
            preco = preco.replace(".", ",")
        linhas.append(f"SKU-{n:04d};{rng.choice(nomes)} {n};{preco};{rng.randint(0, 200)};{rng.choice(categorias)}")
    (RAIZ / "data" / "erp_export.csv").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main():
    rng = random.Random(42)
    gerar_integracoes(rng)
    gerar_relatorios(rng)
    gerar_export(rng)
    alvo = RAIZ / "tools" / "sincronizar.py"
    alvo.write_text(SINCRONIZAR, encoding="utf-8")
    alvo.chmod(0o755)
    print(f"Gerado em {RAIZ}")


if __name__ == "__main__":
    main()

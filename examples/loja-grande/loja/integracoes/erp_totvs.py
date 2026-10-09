"""Cliente da integração com Totvs (erp).

Faz as chamadas HTTP com repetição e converte as respostas para os modelos da loja. Em
desenvolvimento e testes, o transporte é substituído por um fake que devolve respostas fixas.
"""

import json
import time

from loja.utils.logs import log

URL_BASE = "https://erp.totvs.example/rest"
TENTATIVAS = 4
ESPERA_INICIAL = 0.2


class ErroErpTotvs(Exception):
    """Falha ao falar com Totvs."""


class TransporteErpTotvs:
    """Transporte HTTP mínimo; substituível em testes."""

    def __init__(self, token, timeout=5):
        self.token = token
        self.timeout = timeout

    def chamar(self, metodo, caminho, corpo=None):
        raise ErroErpTotvs("transporte real não disponível neste ambiente")


class ClienteErpTotvs:
    def __init__(self, transporte, cache=None):
        self.transporte = transporte
        self.cache = cache if cache is not None else {}

    def _chamar(self, metodo, caminho, corpo=None):
        espera = ESPERA_INICIAL
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                resposta = self.transporte.chamar(metodo, URL_BASE + caminho, corpo)
                return json.loads(resposta) if isinstance(resposta, str) else resposta
            except ErroErpTotvs:
                if tentativa == TENTATIVAS:
                    raise
                log("WARN", "erp_totvs: nova tentativa", caminho=caminho, tentativa=tentativa)
                time.sleep(espera)
                espera *= 2
        return None

    def exportar_produtos(self, identificador, **opcoes):
        """Totvs: exportar produtos."""
        chave = ("exportar_produtos", identificador)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"ref": identificador, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("PUT", "/exportar-produtos", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroErpTotvs(f"exportar_produtos falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def importar_pedido(self, identificador, **opcoes):
        """Totvs: importar pedido."""
        chave = ("importar_pedido", identificador)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"id": identificador, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/importar-pedido", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroErpTotvs(f"importar_pedido falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def consultar_estoque(self, referencia, **opcoes):
        """Totvs: consultar estoque."""
        chave = ("consultar_estoque", referencia)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"codigo": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/consultar-estoque", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroErpTotvs(f"consultar_estoque falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def baixar_nota(self, referencia, **opcoes):
        """Totvs: baixar nota."""
        chave = ("baixar_nota", referencia)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"codigo": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/baixar-nota", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroErpTotvs(f"baixar_nota falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def sincronizar_clientes(self, referencia, **opcoes):
        """Totvs: sincronizar clientes."""
        chave = ("sincronizar_clientes", referencia)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"id": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("PUT", "/sincronizar-clientes", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroErpTotvs(f"sincronizar_clientes falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta


def mapear_status(codigo):
    """Converte o status de Totvs para o status interno."""
    return {
        "187": "pendente",
        "849": "aprovado",
        "597": "recusado",
        "935": "cancelado",
        "170": "em_transito",
        "878": "concluido",
    }.get(str(codigo), "desconhecido")

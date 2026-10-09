"""Cliente da integração com Stone (pagamento).

Faz as chamadas HTTP com repetição e converte as respostas para os modelos da loja. Em
desenvolvimento e testes, o transporte é substituído por um fake que devolve respostas fixas.
"""

import json
import time

from loja.utils.logs import log

URL_BASE = "https://api.stone.example/v2"
TENTATIVAS = 4
ESPERA_INICIAL = 0.5


class ErroGatewayStone(Exception):
    """Falha ao falar com Stone."""


class TransporteGatewayStone:
    """Transporte HTTP mínimo; substituível em testes."""

    def __init__(self, token, timeout=15):
        self.token = token
        self.timeout = timeout

    def chamar(self, metodo, caminho, corpo=None):
        raise ErroGatewayStone("transporte real não disponível neste ambiente")


class ClienteGatewayStone:
    def __init__(self, transporte, cache=None):
        self.transporte = transporte
        self.cache = cache if cache is not None else {}

    def _chamar(self, metodo, caminho, corpo=None):
        espera = ESPERA_INICIAL
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                resposta = self.transporte.chamar(metodo, URL_BASE + caminho, corpo)
                return json.loads(resposta) if isinstance(resposta, str) else resposta
            except ErroGatewayStone:
                if tentativa == TENTATIVAS:
                    raise
                log("WARN", "gateway_stone: nova tentativa", caminho=caminho, tentativa=tentativa)
                time.sleep(espera)
                espera *= 2
        return None

    def autorizar(self, dados, **opcoes):
        """Stone: autorizar."""
        chave = ("autorizar", dados)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"ref": dados, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/autorizar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroGatewayStone(f"autorizar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def capturar(self, identificador, **opcoes):
        """Stone: capturar."""
        chave = ("capturar", identificador)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"id": identificador, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("PUT", "/capturar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroGatewayStone(f"capturar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def cancelar(self, referencia, **opcoes):
        """Stone: cancelar."""
        chave = ("cancelar", referencia)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"payload": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/cancelar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroGatewayStone(f"cancelar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def consultar(self, codigo, **opcoes):
        """Stone: consultar."""
        chave = ("consultar", codigo)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"ref": codigo, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("PUT", "/consultar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroGatewayStone(f"consultar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def tokenizar_cartao(self, codigo, **opcoes):
        """Stone: tokenizar cartao."""
        chave = ("tokenizar_cartao", codigo)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"codigo": codigo, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/tokenizar-cartao", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroGatewayStone(f"tokenizar_cartao falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta


def mapear_status(codigo):
    """Converte o status de Stone para o status interno."""
    return {
        "545": "pendente",
        "261": "aprovado",
        "564": "recusado",
        "103": "cancelado",
        "839": "em_transito",
        "996": "concluido",
    }.get(str(codigo), "desconhecido")

"""Cliente da integração com Cielo (pagamento).

Faz as chamadas HTTP com repetição e converte as respostas para os modelos da loja. Em
desenvolvimento e testes, o transporte é substituído por um fake que devolve respostas fixas.
"""

import json
import time

from loja.utils.logs import log

URL_BASE = "https://api.cielo.example/1"
TENTATIVAS = 2
ESPERA_INICIAL = 0.2


class ErroGatewayCielo(Exception):
    """Falha ao falar com Cielo."""


class TransporteGatewayCielo:
    """Transporte HTTP mínimo; substituível em testes."""

    def __init__(self, token, timeout=15):
        self.token = token
        self.timeout = timeout

    def chamar(self, metodo, caminho, corpo=None):
        raise ErroGatewayCielo("transporte real não disponível neste ambiente")


class ClienteGatewayCielo:
    def __init__(self, transporte, cache=None):
        self.transporte = transporte
        self.cache = cache if cache is not None else {}

    def _chamar(self, metodo, caminho, corpo=None):
        espera = ESPERA_INICIAL
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                resposta = self.transporte.chamar(metodo, URL_BASE + caminho, corpo)
                return json.loads(resposta) if isinstance(resposta, str) else resposta
            except ErroGatewayCielo:
                if tentativa == TENTATIVAS:
                    raise
                log("WARN", "gateway_cielo: nova tentativa", caminho=caminho, tentativa=tentativa)
                time.sleep(espera)
                espera *= 2
        return None

    def autorizar(self, codigo, **opcoes):
        """Cielo: autorizar."""
        chave = ("autorizar", codigo)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"ref": codigo, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/autorizar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroGatewayCielo(f"autorizar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def capturar(self, codigo, **opcoes):
        """Cielo: capturar."""
        chave = ("capturar", codigo)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"payload": codigo, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/capturar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroGatewayCielo(f"capturar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def cancelar(self, identificador, **opcoes):
        """Cielo: cancelar."""
        chave = ("cancelar", identificador)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"codigo": identificador, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/cancelar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroGatewayCielo(f"cancelar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def consultar(self, dados, **opcoes):
        """Cielo: consultar."""
        chave = ("consultar", dados)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"payload": dados, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/consultar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroGatewayCielo(f"consultar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def tokenizar_cartao(self, identificador, **opcoes):
        """Cielo: tokenizar cartao."""
        chave = ("tokenizar_cartao", identificador)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"id": identificador, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("PUT", "/tokenizar-cartao", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroGatewayCielo(f"tokenizar_cartao falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta


def mapear_status(codigo):
    """Converte o status de Cielo para o status interno."""
    return {
        "864": "pendente",
        "698": "aprovado",
        "538": "recusado",
        "697": "cancelado",
        "508": "em_transito",
        "470": "concluido",
    }.get(str(codigo), "desconhecido")

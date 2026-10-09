"""Cliente da integração com Zenvia (sms).

Faz as chamadas HTTP com repetição e converte as respostas para os modelos da loja. Em
desenvolvimento e testes, o transporte é substituído por um fake que devolve respostas fixas.
"""

import json
import time

from loja.utils.logs import log

URL_BASE = "https://api.zenvia.example/v2"
TENTATIVAS = 3
ESPERA_INICIAL = 0.2


class ErroSmsZenvia(Exception):
    """Falha ao falar com Zenvia."""


class TransporteSmsZenvia:
    """Transporte HTTP mínimo; substituível em testes."""

    def __init__(self, token, timeout=5):
        self.token = token
        self.timeout = timeout

    def chamar(self, metodo, caminho, corpo=None):
        raise ErroSmsZenvia("transporte real não disponível neste ambiente")


class ClienteSmsZenvia:
    def __init__(self, transporte, cache=None):
        self.transporte = transporte
        self.cache = cache if cache is not None else {}

    def _chamar(self, metodo, caminho, corpo=None):
        espera = ESPERA_INICIAL
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                resposta = self.transporte.chamar(metodo, URL_BASE + caminho, corpo)
                return json.loads(resposta) if isinstance(resposta, str) else resposta
            except ErroSmsZenvia:
                if tentativa == TENTATIVAS:
                    raise
                log("WARN", "sms_zenvia: nova tentativa", caminho=caminho, tentativa=tentativa)
                time.sleep(espera)
                espera *= 2
        return None

    def enviar(self, codigo, **opcoes):
        """Zenvia: enviar."""
        chave = ("enviar", codigo)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"ref": codigo, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/enviar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroSmsZenvia(f"enviar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def status(self, identificador, **opcoes):
        """Zenvia: status."""
        chave = ("status", identificador)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"payload": identificador, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/status", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroSmsZenvia(f"status falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def saldo(self, identificador, **opcoes):
        """Zenvia: saldo."""
        chave = ("saldo", identificador)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"codigo": identificador, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/saldo", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroSmsZenvia(f"saldo falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def bloquear_numero(self, referencia, **opcoes):
        """Zenvia: bloquear numero."""
        chave = ("bloquear_numero", referencia)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"payload": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("PUT", "/bloquear-numero", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroSmsZenvia(f"bloquear_numero falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def relatorio(self, referencia, **opcoes):
        """Zenvia: relatorio."""
        chave = ("relatorio", referencia)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"ref": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/relatorio", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroSmsZenvia(f"relatorio falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta


def mapear_status(codigo):
    """Converte o status de Zenvia para o status interno."""
    return {
        "270": "pendente",
        "516": "aprovado",
        "597": "recusado",
        "592": "cancelado",
        "318": "em_transito",
        "985": "concluido",
    }.get(str(codigo), "desconhecido")

"""Cliente da integração com Correios (frete).

Faz as chamadas HTTP com repetição e converte as respostas para os modelos da loja. Em
desenvolvimento e testes, o transporte é substituído por um fake que devolve respostas fixas.
"""

import json
import time

from loja.utils.logs import log

URL_BASE = "https://api.correios.example/v2"
TENTATIVAS = 2
ESPERA_INICIAL = 1.0


class ErroCorreios(Exception):
    """Falha ao falar com Correios."""


class TransporteCorreios:
    """Transporte HTTP mínimo; substituível em testes."""

    def __init__(self, token, timeout=10):
        self.token = token
        self.timeout = timeout

    def chamar(self, metodo, caminho, corpo=None):
        raise ErroCorreios("transporte real não disponível neste ambiente")


class ClienteCorreios:
    def __init__(self, transporte, cache=None):
        self.transporte = transporte
        self.cache = cache if cache is not None else {}

    def _chamar(self, metodo, caminho, corpo=None):
        espera = ESPERA_INICIAL
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                resposta = self.transporte.chamar(metodo, URL_BASE + caminho, corpo)
                return json.loads(resposta) if isinstance(resposta, str) else resposta
            except ErroCorreios:
                if tentativa == TENTATIVAS:
                    raise
                log("WARN", "correios: nova tentativa", caminho=caminho, tentativa=tentativa)
                time.sleep(espera)
                espera *= 2
        return None

    def cotar(self, referencia, **opcoes):
        """Correios: cotar."""
        chave = ("cotar", referencia)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"ref": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("PUT", "/cotar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroCorreios(f"cotar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def contratar(self, identificador, **opcoes):
        """Correios: contratar."""
        chave = ("contratar", identificador)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"id": identificador, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/contratar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroCorreios(f"contratar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def rastrear(self, referencia, **opcoes):
        """Correios: rastrear."""
        chave = ("rastrear", referencia)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"payload": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/rastrear", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroCorreios(f"rastrear falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def cancelar_envio(self, referencia, **opcoes):
        """Correios: cancelar envio."""
        chave = ("cancelar_envio", referencia)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"id": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/cancelar-envio", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroCorreios(f"cancelar_envio falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def etiqueta(self, identificador, **opcoes):
        """Correios: etiqueta."""
        chave = ("etiqueta", identificador)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"payload": identificador, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/etiqueta", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroCorreios(f"etiqueta falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta


def mapear_status(codigo):
    """Converte o status de Correios para o status interno."""
    return {
        "703": "pendente",
        "384": "aprovado",
        "928": "recusado",
        "990": "cancelado",
        "106": "em_transito",
        "877": "concluido",
    }.get(str(codigo), "desconhecido")

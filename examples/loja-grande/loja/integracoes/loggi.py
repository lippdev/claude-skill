"""Cliente da integração com Loggi (frete).

Faz as chamadas HTTP com repetição e converte as respostas para os modelos da loja. Em
desenvolvimento e testes, o transporte é substituído por um fake que devolve respostas fixas.
"""

import json
import time

from loja.utils.logs import log

URL_BASE = "https://api.loggi.example/v1"
TENTATIVAS = 4
ESPERA_INICIAL = 0.2


class ErroLoggi(Exception):
    """Falha ao falar com Loggi."""


class TransporteLoggi:
    """Transporte HTTP mínimo; substituível em testes."""

    def __init__(self, token, timeout=15):
        self.token = token
        self.timeout = timeout

    def chamar(self, metodo, caminho, corpo=None):
        raise ErroLoggi("transporte real não disponível neste ambiente")


class ClienteLoggi:
    def __init__(self, transporte, cache=None):
        self.transporte = transporte
        self.cache = cache if cache is not None else {}

    def _chamar(self, metodo, caminho, corpo=None):
        espera = ESPERA_INICIAL
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                resposta = self.transporte.chamar(metodo, URL_BASE + caminho, corpo)
                return json.loads(resposta) if isinstance(resposta, str) else resposta
            except ErroLoggi:
                if tentativa == TENTATIVAS:
                    raise
                log("WARN", "loggi: nova tentativa", caminho=caminho, tentativa=tentativa)
                time.sleep(espera)
                espera *= 2
        return None

    def cotar(self, referencia, **opcoes):
        """Loggi: cotar."""
        chave = ("cotar", referencia)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"id": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/cotar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroLoggi(f"cotar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def contratar(self, identificador, **opcoes):
        """Loggi: contratar."""
        chave = ("contratar", identificador)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"ref": identificador, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/contratar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroLoggi(f"contratar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def rastrear(self, dados, **opcoes):
        """Loggi: rastrear."""
        chave = ("rastrear", dados)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"codigo": dados, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/rastrear", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroLoggi(f"rastrear falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def cancelar_envio(self, codigo, **opcoes):
        """Loggi: cancelar envio."""
        chave = ("cancelar_envio", codigo)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"id": codigo, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("PUT", "/cancelar-envio", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroLoggi(f"cancelar_envio falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def etiqueta(self, referencia, **opcoes):
        """Loggi: etiqueta."""
        chave = ("etiqueta", referencia)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"id": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("PUT", "/etiqueta", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroLoggi(f"etiqueta falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta


def mapear_status(codigo):
    """Converte o status de Loggi para o status interno."""
    return {
        "267": "pendente",
        "573": "aprovado",
        "488": "recusado",
        "376": "cancelado",
        "755": "em_transito",
        "804": "concluido",
    }.get(str(codigo), "desconhecido")

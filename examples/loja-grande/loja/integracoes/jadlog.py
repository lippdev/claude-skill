"""Cliente da integração com Jadlog (frete).

Faz as chamadas HTTP com repetição e converte as respostas para os modelos da loja. Em
desenvolvimento e testes, o transporte é substituído por um fake que devolve respostas fixas.
"""

import json
import time

from loja.utils.logs import log

URL_BASE = "https://api.jadlog.example/embarcador"
TENTATIVAS = 2
ESPERA_INICIAL = 1.0


class ErroJadlog(Exception):
    """Falha ao falar com Jadlog."""


class TransporteJadlog:
    """Transporte HTTP mínimo; substituível em testes."""

    def __init__(self, token, timeout=5):
        self.token = token
        self.timeout = timeout

    def chamar(self, metodo, caminho, corpo=None):
        raise ErroJadlog("transporte real não disponível neste ambiente")


class ClienteJadlog:
    def __init__(self, transporte, cache=None):
        self.transporte = transporte
        self.cache = cache if cache is not None else {}

    def _chamar(self, metodo, caminho, corpo=None):
        espera = ESPERA_INICIAL
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                resposta = self.transporte.chamar(metodo, URL_BASE + caminho, corpo)
                return json.loads(resposta) if isinstance(resposta, str) else resposta
            except ErroJadlog:
                if tentativa == TENTATIVAS:
                    raise
                log("WARN", "jadlog: nova tentativa", caminho=caminho, tentativa=tentativa)
                time.sleep(espera)
                espera *= 2
        return None

    def cotar(self, codigo, **opcoes):
        """Jadlog: cotar."""
        chave = ("cotar", codigo)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"codigo": codigo, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/cotar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroJadlog(f"cotar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def contratar(self, codigo, **opcoes):
        """Jadlog: contratar."""
        chave = ("contratar", codigo)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"ref": codigo, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/contratar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroJadlog(f"contratar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def rastrear(self, referencia, **opcoes):
        """Jadlog: rastrear."""
        chave = ("rastrear", referencia)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"codigo": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/rastrear", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroJadlog(f"rastrear falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def cancelar_envio(self, referencia, **opcoes):
        """Jadlog: cancelar envio."""
        chave = ("cancelar_envio", referencia)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"payload": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("PUT", "/cancelar-envio", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroJadlog(f"cancelar_envio falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def etiqueta(self, dados, **opcoes):
        """Jadlog: etiqueta."""
        chave = ("etiqueta", dados)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"ref": dados, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("PUT", "/etiqueta", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroJadlog(f"etiqueta falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta


def mapear_status(codigo):
    """Converte o status de Jadlog para o status interno."""
    return {
        "949": "pendente",
        "743": "aprovado",
        "733": "recusado",
        "982": "cancelado",
        "470": "em_transito",
        "691": "concluido",
    }.get(str(codigo), "desconhecido")

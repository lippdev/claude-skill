"""Cliente da integração com SendGrid (email).

Faz as chamadas HTTP com repetição e converte as respostas para os modelos da loja. Em
desenvolvimento e testes, o transporte é substituído por um fake que devolve respostas fixas.
"""

import json
import time

from loja.utils.logs import log

URL_BASE = "https://api.sendgrid.example/v3"
TENTATIVAS = 2
ESPERA_INICIAL = 0.2


class ErroEmailSendgrid(Exception):
    """Falha ao falar com SendGrid."""


class TransporteEmailSendgrid:
    """Transporte HTTP mínimo; substituível em testes."""

    def __init__(self, token, timeout=10):
        self.token = token
        self.timeout = timeout

    def chamar(self, metodo, caminho, corpo=None):
        raise ErroEmailSendgrid("transporte real não disponível neste ambiente")


class ClienteEmailSendgrid:
    def __init__(self, transporte, cache=None):
        self.transporte = transporte
        self.cache = cache if cache is not None else {}

    def _chamar(self, metodo, caminho, corpo=None):
        espera = ESPERA_INICIAL
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                resposta = self.transporte.chamar(metodo, URL_BASE + caminho, corpo)
                return json.loads(resposta) if isinstance(resposta, str) else resposta
            except ErroEmailSendgrid:
                if tentativa == TENTATIVAS:
                    raise
                log("WARN", "email_sendgrid: nova tentativa", caminho=caminho, tentativa=tentativa)
                time.sleep(espera)
                espera *= 2
        return None

    def enviar(self, referencia, **opcoes):
        """SendGrid: enviar."""
        chave = ("enviar", referencia)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"codigo": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/enviar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroEmailSendgrid(f"enviar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def enviar_lote(self, codigo, **opcoes):
        """SendGrid: enviar lote."""
        chave = ("enviar_lote", codigo)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"payload": codigo, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/enviar-lote", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroEmailSendgrid(f"enviar_lote falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def status(self, dados, **opcoes):
        """SendGrid: status."""
        chave = ("status", dados)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"id": dados, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/status", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroEmailSendgrid(f"status falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def descadastrar(self, identificador, **opcoes):
        """SendGrid: descadastrar."""
        chave = ("descadastrar", identificador)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"ref": identificador, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/descadastrar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroEmailSendgrid(f"descadastrar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def modelos(self, codigo, **opcoes):
        """SendGrid: modelos."""
        chave = ("modelos", codigo)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"payload": codigo, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/modelos", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroEmailSendgrid(f"modelos falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta


def mapear_status(codigo):
    """Converte o status de SendGrid para o status interno."""
    return {
        "984": "pendente",
        "846": "aprovado",
        "155": "recusado",
        "789": "cancelado",
        "769": "em_transito",
        "761": "concluido",
    }.get(str(codigo), "desconhecido")

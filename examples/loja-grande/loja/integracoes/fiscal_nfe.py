"""Cliente da integração com NFe (fiscal).

Faz as chamadas HTTP com repetição e converte as respostas para os modelos da loja. Em
desenvolvimento e testes, o transporte é substituído por um fake que devolve respostas fixas.
"""

import json
import time

from loja.utils.logs import log

URL_BASE = "https://nfe.fazenda.example/ws"
TENTATIVAS = 2
ESPERA_INICIAL = 0.2


class ErroFiscalNfe(Exception):
    """Falha ao falar com NFe."""


class TransporteFiscalNfe:
    """Transporte HTTP mínimo; substituível em testes."""

    def __init__(self, token, timeout=5):
        self.token = token
        self.timeout = timeout

    def chamar(self, metodo, caminho, corpo=None):
        raise ErroFiscalNfe("transporte real não disponível neste ambiente")


class ClienteFiscalNfe:
    def __init__(self, transporte, cache=None):
        self.transporte = transporte
        self.cache = cache if cache is not None else {}

    def _chamar(self, metodo, caminho, corpo=None):
        espera = ESPERA_INICIAL
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                resposta = self.transporte.chamar(metodo, URL_BASE + caminho, corpo)
                return json.loads(resposta) if isinstance(resposta, str) else resposta
            except ErroFiscalNfe:
                if tentativa == TENTATIVAS:
                    raise
                log("WARN", "fiscal_nfe: nova tentativa", caminho=caminho, tentativa=tentativa)
                time.sleep(espera)
                espera *= 2
        return None

    def emitir(self, dados, **opcoes):
        """NFe: emitir."""
        chave = ("emitir", dados)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"ref": dados, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/emitir", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroFiscalNfe(f"emitir falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def cancelar_nota(self, dados, **opcoes):
        """NFe: cancelar nota."""
        chave = ("cancelar_nota", dados)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"codigo": dados, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/cancelar-nota", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroFiscalNfe(f"cancelar_nota falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def consultar_nota(self, identificador, **opcoes):
        """NFe: consultar nota."""
        chave = ("consultar_nota", identificador)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"id": identificador, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/consultar-nota", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroFiscalNfe(f"consultar_nota falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def inutilizar(self, referencia, **opcoes):
        """NFe: inutilizar."""
        chave = ("inutilizar", referencia)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"ref": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("PUT", "/inutilizar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroFiscalNfe(f"inutilizar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def carta_correcao(self, referencia, **opcoes):
        """NFe: carta correcao."""
        chave = ("carta_correcao", referencia)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"ref": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("PUT", "/carta-correcao", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroFiscalNfe(f"carta_correcao falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta


def mapear_status(codigo):
    """Converte o status de NFe para o status interno."""
    return {
        "614": "pendente",
        "973": "aprovado",
        "643": "recusado",
        "261": "cancelado",
        "158": "em_transito",
        "620": "concluido",
    }.get(str(codigo), "desconhecido")

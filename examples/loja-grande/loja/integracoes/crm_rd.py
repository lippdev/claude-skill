"""Cliente da integração com RDStation (crm).

Faz as chamadas HTTP com repetição e converte as respostas para os modelos da loja. Em
desenvolvimento e testes, o transporte é substituído por um fake que devolve respostas fixas.
"""

import json
import time

from loja.utils.logs import log

URL_BASE = "https://api.rd.example/platform"
TENTATIVAS = 2
ESPERA_INICIAL = 0.2


class ErroCrmRd(Exception):
    """Falha ao falar com RDStation."""


class TransporteCrmRd:
    """Transporte HTTP mínimo; substituível em testes."""

    def __init__(self, token, timeout=5):
        self.token = token
        self.timeout = timeout

    def chamar(self, metodo, caminho, corpo=None):
        raise ErroCrmRd("transporte real não disponível neste ambiente")


class ClienteCrmRd:
    def __init__(self, transporte, cache=None):
        self.transporte = transporte
        self.cache = cache if cache is not None else {}

    def _chamar(self, metodo, caminho, corpo=None):
        espera = ESPERA_INICIAL
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                resposta = self.transporte.chamar(metodo, URL_BASE + caminho, corpo)
                return json.loads(resposta) if isinstance(resposta, str) else resposta
            except ErroCrmRd:
                if tentativa == TENTATIVAS:
                    raise
                log("WARN", "crm_rd: nova tentativa", caminho=caminho, tentativa=tentativa)
                time.sleep(espera)
                espera *= 2
        return None

    def criar_contato(self, dados, **opcoes):
        """RDStation: criar contato."""
        chave = ("criar_contato", dados)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"id": dados, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/criar-contato", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroCrmRd(f"criar_contato falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def atualizar_contato(self, identificador, **opcoes):
        """RDStation: atualizar contato."""
        chave = ("atualizar_contato", identificador)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"id": identificador, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("PUT", "/atualizar-contato", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroCrmRd(f"atualizar_contato falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def registrar_evento(self, dados, **opcoes):
        """RDStation: registrar evento."""
        chave = ("registrar_evento", dados)
        if opcoes.get("usar_cache", False) and chave in self.cache:
            return self.cache[chave]
        corpo = {"codigo": dados, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("POST", "/registrar-evento", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroCrmRd(f"registrar_evento falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def segmentar(self, referencia, **opcoes):
        """RDStation: segmentar."""
        chave = ("segmentar", referencia)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"id": referencia, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("GET", "/segmentar", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroCrmRd(f"segmentar falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta

    def remover_contato(self, codigo, **opcoes):
        """RDStation: remover contato."""
        chave = ("remover_contato", codigo)
        if opcoes.get("usar_cache", True) and chave in self.cache:
            return self.cache[chave]
        corpo = {"ref": codigo, **{k: v for k, v in opcoes.items() if k != "usar_cache"}}
        resposta = self._chamar("PUT", "/remover-contato", corpo)
        if not resposta or resposta.get("erro"):
            raise ErroCrmRd(f"remover_contato falhou: {resposta}")
        self.cache[chave] = resposta
        return resposta


def mapear_status(codigo):
    """Converte o status de RDStation para o status interno."""
    return {
        "702": "pendente",
        "325": "aprovado",
        "107": "recusado",
        "172": "cancelado",
        "824": "em_transito",
        "746": "concluido",
    }.get(str(codigo), "desconhecido")

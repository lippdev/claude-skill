"""Notificador em memória: guarda as mensagens em vez de enviar."""


class NotificadorFake:
    def __init__(self):
        self.enviadas = []

    def enviar(self, email, assunto, corpo):
        self.enviadas.append((email, assunto, corpo))

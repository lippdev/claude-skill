"""Datas e prazos."""

from datetime import date, timedelta

FERIADOS = {(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (12, 25)}


def dia_util(dia):
    return dia.weekday() < 5 and (dia.month, dia.day) not in FERIADOS


def somar_dias_uteis(inicio, dias):
    atual = inicio
    while dias > 0:
        atual += timedelta(days=1)
        if dia_util(atual):
            dias -= 1
    return atual


def hoje():
    return date.today()

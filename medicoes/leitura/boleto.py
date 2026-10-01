"""Linha digitável do boleto bancário: valor e vencimento com certeza matemática.

Camada 1 da leitura em cascata (PLANEJAMENTO §8.2, decisão D14): regra, sem IA, validada
pelos dígitos verificadores do padrão FEBRABAN. Boletos de arrecadação (47 → 48 dígitos,
começam com 8) ficam de fora.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

BASE_ANTIGA = date(1997, 10, 7)  # fator 1000 = 03/07/2000
BASE_NOVA = date(2025, 2, 22) - timedelta(days=1000)  # em 22/02/2025 o fator voltou a 1000


@dataclass(frozen=True)
class Boleto:
    banco: str
    valor: Decimal
    vencimento: date | None  # None: boleto sem vencimento (fator 0000)
    codigo_barras: str


class BoletoInvalido(ValueError):
    """A linha digitável não fecha os dígitos verificadores: não confiar em nenhum campo."""


def modulo10(numero: str) -> int:
    soma = 0
    for i, digito in enumerate(reversed(numero)):
        produto = int(digito) * (2 if i % 2 == 0 else 1)
        soma += produto - 9 if produto > 9 else produto
    return (10 - soma % 10) % 10


def modulo11_codigo_barras(numero: str) -> int:
    soma = sum(int(digito) * (2 + i % 8) for i, digito in enumerate(reversed(numero)))
    dv = 11 - soma % 11
    return 1 if dv in (0, 10, 11) else dv


def vencimento_do_fator(fator: int, hoje: date) -> date | None:
    """O fator repete a cada ~27 anos: fica a data candidata mais próxima de hoje."""
    if fator == 0:
        return None
    candidatas = (BASE_ANTIGA + timedelta(days=fator), BASE_NOVA + timedelta(days=fator))
    return min(candidatas, key=lambda d: abs((d - hoje).days))


def ler_linha_digitavel(texto: str, hoje: date) -> Boleto:
    linha = re.sub(r"\D", "", texto)
    if len(linha) != 47:
        raise BoletoInvalido("A linha digitável do boleto bancário tem 47 dígitos. Confira se foi copiada inteira.")
    for n, (corpo, dv) in enumerate([(linha[0:9], linha[9]), (linha[10:20], linha[20]), (linha[21:31], linha[31])], 1):
        if modulo10(corpo) != int(dv):
            raise BoletoInvalido(f"O dígito verificador do campo {n} não confere. Confira a linha digitável.")
    dv_geral, fator_valor = linha[32], linha[33:47]
    codigo = linha[0:4] + dv_geral + fator_valor + linha[4:9] + linha[10:20] + linha[21:31]
    if modulo11_codigo_barras(codigo[:4] + codigo[5:]) != int(dv_geral):
        raise BoletoInvalido("O dígito verificador geral não confere. Confira a linha digitável.")
    return Boleto(
        banco=linha[0:3],
        valor=Decimal(int(fator_valor[4:])) / 100,
        vencimento=vencimento_do_fator(int(fator_valor[:4]), hoje),
        codigo_barras=codigo,
    )

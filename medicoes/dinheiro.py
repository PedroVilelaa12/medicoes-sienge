"""Dinheiro sempre em Decimal, nunca em float. Formato brasileiro na entrada e na saída."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import NamedTuple

CENTAVOS = Decimal("0.01")
QUATRO_CASAS = Decimal("0.0001")  # precisão de measuredQuantity na API do Sienge


def centavos(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def ler_valor_br(texto: str) -> Decimal:
    """'3.042,36' -> Decimal('3042.36'). Ponto separa milhar; vírgula, decimais."""
    limpo = texto.replace("R$", "").replace("\xa0", "").replace(" ", "").strip()
    limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return centavos(Decimal(limpo))
    except InvalidOperation as erro:
        raise ValueError(f"Valor em formato inválido: {texto!r}") from erro


def formatar_br(valor: Decimal) -> str:
    """Decimal('3042.36') -> 'R$ 3.042,36'."""
    v = centavos(valor)
    inteiro, decimais = f"{abs(v):.2f}".split(".")
    milhar = f"{int(inteiro):,}".replace(",", ".")
    sinal = "-" if v < 0 else ""
    return f"{sinal}R$ {milhar},{decimais}"


def formatar_quantidade(quantidade: Decimal) -> str:
    return f"{quantidade:.4f}".replace(".", ",")


class Conversao(NamedTuple):
    quantidade: Decimal
    valor_efetivo: Decimal
    diferenca: Decimal  # valor_efetivo - valor pedido


def valor_para_quantidade(valor: Decimal, preco_unitario: Decimal) -> Conversao:
    """A API mede em quantidade com 4 casas, não em reais: nem todo valor é representável.

    1 vb x R$ 3.200,00 e valor R$ 264,66 -> quantidade 0,0827 -> R$ 264,64.
    """
    if preco_unitario <= 0:
        raise ValueError("O preço unitário do item precisa ser maior que zero.")
    quantidade = (valor / preco_unitario).quantize(QUATRO_CASAS, rounding=ROUND_HALF_UP)
    valor_efetivo = centavos(quantidade * preco_unitario)
    return Conversao(quantidade, valor_efetivo, valor_efetivo - valor)

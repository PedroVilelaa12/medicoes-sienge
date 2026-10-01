"""Apoio dos testes: relógio fixo e construtores curtos."""

import hashlib
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from medicoes.dominio import Anexo, PedidoMedicao


def relogio_fixo() -> datetime:
    return datetime(2026, 10, 1, 9, 30, tzinfo=ZoneInfo("America/Recife"))


def anexo(nome: str, tipo: str, dono: str = "") -> Anexo:
    return Anexo(nome, tipo, nome, 120_000, hashlib.sha256(f"{dono}/{nome}".encode()).hexdigest())


def pedido(id: str, contrato: str | None, valor: str | None, anexos=None, **extras) -> PedidoMedicao:
    if anexos is None:
        anexos = [anexo("nf.pdf", "NF", id), anexo("boleto.pdf", "BOLETO", id)]
    return PedidoMedicao(id, contrato, Decimal(valor) if valor is not None else None, anexos=anexos, **extras)

"""Preenchimento automático do que o Sienge já sabe ou segue regra fixa. Funções puras."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from medicoes.dinheiro import centavos
from medicoes.dominio import ItemContrato, Obra

Relogio = Callable[[], datetime]

MESES = (
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)


def agora_recife() -> datetime:
    return datetime.now(ZoneInfo("America/Recife"))


def data_medicao(relogio: Relogio, fuso: str = "America/Recife") -> date:
    return relogio().astimezone(ZoneInfo(fuso)).date()


def data_vencimento(data: date, dias: int) -> date:
    # Fim de semana e feriado: sem ajuste até a área decidir (pergunta em aberto).
    return data + timedelta(days=dias)


def observacao_sugerida(fornecedor: str, data: date, modelo: str) -> str:
    return modelo.format(fornecedor=fornecedor, mes=MESES[data.month - 1], ano=data.year)


def escolher_obra(obras: Sequence[Obra], obra_id: int | None = None) -> Obra | None:
    """Uma obra: escolhe sozinha. Várias: só com a escolha da usuária. Nenhuma: None."""
    if obra_id is not None:
        return next((obra for obra in obras if obra.id == obra_id), None)
    return obras[0] if len(obras) == 1 else None


def item_alvo(
    itens: Sequence[ItemContrato], valor: Decimal | None = None, item_anterior: int | None = None
) -> ItemContrato | None:
    """Item que recebe o valor, nesta ordem:

    1. só entram itens com saldo que comporte o valor;
    2. o mesmo item da última medição do contrato (continuidade);
    3. senão, o mais recente (com aditivo, depois maior referência).
    Sem item com saldo, devolve o mais recente para a V9 avisar. Desempate a confirmar com a área.
    """
    if not itens:
        return None
    com_saldo = [item for item in itens if saldo_item(item) > 0]
    if valor is not None:
        com_saldo = [item for item in com_saldo if saldo_item(item) >= valor] or com_saldo
    for item in com_saldo:
        if item.id == item_anterior:
            return item
    return max(com_saldo or itens, key=lambda item: (item.tem_aditivo, item.referencia))


def saldo_item(item: ItemContrato) -> Decimal:
    return centavos((item.quantidade_contratada - item.quantidade_acumulada) * item.preco_unitario)


def nome_para_envio(nome: str, limite: int) -> str:
    """O Sienge aceita nomes de até `limite` caracteres; encurta preservando a extensão."""
    if len(nome) <= limite:
        return nome
    base, ponto, extensao = nome.rpartition(".")
    if not ponto:
        return nome[:limite]
    return f"{base[: limite - len(extensao) - 1]}.{extensao}"

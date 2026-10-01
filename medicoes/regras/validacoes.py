"""Validações V1 a V19, em funções puras: recebem o que foi lido do Sienge e devolvem
alertas na linguagem da usuária. V12, V13 e V19 acontecem depois de lançar (orquestrador)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from medicoes.config import Config
from medicoes.dinheiro import Conversao, formatar_br, formatar_quantidade, valor_para_quantidade
from medicoes.dominio import (
    SITUACOES_ENCERRADAS,
    Alerta,
    Anexo,
    Contrato,
    ItemContrato,
    MedicaoSienge,
    Obra,
    PedidoMedicao,
    Severidade,
    Status,
    UnidadeConstrutiva,
)
from medicoes.regras import preenchimento
from medicoes.regras.preenchimento import Relogio

BLOQUEIA = Severidade.BLOQUEIA
ATENCAO = Severidade.ATENCAO
FORA_MVP = Severidade.FORA_MVP
BYTES_POR_MB = 1024 * 1024


@dataclass
class Contexto:
    """O que foi lido do Sienge sobre o contrato."""

    contrato: Contrato | None
    obras: list[Obra] = field(default_factory=list)
    itens: list[ItemContrato] = field(default_factory=list)  # da obra e unidade escolhidas
    medicoes: list[MedicaoSienge] = field(default_factory=list)


@dataclass
class Preenchimento:
    obra: Obra
    unidade: UnidadeConstrutiva
    item: ItemContrato
    saldo: Decimal
    data_medicao: date
    data_vencimento: date
    observacao: str
    conversao: Conversao | None


@dataclass
class Resultado:
    pedido: PedidoMedicao
    status: Status
    alertas: list[Alerta]
    contrato: Contrato | None = None
    preenchimento: Preenchimento | None = None
    plano: dict | None = None  # o que seria enviado ao Sienge

    @property
    def pode_lancar(self) -> bool:
        return self.status is Status.PRONTA


def _percentual(valor: Decimal) -> str:
    return f"{valor.normalize():f}".replace(".", ",")


def v1_contrato(contrato: Contrato | None, codigo: str) -> list[Alerta]:
    if contrato is None:
        return [Alerta("V1", BLOQUEIA, f"Não encontrei o contrato {codigo} no Sienge. Confira o número no documento.")]
    if not contrato.autorizado:
        return [Alerta(
            "V1", BLOQUEIA,
            f"O contrato {codigo} está desautorizado no Sienge. A medição só pode ser lançada depois que ele for autorizado.",
            "isAuthorized=false",
        )]
    return []


def v15_situacao(contrato: Contrato) -> list[Alerta]:
    situacao = SITUACOES_ENCERRADAS.get(contrato.situacao)
    if situacao is None:
        return []
    return [Alerta(
        "V15", BLOQUEIA,
        f"O contrato {contrato.codigo} está {situacao}. Não é possível lançar novas medições nele.",
        f"status={contrato.situacao}",
    )]


def v3_retencao(contrato: Contrato, medicoes: Sequence[MedicaoSienge]) -> list[Alerta]:
    if contrato.caucao_percentual > 0:
        return [Alerta(
            "V3", FORA_MVP,
            f"Este contrato tem caução de {_percentual(contrato.caucao_percentual)}%. "
            "Medições com retenção seguem pelo caminho manual no Sienge.",
            "securityDeposit.securityDepositPercentage > 0",
        )]
    if any(m.valor_liquido < m.valor_bruto for m in medicoes):
        return [Alerta(
            "V3", FORA_MVP,
            "As medições anteriores deste contrato tiveram descontos ou impostos retidos. "
            "Medições com retenção seguem pelo caminho manual no Sienge.",
            "netValue < totalMaterialValue + totalLaborValue em medição anterior",
        )]
    return []


def v2_obra(obras: Sequence[Obra], obra_id: int | None) -> list[Alerta]:
    if not obras:
        return [Alerta("V2", BLOQUEIA, "Este contrato não tem obra vinculada no Sienge. Fale com quem cadastrou o contrato.")]
    if obra_id is not None and all(obra.id != obra_id for obra in obras):
        return [Alerta("V2", BLOQUEIA, f"A obra {obra_id} não pertence a este contrato. Escolha uma das obras do contrato.")]
    if obra_id is None and len(obras) > 1:
        nomes = "; ".join(f"{obra.id} {obra.nome}" for obra in obras)
        return [Alerta("V2", BLOQUEIA, f"Escolha a obra: este contrato tem {len(obras)} obras ({nomes}).")]
    return []


def v4_v16_unidades(obra: Obra) -> list[Alerta]:
    if len(obra.unidades) > 1:
        return [Alerta(
            "V4", FORA_MVP,
            f"A obra {obra.id} tem {len(obra.unidades)} unidades construtivas neste contrato. "
            "Esse caso segue pelo caminho manual no Sienge.",
        )]
    if not obra.unidades:
        return [Alerta("V13", BLOQUEIA, f"A obra {obra.id} não tem unidade construtiva no contrato. Confira o cadastro no Sienge.")]
    unidade = obra.unidades[0]
    if unidade.bloqueada:
        return [Alerta(
            "V16", BLOQUEIA,
            f"A unidade construtiva {unidade.nome} está bloqueada no Sienge. Ela precisa ser liberada antes da medição.",
            "constructUnit.status=B",
        )]
    return []


def v14_nao_finalizadas(medicoes: Sequence[MedicaoSienge], hoje: date) -> list[Alerta]:
    abertas = [m for m in medicoes if not m.finalizada and m.data <= hoje]
    if not abertas:
        return []
    numeros = ", ".join(f"nº {m.numero}" for m in abertas)
    return [Alerta(
        "V14", BLOQUEIA,
        f"Há medições anteriores ainda não finalizadas ({numeros}). "
        "O Sienge só aceita uma nova medição depois que elas forem finalizadas.",
        "422: Existem medições anteriores ainda não finalizadas",
    )]


def v6_v7_posteriores(medicoes: Sequence[MedicaoSienge], hoje: date) -> list[Alerta]:
    posteriores = [m for m in medicoes if m.data > hoje]
    if not posteriores:
        return []
    if any(m.liberada for m in posteriores):
        return [Alerta(
            "V6", BLOQUEIA,
            "Existem medições posteriores já liberadas neste contrato. Não é possível lançar uma medição antes delas.",
            "Sienge: Existem medições posteriores liberadas",
        )]
    ultima = max(posteriores, key=lambda m: m.data)
    return [Alerta(
        "V7", BLOQUEIA,
        f"A última medição deste contrato é de {ultima.data:%d/%m/%Y}, depois de hoje. As medições precisam seguir a ordem das datas.",
        "422: Já existem outras medições com data posterior",
    )]


def v5_mes_corrente(medicoes: Sequence[MedicaoSienge], hoje: date) -> list[Alerta]:
    no_mes = [m for m in medicoes if (m.data.year, m.data.month) == (hoje.year, hoje.month)]
    if not no_mes:
        return []
    m = max(no_mes, key=lambda medicao: medicao.numero)
    return [Alerta(
        "V5", ATENCAO,
        f"Já existe a medição nº {m.numero} deste contrato em {m.data:%d/%m/%Y}, de {formatar_br(m.valor_bruto)}. "
        "Confirme que esta é uma nova medição, e não um lançamento repetido.",
    )]


def v9_sem_saldo(saldo: Decimal) -> list[Alerta]:
    if saldo > 0:
        return []
    return [Alerta(
        "V9", ATENCAO,
        "O item mais recente do contrato não tem saldo. Confira com o responsável pelo contrato qual item deve receber a medição.",
    )]


def v8_valor(valor: Decimal, saldo: Decimal) -> list[Alerta]:
    if valor <= 0:
        return [Alerta("V8", BLOQUEIA, "O valor precisa ser maior que zero.")]
    if valor > saldo:
        return [Alerta("V8", BLOQUEIA, f"Valor acima do saldo do item ({formatar_br(saldo)}). Confira o valor no documento.")]
    return []


def v17_representavel(valor: Decimal, conversao: Conversao) -> list[Alerta]:
    if conversao.diferenca == 0:
        return []
    return [Alerta(
        "V17", ATENCAO,
        f"O Sienge recebe a medição em quantidade, com 4 casas decimais. Com o preço deste item, "
        f"{formatar_br(valor)} vira {formatar_br(conversao.valor_efetivo)} "
        f"(diferença de {formatar_br(abs(conversao.diferenca))}). Confirme se pode lançar assim.",
        f"measuredQuantity={formatar_quantidade(conversao.quantidade)}",
    )]


def v11_sem_anexo(anexos: Sequence[Anexo]) -> list[Alerta]:
    if anexos:
        return []
    return [Alerta(
        "V11", ATENCAO,
        "Esta medição está sem anexo, e o Sienge vai avisar que ela não possui nenhum anexo. Confirme se quer lançar assim.",
    )]


def v18_anexos(anexos: Sequence[Anexo], config: Config) -> list[Alerta]:
    alertas = []
    for anexo in anexos:
        if anexo.tipo not in config.tipos_anexo:
            alertas.append(Alerta("V18", BLOQUEIA, f"Escolha o tipo do arquivo {anexo.nome}: {', '.join(config.tipos_anexo)}."))
        if anexo.tamanho_bytes > config.limite_anexo_mb * BYTES_POR_MB:
            alertas.append(Alerta(
                "V18", BLOQUEIA,
                f"O arquivo {anexo.nome} passa de {config.limite_anexo_mb} MB, o limite do Sienge. Reduza o arquivo antes de anexar.",
            ))
        elif len(anexo.nome) > config.limite_nome_anexo:
            alertas.append(Alerta(
                "V18", ATENCAO,
                f"O nome do arquivo {anexo.nome[:40]}… passa de {config.limite_nome_anexo} caracteres e será encurtado no envio.",
            ))
    return alertas


def validar_lote(pedidos: Sequence[PedidoMedicao]) -> dict[str, list[Alerta]]:
    """V10: o mesmo arquivo ou o mesmo contrato aparecendo duas vezes no lote."""
    alertas: dict[str, list[Alerta]] = {p.id: [] for p in pedidos}
    contratos = Counter(p.contrato for p in pedidos if p.contrato)
    hashes = Counter(a.hash for p in pedidos for a in p.anexos)
    for p in pedidos:
        if p.contrato and contratos[p.contrato] > 1:
            alertas[p.id].append(Alerta(
                "V10", ATENCAO,
                f"O contrato {p.contrato} aparece mais de uma vez neste lote. Confirme que são medições diferentes.",
            ))
        repetidos = [a.nome for a in p.anexos if hashes[a.hash] > 1]
        if repetidos:
            alertas[p.id].append(Alerta(
                "V10", ATENCAO,
                f"O arquivo {repetidos[0]} aparece em mais de uma medição deste lote. Confirme que não é o mesmo documento.",
            ))
    return alertas


def definir_status(pedido: PedidoMedicao, alertas: Iterable[Alerta]) -> Status:
    if not pedido.contrato:
        return Status.FALTA_CONTRATO
    pendentes = [a for a in alertas if not (a.severidade is ATENCAO and a.codigo in pedido.confirmacoes)]
    severidades = {a.severidade for a in pendentes}
    if BLOQUEIA in severidades:
        return Status.PRECISA_ATENCAO
    if FORA_MVP in severidades:
        return Status.FORA_MVP
    if pedido.valor is None:
        return Status.FALTA_VALOR
    if ATENCAO in severidades:
        return Status.PRECISA_ATENCAO
    return Status.PRONTA


def montar_plano(contrato: Contrato, dados: Preenchimento, anexos: Sequence[Anexo], config: Config) -> dict:
    """As requisições que seriam enviadas ao Sienge, exatamente como a spec oficial pede."""
    return {
        "criar_medicao": {
            "metodo": "POST",
            "rota": "/supply-contracts/measurements",
            "query": {"documentId": contrato.documento, "contractNumber": contrato.numero, "buildingId": dados.obra.id},
            "corpo": {
                "measurementDate": dados.data_medicao.isoformat(),
                "dueDate": dados.data_vencimento.isoformat(),
                "notes": dados.observacao,
                "makeUnauthorized": config.marcar_desautorizada,
                "items": [{
                    "buildingUnitId": dados.unidade.id,
                    "itemId": dados.item.id,
                    "measuredQuantity": str(dados.conversao.quantidade),
                }],
            },
        },
        "anexos": [
            {
                "metodo": "POST",
                "rota": "/supply-contracts/measurements/attachments",
                "description": anexo.tipo,
                "arquivo": preenchimento.nome_para_envio(anexo.nome, config.limite_nome_anexo),
            }
            for anexo in anexos
        ],
    }


def validar(
    pedido: PedidoMedicao,
    contexto: Contexto,
    config: Config,
    relogio: Relogio,
    alertas_extras: Iterable[Alerta] = (),
) -> Resultado:
    alertas = list(alertas_extras)
    if not pedido.contrato:
        return Resultado(pedido, Status.FALTA_CONTRATO, alertas)
    contrato = contexto.contrato
    alertas += v1_contrato(contrato, pedido.contrato)
    if contrato is None:
        return Resultado(pedido, definir_status(pedido, alertas), alertas)

    hoje = preenchimento.data_medicao(relogio, config.fuso)
    alertas += v15_situacao(contrato)
    alertas += v3_retencao(contrato, contexto.medicoes)
    alertas += v2_obra(contexto.obras, pedido.obra_id)
    obra = preenchimento.escolher_obra(contexto.obras, pedido.obra_id)
    unidade = None
    if obra is not None:
        alertas += v4_v16_unidades(obra)
        if len(obra.unidades) == 1:
            unidade = obra.unidades[0]
    medicoes = [m for m in contexto.medicoes if obra is None or m.obra_id == obra.id]
    alertas += v14_nao_finalizadas(medicoes, hoje)
    alertas += v6_v7_posteriores(medicoes, hoje)
    alertas += v5_mes_corrente(medicoes, hoje)
    alertas += v11_sem_anexo(pedido.anexos)
    alertas += v18_anexos(pedido.anexos, config)

    dados = None
    if obra is not None and unidade is not None:
        item = preenchimento.item_alvo(contexto.itens)
        if item is None:
            alertas.append(Alerta(
                "V13", BLOQUEIA,
                "Não encontrei itens deste contrato para a obra escolhida. Confira o contrato no Sienge.",
                "GET /supply-contracts/items sem resultados",
            ))
        else:
            saldo = preenchimento.saldo_item(item)
            alertas += v9_sem_saldo(saldo)
            conversao = None
            if pedido.valor is not None:
                alertas += v8_valor(pedido.valor, saldo)
                if pedido.valor > 0:
                    conversao = valor_para_quantidade(pedido.valor, item.preco_unitario)
                    alertas += v17_representavel(pedido.valor, conversao)
            observacao = pedido.observacao or preenchimento.observacao_sugerida(
                contrato.fornecedor, hoje, config.modelo_observacao
            )
            dados = Preenchimento(
                obra, unidade, item, saldo, hoje,
                preenchimento.data_vencimento(hoje, config.dias_vencimento),
                observacao, conversao,
            )

    resultado = Resultado(pedido, definir_status(pedido, alertas), alertas, contrato, dados)
    if dados is not None and dados.conversao is not None:
        resultado.plano = montar_plano(contrato, dados, pedido.anexos, config)
    return resultado

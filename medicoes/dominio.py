"""Modelos do domínio, com os nomes que a usuária usa."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class Severidade(str, Enum):
    BLOQUEIA = "BLOQUEIA"  # não lança até resolver
    ATENCAO = "ATENCAO"  # lança só com confirmação explícita
    FORA_MVP = "FORA_MVP"  # segue pelo caminho manual
    PENDENCIA = "PENDENCIA"  # lançada, mas falta algo no Sienge


class Status(str, Enum):
    FALTA_CONTRATO = "Falta contrato"
    FALTA_VALOR = "Falta valor"
    PRECISA_ATENCAO = "Precisa de atenção"
    FORA_MVP = "Fora do MVP"
    PRONTA = "Pronta"
    LANCANDO = "Lançando"
    LANCADA = "Lançada"
    FALHOU = "Falhou"


class Etapa(str, Enum):
    RASCUNHO = "RASCUNHO"
    VALIDADA = "VALIDADA"
    CONFIRMADA = "CONFIRMADA"
    CRIACAO_ENVIADA = "CRIACAO_ENVIADA"  # POST enviado; ainda sem certeza se gravou
    CRIADA = "CRIADA"
    ANEXOS_ENVIADOS = "ANEXOS_ENVIADOS"
    CONFERIDA = "CONFERIDA"


SITUACOES_ENCERRADAS = {
    "RESCINDED": "rescindido",
    "COMPLETED": "concluído",
    "FULLY_MEASURED": "totalmente medido",
}


@dataclass(frozen=True)
class Contrato:
    documento: str  # "CT"
    numero: str  # "1241"
    fornecedor: str
    autorizado: bool = True
    situacao: str = "PARTIALLY_MEASURED"
    caucao_percentual: Decimal = Decimal("0")

    @property
    def codigo(self) -> str:
        return f"{self.documento}/{self.numero}"


@dataclass(frozen=True)
class UnidadeConstrutiva:
    id: int
    nome: str
    bloqueada: bool = False  # status "B" no Sienge


@dataclass(frozen=True)
class Obra:
    id: int
    nome: str
    unidades: tuple[UnidadeConstrutiva, ...] = ()


@dataclass(frozen=True)
class ItemContrato:
    id: int
    referencia: str  # wbsCode, ex.: 00.000.000.002
    descricao: str
    quantidade_contratada: Decimal
    quantidade_acumulada: Decimal
    preco_unitario: Decimal  # material + mão de obra
    tem_aditivo: bool = False
    unidade_medida: str = "R$"


@dataclass(frozen=True)
class MedicaoSienge:
    numero: int
    obra_id: int
    data: date
    valor_bruto: Decimal
    valor_liquido: Decimal
    finalizada: bool = True
    liberada: bool = True
    consistente: bool = True
    autorizada: bool = False
    itens_medidos: tuple[int, ...] = ()  # ids dos itens medidos (GET /supply-contracts/measurements/items)


@dataclass(frozen=True)
class Anexo:
    caminho: str
    tipo: str  # BOLETO, NF, CONTRATO ou PROPOSTA
    nome: str
    tamanho_bytes: int
    hash: str


@dataclass
class PedidoMedicao:
    """O que a usuária informa. Todo o resto a ferramenta preenche."""

    id: str
    contrato: str | None  # "CT/1241"
    valor: Decimal | None
    observacao: str | None = None
    anexos: list[Anexo] = field(default_factory=list)
    obra_id: int | None = None  # só quando o contrato tem mais de uma obra
    confirmacoes: frozenset[str] = frozenset()  # alertas de atenção que ela confirmou


@dataclass(frozen=True)
class Alerta:
    codigo: str
    severidade: Severidade
    mensagem: str  # para a usuária
    detalhe_tecnico: str = ""  # para o log

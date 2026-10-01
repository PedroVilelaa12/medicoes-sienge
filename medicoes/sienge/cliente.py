"""Interface do cliente do Sienge. Cada método espelha uma rota verificada na spec oficial:
https://api.sienge.com.br/docs/yaml-files/measurement-v1.yaml e contracts-v1.yaml.

URL base: https://api.sienge.com.br/{subdominio}/public/api/v1 · autenticação Basic
(usuário de API) · limite de 200 requisições por minuto, mais a cota diária do plano.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from medicoes.dominio import Anexo, Contrato, ItemContrato, MedicaoSienge, Obra


class ErroSienge(Exception):
    """A API respondeu com erro (400, 404, 422, 429, 5xx)."""

    def __init__(self, mensagem: str, status: int | None = None):
        super().__init__(mensagem)
        self.status = status


class RespostaAmbigua(ErroSienge):
    """Escrita enviada sem confirmação (timeout): pode ter sido gravada ou não."""


class ClienteSienge(Protocol):
    def buscar_contrato(self, documento: str, numero: str) -> Contrato | None:
        """GET /supply-contracts?documentId&contractNumber (isAuthorized, status, securityDeposit)."""

    def listar_obras(self, documento: str, numero: str) -> list[Obra]:
        """GET /supply-contracts/buildings — obras do contrato com unidades construtivas."""

    def listar_itens(self, documento: str, numero: str, obra_id: int, unidade_id: int) -> list[ItemContrato]:
        """GET /supply-contracts/items?buildingId&buildingUnitId (wbsCode, quantity, preços, hasAddendum)."""

    def listar_medicoes(self, documento: str, numero: str, obra_id: int | None = None) -> list[MedicaoSienge]:
        """GET /supply-contracts/measurements/all?contractNumber&buildingId (released, finalized, netValue)."""

    def criar_medicao(self, documento: str, numero: str, obra_id: int, corpo: dict) -> int:
        """POST /supply-contracts/measurements?documentId&contractNumber&buildingId.

        Corpo: measurementDate, dueDate, notes, makeUnauthorized e
        items[buildingUnitId, itemId, measuredQuantity]. Devolve measurementNumber (201).
        Valor e criação vão juntos: não existe medição com valor zero no meio do caminho.
        """

    def enviar_anexo(self, documento: str, numero: str, obra_id: int, medicao: int, anexo: Anexo, nome_envio: str) -> None:
        """POST /supply-contracts/measurements/attachments — multipart, 1 arquivo por chamada,
        até 70 MB, nome até 100 caracteres, description = tipo. A resposta (201) não traz id."""

    def listar_anexos(self, documento: str, numero: str, obra_id: int, medicao: int, data: date) -> list[tuple[str, str]]:
        """GET /supply-contracts/measurements/attachments/all — (nome, descrição) de cada anexo."""

    def ler_medicao(self, documento: str, numero: str, obra_id: int, medicao: int) -> MedicaoSienge:
        """GET /supply-contracts/measurements — totalização: netValue, consistent, authorized."""

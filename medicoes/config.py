"""Regras configuráveis. Mudam com uma conversa com a área, não com código novo."""

from dataclasses import dataclass

TIPOS_ANEXO = ("BOLETO", "NF", "CONTRATO", "PROPOSTA")


@dataclass(frozen=True)
class Config:
    dias_vencimento: int = 15
    fuso: str = "America/Recife"
    modelo_observacao: str = "Referente aos serviços prestados pelo {fornecedor} - {mes}/{ano}"
    tipos_anexo: tuple[str, ...] = TIPOS_ANEXO
    # Vira makeUnauthorized no POST: a medição segue o fluxo normal de autorização,
    # mesmo que o usuário de API tenha permissão para autorizar.
    marcar_desautorizada: bool = True
    limite_anexo_mb: int = 70
    limite_nome_anexo: int = 100

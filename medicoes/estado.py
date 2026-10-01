"""Estado de cada medição do lote, salvo em JSON para retomar de onde parou.
No MVP é um arquivo; SQLite (estado + auditoria consultável) está no roadmap."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from medicoes.dominio import Etapa

# Etapas em que algo já pode ter sido gravado no Sienge: retomar, nunca recomeçar.
RETOMAVEIS = (Etapa.CRIACAO_ENVIADA, Etapa.CRIADA, Etapa.ANEXOS_ENVIADOS)


@dataclass
class EstadoMedicao:
    pedido_id: str
    chave: str  # idempotência: contrato + obra + data + valor + hashes dos anexos
    contrato: str
    fornecedor: str
    plano: dict  # requisições congeladas na confirmação (data e valor não mudam na retomada)
    data_medicao: str
    valor_efetivo: str
    etapa: Etapa = Etapa.CONFIRMADA
    numero_sienge: int | None = None
    anexos_enviados: list[str] = field(default_factory=list)
    passo_falha: str | None = None
    erro: str | None = None
    eventos: list[dict] = field(default_factory=list)  # auditoria, sem dados sensíveis

    def registrar(self, passo: str, resultado: str, mensagem: str = "") -> None:
        self.eventos.append({
            "quando": datetime.now().astimezone().isoformat(timespec="seconds"),
            "passo": passo,
            "resultado": resultado,
            "mensagem": mensagem,
        })


class Armazem:
    """Sem caminho, guarda só em memória (testes)."""

    def __init__(self, caminho: Path | None = None):
        self.caminho = caminho
        self._estados: dict[str, EstadoMedicao] = {}
        if caminho is not None and caminho.exists():
            for dados in json.loads(caminho.read_text(encoding="utf-8")):
                dados["etapa"] = Etapa(dados["etapa"])
                self._estados[dados["pedido_id"]] = EstadoMedicao(**dados)

    def obter(self, pedido_id: str) -> EstadoMedicao | None:
        return self._estados.get(pedido_id)

    def por_chave(self, chave: str) -> EstadoMedicao | None:
        return next((e for e in self._estados.values() if e.chave == chave), None)

    def salvar(self, estado: EstadoMedicao) -> None:
        self._estados[estado.pedido_id] = estado
        if self.caminho is None:
            return
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        dados = [{**asdict(e), "etapa": e.etapa.value} for e in self._estados.values()]
        temporario = self.caminho.with_suffix(".tmp")
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        temporario.replace(self.caminho)  # escrita atômica: nunca fica meio arquivo

"""Sienge falso, em memória, com os dados fictícios. Serve aos testes e à demonstração:
simula falha em qualquer passo e a resposta ambígua do POST (gravou, mas não respondeu)."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from medicoes.dinheiro import centavos
from medicoes.dominio import Anexo, Contrato, ItemContrato, MedicaoSienge, Obra, UnidadeConstrutiva
from medicoes.sienge.cliente import ErroSienge, RespostaAmbigua

D = Decimal
UNICA = (UnidadeConstrutiva(1, "UNIDADE 1"),)
MUMBECA = "START RECIFE ESTR. DA MUMBECA (COMERCIAL)"


def dados_ficticios():
    contratos = {
        "CT/1241": Contrato("CT", "1241", "ALFA SISTEMAS LTDA"),
        "CT/154": Contrato("CT", "154", "1776 METADADOS"),
        "CT/2088": Contrato("CT", "2088", "CONSTRUTORA PILAR LTDA", caucao_percentual=D("5")),
        "CT/3310": Contrato("CT", "3310", "HIDRO INSTALAÇÕES LTDA"),
        "CT/0977": Contrato("CT", "0977", "VIDRAÇARIA BOA VISTA LTDA", autorizado=False),
        "CT/4102": Contrato("CT", "4102", "LOCAMAQ EQUIPAMENTOS LTDA"),
    }
    obras = {
        "CT/1241": [Obra(480, MUMBECA, UNICA)],
        "CT/154": [Obra(56, "ESCRITORIO CENTRAL - C.S.C (ADM)", UNICA)],
        "CT/2088": [Obra(312, "RESIDENCIAL JARDIM DO CAPIBARIBE", UNICA)],
        "CT/3310": [Obra(205, "EMPRESARIAL BOA VIAGEM", (UnidadeConstrutiva(1, "TORRE A"), UnidadeConstrutiva(2, "TORRE B")))],
        "CT/0977": [Obra(118, "EDIFÍCIO MIRANTE DO PINA", UNICA)],
        "CT/4102": [Obra(480, MUMBECA, UNICA)],
    }
    itens = {
        ("CT/1241", 480, 1): [
            ItemContrato(1, "00.000.000.001", "Mensalidade de Software", D("3042.36"), D("2788.83"), D("1.00")),
            ItemContrato(2, "00.000.000.002", "Mensalidade de Software", D("3200.00"), D("2911.26"), D("1.00"), tem_aditivo=True),
        ],
        ("CT/154", 56, 1): [
            ItemContrato(1, "00.000.000.001", "Licença e suporte de software", D("24000.00"), D("18000.00"), D("1.00")),
        ],
        ("CT/2088", 312, 1): [
            ItemContrato(1, "01.001.000.001", "Execução de alvenaria", D("120000.00"), D("80000.00"), D("1.00")),
        ],
        ("CT/0977", 118, 1): [
            ItemContrato(1, "01.002.000.001", "Esquadrias de vidro temperado", D("45000.00"), D("10000.00"), D("1.00")),
        ],
        ("CT/4102", 480, 1): [
            ItemContrato(1, "00.000.000.001", "Locação mensal de equipamento", D("1"), D("0"), D("3200.00"), unidade_medida="vb"),
        ],
    }
    medicoes = {
        "CT/1241": [MedicaoSienge(24, 480, date(2026, 9, 15), D("261.53"), D("261.53"), itens_medidos=(2,))],
        "CT/154": [MedicaoSienge(9, 56, date(2026, 9, 5), D("2000.00"), D("2000.00"))],
        "CT/2088": [MedicaoSienge(5, 312, date(2026, 9, 10), D("10000.00"), D("9500.00"))],
    }
    return contratos, obras, itens, medicoes


def _medicao_para_json(m: MedicaoSienge) -> dict:
    return {**asdict(m), "data": m.data.isoformat(), "valor_bruto": str(m.valor_bruto), "valor_liquido": str(m.valor_liquido)}


def _medicao_de_json(d: dict) -> MedicaoSienge:
    return MedicaoSienge(**{
        **d,
        "data": date.fromisoformat(d["data"]),
        "valor_bruto": D(d["valor_bruto"]),
        "valor_liquido": D(d["valor_liquido"]),
    })


class ClienteFalso:
    """Implementa ClienteSienge. Com `caminho`, guarda o que foi gravado entre execuções."""

    def __init__(self, caminho: Path | None = None, avaliacao_obrigatoria: bool = True):
        self.contratos, self.obras, self.itens, self.medicoes = dados_ficticios()
        self.anexos: dict[tuple[str, int], list[tuple[str, str]]] = {}
        self.escritas: list[str] = []
        self.ambiguas = 0  # POSTs de criação que gravam mas não respondem
        self.ajuste_liquido = D("0")  # simula imposto/desconto na totalização (V12)
        # Parâmetro 131: avaliação obrigatória deixa a medição inconsistente até ser feita.
        self.avaliacao_obrigatoria = avaliacao_obrigatoria
        self._falhas: dict[str, list[int]] = {}
        self._caminho = caminho
        self._carregar()

    # --- simulação de falhas ---
    def falhar(self, passo: str, vezes: int = 1, depois_de: int = 0) -> None:
        """Faz `passo` ("criacao", "anexos", "conferencia") falhar `vezes` vezes,
        depois de `depois_de` chamadas bem-sucedidas."""
        self._falhas[passo] = [depois_de, vezes]

    def _talvez_falhar(self, passo: str) -> None:
        regra = self._falhas.get(passo)
        if not regra:
            return
        if regra[0] > 0:
            regra[0] -= 1
            return
        if regra[1] > 0:
            regra[1] -= 1
            raise ErroSienge(f"Falha simulada em {passo}: HTTP 503 Service Unavailable", status=503)

    # --- leituras ---
    def buscar_contrato(self, documento, numero):
        return self.contratos.get(f"{documento}/{numero}")

    def listar_obras(self, documento, numero):
        return list(self.obras.get(f"{documento}/{numero}", []))

    def listar_itens(self, documento, numero, obra_id, unidade_id):
        return list(self.itens.get((f"{documento}/{numero}", obra_id, unidade_id), []))

    def listar_medicoes(self, documento, numero, obra_id=None):
        medicoes = self.medicoes.get(f"{documento}/{numero}", [])
        return [m for m in medicoes if obra_id is None or m.obra_id == obra_id]

    def listar_anexos(self, documento, numero, obra_id, medicao, data):
        return list(self.anexos.get((f"{documento}/{numero}", medicao), []))

    def ler_medicao(self, documento, numero, obra_id, medicao):
        self._talvez_falhar("conferencia")
        for m in self.medicoes.get(f"{documento}/{numero}", []):
            if m.numero == medicao and m.obra_id == obra_id:
                return m
        raise ErroSienge(f"Medição {documento}/{numero} nº {medicao} não encontrada", status=404)

    # --- escritas ---
    def criar_medicao(self, documento, numero, obra_id, corpo):
        codigo = f"{documento}/{numero}"
        self._talvez_falhar("criacao")
        bruto = D("0")
        for linha in corpo["items"]:
            item = next(i for i in self.itens[(codigo, obra_id, linha["buildingUnitId"])] if i.id == linha["itemId"])
            bruto += centavos(D(linha["measuredQuantity"]) * item.preco_unitario)
        caucao = centavos(bruto * self.contratos[codigo].caucao_percentual / 100)
        numero_medicao = max((m.numero for m in self.medicoes.get(codigo, [])), default=0) + 1
        self.medicoes.setdefault(codigo, []).append(MedicaoSienge(
            numero_medicao, obra_id, date.fromisoformat(corpo["measurementDate"]),
            bruto, bruto - caucao + self.ajuste_liquido,
            finalizada=False, liberada=False,
            consistente=not self.avaliacao_obrigatoria,
            autorizada=not corpo.get("makeUnauthorized", False),
        ))
        self.escritas.append(f"POST medição {codigo} nº {numero_medicao}")
        self._salvar()
        if self.ambiguas > 0:
            self.ambiguas -= 1
            raise RespostaAmbigua("Tempo esgotado esperando a resposta do Sienge à criação da medição.")
        return numero_medicao

    def enviar_anexo(self, documento, numero, obra_id, medicao, anexo: Anexo, nome_envio: str):
        self._talvez_falhar("anexos")
        self.anexos.setdefault((f"{documento}/{numero}", medicao), []).append((nome_envio, anexo.tipo))
        self.escritas.append(f"POST anexo {anexo.tipo} {nome_envio} na medição {documento}/{numero} nº {medicao}")
        self._salvar()

    # --- persistência da demonstração ---
    def _salvar(self) -> None:
        if self._caminho is None:
            return
        dados = {
            "medicoes": {c: [_medicao_para_json(m) for m in ms] for c, ms in self.medicoes.items()},
            "anexos": [
                {"contrato": c, "medicao": n, "nome": nome, "tipo": tipo}
                for (c, n), lista in self.anexos.items()
                for nome, tipo in lista
            ],
        }
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        self._caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    def _carregar(self) -> None:
        if self._caminho is None or not self._caminho.exists():
            return
        dados = json.loads(self._caminho.read_text(encoding="utf-8"))
        self.medicoes = {c: [_medicao_de_json(m) for m in ms] for c, ms in dados["medicoes"].items()}
        for a in dados["anexos"]:
            self.anexos.setdefault((a["contrato"], a["medicao"]), []).append((a["nome"], a["tipo"]))

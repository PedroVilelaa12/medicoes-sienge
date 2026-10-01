"""Linha de comando: medicoes lancar <lote.json> [--executar] [--falhar-em criacao|anexos|ambiguo].

Simulação é o padrão. Nesta versão a execução grava no Sienge falso (.medicoes/), o que
permite demonstrar falha, retomada e idempotência sem acesso ao Sienge real.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

from medicoes.config import Config
from medicoes.dinheiro import formatar_br, formatar_quantidade, ler_valor_br
from medicoes.dominio import Anexo, PedidoMedicao, Severidade, Status
from medicoes.estado import Armazem
from medicoes.orquestrador import Execucao, Orquestrador
from medicoes.sienge.falso import ClienteFalso

PASTA = Path(".medicoes")
ROTULOS = {
    Severidade.BLOQUEIA: "bloqueia",
    Severidade.ATENCAO: "atenção",
    Severidade.FORA_MVP: "fora do MVP",
    Severidade.PENDENCIA: "pendência",
}


def ler_anexo(base: Path, item: dict) -> Anexo:
    caminho = base / item["arquivo"]
    tipo = item["tipo"].upper()
    if caminho.is_file():
        conteudo = caminho.read_bytes()
        return Anexo(str(caminho), tipo, caminho.name, len(conteudo), hashlib.sha256(conteudo).hexdigest())
    # Arquivo de exemplo ausente: o hash usa o nome.
    return Anexo(
        str(caminho), tipo, caminho.name, int(item.get("tamanho_bytes", 0)),
        hashlib.sha256(caminho.name.encode("utf-8")).hexdigest(),
    )


def ler_lote(caminho: Path) -> list[PedidoMedicao]:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    pedidos = []
    for i, m in enumerate(dados["medicoes"], start=1):
        pedidos.append(PedidoMedicao(
            id=f"{caminho.stem}/{m.get('id', i)}",
            contrato=m.get("contrato"),
            valor=ler_valor_br(m["valor"]) if m.get("valor") else None,
            observacao=m.get("observacao"),
            anexos=[ler_anexo(caminho.parent, a) for a in m.get("anexos", [])],
            obra_id=m.get("obra"),
            confirmacoes=frozenset(m.get("confirmacoes", [])),
        ))
    return pedidos


def _status(e: Execucao) -> str:
    if e.status is Status.FALHOU and e.passo_falha:
        return f"Falhou em {e.passo_falha}"
    return e.status.value


def descrever(execucoes: list[Execucao], executar: bool) -> str:
    modo = "EXECUÇÃO no Sienge simulado" if executar else "SIMULAÇÃO: nada é gravado no Sienge"
    linhas = [f"Lote com {len(execucoes)} medições · {modo}"]
    for n, e in enumerate(execucoes, start=1):
        p = e.pedido
        fornecedor = e.contrato.fornecedor if e.contrato else (e.estado.fornecedor if e.estado else "")
        valor = formatar_br(p.valor) if p.valor is not None else "sem valor"
        cabecalho = " · ".join(x for x in (p.contrato or "sem contrato", fornecedor, valor) if x)
        numero = f" · medição nº {e.numero_sienge} no Sienge" if e.numero_sienge else ""
        linhas += ["", f"[{n}] {cabecalho}", f"    Status: {_status(e)}{numero}"]
        dados = e.resultado.preenchimento if e.resultado else None
        if dados is not None:
            linhas.append(f"    Obra {dados.obra.id} {dados.obra.nome}")
            linhas.append(f"    Item {dados.item.referencia} {dados.item.descricao} · saldo {formatar_br(dados.saldo)}")
            linhas.append(f"    Medição em {dados.data_medicao:%d/%m/%Y} · vencimento {dados.data_vencimento:%d/%m/%Y}")
            if dados.conversao is not None:
                linhas.append(
                    f"    Vai ao Sienge como quantidade {formatar_quantidade(dados.conversao.quantidade)}"
                    f" = {formatar_br(dados.conversao.valor_efetivo)}"
                )
            linhas.append(f"    Observação: {dados.observacao}")
        for a in e.alertas:
            confirmado = " (confirmado)" if a.severidade is Severidade.ATENCAO and a.codigo in p.confirmacoes else ""
            linhas.append(f"    {a.codigo} · {ROTULOS[a.severidade]}: {a.mensagem}{confirmado}")
        for passo in e.passos:
            linhas.append(f"    → {passo}")
    contagem = Counter("Falhou" if e.status is Status.FALHOU else e.status.value for e in execucoes)
    linhas += ["", "Resumo: " + " · ".join(f"{rotulo}: {qtd}" for rotulo, qtd in contagem.items())]
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medicoes", description="Lança medições de contratos no Sienge, em lote.")
    comandos = parser.add_subparsers(dest="comando", required=True)
    lancar = comandos.add_parser("lancar", help="valida e lança um lote (simulação por padrão)")
    lancar.add_argument("lote", type=Path, help="arquivo JSON do lote")
    lancar.add_argument("--executar", action="store_true", help="grava (nesta versão, no Sienge simulado)")
    lancar.add_argument(
        "--falhar-em", choices=["criacao", "anexos", "ambiguo"],
        help="simula uma falha para demonstrar a retomada",
    )
    comandos.add_parser("limpar", help="apaga o estado da demonstração (.medicoes/)")
    args = parser.parse_args(argv)

    if args.comando == "limpar":
        shutil.rmtree(PASTA, ignore_errors=True)
        print("Estado da demonstração apagado.")
        return 0

    cliente = ClienteFalso(PASTA / "sienge_falso.json")
    if args.falhar_em == "criacao":
        cliente.falhar("criacao")
    elif args.falhar_em == "anexos":
        cliente.falhar("anexos", depois_de=1)  # o 1º anexo vai, o 2º falha
    elif args.falhar_em == "ambiguo":
        cliente.ambiguas = 1  # grava, mas não responde
    orquestrador = Orquestrador(cliente, Armazem(PASTA / "estado.json"), Config())

    preparadas = orquestrador.preparar(ler_lote(args.lote))
    if args.executar:
        prontas = [e for e in preparadas if e.status is Status.PRONTA]
        retomadas = [e for e in preparadas if e.retomavel]
        total = sum((e.resultado.preenchimento.conversao.valor_efetivo for e in prontas), Decimal("0"))
        aviso = f"Confirmado com --executar: lançar {len(prontas)} medição(ões) pronta(s), total {formatar_br(total)}"
        if retomadas:
            aviso += f", e retomar {len(retomadas)} interrompida(s)"
        print(aviso + ".\n")
        execucoes = orquestrador.lancar(preparadas)
    else:
        execucoes = orquestrador.simular(preparadas)

    print(descrever(execucoes, args.executar))
    return 1 if any(e.status is Status.FALHOU for e in execucoes) else 0


if __name__ == "__main__":
    sys.exit(main())

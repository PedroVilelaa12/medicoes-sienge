from dataclasses import replace
from datetime import date
from decimal import Decimal as D

from apoio import anexo, pedido, relogio_fixo

from medicoes.config import Config
from medicoes.dominio import Anexo, ItemContrato, MedicaoSienge, Severidade, Status
from medicoes.orquestrador import carregar_contexto
from medicoes.regras import preenchimento
from medicoes.regras.validacoes import validar, validar_lote


def validar_no_falso(cliente, p):
    return validar(p, carregar_contexto(cliente, p), Config(), relogio_fixo)


def codigos(resultado):
    return {a.codigo for a in resultado.alertas}


def test_ct1241_preenche_tudo_a_partir_do_contrato(cliente):
    r = validar_no_falso(cliente, pedido("m1", "CT/1241", "264.66"))
    assert r.status is Status.PRONTA
    d = r.preenchimento
    assert d.obra.id == 480
    assert d.item.referencia == "00.000.000.002"
    assert d.saldo == D("288.74")
    assert d.data_medicao == date(2026, 10, 1)
    assert d.data_vencimento == date(2026, 10, 16)
    assert d.observacao == "Referente aos serviços prestados pelo ALFA SISTEMAS LTDA - Outubro/2026"
    criar = r.plano["criar_medicao"]
    assert criar["query"] == {"documentId": "CT", "contractNumber": "1241", "buildingId": 480}
    assert criar["corpo"]["items"] == [{"buildingUnitId": 1, "itemId": 2, "measuredQuantity": "264.6600"}]
    assert criar["corpo"]["makeUnauthorized"] is True
    assert [a["description"] for a in r.plano["anexos"]] == ["NF", "BOLETO"]


def test_valor_acima_do_saldo_bloqueia(cliente):
    r = validar_no_falso(cliente, pedido("m1", "CT/1241", "300.00"))
    assert r.status is Status.PRECISA_ATENCAO
    v8 = next(a for a in r.alertas if a.codigo == "V8")
    assert v8.severidade is Severidade.BLOQUEIA
    assert "acima do saldo do item (R$ 288,74)" in v8.mensagem


def test_caucao_fica_fora_do_mvp(cliente):
    r = validar_no_falso(cliente, pedido("m1", "CT/2088", "5000.00"))
    assert r.status is Status.FORA_MVP
    assert "V3" in codigos(r)


def test_contrato_desautorizado_bloqueia(cliente):
    r = validar_no_falso(cliente, pedido("m1", "CT/0977", "1000.00"))
    assert r.status is Status.PRECISA_ATENCAO
    assert any(a.codigo == "V1" and a.severidade is Severidade.BLOQUEIA for a in r.alertas)


def test_varias_unidades_construtivas_fica_fora_do_mvp(cliente):
    r = validar_no_falso(cliente, pedido("m1", "CT/3310", "1000.00"))
    assert r.status is Status.FORA_MVP
    assert "V4" in codigos(r)


def test_valor_nao_representavel_pede_confirmacao(cliente):
    r = validar_no_falso(cliente, pedido("m1", "CT/4102", "264.66"))
    assert r.status is Status.PRECISA_ATENCAO
    v17 = next(a for a in r.alertas if a.codigo == "V17")
    assert "R$ 264,64" in v17.mensagem
    confirmado = validar_no_falso(cliente, pedido("m1", "CT/4102", "264.66", confirmacoes=frozenset({"V17"})))
    assert confirmado.status is Status.PRONTA


def test_contrato_inexistente_bloqueia(cliente):
    r = validar_no_falso(cliente, pedido("m1", "CT/9999", "10.00"))
    assert r.status is Status.PRECISA_ATENCAO
    assert "V1" in codigos(r)


def test_falta_contrato_e_falta_valor(cliente):
    assert validar_no_falso(cliente, pedido("m1", None, "10.00")).status is Status.FALTA_CONTRATO
    assert validar_no_falso(cliente, pedido("m1", "CT/1241", None)).status is Status.FALTA_VALOR


def test_sem_anexo_pede_confirmacao(cliente):
    r = validar_no_falso(cliente, pedido("m1", "CT/1241", "264.66", anexos=[]))
    assert r.status is Status.PRECISA_ATENCAO
    assert "V11" in codigos(r)


def test_medicoes_anteriores_nao_finalizadas_bloqueiam(cliente):
    cliente.medicoes["CT/1241"][0] = replace(cliente.medicoes["CT/1241"][0], finalizada=False)
    r = validar_no_falso(cliente, pedido("m1", "CT/1241", "264.66"))
    assert r.status is Status.PRECISA_ATENCAO
    assert "V14" in codigos(r)


def test_medicao_posterior_liberada_bloqueia(cliente):
    cliente.medicoes["CT/1241"].append(MedicaoSienge(25, 480, date(2026, 10, 20), D("10.00"), D("10.00")))
    r = validar_no_falso(cliente, pedido("m1", "CT/1241", "264.66"))
    assert "V6" in codigos(r)


def test_anexo_acima_de_70_mb_bloqueia(cliente):
    grande = Anexo("nf.pdf", "NF", "nf.pdf", 71 * 1024 * 1024, "h")
    r = validar_no_falso(cliente, pedido("m1", "CT/1241", "264.66", anexos=[grande]))
    assert any(a.codigo == "V18" and a.severidade is Severidade.BLOQUEIA for a in r.alertas)


def test_item_mais_recente_prefere_o_aditivo():
    base = dict(descricao="x", quantidade_contratada=D("1"), quantidade_acumulada=D("0"), preco_unitario=D("1"))
    itens = [
        ItemContrato(1, "00.000.000.003", tem_aditivo=False, **base),
        ItemContrato(2, "00.000.000.002", tem_aditivo=True, **base),
    ]
    assert preenchimento.item_alvo(itens).id == 2


def test_item_alvo_e_o_que_ainda_tem_saldo():
    base = dict(descricao="x", quantidade_contratada=D("500"), preco_unitario=D("1"))
    itens = [
        ItemContrato(1, "00.000.000.001", tem_aditivo=False, quantidade_acumulada=D("100"), **base),
        ItemContrato(2, "00.000.000.002", tem_aditivo=True, quantidade_acumulada=D("500"), **base),
    ]
    assert preenchimento.item_alvo(itens).id == 1  # o mais recente está sem saldo


def test_item_alvo_prefere_o_item_cujo_saldo_comporta_o_valor():
    base = dict(descricao="x", preco_unitario=D("1"))
    itens = [
        ItemContrato(1, "00.000.000.001", tem_aditivo=False, quantidade_contratada=D("3042.36"), quantidade_acumulada=D("2788.83"), **base),
        ItemContrato(2, "00.000.000.002", tem_aditivo=True, quantidade_contratada=D("3000.00"), quantidade_acumulada=D("2900.00"), **base),
    ]
    assert preenchimento.item_alvo(itens, D("200.00")).id == 1  # só o 001 (saldo 253,53) comporta 200,00


def test_duplicidade_dentro_do_lote():
    mesmo = anexo("nf.pdf", "NF", "igual")
    alertas = validar_lote([
        pedido("m1", "CT/1241", "1", anexos=[mesmo]),
        pedido("m2", "CT/1241", "2", anexos=[mesmo]),
    ])
    assert len(alertas["m1"]) == 2
    assert {a.codigo for a in alertas["m2"]} == {"V10"}


def test_nome_de_anexo_longo_e_encurtado_preservando_extensao():
    nome = "a" * 120 + ".pdf"
    encurtado = preenchimento.nome_para_envio(nome, 100)
    assert len(encurtado) == 100 and encurtado.endswith(".pdf")

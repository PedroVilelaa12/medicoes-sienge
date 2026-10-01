from dataclasses import replace
from datetime import date
from decimal import Decimal as D

from apoio import anexo, pedido, relogio_fixo

from medicoes.config import Config
from medicoes.dominio import MedicaoSienge, Status
from medicoes.estado import Armazem
from medicoes.orquestrador import PASSO_ANEXOS, PASSO_CRIACAO, Orquestrador
from medicoes.sienge.falso import ClienteFalso


def posts_de_medicao(cliente):
    return [e for e in cliente.escritas if e.startswith("POST medição")]


def test_simulacao_nao_grava_nada(orquestrador, cliente):
    [e] = orquestrador.processar_lote([pedido("m1", "CT/1241", "264.66")])
    assert e.status is Status.PRONTA
    assert cliente.escritas == []
    assert any("Simulação" in passo for passo in e.passos)


def test_lancamento_completo_com_pendencia_de_avaliacao(orquestrador, cliente):
    [e] = orquestrador.processar_lote([pedido("m1", "CT/1241", "264.66")], executar=True)
    assert e.status is Status.LANCADA
    assert e.numero_sienge == 25
    assert len(posts_de_medicao(cliente)) == 1
    assert cliente.anexos[("CT/1241", 25)] == [("nf.pdf", "NF"), ("boleto.pdf", "BOLETO")]
    v19 = [a for a in e.alertas if a.codigo == "V19"]
    assert v19 and "avaliação do fornecedor" in v19[0].mensagem


def test_medicao_no_mes_exige_confirmacao_explicita(orquestrador, cliente):
    cliente.medicoes["CT/1241"].append(MedicaoSienge(25, 480, date(2026, 10, 1), D("100.00"), D("100.00")))
    [e] = orquestrador.processar_lote([pedido("m1", "CT/1241", "100.00")], executar=True)
    assert e.status is Status.PRECISA_ATENCAO
    assert any(a.codigo == "V5" for a in e.alertas)
    assert cliente.escritas == []

    confirmada = pedido("m2", "CT/1241", "100.00", confirmacoes=frozenset({"V5"}))
    [e2] = orquestrador.processar_lote([confirmada], executar=True)
    assert e2.status is Status.LANCADA


def test_falha_nos_anexos_retoma_sem_criar_outra_medicao(cliente, armazem):
    cliente.falhar("anexos", depois_de=1)  # a NF vai, o boleto falha
    orquestrador = Orquestrador(cliente, armazem, Config(), relogio_fixo)
    [primeira] = orquestrador.processar_lote([pedido("m1", "CT/1241", "264.66")], executar=True)
    assert primeira.status is Status.FALHOU
    assert primeira.passo_falha == PASSO_ANEXOS
    assert cliente.anexos[("CT/1241", 25)] == [("nf.pdf", "NF")]

    [retomada] = orquestrador.processar_lote([pedido("m1", "CT/1241", "264.66")], executar=True)
    assert retomada.status is Status.LANCADA
    assert len(posts_de_medicao(cliente)) == 1
    assert cliente.anexos[("CT/1241", 25)] == [("nf.pdf", "NF"), ("boleto.pdf", "BOLETO")]


def test_lote_com_falha_no_meio_segue_com_as_outras(cliente, armazem):
    cliente.falhar("criacao", depois_de=1)
    orquestrador = Orquestrador(cliente, armazem, Config(), relogio_fixo)
    lote = [
        pedido("m1", "CT/1241", "264.66"),
        pedido("m2", "CT/154", "2000.00"),
        pedido("m3", "CT/4102", "264.66", confirmacoes=frozenset({"V17"})),
    ]
    resultados = orquestrador.processar_lote(lote, executar=True)
    assert [r.status for r in resultados] == [Status.LANCADA, Status.FALHOU, Status.LANCADA]
    assert resultados[1].passo_falha == PASSO_CRIACAO
    assert "503" in resultados[1].erro


def test_post_sem_resposta_reconcilia_e_nao_duplica(cliente, armazem):
    cliente.ambiguas = 1  # o Sienge grava, mas a resposta não chega
    orquestrador = Orquestrador(cliente, armazem, Config(), relogio_fixo)
    [primeira] = orquestrador.processar_lote([pedido("m1", "CT/1241", "264.66")], executar=True)
    assert primeira.status is Status.FALHOU
    assert primeira.passo_falha == PASSO_CRIACAO
    assert len(posts_de_medicao(cliente)) == 1

    [retomada] = orquestrador.processar_lote([pedido("m1", "CT/1241", "264.66")], executar=True)
    assert retomada.status is Status.LANCADA
    assert retomada.numero_sienge == 25
    assert len(posts_de_medicao(cliente)) == 1
    assert any("já tinha sido criada" in passo for passo in retomada.passos)


def test_total_liquido_diferente_gera_alerta(orquestrador, cliente):
    cliente.ajuste_liquido = D("-15.00")
    [e] = orquestrador.processar_lote([pedido("m1", "CT/1241", "264.66")], executar=True)
    v12 = next(a for a in e.alertas if a.codigo == "V12")
    assert "R$ 15,00" in v12.mensagem


def test_medicao_lancada_nao_e_lancada_de_novo(orquestrador, cliente):
    orquestrador.processar_lote([pedido("m1", "CT/1241", "264.66")], executar=True)
    [de_novo] = orquestrador.processar_lote([pedido("m1", "CT/1241", "264.66")], executar=True)
    assert de_novo.status is Status.LANCADA
    assert len(posts_de_medicao(cliente)) == 1


def test_retomada_funciona_entre_execucoes_diferentes(tmp_path):
    cliente = ClienteFalso(tmp_path / "sienge.json")
    cliente.falhar("anexos", depois_de=1)
    Orquestrador(cliente, Armazem(tmp_path / "estado.json"), Config(), relogio_fixo).processar_lote(
        [pedido("m1", "CT/1241", "264.66")], executar=True
    )
    novo_cliente = ClienteFalso(tmp_path / "sienge.json")  # outro processo, lendo do disco
    [e] = Orquestrador(novo_cliente, Armazem(tmp_path / "estado.json"), Config(), relogio_fixo).processar_lote(
        [pedido("m1", "CT/1241", "264.66")], executar=True
    )
    assert e.status is Status.LANCADA
    assert novo_cliente.anexos[("CT/1241", 25)] == [("nf.pdf", "NF"), ("boleto.pdf", "BOLETO")]


def test_mesma_medicao_em_outro_pedido_nao_e_lancada_de_novo(orquestrador, cliente):
    docs = [anexo("nf.pdf", "NF", "m1"), anexo("boleto.pdf", "BOLETO", "m1")]
    orquestrador.processar_lote([pedido("m1", "CT/154", "2000.00", anexos=docs)], executar=True)
    # Camadas anteriores (V14: anterior não finalizada; V5: medição no mês) já barram a duplicata.
    # Aqui elas são superadas de propósito, para provar que a chave de idempotência segura sozinha.
    cliente.medicoes["CT/154"][-1] = replace(cliente.medicoes["CT/154"][-1], finalizada=True)
    [e] = orquestrador.processar_lote(
        [pedido("m2", "CT/154", "2000.00", anexos=docs, confirmacoes=frozenset({"V5"}))], executar=True
    )
    assert e.status is Status.FALHOU
    assert any("já ter sido lançada" in a.mensagem for a in e.alertas)
    assert len(posts_de_medicao(cliente)) == 1

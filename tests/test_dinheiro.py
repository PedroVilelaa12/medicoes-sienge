from decimal import Decimal as D

import pytest

from medicoes.dinheiro import formatar_br, ler_valor_br, valor_para_quantidade


def test_le_formato_brasileiro():
    assert ler_valor_br("3.042,36") == D("3042.36")
    assert ler_valor_br("R$ 264,66") == D("264.66")


def test_recusa_valor_invalido():
    with pytest.raises(ValueError):
        ler_valor_br("duzentos")


def test_recusa_ponto_como_centavos_para_nao_lancar_100_vezes_o_valor():
    with pytest.raises(ValueError, match="vírgula"):
        ler_valor_br("264.66")  # lido como milhar, viraria R$ 26.466,00
    assert ler_valor_br("1.500") == D("1500.00")  # ponto com 3 dígitos é milhar


def test_formata_em_reais():
    assert formatar_br(D("3042.36")) == "R$ 3.042,36"
    assert formatar_br(D("288.74")) == "R$ 288,74"
    assert formatar_br(D("1234567.8")) == "R$ 1.234.567,80"


def test_quantidade_com_4_casas_nem_sempre_representa_o_valor():
    quantidade, efetivo, diferenca = valor_para_quantidade(D("264.66"), D("3200.00"))
    assert quantidade == D("0.0827")
    assert efetivo == D("264.64")
    assert diferenca == D("-0.02")


def test_com_preco_unitario_1_o_valor_e_exato():
    quantidade, efetivo, diferenca = valor_para_quantidade(D("264.66"), D("1.00"))
    assert quantidade == D("264.6600")
    assert efetivo == D("264.66")
    assert diferenca == 0

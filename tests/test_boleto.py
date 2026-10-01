from datetime import date
from decimal import Decimal as D

import pytest

from medicoes.leitura.boleto import BoletoInvalido, ler_linha_digitavel

HOJE = date(2026, 10, 1)

# Vetor montado à mão, sem usar o código testado:
#   código de barras sem DV = 001 9 | fator 1601 | valor 0000026466 | campo livre 1234567890123456789012345
#   DV geral (módulo 11, pesos 2..9): soma 758, 758 % 11 = 10, 11 - 10 = 1
#   campo 1 "001912345" → módulo 10 = 4; campos 2 e 3 "6789012345" → módulo 10 = 7
#   fator 1601 no ciclo novo = 22/02/2025 + 601 dias = 16/10/2026
LINHA = "00191.23454 67890.123457 67890.123457 1 16010000026466"


def test_le_valor_e_vencimento_do_boleto():
    boleto = ler_linha_digitavel(LINHA, HOJE)
    assert boleto.banco == "001"
    assert boleto.valor == D("264.66")
    assert boleto.vencimento == date(2026, 10, 16)
    assert boleto.codigo_barras == "00191160100000264661234567890123456789012345"


def test_valor_adulterado_nao_fecha_o_dv_geral():
    with pytest.raises(BoletoInvalido, match="geral"):
        ler_linha_digitavel(LINHA.replace("26466", "26467"), HOJE)


def test_erro_de_digitacao_no_campo_1_e_detectado():
    with pytest.raises(BoletoInvalido, match="campo 1"):
        ler_linha_digitavel(LINHA.replace("00191.23454", "00191.23464"), HOJE)


def test_linha_incompleta_e_recusada():
    with pytest.raises(BoletoInvalido, match="47 dígitos"):
        ler_linha_digitavel(LINHA[:-3], HOJE)

from pathlib import Path

from medicoes.cli import main

LOTE = Path(__file__).resolve().parent.parent / "exemplos" / "lote.json"


def test_simula_o_lote_de_exemplo(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["lancar", str(LOTE)]) == 0
    saida = capsys.readouterr().out
    assert "SIMULAÇÃO" in saida
    assert "Item 00.000.000.002" in saida
    assert "Fora do MVP" in saida
    assert not (tmp_path / ".medicoes" / "sienge_falso.json").exists()


def test_valor_ambiguo_no_lote_para_com_mensagem_clara(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    lote = tmp_path / "lote.json"
    lote.write_text('{"medicoes": [{"id": "m1", "contrato": "CT/1241", "valor": "264.66"}]}', encoding="utf-8")
    assert main(["lancar", str(lote), "--executar"]) == 2
    erro = capsys.readouterr().err
    assert "medição m1 (CT/1241)" in erro and "vírgula" in erro
    assert not (tmp_path / ".medicoes" / "sienge_falso.json").exists()  # nada foi gravado

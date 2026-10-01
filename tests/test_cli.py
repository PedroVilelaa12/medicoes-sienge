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

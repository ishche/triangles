from domeprint.cli import main


def test_writes_svg(tmp_path, capsys):
    out = tmp_path / "t.svg"
    assert main(["120", "100", "100", "--tab", "5", "-o", str(out)]) == 0
    text = out.read_text()
    assert text.startswith("<?xml") and 'width="' in text and "mm" in text
    err = capsys.readouterr().err
    assert "angles" in err and "print at 100%" in err


def test_stdout_and_paper(capsysbinary):
    assert main(["50", "50", "50", "--paper", "a4"]) == 0
    assert b'width="210mm"' in capsysbinary.readouterr().out


def test_writes_pdf_by_extension(tmp_path):
    out = tmp_path / "t.pdf"
    assert main(["120", "100", "100", "--paper", "A4", "-o", str(out)]) == 0
    assert out.read_bytes().startswith(b"%PDF-1.7")


def test_format_flag_overrides_extension(tmp_path):
    out = tmp_path / "t.svg"
    assert main(["50", "50", "50", "--format", "pdf", "-o", str(out)]) == 0
    assert out.read_bytes().startswith(b"%PDF")


def test_invalid_triangle_exit_code(capsys):
    assert main(["1", "2", "3"]) == 2
    assert "triangle inequality" in capsys.readouterr().err


def test_truncation_warning(capsys):
    assert main(["20", "20", "20", "--tab", "8"]) == 0
    assert "warning: tab on edge AB truncated" in capsys.readouterr().err


def test_does_not_fit(capsys):
    assert main(["500", "500", "500", "--paper", "A4"]) == 2
    assert "does not fit" in capsys.readouterr().err

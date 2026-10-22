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
    out = capsysbinary.readouterr().out
    assert b'width="210mm"' in out or b'width="297mm"' in out


def test_default_fills_one_a4_sheet(tmp_path, capsys):
    from pypdf import PdfReader

    out = tmp_path / "sheet.pdf"
    assert main(["61.8", "54.7", "54.7", "-o", str(out)]) == 0
    reader = PdfReader(str(out))
    assert len(reader.pages) == 1
    box = reader.pages[0].mediabox
    assert sorted((round(float(box.width)), round(float(box.height)))) == [595, 842]  # A4
    assert "18 pieces on 1 sheet (as many as fit)" in capsys.readouterr().err


def test_count_one_centres_a_single_piece(tmp_path, capsys):
    out = tmp_path / "one.pdf"
    assert main(["120", "100", "100", "--count", "1", "-o", str(out)]) == 0
    assert "pieces on" not in capsys.readouterr().err


def test_tight_paper_still_available(tmp_path):
    out = tmp_path / "t.svg"
    assert main(["120", "100", "100", "--paper", "tight", "-o", str(out)]) == 0
    assert 'width="140mm"' in out.read_text()


def test_tight_paper_rejects_count(capsys):
    assert main(["50", "50", "50", "--paper", "tight", "--count", "3"]) == 2
    assert "tight" in capsys.readouterr().err


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


def test_count_packs_multiple_pieces_into_pdf(tmp_path, capsys):
    from pypdf import PdfReader

    out = tmp_path / "many.pdf"
    assert main(["61.8", "54.7", "54.7", "--tab", "5", "--count", "30", "-o", str(out)]) == 0
    reader = PdfReader(str(out))
    assert len(reader.pages) == 2  # 18 per landscape A4 sheet
    err = capsys.readouterr().err
    assert "30 pieces on 2 sheets" in err


def test_count_with_svg_writes_one_file_per_sheet(tmp_path):
    out = tmp_path / "many.svg"
    assert main(["61.8", "54.7", "54.7", "--count", "30", "-o", str(out)]) == 0
    assert (tmp_path / "many-1.svg").exists() and (tmp_path / "many-2.svg").exists()
    assert not out.exists()


def test_count_svg_to_stdout_needs_single_sheet(capsys):
    assert main(["61.8", "54.7", "54.7", "--count", "30"]) == 2
    assert "one sheet" in capsys.readouterr().err


def test_spacing_option(tmp_path):
    out = tmp_path / "s.pdf"
    assert main(["50", "50", "50", "--count", "10", "--spacing", "0", "-o", str(out)]) == 0


def test_bad_count(capsys):
    assert main(["50", "50", "50", "--count", "0"]) == 2

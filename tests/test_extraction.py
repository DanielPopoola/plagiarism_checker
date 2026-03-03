"""
tests/test_extraction.py
"""

import pytest

from app.services.extraction import extract_text, _normalise


class TestNormalise:
    def test_lowercases(self):
        assert _normalise("Hello WORLD") == "hello world"

    def test_strips_punctuation(self):
        result = _normalise("Hello, world! It's great.")
        assert "," not in result
        assert "!" not in result
        assert "'" not in result

    def test_collapses_whitespace(self):
        assert "  " not in _normalise("too   many    spaces")

    def test_strips_leading_trailing_whitespace(self):
        # "hello" is not a stop word
        assert _normalise("  hello  ") == "hello"

    def test_empty_string_returns_empty(self):
        assert _normalise("") == ""

    def test_unicode_normalised_to_ascii(self):
        result = _normalise("café résumé naïve")
        assert isinstance(result, str)
        assert "é" not in result

    def test_numbers_preserved(self):
        assert "42" in _normalise("There are 42 items.")

    def test_only_punctuation_returns_empty(self):
        assert _normalise("!!! ???") == ""


class TestExtractTxt:
    def test_reads_txt_content(self):
        result = extract_text(b"Hello World This Is A Test", "txt")
        assert "hello" in result
        assert "world" in result

    def test_normalisation_applied_to_txt(self):
        result = extract_text(b"UPPERCASE AND punctuation!!!", "txt")
        assert result == result.lower()
        assert "!" not in result

    def test_empty_txt_returns_empty_string(self):
        assert extract_text(b"", "txt") == ""

    def test_utf8_encoding_handled(self):
        result = extract_text("Content with unicode: café".encode("utf-8"), "txt")
        assert isinstance(result, str)


class TestExtractDocx:
    def test_reads_docx_paragraphs(self, tmp_path):
        pytest.importorskip("docx")
        from docx import Document
        import io
        path = tmp_path / "essay.docx"
        doc = Document()
        doc.add_paragraph("The mitochondria is the powerhouse of the cell.")
        doc.save(str(path))
        result = extract_text(path.read_bytes(), "docx")
        assert "mitochondria" in result

    def test_multipage_docx_concatenated(self, tmp_path):
        pytest.importorskip("docx")
        from docx import Document
        path = tmp_path / "multi.docx"
        doc = Document()
        for i in range(5):
            doc.add_paragraph(f"Paragraph number {i} with content.")
        doc.save(str(path))
        result = extract_text(path.read_bytes(), "docx")
        assert "paragraph" in result


class TestExtractPdf:
    def test_reads_pdf_text(self, tmp_path):
        pytest.importorskip("pypdf")
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        path = tmp_path / "essay.pdf"
        with open(str(path), "wb") as f:
            writer.write(f)
        result = extract_text(path.read_bytes(), "pdf")
        assert isinstance(result, str)


class TestExtractUnsupported:
    def test_unsupported_extension_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported"):
            extract_text(b"col1,col2", "csv")

    def test_unknown_extension_raises_value_error(self):
        with pytest.raises(ValueError):
            extract_text(b"data", "xyz")
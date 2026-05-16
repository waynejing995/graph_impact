import tempfile
import sys
import types
import unittest
from pathlib import Path

from asip.documents import convert_pdf_to_chunks


class DocumentConversionTests(unittest.TestCase):
    def test_text_based_pdf_fallback_preserves_page_metadata(self):
        pdf_text = """%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj
4 0 obj << /Length 61 >> stream
BT /F1 12 Tf 72 720 Td (AMD GCVM_L2_CNTL PDF evidence) Tj ET
endstream endobj
trailer << /Root 1 0 R >>
%%EOF
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "amd-register-note.pdf"
            pdf_path.write_text(pdf_text, encoding="latin-1")

            chunks = convert_pdf_to_chunks(pdf_path)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].page, 1)
        self.assertEqual(chunks[0].source_type, "pdf")
        self.assertIn("GCVM_L2_CNTL", chunks[0].text)

    def test_reportlab_ascii85_flate_pdf_fallback_extracts_text(self):
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
        except Exception as exc:
            self.skipTest(f"reportlab unavailable: {exc}")

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "compressed-reportlab.pdf"
            pdf = canvas.Canvas(str(pdf_path), pagesize=letter)
            pdf.drawString(72, 720, "AMD compressed PDF GCVM_L2_CNTL driver source tree")
            pdf.save()

            chunks = convert_pdf_to_chunks(pdf_path)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].source_type, "pdf")
        self.assertIn("GCVM_L2_CNTL", chunks[0].text)

    def test_pypdf_converter_preserves_multiple_pages(self):
        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakePdfReader:
            def __init__(self, _path):
                self.pages = [
                    FakePage("AMD Instinct MI300 overview"),
                    FakePage("GCVM_L2_CNTL register page evidence"),
                ]

        original = sys.modules.get("pypdf")
        sys.modules["pypdf"] = types.SimpleNamespace(PdfReader=FakePdfReader)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                pdf_path = Path(tmpdir) / "amd-mi300.pdf"
                pdf_path.write_bytes(b"%PDF-1.7 fake body for pypdf stub")

                chunks = convert_pdf_to_chunks(pdf_path)
        finally:
            if original is None:
                sys.modules.pop("pypdf", None)
            else:
                sys.modules["pypdf"] = original

        self.assertEqual([chunk.page for chunk in chunks], [1, 2])
        self.assertIn("MI300", chunks[0].text)
        self.assertIn("GCVM_L2_CNTL", chunks[1].text)

    def test_reduced_amd_pdf_fixture_is_extractable(self):
        repo_root = Path(__file__).resolve().parents[3]
        pdf_path = repo_root / "docs" / "fixtures" / "amd-amdgpu-docs" / "amdgpu-driver-source-tree.pdf"

        chunks = convert_pdf_to_chunks(pdf_path)

        self.assertGreater(len(chunks), 0)
        self.assertEqual(chunks[0].source_type, "pdf")
        self.assertIn("amdgpu documentation", chunks[0].text)
        self.assertIn("driver source tree", chunks[0].text)


if __name__ == "__main__":
    unittest.main()

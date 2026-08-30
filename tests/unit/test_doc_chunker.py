from types import ModuleType, SimpleNamespace
import sys
import unittest

from test_support import load_module


def load_chunker_module() -> ModuleType:
    constant_stub = ModuleType("constant")
    constant_stub.DOC_DEFAULT_SECTION = "Introduction"
    constant_stub.DOC_TABLE_MAX_CHARS = 4000

    services_stub = ModuleType("services")
    pdf_extractor_stub = ModuleType("services.pdf_extractor")
    pdf_extractor_stub.ExtractedBlock = object
    services_stub.pdf_extractor = pdf_extractor_stub

    names = ["constant", "services", "services.pdf_extractor"]
    previous_modules = {name: sys.modules.get(name) for name in names}
    try:
        sys.modules["constant"] = constant_stub
        sys.modules["services"] = services_stub
        sys.modules["services.pdf_extractor"] = pdf_extractor_stub
        return load_module("doc_chunker_under_test", "doc_agent/backend/services/chunker.py")
    finally:
        for name, previous in previous_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


chunker = load_chunker_module()

chunk_extracted_document = chunker.chunk_extracted_document
chunk_table = chunker.chunk_table
chunk_text = chunker.chunk_text
format_chunk = chunker.format_chunk


class DocumentChunkerTests(unittest.TestCase):
    def test_format_chunk_sanitizes_metadata_and_includes_body(self) -> None:
        chunk = format_chunk("  Annual | Report  ", " Risk | Factors ", "  Body text.  ")

        self.assertEqual(
            chunk,
            "Document: Annual / Report | Section: Risk / Factors\n\nBody text.",
        )

    def test_format_chunk_returns_header_for_empty_body(self) -> None:
        self.assertEqual(
            format_chunk("report.pdf", "", "   "),
            "Document: report.pdf | Section: Introduction",
        )

    def test_chunk_text_splits_with_overlap_and_preserves_text(self) -> None:
        text = "Alpha beta gamma. Delta epsilon zeta. Eta theta iota."
        chunks = chunk_text(text, chunk_chars=28, overlap=6)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(chunks[0].startswith("Alpha beta"))
        self.assertTrue(chunks[-1].endswith("theta iota."))
        self.assertTrue(all(chunk.strip() == chunk for chunk in chunks))

    def test_chunk_text_rejects_non_positive_chunk_size(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integer"):
            chunk_text("hello", chunk_chars=0, overlap=0)

    def test_chunk_table_repeats_markdown_header_when_splitting(self) -> None:
        table = "\n".join(
            [
                "| Ticker | Price |",
                "| --- | --- |",
                "| AAPL | 200 |",
                "| MSFT | 300 |",
                "| NVDA | 400 |",
            ]
        )

        chunks = chunk_table(table, max_chars=55)

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertTrue(chunk.startswith("| Ticker | Price |\n| --- | --- |"))

    def test_chunk_extracted_document_formats_prose_and_tables(self) -> None:
        blocks = [
            SimpleNamespace(kind="prose", section="Overview", text="One. Two. Three."),
            SimpleNamespace(kind="table", section="Metrics", text="| A | B |\n| --- | --- |\n| 1 | 2 |"),
        ]

        chunks = chunk_extracted_document(
            blocks,
            document_name="filing.pdf",
            chunk_chars=20,
            overlap=3,
        )

        self.assertTrue(all(chunk.startswith("Document: filing.pdf | Section:") for chunk in chunks))
        self.assertTrue(any("Section: Overview" in chunk for chunk in chunks))
        self.assertTrue(any("Section: Metrics" in chunk for chunk in chunks))


if __name__ == "__main__":
    unittest.main()

import unittest

from test_support import import_project_module

pdf_extractor = import_project_module("services.pdf_extractor", "common", "doc_agent/backend")
article_util = import_project_module("article_extractor.util", "common")
article_extractor = import_project_module("article_extractor.extractor", "common")


class PdfExtractorTests(unittest.TestCase):
    def test_parse_markdown_blocks_tracks_headings_and_tables(self) -> None:
        markdown = """
# Overview
First paragraph.

| Metric | Value |
| --- | --- |
| Revenue | 10 |

## Risk Factors
Risk text.
"""
        blocks = pdf_extractor.parse_markdown_blocks(markdown)

        self.assertEqual([block.kind for block in blocks], ["prose", "table", "prose"])
        self.assertEqual(blocks[0].section, "Overview")
        self.assertEqual(blocks[1].section, "Overview")
        self.assertEqual(blocks[2].section, "Risk Factors")

    def test_parse_markdown_blocks_combines_item_heading_with_next_line(self) -> None:
        blocks = pdf_extractor.parse_markdown_blocks("ITEM 7\nManagement Discussion\nThe company grew.")
        self.assertEqual(blocks[0].section, "Item 7. Management Discussion")

    def test_extract_pdf_markdown_rejects_non_pdf_magic(self) -> None:
        with self.assertRaises(pdf_extractor.PdfExtractError):
            pdf_extractor.extract_pdf_markdown(b"not a pdf")


class ArticleExtractorUtilTests(unittest.TestCase):
    def test_clean_text_and_truncate(self) -> None:
        self.assertEqual(article_util.clean_text(" A   B\n\n\nC "), "A B\n\nC")
        self.assertEqual(article_util.truncate("abcdef", 4), "abcd...")

    def test_usable_article_text_rejects_short_or_blocked_pages(self) -> None:
        self.assertFalse(article_util.is_usable_article_text("short", min_chars=20))
        self.assertFalse(article_util.is_usable_article_text("Please enable JavaScript " * 10, min_chars=20))
        self.assertTrue(article_util.is_usable_article_text("Real article content " * 10, min_chars=20))

    def test_safe_article_url_rejects_local_and_non_http_urls(self) -> None:
        self.assertFalse(article_util.is_safe_article_url("file:///etc/passwd"))
        self.assertFalse(article_util.is_safe_article_url("http://localhost/a"))

    def test_article_extractor_returns_none_for_blank_or_failed_download(self) -> None:
        extractor = article_extractor.ArticleExtractor()
        extractor._download = lambda url: None
        self.assertIsNone(extractor.extract(" "))
        self.assertIsNone(extractor.extract("https://example.com/a"))

    def test_article_extractor_cleans_and_truncates_extracted_text(self) -> None:
        extractor = article_extractor.ArticleExtractor(max_chars=25)
        extractor._download = lambda url: "<html></html>"
        article_extractor.trafilatura.extract = lambda *_args, **_kwargs: "Real   article text " * 20
        result = extractor.extract("https://example.com/a")
        self.assertTrue(result.startswith("Real article text"))
        self.assertTrue(result.endswith("..."))


if __name__ == "__main__":
    unittest.main()

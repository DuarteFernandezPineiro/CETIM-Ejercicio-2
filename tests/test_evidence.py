import unittest

from app.index import Passage
from app.main import GeneratedAnswer, cite_answer


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.passages = [
            Passage("test.pdf", "Study", 2, "The sensor is described in Methods."),
            Passage("test.pdf", "Study", 6, "The device covers wavelengths between 350 and 2500 nm."),
        ]

    def test_returns_exact_quote_and_its_own_page(self):
        generated = GeneratedAnswer(
            evidence=["WAVELENGTHS  between 350 and 2500 nm"], answer="350–2500 nm"
        )
        result = cite_answer(generated, self.passages)
        self.assertEqual(result.answer, "350–2500 nm [2]")
        source, = result.sources
        self.assertEqual((source.document, source.page), ("test.pdf", 6))
        self.assertEqual(source.quotes, ["wavelengths between 350 and 2500 nm"])
        self.assertIn(source.quotes[0], source.excerpt)

    def test_abstains_when_any_quote_is_invented(self):
        generated = GeneratedAnswer(
            evidence=["The sensor is described in Methods.", "The device reaches 3000 nm."],
            answer="3000 nm",
        )
        result = cite_answer(generated, self.passages)
        self.assertEqual(result.answer, "No hay evidencia suficiente en los documentos.")
        self.assertEqual(result.sources, [])

    def test_abstains_when_a_cited_quote_does_not_contain_the_answer_value(self):
        generated = GeneratedAnswer(
            evidence=["The device covers wavelengths between 350 and 2500 nm."],
            answer="350–3000 nm",
        )
        result = cite_answer(generated, self.passages)
        self.assertEqual(result.sources, [])

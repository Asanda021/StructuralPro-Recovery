"""Regression for PDF dimension text: candidate extraction is never approved BOQ.

The real privately supplied naghshe.pdf p19 contains these three dimensions in
the extracted text stream. No private PDF content or binary is published.
"""
import unittest

from core.drawings.pdf_takeoff import PDFPageInfo, PDFTakeoffAdapter


class PDFDimensionTextRegressionTests(unittest.TestCase):
    def setUp(self):
        self.adapter = PDFTakeoffAdapter()

    def extract(self, text):
        return self.adapter.measurements([PDFPageInfo(19, 595.0, 842.0, text)])

    def test_original_pdf_page19_three_dimensions_without_first_digit_loss(self):
        # PDF extraction can concatenate m and the next label L= without a space.
        text = "L= 10.70 m C-1 4 C-2 L= 14.00 mL= 12.00 m C-3"
        actual = self.extract(text)
        self.assertEqual([x.value for x in actual], [10.70, 14.00, 12.00])
        self.assertEqual([x.unit for x in actual], ["m", "m", "m"])
        self.assertEqual([x.page for x in actual], [19, 19, 19])
        self.assertTrue(all(x.source == "pdf-text" for x in actual))
        self.assertTrue(all(x.confidence < 1 for x in actual))

    def test_digits_and_label_do_not_consume_significant_prefix(self):
        actual = self.extract("Wall Width 10.70 m, 1000mm, 45 cm, 12.00m")
        self.assertEqual([x.value for x in actual], [10.70, 1.0, 0.45, 12.0])
        self.assertEqual(actual[0].label, "Wall Width")

    def test_persian_digits_decimal_and_unit_spelling(self):
        actual = self.extract("ارتفاع ۱۲٫۵ متر\nعرض ۲۵ سانتی‌متر\nضخامت ۸ میلی متر")
        self.assertEqual([x.value for x in actual], [12.5, 0.25, 0.008])

    def test_no_unit_no_numeric_guess_and_no_partial_embedded_match(self):
        self.assertEqual(self.extract("410 420 170"), [])
        self.assertEqual(self.extract("A10.70 m -12m 33m2 3meter"), [])

    def test_text_candidates_require_confirmation(self):
        pages = [PDFPageInfo(19, 595.0, 842.0, "L= 10.70 m")]
        candidates = self.adapter.text_takeoff_candidates(pages)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["quantity"], 10.70)
        self.assertEqual(candidates[0]["source"], "pdf:p19")
        self.assertTrue(candidates[0]["needs_confirmation"])


if __name__ == "__main__":
    unittest.main()

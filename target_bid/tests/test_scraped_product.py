from django.test import SimpleTestCase

from target_bid.models.scraped_product import (
    GemilangProduct,
    JuraganMaterialProduct,
    Mitra10Product,
    ScrapedProduct,
    TokopediaProduct,
)


class ScrapedProductModelTests(SimpleTestCase):
    def test_model_fields_exist_and_is_abstract(self):
        fields = [f.name for f in ScrapedProduct._meta.get_fields()]
        expected_fields = [
            "id", "name", "price", "unit", "category",
            "url", "location", "created_at", "updated_at"
        ]
        for field in expected_fields:
            self.assertIn(field, fields)
        self.assertTrue(ScrapedProduct._meta.abstract)

    def test_concrete_models_have_correct_meta(self):
        self.assertEqual(JuraganMaterialProduct._meta.db_table, "juragan_material_products")
        self.assertEqual(Mitra10Product._meta.db_table, "mitra10_products")
        self.assertEqual(TokopediaProduct._meta.db_table, "tokopedia_products")
        self.assertEqual(GemilangProduct._meta.db_table, "gemilang_products")
        self.assertFalse(JuraganMaterialProduct._meta.managed)
        self.assertFalse(GemilangProduct._meta.managed)

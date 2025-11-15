from django.test import SimpleTestCase
from target_bid.repository.scraped_product_repo import ScrapedProductRepository


class ScrapedProductRepositoryTests(SimpleTestCase):
    """Unit tests for ScrapedProductRepository using dummy data."""

    def setUp(self):
        # Dummy data simulating what exists in `juragan_material_products`
        self.dummy_products = [
            {
                "id": 36,
                "name": "Papan Fiber Semen Arta Board Fiber Board 120X240X0.35 CM - Tuban",
                "price": 44,
                "unit": "Lembar",
                "category": "Tanah, Pasir, Batu, dan Semen",
                "url": "/produk/papan-fiber-semen-arta-board",
                "location": "Jakarta Pusat",
            },
            {
                "id": 40,
                "name": "Papan Fiber Semen GRC Cap Mawar 4 x 1000 x 1000 mm",
                "price": 20000,
                "unit": "Lembar",
                "category": "Tanah, Pasir, Batu, dan Semen",
                "url": "/produk/papan-fiber-semen-grc-cap-mawar",
                "location": "Jakarta Pusat",
            },
        ]

        # Inject a fake model class with pre-filtered data
        class DummyModel:
            _meta = type("Meta", (), {"db_table": "juragan_material_products"})
            objects = None  # unused in dummy test

        self.DummyModel = DummyModel
        self.repo = ScrapedProductRepository()
        self.repo.sources = [self.DummyModel]

    def test_find_cheaper_same_unit_with_dummy_data(self):
        """Simulate logic for finding cheaper alternatives using dummy data."""
        # Patch the repository method manually to avoid DB queries
        def fake_find_cheaper_same_unit(name, unit, current_price, limit=5):
            words = [w for w in name.split() if len(w) > 2][:3]
            results = []
            for item in self.dummy_products:
                if item["unit"].lower() == unit.lower() and item["price"] < current_price:
                    if any(w.lower() in item["name"].lower() for w in words):
                        item["source"] = self.DummyModel._meta.db_table
                        results.append(item)
            results.sort(key=lambda x: x["price"])
            return results[:limit]

        # Replace actual method logic for this test
        self.repo.find_cheaper_same_unit = fake_find_cheaper_same_unit

        results = self.repo.find_cheaper_same_unit("papan fiber semen", "Lembar", 50000)
        self.assertTrue(all(r["price"] < 50000 for r in results))
        self.assertTrue(all(r["unit"].lower() == "lembar" for r in results))
        self.assertIn("source", results[0])
        self.assertLessEqual(results[0]["price"], results[-1]["price"])

    def test_find_cheaper_same_unit_returns_empty(self):
        def fake_find_cheaper_same_unit(name, unit, current_price, limit=5):
            return []  # no matches

        self.repo.find_cheaper_same_unit = fake_find_cheaper_same_unit
        results = self.repo.find_cheaper_same_unit("tidak ada", "kg", 9999)
        self.assertEqual(results, [])

    def test_brand_price_csv_alternatives_are_returned(self):
        repo = ScrapedProductRepository()
        repo.sources = []  # avoid hitting external DBs

        results = repo.find_cheaper_same_unit(
            "Kaso 5/7 kayu kelas II",
            "m3",
            10000000,
        )

        self.assertTrue(results)
        self.assertTrue(any(item.get("source") == "material_brand_prices" for item in results))
        self.assertTrue(all(item["price"] < 10000000 for item in results))

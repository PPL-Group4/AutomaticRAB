from decimal import Decimal
from unittest import TestCase
from efficiency_recommendations.services.top_cost_contributors_identifier import identify_top_cost_contributors


class TopCostContributorsIdentifierTest(TestCase):
    def setUp(self):
        """Set up test data with 5 items"""
        self.job_data = {
            'job_id': 1,
            'job_name': 'Proyek Pembangunan Gedung Perkantoran',
            'total_cost': Decimal('755000000'),
            'items': [
                {
                    'name': 'Pekerjaan Struktur Bangunan',
                    'cost': Decimal('500000000'),
                    'weight_pct': Decimal('66.23'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('500000000')
                },
                {
                    'name': 'Pekerjaan Pondasi',
                    'cost': Decimal('150000000'),
                    'weight_pct': Decimal('19.87'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('150000000')
                },
                {
                    'name': 'Pemasangan Atap',
                    'cost': Decimal('80000000'),
                    'weight_pct': Decimal('10.60'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('80000000')
                },
                {
                    'name': 'Pengecatan Dinding',
                    'cost': Decimal('15000000'),
                    'weight_pct': Decimal('1.99'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('15000000')
                },
                {
                    'name': 'Galian Tanah',
                    'cost': Decimal('10000000'),
                    'weight_pct': Decimal('1.32'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('10000000')
                }
            ]
        }

    def test_identify_top_3_cost_contributors(self):
        """Test basic functionality: should return top 3 items by weight_pct"""
        result = identify_top_cost_contributors(self.job_data)

        # Should have top_items key
        self.assertIn('top_items', result)

        # Should return exactly 3 items
        top_items = result['top_items']
        self.assertEqual(len(top_items), 3)

        # First item should be Pekerjaan Struktur Bangunan (66.23%)
        self.assertEqual(top_items[0]['name'], 'Pekerjaan Struktur Bangunan')
        self.assertEqual(top_items[0]['weight_pct'], Decimal('66.23'))

        # Second item should be Pekerjaan Pondasi (19.87%)
        self.assertEqual(top_items[1]['name'], 'Pekerjaan Pondasi')
        self.assertEqual(top_items[1]['weight_pct'], Decimal('19.87'))

        # Third item should be Pemasangan Atap (10.60%)
        self.assertEqual(top_items[2]['name'], 'Pemasangan Atap')
        self.assertEqual(top_items[2]['weight_pct'], Decimal('10.60'))

    def test_items_are_sorted_by_weight_pct_descending(self):
        """Test that items are sorted from highest to lowest weight_pct"""
        result = identify_top_cost_contributors(self.job_data)
        top_items = result['top_items']

        # Verify sorting: each item should have weight_pct >= next item
        for i in range(len(top_items) - 1):
            current_weight = top_items[i]['weight_pct']
            next_weight = top_items[i + 1]['weight_pct']
            self.assertGreaterEqual(
                current_weight,
                next_weight,
                f"Item at index {i} has lower weight than item at {i+1}"
            )

    def test_result_includes_job_metadata(self):
        """Test that result includes job_id, job_name, and total_cost"""
        result = identify_top_cost_contributors(self.job_data)

        self.assertEqual(result['job_id'], 1)
        self.assertEqual(result['job_name'], 'Proyek Pembangunan Gedung Perkantoran')
        self.assertEqual(result['total_cost'], Decimal('755000000'))

    def test_each_item_has_all_required_fields(self):
        """Test that each item in top_items has all necessary fields"""
        result = identify_top_cost_contributors(self.job_data)
        top_items = result['top_items']

        required_fields = ['name', 'cost', 'weight_pct', 'quantity', 'unit_price']

        for item in top_items:
            for field in required_fields:
                self.assertIn(
                    field,
                    item,
                    f"Item '{item.get('name', 'Unknown')}' missing field '{field}'"
                )

    def test_handles_job_with_less_than_3_items(self):
        """Test edge case: job with only 2 items should return 2 items"""
        job_data_2_items = {
            'job_id': 2,
            'job_name': 'Proyek Renovasi Kecil',
            'total_cost': Decimal('100000000'),
            'items': [
                {
                    'name': 'Pemasangan Keramik',
                    'cost': Decimal('60000000'),
                    'weight_pct': Decimal('60.00'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('60000000')
                },
                {
                    'name': 'Pemasangan Pintu',
                    'cost': Decimal('40000000'),
                    'weight_pct': Decimal('40.00'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('40000000')
                }
            ]
        }

        result = identify_top_cost_contributors(job_data_2_items)
        top_items = result['top_items']

        # Should return only 2 items (not 3)
        self.assertEqual(len(top_items), 2)
        self.assertEqual(top_items[0]['name'], 'Pemasangan Keramik')
        self.assertEqual(top_items[1]['name'], 'Pemasangan Pintu')

    def test_handles_empty_items_list(self):
        """Test edge case: job with no items should return empty list"""
        job_data_empty = {
            'job_id': 3,
            'job_name': 'Proyek Kosong',
            'total_cost': Decimal('0'),
            'items': []
        }

        result = identify_top_cost_contributors(job_data_empty)

        # Should return empty list for top_items
        self.assertEqual(result['top_items'], [])

        # Job metadata should still be present
        self.assertEqual(result['job_id'], 3)
        self.assertEqual(result['job_name'], 'Proyek Kosong')

    def test_handles_job_with_exactly_3_items(self):
        """Test boundary case: job with exactly 3 items"""
        job_data_3_items = {
            'job_id': 4,
            'job_name': 'Proyek Renovasi Rumah',
            'total_cost': Decimal('300000000'),
            'items': [
                {
                    'name': 'Pekerjaan Plafon',
                    'cost': Decimal('150000000'),
                    'weight_pct': Decimal('50.00'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('150000000')
                },
                {
                    'name': 'Pemasangan Lantai',
                    'cost': Decimal('90000000'),
                    'weight_pct': Decimal('30.00'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('90000000')
                },
                {
                    'name': 'Pekerjaan Listrik',
                    'cost': Decimal('60000000'),
                    'weight_pct': Decimal('20.00'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('60000000')
                }
            ]
        }

        result = identify_top_cost_contributors(job_data_3_items)
        top_items = result['top_items']

        # Should return all 3 items
        self.assertEqual(len(top_items), 3)

    def test_does_not_modify_original_job_data(self):
        """Test that the function does not mutate the input data"""
        original_items_count = len(self.job_data['items'])
        original_first_item = self.job_data['items'][0].copy()

        _ = identify_top_cost_contributors(self.job_data)

        # Original data should remain unchanged
        self.assertEqual(len(self.job_data['items']), original_items_count)
        self.assertEqual(self.job_data['items'][0], original_first_item)

    def test_sorting_works_with_random_order(self):
        """Test that sorting works correctly when items are in random order"""
        job_data_random = {
            'job_id': 5,
            'job_name': 'Proyek dengan Item Acak',
            'total_cost': Decimal('500000000'),
            'items': [
                # Items intentionally in random order by weight_pct
                {
                    'name': 'Item Sedang',
                    'cost': Decimal('100000000'),
                    'weight_pct': Decimal('20.00'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('100000000')
                },
                {
                    'name': 'Item Terbesar',
                    'cost': Decimal('250000000'),
                    'weight_pct': Decimal('50.00'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('250000000')
                },
                {
                    'name': 'Item Terkecil',
                    'cost': Decimal('50000000'),
                    'weight_pct': Decimal('10.00'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('50000000')
                },
                {
                    'name': 'Item Kedua Terbesar',
                    'cost': Decimal('100000000'),
                    'weight_pct': Decimal('20.00'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('100000000')
                }
            ]
        }

        result = identify_top_cost_contributors(job_data_random)
        top_items = result['top_items']

        # Should return top 3
        self.assertEqual(len(top_items), 3)

        # First should be Item Terbesar (50%)
        self.assertEqual(top_items[0]['name'], 'Item Terbesar')
        self.assertEqual(top_items[0]['weight_pct'], Decimal('50.00'))

        # Second and third should be the 20% items (either order is fine for ties)
        self.assertEqual(top_items[1]['weight_pct'], Decimal('20.00'))
        self.assertEqual(top_items[2]['weight_pct'], Decimal('20.00'))

        # Item Terkecil (10%) should NOT be in top 3
        item_names = [item['name'] for item in top_items]
        self.assertNotIn('Item Terkecil', item_names)

    def test_sorting_with_unsorted_descending_order(self):
        """Test sorting when items are in reverse order (cheapest to most expensive)"""
        job_data_reversed = {
            'job_id': 6,
            'job_name': 'Proyek Urutan Terbalik',
            'total_cost': Decimal('300000000'),
            'items': [
                {
                    'name': 'Item Paling Murah',
                    'cost': Decimal('30000000'),
                    'weight_pct': Decimal('10.00'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('30000000')
                },
                {
                    'name': 'Item Menengah Bawah',
                    'cost': Decimal('60000000'),
                    'weight_pct': Decimal('20.00'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('60000000')
                },
                {
                    'name': 'Item Menengah Atas',
                    'cost': Decimal('90000000'),
                    'weight_pct': Decimal('30.00'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('90000000')
                },
                {
                    'name': 'Item Paling Mahal',
                    'cost': Decimal('120000000'),
                    'weight_pct': Decimal('40.00'),
                    'quantity': Decimal('1'),
                    'unit_price': Decimal('120000000')
                }
            ]
        }

        result = identify_top_cost_contributors(job_data_reversed)
        top_items = result['top_items']

        # Should correctly identify top 3 despite reverse order
        self.assertEqual(len(top_items), 3)

        # First should be Item Paling Mahal (40%)
        self.assertEqual(top_items[0]['name'], 'Item Paling Mahal')
        self.assertEqual(top_items[0]['weight_pct'], Decimal('40.00'))

        # Second should be Item Menengah Atas (30%)
        self.assertEqual(top_items[1]['name'], 'Item Menengah Atas')
        self.assertEqual(top_items[1]['weight_pct'], Decimal('30.00'))

        # Third should be Item Menengah Bawah (20%)
        self.assertEqual(top_items[2]['name'], 'Item Menengah Bawah')
        self.assertEqual(top_items[2]['weight_pct'], Decimal('20.00'))

        # Item Paling Murah should NOT be in top 3
        item_names = [item['name'] for item in top_items]
        self.assertNotIn('Item Paling Murah', item_names)

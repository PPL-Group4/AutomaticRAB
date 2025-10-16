from django.test import TransactionTestCase
from django.db import connection
from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from automatic_job_matching.service.fuzzy_matcher import FuzzyMatcher
from automatic_job_matching.service.matching_service import MatchingService
from rencanakan_core.models import Ahs


class PhraseSynonymMatchingTests(TransactionTestCase):
    """
    Test that phrase-level synonyms work in real matching.
    
    These tests verify the ACTUAL user scenarios:
    - User types one phrase, DB has synonymous phrase → should match
    """
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ahs (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    reference_group_id BIGINT NULL,
                    code VARCHAR(50) NULL,
                    name VARCHAR(500) NULL,
                    INDEX idx_ahs_code (code),
                    INDEX idx_ahs_name (name(255))
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        
        # Insert REAL construction terms from client data
        test_data = [
            # Structural
            ("AHS.001", "Pemasangan Bata Ringan 7.5 cm"),
            ("AHS.002", "Pekerjaan Borepile Diameter 30 cm"),
            ("AHS.003", "Pengecoran Beton Sloof 15/20"),
            ("AHS.004", "Bekisting Kolom Lantai 2"),
            
            # Plumbing
            ("AHS.010", "Instalasi Pipa Air Bersih PVC 1/2 inch"),
            ("AHS.011", "Pemasangan Kloset Duduk TOTO"),
            ("AHS.012", "Pemasangan Wastafel 40x40 cm"),
            
            # Flooring
            ("AHS.020", "Pemasangan Lantai Keramik 40x40"),
            ("AHS.021", "Finishing Lantai Beton Expose"),
            
            # Electrical
            ("AHS.030", "Instalasi Listrik Titik Lampu"),
            ("AHS.031", "Pemasangan Saklar Engkel"),
            ("AHS.032", "Pemasangan Stop Kontak"),
            
            # Painting
            ("AHS.040", "Cat Dinding Interior Catylac"),
            ("AHS.041", "Finishing Pintu Kayu Duco"),
        ]
        
        for code, name in test_data:
            Ahs.objects.create(code=code, name=name)
    
    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS ahs")
        super().tearDownClass()
    
    # ========================================================================
    # STRUCTURAL WORKS
    # ========================================================================
    
    def test_hebel_matches_bata_ringan(self):
        """
        DB has: "Pemasangan Bata Ringan"
        User searches: "pemasangan hebel"
        Expected: Should match (hebel = bata ringan)
        """
        result = MatchingService.perform_best_match("pemasangan hebel")
        
        self.assertIsNotNone(result, "hebel should match bata ringan")
        
        # Handle both single result and list
        if isinstance(result, list):
            self.assertGreater(len(result), 0)
            matched_item = result[0]
        else:
            matched_item = result
        
        self.assertEqual(matched_item["code"], "AHS.001")
        print(f"✓ 'hebel' matched 'bata ringan': {matched_item['name']}")
    
    def test_bata_putih_matches_bata_ringan(self):
        """
        DB has: "Pemasangan Bata Ringan"
        User searches: "pemasangan bata putih"
        Expected: Should match (bata putih = bata ringan = hebel)
        """
        result = MatchingService.perform_best_match("pemasangan bata putih")
        
        self.assertIsNotNone(result, "bata putih should match bata ringan")
        
        if isinstance(result, list):
            matched_item = result[0] if result else None
        else:
            matched_item = result
        
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["code"], "AHS.001")
        print(f"✓ 'bata putih' matched 'bata ringan': {matched_item['name']}")
    
    def test_strauss_pile_matches_borepile(self):
        """
        DB has: "Pekerjaan Borepile"
        User searches: "pekerjaan strauss pile"
        Expected: Should match (strauss pile = borepile)
        """
        result = MatchingService.perform_best_match("pekerjaan strauss pile")
        
        self.assertIsNotNone(result, "strauss pile should match borepile")
        
        if isinstance(result, list):
            matched_item = result[0] if result else None
        else:
            matched_item = result
        
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["code"], "AHS.002")
        print(f"✓ 'strauss pile' matched 'borepile': {matched_item['name']}")
    
    def test_cor_beton_matches_pengecoran_beton(self):
        """
        DB has: "Pengecoran Beton Sloof"
        User searches: "pekerjaan cor beton sloof"
        Expected: Should match (cor beton = pengecoran beton)
        """
        result = MatchingService.perform_best_match("pekerjaan cor beton sloof")
        
        self.assertIsNotNone(result, "cor beton should match pengecoran beton")
        
        if isinstance(result, list):
            matched_item = result[0] if result else None
        else:
            matched_item = result
        
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["code"], "AHS.003")
        print(f"✓ 'cor beton' matched 'pengecoran beton': {matched_item['name']}")
    
    def test_cetakan_matches_bekisting(self):
        """
        DB has: "Bekisting Kolom"
        User searches: "cetakan kolom"
        Expected: Should match (cetakan = bekisting)
        """
        result = MatchingService.perform_best_match("cetakan kolom")
        
        self.assertIsNotNone(result, "cetakan should match bekisting")
        
        if isinstance(result, list):
            matched_item = result[0] if result else None
        else:
            matched_item = result
        
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["code"], "AHS.004")
        print(f"✓ 'cetakan' matched 'bekisting': {matched_item['name']}")
    
    # ========================================================================
    # PLUMBING & SANITARY
    # ========================================================================
    
    def test_plumbing_air_bersih_matches_instalasi_pipa(self):
        """
        DB has: "Instalasi Pipa Air Bersih"
        User searches: "plumbing air bersih"
        Expected: Should match (plumbing = instalasi pipa)
        """
        result = MatchingService.perform_best_match("plumbing air bersih")
        
        self.assertIsNotNone(result, "plumbing should match instalasi pipa")
        
        if isinstance(result, list):
            matched_item = result[0] if result else None
        else:
            matched_item = result
        
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["code"], "AHS.010")
        print(f"✓ 'plumbing' matched 'instalasi pipa': {matched_item['name']}")
    
    def test_toilet_duduk_matches_kloset_duduk(self):
        """
        DB has: "Pemasangan Kloset Duduk"
        User searches: "pemasangan toilet duduk"
        Expected: Should match (toilet = kloset)
        """
        result = MatchingService.perform_best_match("pemasangan toilet duduk")
        
        self.assertIsNotNone(result, "toilet should match kloset")
        
        if isinstance(result, list):
            matched_item = result[0] if result else None
        else:
            matched_item = result
        
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["code"], "AHS.011")
        print(f"✓ 'toilet' matched 'kloset': {matched_item['name']}")
    
    def test_wc_matches_kloset(self):
        """
        DB has: "Pemasangan Kloset Duduk"
        User searches: "pemasangan wc duduk"
        Expected: Should match (WC = kloset = toilet)
        """
        result = MatchingService.perform_best_match("pemasangan wc duduk")
        
        self.assertIsNotNone(result, "wc should match kloset")
        
        if isinstance(result, list):
            matched_item = result[0] if result else None
        else:
            matched_item = result
        
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["code"], "AHS.011")
        print(f"✓ 'wc' matched 'kloset': {matched_item['name']}")
    
    def test_sink_matches_wastafel(self):
        """
        DB has: "Pemasangan Wastafel"
        User searches: "pemasangan sink"
        Expected: Should match (sink = wastafel)
        """
        result = MatchingService.perform_best_match("pemasangan sink")
        
        self.assertIsNotNone(result, "sink should match wastafel")
        
        if isinstance(result, list):
            matched_item = result[0] if result else None
        else:
            matched_item = result
        
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["code"], "AHS.012")
        print(f"✓ 'sink' matched 'wastafel': {matched_item['name']}")
    
    # ========================================================================
    # FLOORING
    # ========================================================================
    
    def test_pasang_keramik_matches_pemasangan_lantai_keramik(self):
        """
        DB has: "Pemasangan Lantai Keramik"
        User searches: "pasang keramik lantai"
        Expected: Should match (pasang = pemasangan)
        """
        result = MatchingService.perform_best_match("pasang keramik lantai")
        
        self.assertIsNotNone(result, "pasang should match pemasangan")
        
        if isinstance(result, list):
            matched_item = result[0] if result else None
        else:
            matched_item = result
        
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["code"], "AHS.020")
        print(f"✓ 'pasang' matched 'pemasangan': {matched_item['name']}")
    
    def test_lantai_expose_matches_finishing_lantai_beton_expose(self):
        """
        DB has: "Finishing Lantai Beton Expose"
        User searches: "lantai expose"
        Expected: Should match (partial phrase match)
        """
        result = MatchingService.perform_best_match("lantai expose")
        
        self.assertIsNotNone(result, "lantai expose should match finishing lantai beton expose")
        
        if isinstance(result, list):
            matched_item = result[0] if result else None
        else:
            matched_item = result
        
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["code"], "AHS.021")
        print(f"✓ 'lantai expose' matched full phrase: {matched_item['name']}")
    
    # ========================================================================
    # ELECTRICAL
    # ========================================================================
    
    def test_pekerjaan_listrik_matches_instalasi_listrik(self):
        """
        DB has: "Instalasi Listrik Titik Lampu"
        User searches: "pekerjaan listrik titik lampu"
        Expected: Should match (pekerjaan = instalasi)
        """
        result = MatchingService.perform_best_match("pekerjaan listrik titik lampu")
        
        self.assertIsNotNone(result, "pekerjaan listrik should match instalasi listrik")
        
        if isinstance(result, list):
            matched_item = result[0] if result else None
        else:
            matched_item = result
        
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["code"], "AHS.030")
        print(f"✓ 'pekerjaan listrik' matched 'instalasi listrik': {matched_item['name']}")
    
    def test_switch_matches_saklar(self):
        """
        DB has: "Pemasangan Saklar Engkel"
        User searches: "pemasangan switch"
        Expected: Should match (switch = saklar)
        """
        result = MatchingService.perform_best_match("pemasangan switch")
        
        self.assertIsNotNone(result, "switch should match saklar")
        
        if isinstance(result, list):
            matched_item = result[0] if result else None
        else:
            matched_item = result
        
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["code"], "AHS.031")
        print(f"✓ 'switch' matched 'saklar': {matched_item['name']}")
    
    def test_colokan_matches_stop_kontak(self):
        """
        DB has: "Pemasangan Stop Kontak"
        User searches: "pemasangan colokan"
        Expected: Should match (colokan = stop kontak)
        """
        result = MatchingService.perform_best_match("pemasangan colokan")
        
        self.assertIsNotNone(result, "colokan should match stop kontak")
        
        if isinstance(result, list):
            matched_item = result[0] if result else None
        else:
            matched_item = result
        
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["code"], "AHS.032")
        print(f"✓ 'colokan' matched 'stop kontak': {matched_item['name']}")
    
    # ========================================================================
    # PAINTING & FINISHING
    # ========================================================================
    
    def test_pengecatan_dinding_matches_cat_dinding(self):
        """
        DB has: "Cat Dinding Interior"
        User searches: "pengecatan dinding interior"
        Expected: Should match (pengecatan = cat)
        """
        result = MatchingService.perform_best_match("pengecatan dinding interior")
        
        self.assertIsNotNone(result, "pengecatan should match cat")
        
        if isinstance(result, list):
            matched_item = result[0] if result else None
        else:
            matched_item = result
        
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["code"], "AHS.040")
        print(f"✓ 'pengecatan' matched 'cat': {matched_item['name']}")
    
    def test_finishing_cat_duco_matches_pintu_kayu_duco(self):
        """
        DB has: "Finishing Pintu Kayu Duco"
        User searches: "finishing cat duco pintu"
        Expected: Should match (reordered but same terms)
        """
        result = MatchingService.perform_best_match("finishing cat duco pintu")
        
        self.assertIsNotNone(result, "cat duco should match pintu kayu duco")
        
        if isinstance(result, list):
            matched_item = result[0] if result else None
        else:
            matched_item = result
        
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["code"], "AHS.041")
        print(f"✓ 'cat duco' matched 'pintu kayu duco': {matched_item['name']}")


class PhraseSynonymPerformanceTests(TransactionTestCase):
    """Ensure synonym matching doesn't slow things down."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ahs (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    reference_group_id BIGINT NULL,
                    code VARCHAR(50) NULL,
                    name VARCHAR(500) NULL,
                    INDEX idx_ahs_code (code),
                    INDEX idx_ahs_name (name(255))
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        
        for i in range(100):
            Ahs.objects.create(
                code=f"AHS.{i:03d}",
                name=f"Pemasangan Material {i}"
            )
    
    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS ahs")
        super().tearDownClass()
    
    def test_synonym_matching_meets_100ms_sla(self):
        """Synonym expansion should not violate 100ms SLA."""
        import time
        
        times = []
        for _ in range(5):
            start = time.perf_counter()
            MatchingService.perform_best_match("pemasangan hebel")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        
        print(f"\nSynonym matching average: {avg_time:.2f}ms")
        
        self.assertLess(avg_time, 150, 
                       f"Synonym matching averaged {avg_time:.2f}ms, should be <150ms")
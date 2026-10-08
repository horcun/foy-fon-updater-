"""update_sertifika.py — saf kurallar (ağ yok). Koşum: python -m unittest test_sertifika"""
import json
import os
import tempfile
import unittest
from datetime import date, datetime

import update_sertifika as u


class Takvim(unittest.TestCase):
    def test_siradan_gun(self):
        self.assertEqual(u.onceki_seans(date(2026, 10, 8)), ("2026-10-07", None))

    def test_pazartesi_cumaya_doner(self):
        self.assertEqual(u.onceki_seans(date(2026, 10, 12))[0], "2026-10-09")

    def test_bayram_atlanir(self):
        # 15 Tem 2026 Çarşamba tatil → 16 Tem'in önceki seansı 14 Tem
        self.assertEqual(u.onceki_seans(date(2026, 7, 16))[0], "2026-07-14")

    def test_yarim_gun_sonrasi_yazilmaz(self):
        tarih, sebep = u.onceki_seans(date(2026, 10, 30))
        self.assertIsNone(tarih)
        self.assertIn("yarım gün", sebep)

    def test_bilinmeyen_yil_yazilmaz(self):
        self.assertIsNone(u.onceki_seans(date(2028, 1, 4))[0])

    def test_canli_pencere(self):
        self.assertTrue(u.canli_seans_mi(datetime(2026, 10, 8, 12, 40, tzinfo=u.TR)))
        self.assertFalse(u.canli_seans_mi(datetime(2026, 10, 8, 9, 52, tzinfo=u.TR)))   # açılış öncesi
        self.assertFalse(u.canli_seans_mi(datetime(2026, 10, 8, 18, 5, tzinfo=u.TR)))   # akşam
        self.assertFalse(u.canli_seans_mi(datetime(2026, 10, 10, 12, 0, tzinfo=u.TR)))  # cumartesi
        self.assertFalse(u.canli_seans_mi(datetime(2026, 10, 29, 12, 0, tzinfo=u.TR)))  # bayram


class Uzlasma(unittest.TestCase):
    def test_bugun_islem_yok_tv_close_dunku(self):
        # 8 Eki 10:16 ölçümü: İş last 0, dayClose 70,49; TV close 70,49
        self.assertEqual(u.uzlas(70.49, u.tv_onceki(None, 70.49, -0.6)), 70.49)

    def test_bugun_islem_var(self):
        self.assertEqual(u.uzlas(70.49, u.tv_onceki(72.1, 72.1, 1.61)), 70.49)

    def test_tv_gecikmeli_ayrisir(self):
        # İş bugün işlem gördü, TV henüz görmedi: close − değişim önceki günü verir → red
        self.assertIsNone(u.uzlas(70.49, u.tv_onceki(72.1, 70.49, -0.6)))

    def test_tek_kaynak_yetmez(self):
        self.assertIsNone(u.uzlas(70.49, None))
        self.assertIsNone(u.uzlas(None, 70.49))


class Arsiv(unittest.TestCase):
    def setUp(self):
        self.eski = os.getcwd()
        self.d = tempfile.mkdtemp()
        os.chdir(self.d)

    def tearDown(self):
        os.chdir(self.eski)

    def oku(self):
        with open(os.path.join("gecmis", "ALTINS1.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_fon_bicimi(self):
        self.assertTrue(u.arsive_yaz("2026-10-07", 70.49, "2026-10-08T09:40:00Z"))
        j = self.oku()
        self.assertEqual(j, {"kod": "ALTINS1", "historyFrom": "2026-10-07",
                             "updatedAt": "2026-10-08T09:40:00Z", "daily": {"2026-10-07": 70.49}})

    def test_ayni_gun_ezilmez(self):
        u.arsive_yaz("2026-10-07", 70.49, "t1")
        self.assertFalse(u.arsive_yaz("2026-10-07", 71.0, "t2"))
        self.assertEqual(self.oku()["daily"]["2026-10-07"], 70.49)

    def test_sirali(self):
        u.arsive_yaz("2026-10-08", 71.0, "t")
        u.arsive_yaz("2026-10-07", 70.49, "t")
        j = self.oku()
        self.assertEqual(list(j["daily"]), ["2026-10-07", "2026-10-08"])
        self.assertEqual(j["historyFrom"], "2026-10-07")


if __name__ == "__main__":
    unittest.main()

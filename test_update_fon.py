"""update_fon.py — saf kurallar (ağ yok). Koşum: python -m unittest test_update_fon"""
import json
import os
import tempfile
import unittest

import update_fon as u

YAT = [["AAK", "ATA PORTFÖY ÇOKLU VARLIK", 34.31], ["TGE", "TGE FON", 0.29]]
EMK = [["AEK", "AGESA BORÇLANMA ARAÇLARI GRUP EMEKLİLİK", 0.395381],
       ["AEH", "AGESA HİSSE SENEDİ EMEKLİLİK", 1.290536]]


class Bicim(unittest.TestCase):
    def test_sifir_ve_bos_fiyat_atilir(self):
        ham = [{"fonKodu": "A", "fonUnvan": "a", "fiyat": 1.23456789},
               {"fonKodu": "B", "fonUnvan": "b", "fiyat": 0},
               {"fonKodu": "C", "fonUnvan": "c", "fiyat": None},
               {"fonKodu": "D", "fonUnvan": "d"}]
        self.assertEqual(u.foy_bicimi(ham), [["A", "a", 1.234568]])


class Ayikla(unittest.TestCase):
    def test_cakisma_yoksa_aynen(self):
        self.assertEqual(u.emk_ayikla(YAT, EMK), (EMK, []))

    def test_cakisan_kod_emk_den_cikar_yat_korunur(self):
        emk = EMK + [["AAK", "AYNI KOD EMEKLİLİK", 9.99]]
        temiz, cakisan = u.emk_ayikla(YAT, emk)
        self.assertEqual(cakisan, ["AAK"])
        self.assertEqual(temiz, EMK)


class GistDosyalari(unittest.TestCase):
    def test_iki_dosya_ayri(self):
        d = u.gist_dosyalari(YAT, EMK)
        self.assertEqual(set(d), {"foy-fonlar.json", "foy-emeklilik.json"})
        self.assertEqual(json.loads(d["foy-fonlar.json"]["content"]), YAT)
        self.assertEqual(json.loads(d["foy-emeklilik.json"]["content"]), EMK)

    def test_yat_dosyasi_eski_bicimle_ayni(self):
        # Yayındaki her sürüm bu dosyayı okuyor: biçim bir bayt bile değişmemeli.
        eski = json.dumps(YAT, ensure_ascii=False, separators=(",", ":"))
        self.assertEqual(u.gist_dosyalari(YAT, EMK)["foy-fonlar.json"]["content"], eski)

    def test_emk_alinamazsa_bos_liste_yat_etkilenmez(self):
        for emk in (None, []):
            d = u.gist_dosyalari(YAT, emk)
            self.assertEqual(json.loads(d["foy-emeklilik.json"]["content"]), [])
            self.assertEqual(json.loads(d["foy-fonlar.json"]["content"]), YAT)


class Arsiv(unittest.TestCase):
    def test_kod_basina_dosya_ve_eski_gunler_korunur(self):
        with tempfile.TemporaryDirectory() as dz:
            with open(os.path.join(dz, "AAK.json"), "w", encoding="utf-8") as f:
                json.dump({"kod": "AAK", "daily": {"2026-10-09": 34.0}}, f)
            n = u.arsive_yaz(YAT + EMK, "2026-10-12", "2026-10-12T07:15:00Z", dizin=dz)
            self.assertEqual(n, 4)
            aak = json.load(open(os.path.join(dz, "AAK.json"), encoding="utf-8"))
            self.assertEqual(aak["daily"], {"2026-10-09": 34.0, "2026-10-12": 34.31})
            self.assertEqual(aak["historyFrom"], "2026-10-09")
            aek = json.load(open(os.path.join(dz, "AEK.json"), encoding="utf-8"))
            self.assertEqual(aek["daily"], {"2026-10-12": 0.395381})
            self.assertEqual(aek["historyFrom"], "2026-10-12")


class Izolasyon(unittest.TestCase):
    """main(): EMK çekimi patlasa da YAT yazılır, EMK boş yazılır."""
    def setUp(self):
        self.yazilan = {}
        self._cek, self._yaz, self._ars = u.tefas_cek, u.gist_yaz, u.arsive_yaz
        u.gist_yaz = lambda d: self.yazilan.update(d)
        u.arsive_yaz = lambda s, *a, **k: len(s)

    def tearDown(self):
        u.tefas_cek, u.gist_yaz, u.arsive_yaz = self._cek, self._yaz, self._ars

    def _ham(self, satirlar):
        return [{"fonKodu": k, "fonUnvan": a, "fiyat": f} for k, a, f in satirlar]

    def test_emk_hatasi_yat_i_durdurmaz(self):
        def cek(tip, gun):
            if tip == "EMK":
                raise TimeoutError("TEFAS EMK zaman aşımı")
            return self._ham(YAT)
        u.tefas_cek = cek
        u.main()
        self.assertEqual(json.loads(self.yazilan["foy-fonlar.json"]["content"]), YAT)
        self.assertEqual(json.loads(self.yazilan["foy-emeklilik.json"]["content"]), [])

    def test_yat_hatasi_gist_e_dokunmaz(self):
        def cek(tip, gun):
            if tip == "YAT":
                raise TimeoutError("TEFAS YAT zaman aşımı")
            return self._ham(EMK)
        u.tefas_cek = cek
        with self.assertRaises(TimeoutError):
            u.main()
        self.assertEqual(self.yazilan, {})

    def test_kuru_hicbir_yere_yazmaz(self):
        u.tefas_cek = lambda tip, gun: self._ham(YAT if tip == "YAT" else EMK)
        u.arsive_yaz = lambda *a, **k: self.fail("kuru arşive yazdı")
        u.main(kuru=True)
        self.assertEqual(self.yazilan, {})


if __name__ == "__main__":
    unittest.main()

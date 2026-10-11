"""surum_gist.py — saf kurallar (ağ yok). Koşum: python -m unittest test_surum_gist"""
import json
import unittest

import surum_gist as g

ORNEK = ('{\n  "minimum_version_android": "1.7.0",\n  "force_update": false,\n'
         '  "update_message_tr": "Yeni sürüm: 1.7.0",\n  "update_message_en": "New"\n}')


class Degistir(unittest.TestCase):
    def test_yalniz_alan_degisir(self):
        sonuc, eski = g.degistir(ORNEK, "1.7.1")
        self.assertEqual(eski, "1.7.0")
        self.assertEqual(sonuc, ORNEK.replace('"minimum_version_android": "1.7.0"',
                                              '"minimum_version_android": "1.7.1"'))
        veri = json.loads(sonuc)
        self.assertIs(veri["force_update"], False)
        self.assertEqual(veri["update_message_tr"], "Yeni sürüm: 1.7.0")  # mesaja dokunulmaz

    def test_geri_ve_ayni_surum_reddedilir(self):
        for s in ("1.7.0", "1.6.9", "0.9.9"):
            with self.assertRaises(ValueError):
                g.degistir(ORNEK, s)

    def test_cok_haneli_karsilastirma(self):
        self.assertEqual(g.degistir(ORNEK.replace("1.7.0", "1.9.0"), "1.10.0")[1], "1.9.0")

    def test_bicim_bozuk_reddedilir(self):
        for s in ("1.7", "v1.7.1", "1.7.1-beta", "", None):
            with self.assertRaises(ValueError):
                g.degistir(ORNEK, s)

    def test_alan_yok_ya_da_iki_kez(self):
        with self.assertRaises(ValueError):
            g.degistir('{"force_update": false}', "1.7.1")
        with self.assertRaises(ValueError):
            g.degistir('{"minimum_version_android": "1.7.0", "x": {"minimum_version_android": "1.0.0"}}', "1.7.1")


if __name__ == "__main__":
    unittest.main()

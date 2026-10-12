"""BES (bireysel emeklilik) fonları için TEK SEFERLİK kaynak ölçümü — 12 Eki 2026.

Soru (Orçun, FÖY 1.7.2): FÖY'ün fon fiyatı kaynakları emeklilik fonu fiyatı veriyor mu?
  1) TEFAS resmi ucu (update_fon.py'nin kullandığı) — fonTipi "EMK" ile
  2) finans.dokuz.gen.tr — uygulamanın canlı fon fiyatı ucu (services/prices.js)
  3) Yahoo <KOD>.IS — uygulamanın ikinci yedeği
Yalnız OKUR. Gist'e, arşive, depoya hiçbir şey yazmaz; anahtar kullanmaz.
"""
import json
import urllib.request
from datetime import datetime, timedelta

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
# Web aramasından (fvt.com.tr AGESA BES sayfaları · hisse.net BEFAS listesi) + kontrol AAK (YAT).
HEDEF = ["AEK", "AE2", "AEH", "AEB", "BEE", "FJG", "TVG"]
KONTROL = "AAK"


def tefas(fon_tipi, bas, bit):
    body = json.dumps({
        "dil": "TR", "fonTipi": fon_tipi, "fonKod": None, "fonGrup": None,
        "basTarih": bas, "bitTarih": bit, "fonTurAciklama": None, "fonTurKod": None,
        "fonUnvanTip": None, "kurucuKod": None, "sfonTurKod": None,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetirDosya", data=body,
        headers={"Content-Type": "application/json",
                 "Referer": f"https://www.tefas.gov.tr/tr/fon-verileri?fundType={fon_tipi}",
                 "Origin": "https://www.tefas.gov.tr", "User-Agent": UA},
        method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()).get("resultList", []) or []


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"").decode("utf-8", "replace")[:300]
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


bugun = datetime.utcnow() + timedelta(hours=3)
bas, bit = (bugun - timedelta(days=6)).strftime("%Y%m%d"), bugun.strftime("%Y%m%d")
print(f"Ölçüm anı (TSİ): {bugun:%Y-%m-%d %H:%M} · TEFAS aralığı {bas}–{bit}\n")

# ── 1. TEFAS ────────────────────────────────────────────
sonuc = {}
for tip in ("YAT", "EMK"):
    try:
        satirlar = tefas(tip, bit, bit)
        tek_gun = True
        if not satirlar:
            satirlar = tefas(tip, bas, bit)
            tek_gun = False
        sonuc[tip] = satirlar
        kodlar = {s.get("fonKodu") for s in satirlar}
        print(f"TEFAS {tip}: {len(satirlar)} satır, {len(kodlar)} farklı kod "
              f"({'bugün' if tek_gun else 'son 7 gün'})")
        if satirlar:
            print(f"  alanlar: {sorted(satirlar[0].keys())}")
    except Exception as e:
        sonuc[tip] = None
        print(f"TEFAS {tip}: HATA {type(e).__name__}: {e}")

emk = sonuc.get("EMK") or []
yat = sonuc.get("YAT") or []
if emk:
    son = {}
    for s in emk:
        son[s["fonKodu"]] = s  # aynı kodun son satırı
    gecerli = [s for s in son.values() if (s.get("fiyat") or 0) > 0]
    print(f"\nEMK fiyatı > 0 olan kod: {len(gecerli)} / {len(son)}")
    for s in sorted(gecerli, key=lambda x: x["fonKodu"])[:12]:
        print(f"  {s['fonKodu']}  {s.get('fiyat')}  {s.get('tarih')}  {s.get('fonUnvan','')[:70]}")
    cakisan = sorted({s["fonKodu"] for s in yat} & set(son))
    print(f"\nYAT ile AYNI KODU taşıyan EMK fonu: {len(cakisan)} {cakisan[:20]}")
    print("Hedef kodlar EMK listesinde mi:")
    for k in HEDEF:
        s = son.get(k)
        print(f"  {k}: {'VAR ' + str(s.get('fiyat')) + ' · ' + s.get('fonUnvan','')[:60] if s else 'yok'}")

# ── 2. finans.dokuz.gen.tr ───────────────────────────────
print("\nfinans.dokuz.gen.tr (uygulamanın canlı ucu):")
d_bas, d_bit = (bugun - timedelta(days=7)).strftime("%Y-%m-%d"), bugun.strftime("%Y-%m-%d")
ornek_emk = sorted(s["fonKodu"] for s in emk)[:3] if emk else []
for k in [KONTROL] + HEDEF + [x for x in ornek_emk if x not in HEDEF]:
    st, metin = get(f"https://finans.dokuz.gen.tr/api/v1/tefas/funds/{k}"
                    f"?startDate={d_bas}&endDate={d_bit}&currency=TRY")
    ozet = metin[:160].replace("\n", " ")
    try:
        veri = json.loads(metin)
        if isinstance(veri, list):
            ozet = f"{len(veri)} satır" + (f", son: {sorted(veri, key=lambda r: r.get('date',''))[-1]}" if veri else "")
    except Exception:
        pass
    print(f"  {k}: HTTP {st} · {ozet[:220]}")

# ── 3. Yahoo .IS ─────────────────────────────────────────
print("\nYahoo .IS (uygulamanın ikinci yedeği):")
for k in [KONTROL, "AEK", "AEH"]:
    st, metin = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{k}.IS?interval=1d&range=5d")
    fiyat = None
    try:
        fiyat = json.loads(metin)["chart"]["result"][0]["meta"].get("regularMarketPrice")
    except Exception:
        pass
    print(f"  {k}.IS: HTTP {st} · fiyat {fiyat}")
print("\nBitti.")

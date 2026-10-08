"""Darphane altın sertifikası (ALTINS1) — günlük kapanış arşivi.

NEDEN VAR (8 Eki 2026): FÖY altın sertifikasını Borsa İstanbul altında
destekliyor. Yahoo bu kağıdı hiç tanımıyor (arama 0, fiyat 404); grafiğin
geçmiş serisi ve ay başı referansı, fonlarla AYNI biçimde bu deponun
gecmis/ALTINS1.json dosyasından okunur.

KURAL — ÖNCEKİ SEANSIN KAPANIŞI, İKİ BAĞIMSIZ KAYNAK UZLAŞIRSA:
  İş Yatırım (OneEndeks) `dayClose`          → canlı seansta önceki seansın kapanışı
  TradingView (BIST:ALTIN) önceki kapanış    → seyrek işlem ayrımıyla:
      bugün işlem olduysa (İş `last` > 0): close − change_abs
      bugün işlem yoksa   (İş `last` = 0): close  (TV'nin `close`u dünkü kapanış)
İkisi %0,3 içinde tutmazsa HİÇBİR ŞEY YAZILMAZ. Uygulamadaki kural
(services/kapanisUzlasi.js → yahooDisiBistFiyati) ile birebir aynı.

YALNIZ CANLI SEANSTA (10:10–18:00 TSİ, iş günü) koşar: kaynakların anlamı
yalnız o saatlerde ölçüldü. Gece yarısından sonra İş Yatırım `dayClose`unu
ne zaman devirdiği bilinmiyor; devirmeden önce iki kaynak önceki günün
kapanışında uzlaşıp onu "dün" diye etiketleyebilirdi.

Tarih takvimden gelir (uygulamadaki BIST_HOLIDAYS'in kopyası). Takvim o yılı
bilmiyorsa ya da araya yarım gün girdiyse YAZILMAZ — uydurma yok.

Bir gün bir kez yazılır; sonraki koşu farklı değer bulursa eskisi korunur ve
uyarı basılır (geçmiş sessizce değişmez).

Kullanım: python update_sertifika.py [--kuru]   (--kuru: yazmaz, yalnız raporlar)
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

KOD = "ALTINS1"
TV_SEMBOL = "BIST:ALTIN"
TOLERANS = 0.003
ARSIV_DIZIN = "gecmis"
MAKS_GUN = 1100
TR = timezone(timedelta(hours=3))   # Türkiye 2016'dan beri yaz saati uygulamıyor

IS_YATIRIM = ("https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/"
              f"Common/Data.aspx/OneEndeks?endeks={KOD}")
TRADINGVIEW = "https://scanner.tradingview.com/turkey/scan"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# FinansalOzgurluk/services/marketPolicy.js → BIST_HOLIDAYS (8 Eki 2026 kopyası).
BIST_TATIL = {
    2026: {
        "2026-01-01",
        "2026-03-19", "2026-03-20", "2026-03-21", "2026-03-22",
        "2026-04-23", "2026-05-01", "2026-05-19",
        "2026-05-26", "2026-05-27", "2026-05-28", "2026-05-29", "2026-05-30",
        "2026-07-15", "2026-08-30",
        "2026-10-28", "2026-10-29",
    },
    2027: {
        "2027-01-01",
        "2027-03-09", "2027-03-10", "2027-03-11",
        "2027-04-23", "2027-05-01",
        "2027-05-16", "2027-05-17", "2027-05-18", "2027-05-19",
        "2027-07-15", "2027-08-30", "2027-10-29",
    },
}
# Tabloda tatil sayılan ama aslında yarım seansı olan günler. Ertesi iş gününün
# "önceki seansı" belirsizleşir (yarım günün kapanışı mı, ondan önceki mi?) → yazılmaz.
YARIM_GUN = {"2026-03-19", "2026-05-26", "2026-10-28"}


def tatil_mi(gun):
    """True (tatil/hafta sonu) · False (iş günü) · None (takvim o yılı bilmiyor)."""
    if gun.weekday() >= 5:
        return True
    tablo = BIST_TATIL.get(gun.year)
    if tablo is None:
        return None
    return gun.strftime("%Y-%m-%d") in tablo


def onceki_seans(bugun):
    """(tarih, None) ya da (None, sebep). bugun: datetime.date."""
    gun = bugun
    for _ in range(15):
        gun -= timedelta(days=1)
        t = tatil_mi(gun)
        if t is None:
            return None, f"takvim {gun.year} yılını bilmiyor"
        if t:
            if gun.strftime("%Y-%m-%d") in YARIM_GUN:
                return None, f"araya yarım gün girdi ({gun})"
            continue
        return gun.strftime("%Y-%m-%d"), None
    return None, "15 günde iş günü bulunamadı"


def canli_seans_mi(an):
    """an: TR saatli datetime. Uygulamadaki LIVE penceresi: iş günü 10:10–18:00."""
    if tatil_mi(an.date()) is not False:
        return False
    dakika = an.hour * 60 + an.minute
    return 610 <= dakika < 1080


def pozitif(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v > 0 and v == v and v != float("inf") else None


def tv_onceki(is_last, tv_close, tv_degisim):
    """Seyrek işlem ayrımı: bugün işlem olduysa close − değişim, yoksa close."""
    if tv_close is None or tv_degisim is None:
        return None
    if is_last:
        return pozitif(round(tv_close - tv_degisim, 4))
    return pozitif(tv_close)


def uzlas(a, b, tol=TOLERANS):
    """İki değer tolerans içindeyse ortalamaları (uygulamadaki ortanca), değilse None."""
    a, b = pozitif(a), pozitif(b)
    if a is None or b is None:
        return None
    if abs(a - b) / a > tol:
        return None
    return round((a + b) / 2, 4)


def getir(url, govde=None):
    istek = urllib.request.Request(
        url,
        data=json.dumps(govde).encode("utf-8") if govde is not None else None,
        headers={"Accept": "application/json", "User-Agent": UA,
                 **({"Content-Type": "application/json"} if govde is not None else {})},
        method="POST" if govde is not None else "GET",
    )
    with urllib.request.urlopen(istek, timeout=20) as r:
        return json.loads(r.read())


def is_yatirim_oku():
    j = getir(IS_YATIRIM)
    s = j[0] if isinstance(j, list) and j else None
    if not s or str(s.get("symbol", KOD)).upper() != KOD:
        return None
    return {"last": pozitif(s.get("last")), "dayClose": pozitif(s.get("dayClose"))}


def tradingview_oku():
    j = getir(TRADINGVIEW, {"symbols": {"tickers": [TV_SEMBOL]}, "columns": ["close", "change_abs"]})
    for x in (j or {}).get("data") or []:
        if x.get("s") == TV_SEMBOL and isinstance(x.get("d"), list) and len(x["d"]) >= 2:
            close = pozitif(x["d"][0])
            try:
                deg = float(x["d"][1])
            except (TypeError, ValueError):
                return None
            return {"close": close, "degisim": deg} if close else None
    return None


def arsive_yaz(tarih, deger, simdi_utc):
    """Yazıldıysa True. Aynı gün farklı değerle zaten varsa eskisini korur."""
    yol = os.path.join(ARSIV_DIZIN, f"{KOD}.json")
    gunler = {}
    if os.path.exists(yol):
        with open(yol, encoding="utf-8") as f:
            gunler = (json.load(f) or {}).get("daily", {}) or {}
    if tarih in gunler:
        if abs(float(gunler[tarih]) - deger) > 1e-9:
            print(f"UYARI — {tarih} zaten {gunler[tarih]}; yeni ölçüm {deger}. Eski korunuyor.")
        else:
            print(f"{tarih} zaten arşivde ({deger}) — değişiklik yok.")
        return False
    gunler[tarih] = deger
    sirali = dict(sorted(gunler.items()))
    if len(sirali) > MAKS_GUN:
        sirali = dict(list(sirali.items())[-MAKS_GUN:])
    os.makedirs(ARSIV_DIZIN, exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump({"kod": KOD, "historyFrom": next(iter(sirali)), "updatedAt": simdi_utc,
                   "daily": sirali}, f, ensure_ascii=False, separators=(",", ":"))
    return True


def main(kuru=False):
    an = datetime.now(TR)
    print(f"Saat (TSİ): {an:%Y-%m-%d %H:%M}  · kuru={kuru}")
    if not canli_seans_mi(an):
        print("Canlı BIST seansı değil — kaynakların anlamı yalnız seansta ölçüldü, yazılmıyor.")
        return 0
    tarih, sebep = onceki_seans(an.date())
    if tarih is None:
        print(f"Önceki seans tarihi belirsiz ({sebep}) — yazılmıyor.")
        return 0

    try:
        isy = is_yatirim_oku()
    except Exception as e:
        print(f"İş Yatırım okunamadı: {e}")
        isy = None
    try:
        tv = tradingview_oku()
    except Exception as e:
        print(f"TradingView okunamadı: {e}")
        tv = None
    print(f"İş Yatırım: {isy}")
    print(f"TradingView: {tv}")

    tvo = tv_onceki(isy and isy["last"], tv and tv["close"], tv and tv["degisim"]) if isy else None
    deger = uzlas(isy and isy["dayClose"], tvo)
    print(f"{tarih} kapanışı — İş dayClose={isy and isy['dayClose']} · TV önceki={tvo} → uzlaşma={deger}")
    if deger is None:
        print("Kaynaklar uzlaşmadı (ya da biri yok) — yazılmıyor. Sonraki koşu yeniden dener.")
        return 0
    if kuru:
        print(f"KURU: gecmis/{KOD}.json daily[{tarih}] = {deger} yazılacaktı.")
        return 0
    simdi = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if arsive_yaz(tarih, deger, simdi):
        print(f"Yazıldı: gecmis/{KOD}.json daily[{tarih}] = {deger}")
    return 0


if __name__ == "__main__":
    sys.exit(main(kuru="--kuru" in sys.argv))

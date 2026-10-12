"""TEFAS fon fiyatlarını FÖY'ün Gist'ine ve geçmiş arşivine yazar.

Gist dosyaları (biçim: [[KOD, Ad, fiyat], ...]):
  foy-fonlar.json      yatırım fonları (fonTipi YAT) — her FÖY sürümü okur
  foy-emeklilik.json   emeklilik (BES) fonları (fonTipi EMK) — FÖY 1.7.2'den
                       itibaren okunur (Orçun, 12 Eki 2026: "sürümle birlikte").
                       Ayrı dosya olması bilinçli: yayındaki eski sürüm bu dosyayı
                       hiç okumaz, BES onlarda görünmez.

Hata izolasyonu: EMK çekimi ne olursa olsun YAT akışı eskisi gibi sürer.
EMK alınamazsa dosyası BOŞ liste yazılır — uygulama bayat BES fiyatını
"bugünkü" sanmasın, o gün BES fiyatına hiç dokunmasın.

Koşum: python update_fon.py          (yazar)
       python update_fon.py --kuru   (gerçek veriyle ölçer, hiçbir yere yazmaz)
Kurallar (ağsız): python -m unittest test_update_fon
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime

# ── Ayarlar ──────────────────────────────────────────────
GIST_ID           = "a507936dc7a68ae1f9e49c5e4c7e2190"
GIST_FILENAME     = "foy-fonlar.json"
GIST_FILENAME_EMK = "foy-emeklilik.json"
ARSIV_DIZIN = "gecmis"
MAKS_GUN    = 1100   # ~3 yıl. Emniyet supabı: dosya sınırsız büyümesin.


# ── 1. TEFAS'tan fon fiyatlarını çek ─────────────────────
def tefas_cek(fon_tipi, gun):
    body = json.dumps({
        "dil": "TR",
        "fonTipi": fon_tipi,
        "fonKod": None,
        "fonGrup": None,
        "basTarih": gun,
        "bitTarih": gun,
        "fonTurAciklama": None,
        "fonTurKod": None,
        "fonUnvanTip": None,
        "kurucuKod": None,
        "sfonTurKod": None
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetirDosya",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Referer": f"https://www.tefas.gov.tr/tr/fon-verileri?fundType={fon_tipi}",
            "Origin": "https://www.tefas.gov.tr",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    return data.get("resultList", []) or []


# ── 2. FÖY formatına çevir: [[KOD, Ad, fiyat], ...] ──────
def foy_bicimi(funds):
    return [
        [f["fonKodu"], f["fonUnvan"], round(f["fiyat"], 6)]
        for f in funds
        if f.get("fiyat") and f["fiyat"] > 0
    ]


def emk_ayikla(yat, emk):
    """EMK listesinden YAT'ta da olan kodları çıkarır (uygulama fonu koduyla
    tanır; aynı kod iki fiyat taşıyamaz). 12 Eki 2026 ölçümünde çakışma 0'dı.
    Döner: (temiz_emk, cakisan_kodlar)."""
    yat_kodlari = {s[0] for s in yat}
    cakisan = sorted(s[0] for s in emk if s[0] in yat_kodlari)
    return [s for s in emk if s[0] not in yat_kodlari], cakisan


def gist_dosyalari(yat, emk):
    """Gist'e yazılacak dosyalar. YAT eskisi gibi her koşulda yazılır.
    emk None (çekilemedi) ya da boşsa EMK dosyası BOŞ liste olur."""
    paket = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
    return {
        GIST_FILENAME:     {"content": paket(yat)},
        GIST_FILENAME_EMK: {"content": paket(emk or [])},
    }


# ── 3. Gist'i güncelle ───────────────────────────────────
def gist_yaz(dosyalar):
    gist_body = json.dumps({"files": dosyalar}).encode("utf-8")
    gist_req = urllib.request.Request(
        f"https://api.github.com/gists/{GIST_ID}",
        data=gist_body,
        headers={
            "Authorization": f"Bearer {os.environ['GIST_TOKEN']}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="PATCH"
    )
    with urllib.request.urlopen(gist_req, timeout=15) as r:
        print(f"Gist güncellendi! Status: {r.status}")


# ── 4. Bugünü GEÇMİŞ ARŞİVİNE ekle ───────────────────────
# Sözleşme: FOY-FINANSAL-DAVRANIS-SOZLESMESI.md · K6.4–K6.7
#
# NEDEN: TEFAS fonlarının geçmiş NAV'ı hiçbir yerden çekilmiyordu. Grafik
# motoru fiyatı olmayan günler için "son bilineni taşı" kuralını uyguluyor;
# fonun elindeki tek fiyat BUGÜNKÜ fiyat olduğu için geçmişteki her gün
# bugünün fiyatıyla değerleniyordu (30 Tem 2026'da sahada gözlendi).
# Bugünden itibaren kendi arşivimizi biriktiriyoruz: kaynak bir gün şemasını
# değiştirse bile elimizdeki geçmiş etkilenmez. EMK fonları da aynı biçimde,
# kod başına dosya (1.7.2'den önceki sürümler bu dosyaları istemez).
def arsive_yaz(satirlar, bugun_anahtar, simdi, dizin=ARSIV_DIZIN):
    os.makedirs(dizin, exist_ok=True)
    yazilan = 0
    for kod, _ad, fiyat in satirlar:
        yol = os.path.join(dizin, f"{kod}.json")

        gunler = {}
        if os.path.exists(yol):
            try:
                with open(yol, encoding="utf-8") as f:
                    gunler = (json.load(f) or {}).get("daily", {}) or {}
            except Exception:
                # Bozuk dosya backfill'i durdurmaz; o fon bugünden yeniden başlar.
                gunler = {}

        gunler[bugun_anahtar] = fiyat
        sirali = dict(sorted(gunler.items()))
        if len(sirali) > MAKS_GUN:
            sirali = dict(list(sirali.items())[-MAKS_GUN:])

        with open(yol, "w", encoding="utf-8") as f:
            json.dump({
                "kod": kod,
                # K6.7 — kapsamı verinin KENDİSİ ilan eder, tip değil.
                "historyFrom": next(iter(sirali)),
                "updatedAt": simdi,
                "daily": sirali,
            }, f, ensure_ascii=False, separators=(",", ":"))
        yazilan += 1
    return yazilan


def main(kuru=False):
    today = datetime.now().strftime("%Y%m%d")

    # YAT: eskisi gibi — hata işi kırmızıya çevirir, Gist'e dokunulmaz.
    yat = foy_bicimi(tefas_cek("YAT", today))
    print(f"TEFAS YAT: geçerli fon sayısı {len(yat)}")

    # EMK: ayrı hata kapsamı. Ne olursa olsun YAT akışı sürer.
    emk = None
    try:
        emk = foy_bicimi(tefas_cek("EMK", today))
        emk, cakisan = emk_ayikla(yat, emk)
        if cakisan:
            print(f"UYARI — YAT ile aynı kodlu EMK fonu çıkarıldı: {cakisan}")
        print(f"TEFAS EMK: geçerli fon sayısı {len(emk)}")
    except Exception as e:
        print(f"UYARI — EMK (BES) fonları alınamadı, dosyası boş yazılacak (YAT etkilenmedi): {e}")
        emk = None

    dosyalar = gist_dosyalari(yat, emk)
    if kuru:
        for ad, d in dosyalar.items():
            print(f"KURU — {ad}: {len(json.loads(d['content']))} fon, {len(d['content'])} bayt (yazılmadı)")
        print("KURU — Gist ve arşiv yazılmadı.")
        return

    gist_yaz(dosyalar)

    # ⚠️ İZOLASYON: Bu adım Gist'ten SONRA ve AYRI hata kapsamında çalışır.
    # Arşiv yazımı bozulsa bile günlük fiyatlar Gist'e yazılmış olur; kullanıcının
    # bugünkü portföyü hiçbir koşulda etkilenmez.
    try:
        bugun_anahtar = datetime.now().strftime("%Y-%m-%d")
        simdi = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        yazilan = arsive_yaz(yat + (emk or []), bugun_anahtar, simdi)
        print(f"Geçmiş arşivi güncellendi: {yazilan} fon → {ARSIV_DIZIN}/")
    except Exception as e:
        # Bilinçli olarak yutulur: günlük fiyat akışı bundan ETKİLENMEMELİ.
        print(f"UYARI — geçmiş arşivi güncellenemedi (günlük fiyatlar etkilenmedi): {e}")

    print("Tamamlandı.")


if __name__ == "__main__":
    main(kuru="--kuru" in sys.argv)

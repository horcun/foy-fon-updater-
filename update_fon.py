import json
import os
import urllib.request
import urllib.error
from datetime import datetime

# ── Ayarlar ──────────────────────────────────────────────
GIST_ID       = "a507936dc7a68ae1f9e49c5e4c7e2190"
GIST_FILENAME = "foy-fonlar.json"
import os
GIST_TOKEN = os.environ["GIST_TOKEN"]

# ── 1. TEFAS'tan fon fiyatlarını çek ─────────────────────
today = datetime.now().strftime("%Y%m%d")

body = json.dumps({
    "dil": "TR",
    "fonTipi": "YAT",
    "fonKod": None,
    "fonGrup": None,
    "basTarih": today,
    "bitTarih": today,
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
        "Referer": "https://www.tefas.gov.tr/tr/fon-verileri?fundType=YAT",
        "Origin": "https://www.tefas.gov.tr",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    },
    method="POST"
)

with urllib.request.urlopen(req, timeout=30) as r:
    data = json.loads(r.read())

funds = data.get("resultList", [])
print(f"TEFAS'tan {len(funds)} fon çekildi.")

# ── 2. FÖY formatına çevir: [[KOD, Ad, fiyat], ...] ──────
result = [
    [f["fonKodu"], f["fonUnvan"], round(f["fiyat"], 6)]
    for f in funds
    if f.get("fiyat") and f["fiyat"] > 0
]

print(f"Geçerli fon sayısı: {len(result)}")

# ── 3. Gist'i güncelle ───────────────────────────────────
gist_body = json.dumps({
    "files": {
        GIST_FILENAME: {
            "content": json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        }
    }
}).encode("utf-8")

gist_req = urllib.request.Request(
    f"https://api.github.com/gists/{GIST_ID}",
    data=gist_body,
    headers={
        "Authorization": f"Bearer {GIST_TOKEN}",
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
# değiştirse bile elimizdeki geçmiş etkilenmez.
#
# ⚠️ İZOLASYON: Bu adım 1–3'ten SONRA ve AYRI hata kapsamında çalışır.
# Arşiv yazımı bozulsa bile günlük fiyatlar Gist'e yazılmış olur; kullanıcının
# bugünkü portföyü hiçbir koşulda etkilenmez.
ARSIV_DIZIN = "gecmis"
MAKS_GUN    = 1100   # ~3 yıl. Emniyet supabı: dosya sınırsız büyümesin.

try:
    bugun_anahtar = datetime.now().strftime("%Y-%m-%d")
    simdi = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(ARSIV_DIZIN, exist_ok=True)

    yazilan = 0
    for kod, _ad, fiyat in result:
        yol = os.path.join(ARSIV_DIZIN, f"{kod}.json")

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

    print(f"Geçmiş arşivi güncellendi: {yazilan} fon → {ARSIV_DIZIN}/")
except Exception as e:
    # Bilinçli olarak yutulur: günlük fiyat akışı bundan ETKİLENMEMELİ.
    print(f"UYARI — geçmiş arşivi güncellenemedi (günlük fiyatlar etkilenmedi): {e}")

print("Tamamlandı.")

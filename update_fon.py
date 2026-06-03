import json
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

print("Tamamlandı.")

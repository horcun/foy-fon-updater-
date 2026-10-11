"""FÖY Android sürüm kontrolü Gist'i — minimum_version_android'i günceller.

NEDEN VAR (11 Eki 2026): Android uygulaması açılışta bu Gist'i okur; içindeki
minimum_version_android, yüklü sürümden yeniyse kullanıcıya "güncelleme var"
uyarısı gösterir (FinansalOzgurluk App.js → Android: Gist). Android yayını
sonrası bu alan elle çekiliyordu; Orçun: "yayına çıkınca güncellemesi yap,
beni bekleme" → Mergen bu iş akışıyla yapar (CLAUDE.md §1 mağaza işletmesi).

KURALLAR:
  - Yalnız minimum_version_android değişir. force_update, mesajlar ve diğer
    alanlar BAYT BAYT aynı kalır (metin içinde tek alan değiştirilir).
  - Sürüm yalnız İLERİ gider (X.Y.Z, mevcuttan büyük); geri alma yok.
  - Alan dosyada tam bir kez geçmiyorsa ya da sonuç geçerli JSON değilse yazılmaz.
  - Yazdıktan sonra Gist yeniden okunur; değer tutmuyorsa hata.

Kullanım: python surum_gist.py [--surum X.Y.Z] [--yaz]
  --surum yoksa yalnız okur ve raporlar. --yaz yoksa KURU (yazmaz).
"""
import json
import os
import re
import sys
import urllib.request

GIST_ID = "69bf61fe52b9385778f51d8ef8e1622a"
DOSYA = "gistfile1.txt"
ALAN = "minimum_version_android"
SURUM_RE = re.compile(r"^\d+\.\d+\.\d+$")
ALAN_RE = re.compile(r'("' + ALAN + r'"\s*:\s*")([^"]*)(")')


def surum_tuple(s):
    return tuple(int(x) for x in s.split("."))


def degistir(icerik, yeni):
    """(yeni_icerik, eski_surum) ya da ValueError. Saf: ağ yok."""
    if not SURUM_RE.match(yeni or ""):
        raise ValueError(f"sürüm biçimi X.Y.Z değil: {yeni!r}")
    eslesmeler = ALAN_RE.findall(icerik)
    if len(eslesmeler) != 1:
        raise ValueError(f"{ALAN} dosyada {len(eslesmeler)} kez geçiyor (tam 1 olmalı)")
    eski = eslesmeler[0][1]
    if SURUM_RE.match(eski) and surum_tuple(yeni) <= surum_tuple(eski):
        raise ValueError(f"sürüm yalnız ileri gider: mevcut {eski}, istenen {yeni}")
    sonuc = ALAN_RE.sub(lambda m: m.group(1) + yeni + m.group(3), icerik, count=1)
    veri = json.loads(sonuc)  # geçerli JSON değilse ValueError
    if veri.get(ALAN) != yeni:
        raise ValueError("değişiklik sonrası alan beklenen değerde değil")
    return sonuc, eski


def istek(yontem, govde=None):
    req = urllib.request.Request(
        f"https://api.github.com/gists/{GIST_ID}",
        data=json.dumps(govde).encode("utf-8") if govde is not None else None,
        headers={
            "Authorization": f"Bearer {os.environ['GIST_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Content-Type": "application/json"} if govde is not None else {}),
        },
        method=yontem,
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read()), r.headers.get("X-OAuth-Scopes")


def oku():
    veri, kapsam = istek("GET")
    dosya = (veri.get("files") or {}).get(DOSYA)
    if not dosya or dosya.get("truncated"):
        raise RuntimeError(f"{DOSYA} okunamadı (yok ya da kesik)")
    return dosya["content"], veri.get("owner", {}).get("login"), kapsam


def main(argv):
    yeni = argv[argv.index("--surum") + 1] if "--surum" in argv else None
    yaz = "--yaz" in argv
    icerik, sahip, kapsam = oku()
    cfg = json.loads(icerik)
    print(f"Gist sahibi: {sahip} · jeton kapsamı: {kapsam}")
    print(f"Şu an: {ALAN}={cfg.get(ALAN)!r} · force_update={cfg.get('force_update')!r}")
    if not yeni:
        print("Sürüm verilmedi — yalnız okundu.")
        return 0
    sonuc, eski = degistir(icerik, yeni)
    print(f"Plan: {ALAN} {eski} → {yeni} (başka hiçbir alan değişmez)")
    if not yaz:
        print("KURU: yazılmadı.")
        return 0
    istek("PATCH", {"files": {DOSYA: {"content": sonuc}}})
    geri, _, _ = oku()
    if json.loads(geri).get(ALAN) != yeni or geri != sonuc:
        print("❌ Geri okuma tutmuyor.")
        return 1
    print(f"✅ Yazıldı ve geri okundu: {ALAN}={yeni}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

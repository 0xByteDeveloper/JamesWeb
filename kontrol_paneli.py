#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════
 M2GOD KONTROL PANELİ v5 (E194) — PYTHON SUNUCULU · E177_resim-avif-v6 uyumlu
      (E193 taban: Toplu Sıkıştır yok; arama/boyutlandırma/temizle/çeviri aynen)
      E194 YENİ UÇLAR:
        · /api/rkm/coz        → resimler/<ad>_rkm.js'i çözüp resme çevirir
                                (b64 → XOR64 → kare; mime f'ye göre) — önizleme
        · /api/gh/resim-yukle → RKM JS metnini resimler/<ad>_rkm.js olarak
                                GitHub'a pushlar (tarayıcıda canvas ile üretildi)
═══════════════════════════════════════════════════════════════════════
 KULLANIM:
     python kontrol_paneli.py               → http://127.0.0.1:8777 açılır
     python kontrol_paneli.py --port 9000   → farklı port
     python kontrol_paneli.py --tarayici-acma

 NE YAPAR:
   · kontrol_paneli.html'i sunar (site_icerik.json görsel editörü)
   · /api/gh/icerik: içerik TAZE çekimi (raw URL'e önbellek kırıcı ?t=).
     TOKEN OPSİYONELDİR: public depoda token'sız da çalışır; token yalnız
     private depo + push için
   · /api/gh/surum · /api/gh/liste: sürüm notu okuma + klasör listeleme
   · /api/rkm/coz · /api/gh/resim-yukle: RKM çözme + resim yükleme (E194)
   · /api/cevir: otomatik çeviri (Google → MyMemory yedeği)
   · /api/durum · /api/token: sunucu-token eşzamanlaması (token dosyaya
     yazılır, tarayıcıya asla geri gönderilmez)

 GEREKSİNİM: Python 3.8+ — ek paket YOK (yalnız standart kütüphane)
 TOKEN: ilk çalıştırmada paneldeki "Tarayıcıdaki Token'ı Sunucuya Kaydet"
        düğmesini kullanın (github_token.txt oluşturur) veya:
        E194_GH_TOKEN=github_pat_... python kontrol_paneli.py
═══════════════════════════════════════════════════════════════════════
"""
import base64
import datetime
import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ── yapılandırma ──────────────────────────────────────────────────────
SAHIP = "0xByteDeveloper"
REPO = "JamesWeb"
DAL = "main"
ICERIK_YOLU = "icerik/site_icerik.json"
RESIM_KLASORU = "resimler"
SURUM_YOLU = "surum_notu.json"
RAW_KOK = "https://raw.githubusercontent.com/%s/%s/%s" % (SAHIP, REPO, DAL)
API_KOK = "https://api.github.com/repos/%s/%s/contents" % (SAHIP, REPO)
PORT_VARSAYILAN = 8777

KOK_DIZIN = os.path.dirname(os.path.abspath(__file__))
TOKEN_DOSYA = os.path.join(KOK_DIZIN, "github_token.txt")
PANEL_HTML = os.path.join(KOK_DIZIN, "kontrol_paneli.html")

# ═══════════════════ GITHUB İSTEMCİSİ ═══════════════════
def token_al():
    t = os.environ.get("E194_GH_TOKEN", "").strip()
    if not t:
        t = os.environ.get("E193_GH_TOKEN", "").strip()
    if not t:
        t = os.environ.get("E179_GH_TOKEN", "").strip()
    if not t:
        t = os.environ.get("E178_GH_TOKEN", "").strip()
    if t:
        return t
    try:
        t = open(TOKEN_DOSYA, encoding="utf-8").read().strip()
        if t:
            return t
    except OSError:
        pass
    return None

def _istek(url, token, basliklar=None, veri=None, metot="GET", zaman=30):
    b = dict(basliklar or {})
    b["User-Agent"] = "EpinSitesi-KontrolPaneli-E183"
    if token:
        b["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=b, method=metot)
    gv = None
    if veri is not None:
        gv = json.dumps(veri).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, gv, timeout=zaman) as r:
        return r.read()

def gh_raw(yol, token, taze=False):
    url = RAW_KOK + "/" + yol
    if taze:   # E183: önbellek kırıcı — raw CDN eski kopyayı değil günceli versin
        url += ("&" if "?" in url else "?") + "t=%d" % int(time.time() * 1000)
    return _istek(url, token).decode("utf-8")

def gh_icerik_sha(yol, token):
    try:
        j = json.loads(_istek(API_KOK + "/" + yol + "?ref=" + DAL, token))
        return j.get("sha")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise

def gh_push(yol, icerik_b, mesaj, token):
    sha = gh_icerik_sha(yol, token)
    govde = {
        "message": mesaj,
        "content": base64.b64encode(icerik_b).decode("ascii"),
        "branch": DAL,
    }
    if sha:
        govde["sha"] = sha
    j = json.loads(_istek(API_KOK + "/" + yol, token, veri=govde, metot="PUT"))
    return (j.get("commit") or {}).get("sha") or "?"

def gh_liste(klasor, token):
    j = json.loads(_istek(API_KOK + "/" + klasor + "?ref=" + DAL + "&per_page=100", token))
    if not isinstance(j, list):
        raise ValueError("klasör okunamadı: " + klasor)
    return [{"ad": x.get("name"), "boyut": x.get("size"), "tur": x.get("type"), "sha": x.get("sha")}
            for x in j]

# ═══════════════════ E194 · RKM RESİM ÇÖZÜCÜ (/api/rkm/coz) ═══════════════════
# Sitenin resim motoruyla BİREBİR protokol: d=base64(kare XOR k[i%64]),
# f: 'w'=image/webp · 'a'=image/avif · 'p'=image/png. Sunucu yalnız ÇÖZER —
# şifreleme/kare üretimi tarayıcıda canvas ile yapılır (eksik codec derdi yok).
RKM_F_MIME = {"w": "image/webp", "a": "image/avif", "p": "image/png"}
RKM_AD_RE = re.compile(r"^[A-Za-z0-9_\-]{1,80}$")


def rkm_taban(ad):
    """metin2_logo | metin2_logo.png | metin2_logo_rkm.js → metin2_logo"""
    s = str(ad or "").strip()
    s = re.sub(r"_rkm\.js$", "", s, flags=re.I)
    s = re.sub(r"\.(png|webp|avif|jpe?g|gif)$", "", s, flags=re.I)
    return s


def rkm_coz(ad, token):
    """GitHub raw'dan resimler/<ad>_rkm.js çeker → kareyi çözüp döndürür."""
    taban = rkm_taban(ad)
    if not RKM_AD_RE.match(taban):
        raise ValueError("resim adı geçersiz: %r" % ad)
    metin = gh_raw(RESIM_KLASORU + "/" + taban + "_rkm.js", token, taze=True)
    m = re.search(r"RKM_VERI\[\s*['\"]([^'\"]+)['\"]\s*\]\s*=\s*(\{.*\})\s*;?\s*$",
                  metin.strip(), re.S)
    if not m:
        raise ValueError("RKM_VERI bulunamadı — dosya biçimi bilinmiyor")
    obj = json.loads(m.group(2))
    w, h, f, k, d = obj.get("w"), obj.get("h"), obj.get("f"), obj.get("k"), obj.get("d")
    if not (isinstance(w, int) and isinstance(h, int) and isinstance(k, list) and isinstance(d, str)):
        raise ValueError("RKM objesi w/h/f/k/d alanlarını içermiyor")
    kare = bytearray(base64.b64decode(d))
    for i in range(len(kare)):
        kare[i] ^= k[i % len(k)]
    mime = RKM_F_MIME.get(f, "image/webp")
    return {"ok": True, "ad": taban, "w": w, "h": h, "f": f, "mime": mime,
            "veri": base64.b64encode(bytes(kare)).decode("ascii"),
            "boyut": len(kare), "dosyaBoyut": len(metin.encode("utf-8"))}


def rkm_yukle(ad, icerik, token):
    """RKM JS metnini resimler/<ad>_rkm.js olarak GitHub'a pushlar."""
    taban = rkm_taban(ad)
    if not RKM_AD_RE.match(taban):
        raise ValueError("resim adı geçersiz — harf/rakam/_/- (ör. yeni_oyun_logo)")
    icerik = str(icerik or "")
    if len(icerik) > 12 * 1024 * 1024:
        raise ValueError("dosya çok büyük (maks 12 MB)")
    if "RKM_VERI['%s']" % taban not in icerik and 'RKM_VERI["%s"]' % taban not in icerik:
        raise ValueError("içerik RKM_VERI['%s'] tanımını içermiyor — panelin 'Dönüştür' adımını kullan" % taban)
    commit = gh_push(RESIM_KLASORU + "/" + taban + "_rkm.js",
                     icerik.encode("utf-8"),
                     "resimler/%s_rkm.js — kontrol paneli v5 (E194) tarayıcı-canvas RKM üretimi %s" % (taban, datetime.datetime.utcnow().isoformat()),
                     token)
    return commit

# ═══════════════════ E183 · OTOMATİK ÇEVİRİ (/api/cevir) ═══════════════════
# Panelin Metinler bölümündeki 🔄 düğmeleri buraya düşer: tek dil yazılır,
# boş dil alanları otomatik çevrilir. Google (gtx) birincil, MyMemory yedeği.

CEVIRI_BASLIK = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                 "Accept-Language": "en,tr;q=0.9"}
DIL_ESLE = {"cn": "zh-CN", "zh": "zh-CN"}   # panelde "cn", Google'da zh-CN


def _cevir_google(metin, kaynak, hedef):
    q = urllib.parse.quote(metin)
    url = ("https://translate.googleapis.com/translate_a/single"
           "?client=gtx&sl=%s&tl=%s&dt=t&q=%s" % (kaynak or "auto", hedef, q))
    istek = urllib.request.Request(url, headers=CEVIRI_BASLIK)
    with urllib.request.urlopen(istek, timeout=15) as r:
        j = json.loads(r.read().decode("utf-8"))
    parcalar = []
    for blok in (j[0] or []):
        if blok and blok[0]:
            parcalar.append(str(blok[0]))
    sonuc = "".join(parcalar).strip()
    if not sonuc:
        raise ValueError("boş sonuç")
    return sonuc


def _cevir_mymemory(metin, kaynak, hedef):
    if not kaynak or kaynak == "auto":
        raise ValueError("kaynak dil gerekli")
    q = urllib.parse.quote(metin[:500])
    url = ("https://api.mymemory.translated.net/get?q=%s&langpair=%s%%7C%s"
           % (q, kaynak, hedef))
    istek = urllib.request.Request(url, headers=CEVIRI_BASLIK)
    with urllib.request.urlopen(istek, timeout=15) as r:
        j = json.loads(r.read().decode("utf-8"))
    t = ((j.get("responseData") or {}).get("translatedText") or "").strip()
    if not t or t.upper().startswith("MYMEMORY WARNING"):
        raise ValueError("çeviri yok")
    return t


def metin_cevir(metin, kaynak, hedef):
    metin = str(metin or "").strip()
    kaynak = str(kaynak or "").strip().lower()
    hedef = str(hedef or "").strip().lower()
    if not metin:
        return {"ok": False, "mesaj": "metin boş"}
    if not hedef:
        return {"ok": False, "mesaj": "hedef dil boş"}
    if len(metin) > 2000:
        return {"ok": False, "mesaj": "metin çok uzun (maks 2000 karakter)"}
    if kaynak == hedef:
        return {"ok": True, "tamam": True, "ceviri": metin,
                "kaynakDil": kaynak, "hedefDil": hedef, "saglayici": "aynı dil"}
    hk = DIL_ESLE.get(hedef, hedef)
    kk = DIL_ESLE.get(kaynak, kaynak) if kaynak else ""
    saglayici = "google"
    try:
        sonuc = _cevir_google(metin, kk or "auto", hk)
    except Exception as e1:
        saglayici = "mymemory"
        try:
            sonuc = _cevir_mymemory(metin, kk, hk)
        except Exception as e2:
            return {"ok": False,
                    "mesaj": "çeviri başarısız (google: %s · mymemory: %s)" % (e1, e2)}
    return {"ok": True, "tamam": True, "ceviri": sonuc,
            "kaynakDil": kaynak or "auto", "hedefDil": hedef,
            "saglayici": saglayici}


LOG_SON = []          # son 40 işlem satırı (panel günlüğü)


def gunluk(s):
    satir = time.strftime("%H:%M:%S ") + str(s)
    LOG_SON.append(satir)
    del LOG_SON[:-40]
    try:
        print(satir)
    except Exception:
        pass


# ═══════════════════ SUNUCU ═══════════════════
class Panel(BaseHTTPRequestHandler):
    server_version = "EpinPanelE194/5.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[panel] %s\n" % (fmt % args))

    # ── yardımcılar ──
    def json_gonder(self, nesne, durum=200):
        gv = json.dumps(nesne, ensure_ascii=False).encode("utf-8")
        self.send_response(durum)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(gv)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(gv)

    def hata_gonder(self, mesaj, durum=400):
        self.json_gonder({"ok": False, "hata": str(mesaj)}, durum)

    def govde_oku(self):
        uzun = int(self.headers.get("Content-Length") or 0)
        if uzun <= 0 or uzun > 64 * 1024 * 1024:
            raise ValueError("gövde boyutu geçersiz")
        return json.loads(self.rfile.read(uzun).decode("utf-8"))

    # ── GET ──
    def do_GET(self):
        yol = urllib.parse.urlparse(self.path).path
        if yol in ("/", "/index.html", "/kontrol_paneli.html"):
            try:
                icerik = open(PANEL_HTML, "rb").read()
            except OSError:
                self.hata_gonder("kontrol_paneli.html bulunamadı — kontrol_paneli.py ile AYNI klasörde olmalı.", 500)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(icerik)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(icerik)
            return
        if yol == "/api/durum":
            t = token_al()
            self.json_gonder({"ok": True, "sunucu": "E194-python", "port": self.server.server_address[1],
                              "token": bool(t), "tokenSon4": (t[-4:] if t else ""),
                              "repo": {"sahip": SAHIP, "repo": REPO, "dal": DAL,
                                       "icerikYolu": ICERIK_YOLU}})
            return
        if yol == "/api/gh/icerik":
            try:
                metin = gh_raw(ICERIK_YOLU, token_al(), taze=True)   # E183: taze çekim
                gv = metin.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(gv)))
                self.end_headers()
                self.wfile.write(gv)
            except urllib.error.HTTPError as e:
                self.hata_gonder("GitHub %d — site_icerik.json çekilemedi (token/izin/klasör?)" % e.code, 502)
            except Exception as e:
                self.hata_gonder("çekme hatası: " + str(e), 502)
            return
        if yol == "/api/gh/surum":
            try:
                metin = gh_raw(SURUM_YOLU, token_al())
                self.json_gonder(json.loads(metin))
            except Exception as e:
                self.hata_gonder("sürüm notu çekilemedi: " + str(e), 502)
            return
        if yol == "/api/gh/liste":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            klasor = (q.get("klasor") or ["resimler"])[0]
            if klasor not in ("resimler", "koruma", "icerik"):
                self.hata_gonder("izin verilmeyen klasör")
                return
            try:
                self.json_gonder({"ok": True, "klasor": klasor, "dosyalar": gh_liste(klasor, token_al())})
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    self.json_gonder({"ok": True, "klasor": klasor, "dosyalar": []})
                else:
                    self.hata_gonder("GitHub %d — liste alınamadı" % e.code, 502)
            except Exception as e:
                self.hata_gonder("liste hatası: " + str(e), 502)
            return
        if yol == "/api/token":
            t = token_al()
            self.json_gonder({"ok": True, "token": bool(t), "tokenSon4": (t[-4:] if t else "")})
            return
        self.hata_gonder("bilinmeyen yol", 404)

    # ── POST ──
    def do_POST(self):
        yol = urllib.parse.urlparse(self.path).path
        try:
            g = self.govde_oku()
        except Exception as e:
            self.hata_gonder("gövde okunamadı: " + str(e))
            return
        token = token_al()
        try:
            if yol == "/api/cevir":   # E183: Metinler otomatik çeviri
                son = metin_cevir(g.get("metin"), g.get("kaynak"), g.get("hedef"))
                if son.get("ok"):
                    self.json_gonder(son)
                else:
                    self.hata_gonder(son.get("mesaj") or "çeviri başarısız", 502)
                return
            if yol == "/api/rkm/coz":   # E194: RMK → resim (önizleme)
                self.json_gonder(rkm_coz(g.get("ad"), token))
                return
            if yol == "/api/gh/resim-yukle":   # E194: resim→RMK → GitHub push
                if not token:
                    self.hata_gonder("token yok — Ayarlar bölümüne github_pat_… yazıp kaydet (Contents: write)", 401)
                    return
                commit = rkm_yukle(g.get("ad"), g.get("icerik"), token)
                gunluk("resim yüklendi: resimler/%s_rkm.js → commit %s" % (rkm_taban(g.get("ad")), commit))
                self.json_gonder({"ok": True, "commit": commit,
                                  "yol": RESIM_KLASORU + "/" + rkm_taban(g.get("ad")) + "_rkm.js"})
                return
            if yol == "/api/token":
                t = str(g.get("token") or "").strip()
                if not t or len(t) > 255 or " " in t:
                    self.hata_gonder("token biçimi geçersiz")
                    return
                with open(TOKEN_DOSYA, "w", encoding="utf-8") as f:
                    f.write(t + "\n")
                try:
                    os.chmod(TOKEN_DOSYA, 0o600)
                except OSError:
                    pass
                self.json_gonder({"ok": True, "tokenSon4": t[-4:],
                                  "not": "github_token.txt kontrol_paneli.py'in yanına kaydedildi (zip'e dahil değildir)."})
                return
            self.hata_gonder("bilinmeyen API yolu", 404)
        except urllib.error.HTTPError as e:
            det = ""
            try:
                det = e.read().decode("utf-8")[:200]
            except Exception:
                pass
            self.hata_gonder("GitHub HTTP %d %s %s" % (e.code, e.reason, det), 502)
        except Exception as e:
            self.hata_gonder(str(e), 500)

    def handle_one_request(self):
        try:
            BaseHTTPRequestHandler.handle_one_request(self)
        except (ConnectionResetError, BrokenPipeError):
            pass


# ═══════════════════ BAŞLAT ═══════════════════
def main():
    port = PORT_VARSAYILAN
    tarayici = True
    arayuz = "127.0.0.1"
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--port":
            i += 1
            port = int(args[i])
        elif a == "--tum-ag":
            arayuz = "0.0.0.0"
        elif a in ("--tarayici-acma", "--no-browser"):
            tarayici = False
        i += 1

    t = token_al()
    print("═" * 66)
    print(" M2GOD KONTROL PANELİ v5 (E194) — Python sunuculu · E177_resim-avif-v6 uyumlu")
    print("═" * 66)
    print(" Adres      : http://127.0.0.1:%d  (kapatmak için Ctrl+C)" % port)
    print(" Panel      : kontrol_paneli.html %s" %
          ("✓ bulundu" if os.path.exists(PANEL_HTML) else "✗ YOK — aynı klasöre koyun!"))
    print(" GitHub     : %s/%s (%s)" % (SAHIP, REPO, DAL))
    print(" Token      : %s" % (("kayıtlı …" + t[-4:]) if t else
                                   "YOK — public depoda gerekmez; private depo/push için panelde 'Tarayıcıdaki Token'ı Sunucuya Kaydet' veya E194_GH_TOKEN"))
    print("═" * 66)

    srv = ThreadingHTTPServer((arayuz, port), Panel)
    if tarayici:
        threading.Timer(0.7, lambda: webbrowser.open("http://127.0.0.1:%d" % port)).start()
    gunluk("panel başladı: http://127.0.0.1:%d" % port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[panel] kapatıldı.")

if __name__ == "__main__":
    main()

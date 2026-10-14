#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════
 M2GOD KONTROL PANELİ v3 (E188) — PYTHON SUNUCULU
      (E188: Toplu Sıkıştır KALDIRILDI — yalnız içerik otomasyonu)
═══════════════════════════════════════════════════════════════════════
 KULLANIM:
     python kontrol_paneli.py               → http://127.0.0.1:8777 açılır
     python kontrol_paneli.py --port 9000   → farklı port
     python kontrol_paneli.py --tarayici-acma

 NE YAPAR:
   · kontrol_paneli.html'i sunar (içerik otomasyonu)
   · GitHub işlemlerini SUNUCUDA yapar: token github_token.txt'te/env'de
     (E179_GH_TOKEN; yedek: E178_GH_TOKEN) — token tarayıcıya asla gönderilmez
   · /api/gh/icerik: içerik çekimi (panelin "GitHub'dan Çek" düğmesi
     önce bunu dener, sonra raw fallback). TOKEN OPSİYONELDİR: public
     depoda token'sız da çalışır; token yalnız private depo + push için

 GEREKSİNİM: Python 3.8+ — ek paket YOK (yalnız standart kütüphane)
 TOKEN: ilk çalıştırmada paneldeki "Tarayıcıdaki Token'ı Sunucuya Kaydet"
        düğmesini kullanın (github_token.txt oluşturur) veya:
        E179_GH_TOKEN=github_pat_... python kontrol_paneli.py
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
VERI = os.path.join(KOK_DIZIN, "panel_veri")
DEPO = os.path.join(VERI, "depo")
AYARLAR = os.path.join(VERI, "ayarlar.json")

# ═══════════════════ GITHUB İSTEMCİSİ ═══════════════════
def token_al():
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
    b["User-Agent"] = "EpinSitesi-KontrolPaneli-E179"
    if token:
        b["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=b, method=metot)
    gv = None
    if veri is not None:
        gv = json.dumps(veri).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, gv, timeout=zaman) as r:
        return r.read()

def gh_raw(yol, token):
    return _istek(RAW_KOK + "/" + yol, token).decode("utf-8")

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

def gunluk(s):
    satir = time.strftime("%H:%M:%S ") + str(s)
    LOG_SON.append(satir)
    del LOG_SON[:-40]
    try:
        print(satir)
    except Exception:
        pass


def ayar_oku():
    a = dict(VARSAYILAN_AYAR)
    try:
        a.update(json.load(open(AYARLAR, encoding="utf-8")))
    except Exception:
        pass
    if not a.get("token"):
        t = token_al()          # eski akış: E179_GH_TOKEN env + github_token.txt
        if t:
            a["token"] = t
    return a


def ayar_yaz(a):
    os.makedirs(VERI, exist_ok=True)
    with KILIT:
        tmp = AYARLAR + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(a, f, ensure_ascii=False, indent=1)
        os.replace(tmp, AYARLAR)
    try:
        os.chmod(AYARLAR, 0o600)
    except Exception:
        pass


# ═══════════════════ SUNUCU ═══════════════════
class Panel(BaseHTTPRequestHandler):
    server_version = "EpinPanelE188/3.1"

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
            self.json_gonder({"ok": True, "sunucu": "E188-python", "port": self.server.server_address[1],
                              "token": bool(t), "tokenSon4": (t[-4:] if t else ""),
                              "repo": {"sahip": SAHIP, "repo": REPO, "dal": DAL,
                                       "icerikYolu": ICERIK_YOLU}})
            return
        if yol == "/api/gh/icerik":
            try:
                metin = gh_raw(ICERIK_YOLU, token_al())
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
                try:
                    a = ayar_oku()
                    a["token"] = t
                    ayar_yaz(a)      # iki token deposu ortak tutulur
                except Exception:
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
    print(" M2GOD KONTROL PANELİ v3 (E188) — Python sunuculu")
    print("═" * 66)
    print(" Adres      : http://127.0.0.1:%d  (kapatmak için Ctrl+C)" % port)
    print(" Panel      : kontrol_paneli.html %s" %
          ("✓ bulundu" if os.path.exists(PANEL_HTML) else "✗ YOK — aynı klasöre koyun!"))
    print(" GitHub     : %s/%s (%s)" % (SAHIP, REPO, DAL))
    print(" Token      : %s" % (("kayıtlı …" + t[-4:]) if t else
                                   "YOK — public depoda gerekmez; private depo/push için panelde 'Tarayıcıdaki Token'ı Sunucuya Kaydet' veya E179_GH_TOKEN"))
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

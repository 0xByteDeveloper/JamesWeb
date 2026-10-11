# JamesWeb

M2God / EpinSitesi içerik ve savunma deposu. Site (XAMPP paketi) açılışta
**icerik/site_icerik.json** dosyasını buradan çeker; koruma katmanı dosyaları
bu depoda yedeklenir.

## Yapı

| Yol | İçerik |
|---|---|
| `icerik/site_icerik.json` | Sitenin TEK içerik kaynağı: oyunlar, ürünler, fiyatlar, paketler, client/trailer, videolar, arayüz metinleri (en+tr), eksik kayıtlar |
| `resimler/` | Şifreli resim paketleri (`<ad>_rkm.js` — zlib-9 + XOR64 + base64 piksel verisi; site bunları canvas'a çizer) |
| `koruma/` | `kalkan.min.js` (savunma motoru) · `site_rkm.js` (şifreli tam site paketi) · `kilit_rkm.js` (şifreli alan adı kilidi) · kurallar belgesi · OKUBENI |

## Kontrol paneli

XAMPP paketindeki **kontrol_paneli.html**:
- Bu depodaki JSON'u çeker, dosyadan yükler, doğrular, indirir
- **GitHub'a Yükle** ile yeni commit açar (token tarayıcıda localStorage'da
  tutulur; dosyaya gömülmez)

## Site nasıl beslenir?

1. Panelde düzenle → doğrula → `GitHub'a Yükle`
2. Site (EpinSitesi_v2_1x.html) açılışta sırayla çeker:
   `GitHub (main) → yerel icerik/site_icerik.json → gömülü yedek`
3. Veri değiştiyse sayfa bir kez kendini yeniler ve veriyle boot eder.

## Kurallar

İçerik dosyasında bilinmeyen alanlar **korunur** — dilediğiniz anahtarı
ekleyebilirsiniz. Dil eklemek için metin değerlerine yeni dil kodu
(`de`, `ru`, …) ekleyin; çeviri API'si kullanılmaz (deterministik, çevrimdışı,
maliyetsiz).

Sürüm geçmişi site paketinde `OKUBENI_KALKAN.txt` içindedir.

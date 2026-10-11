# KOPYALANAMAZLIK KURALLARI — RKM Savunma Mimarisi (E171→E174)

Bu klasördeki dosyalar sitenin kopyalanamazlık/savunma katmanıdır. Aşağıdaki
kurallar sistemin **gerçekten uyguladığı** kurallardır; belge düzeyinde değil,
kod düzeyinde etkilidir.

## Dosyalar

| Dosya | Görev |
|---|---|
| `kalkan.min.js` | Savunma motoru (en ağır obfuscation) — siteyi saran dış kalkan |
| `site_rkm.js` | ŞİFRELİ TAM SİTE paketi (`RKM_VERI['site_paketi']`: zlib-9 + XOR64 + base64) — içinde okunabilir CSS/HTML/JS YOK |
| `kilit_rkm.js` | Şifreli alan adı listesi (`RKM_VERI['kalkan_kilit']`) — kalkanın çalışacağı alan adları |
| `OKUBENI_KALKAN.txt` | Kurulum + sürüm notları (E170→E174 düzeltim geçmişi) |
| `KOPYALANAMAZLIK-KURALLARI.md` | Bu belge |

## 1. Resim katmanı — RKM web-object engine v3

- Sitede korunan resimler için `<img>` ELEMANI YOKTUR → sağ-tık menüsünde
  "Resmi kaydet" maddesi hiç oluşmaz, `<img src>` bulaşmaz.
- Her resim `<canvas>`'a çizilir (WebGL + 2D blit). Resim hiçbir aşamada
  dosya/format olmaz; ham piksel verisi şifreli paketten çözülür.
- Kaynak paketler: `resimler/` klasöründeki `<ad>_rkm.js` dosyaları
  (`RKM_VERI['<ad>'] = {d,w,h,z,k}`: zlib-9 + XOR64 + base64 piksel verisi).
- `src` damgası: 1×1 şeffaf GIF + `#dosya.png` URI parçası (fetch yok, error
  yok, fallback tetiklenmez). Motor resim adını damgadan okur.
- `canvas`'lar `pointer-events:none` → tık hedefi daima kapsayıcıdır (inspect
  ile canvas'a ulaşılsa bile çizim `Image` nesnesinden geçmez).
- Dil değişimi/ürün geçişi: `RKM_CIZ(canvas, dosya)` ile aynı canvas yeniden
  çizilir; çözülmüş `base64` bellekte kalır (tekrar indirme yapmaz).

## 2. Kod katmanı

- Tam site `site_rkm.js` içinde şifrelidir; DOM'a kaynakta okunabilir CSS/HTML
  kalmaz. Kabuk `EpinSitesi_v2_1x.html` yalnız 3 script yükler.
- `kalkan.min.js` tasarım bilgisi içermez; deobfuscation denemelerinde bile
  içerik şifreli kalır (anahtar, aynı dosyanın içinde çözer şekilde tasarlandı —
  ekstra katman: `kilit_rkm.js` alan adı kilidi).

## 3. Politika (kasıtlı olarak SERBEST olanlar)

- Sol/sağ tık SERBEST · metin seçimi SERBEST · menüler normal çalışır.
  Koruma yapısal: yapı değiştirilmeden sağ-tık/indir senaryosu oluşamaz.
- E173 kararı: tarayıcı eklentisi logları (`[SBI Inspector]` vb.) site
  kaynaklı değildir; engellenmez.

## 4. İçerik kaynağı (E174)

- `icerik/site_icerik.json` (bu deponun `icerik/` klasörü) sitenin TEK içerik
  kaynağıdır. Koruma katmanına DOKUNMAZ — yalnız veri/metin besler.
- Resim paketleri yerelde bulunamazsa motor aynı adı GitHub raw'dan dener
  (yerel önceliklidir).

## 5. Sürüm

- v3.09 (E174) — değişiklik günlüğü `OKUBENI_KALKAN.txt` içinde.
- Üretim araçları XAMPP paketinde `uretici/` klasöründedir (bu depoda
  korunmaz — tasarım gereği paket üretimi yerelde kalır).

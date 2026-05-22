# SGC Akademik Dashboard Otomasyon Paketi

Bu paket, güncel dashboard sürümünü (`S. G. Çolak _ Doğrulanmış Akademik Dashboard`) esas alacak şekilde yeniden düzenlendi. Hakemlik bölümü, IF/Quartile tablosu, COST 2515 / Brezilya ikili iş birliği proje kayıtları ve NiCoSxSe1-x Scopus eşleşme düzeltmesi korunmuştur.

Paket, Scopus verisini 3 günde bir veya manuel olarak güncellemek için hazırlandı.

## Güvenlik
- Ekran görüntüsünde görünen mevcut Elsevier API key artık güvenli kabul edilmemelidir.
- O anahtarı iptal edip **yenisini** üretin.
- Yeni anahtarı hiçbir mesajda paylaşmayın.
- Yeni anahtarı yalnızca yerel `.env` dosyanıza yazın.

## Paket içeriği
- `Suleyman_Gokhan_Colak_dashboard_data_driven.html` : Güncel dashboard görünümü; `dashboard_data.js` ile beslenir
- `index.html` : GitHub Pages için aynı güncel dashboard kopyası
- `dashboard_data.json` : Ana veri dosyası
- `dashboard_data.js` : HTML'nin kullandığı JS veri dosyası
- `update_dashboard.py` : Türetilmiş alanları hesaplayan yardımcı script
- `auto_sync_dashboard.py` : İnternetten veri çekip dashboard verisini güncelleyen ana script
- `run_sync.bat` : Tek tık çalıştırma
- `setup_windows_task.ps1` : Windows Görev Zamanlayıcı kurulumu
- `.env.example` : Ortam değişkeni şablonu

## Çalışma mantığı
1. Scopus API üzerinden yayın kayıtları çekilir.
2. Kayıtlardan toplam doküman, atıf, OA sayısı, en çok atıf alan yayınlar ve yıllık dağılım yeniden hesaplanır.
3. OpenAlex üzerinden ORCID ile eşleşen yazar bulunur.
4. OpenAlex yazar özetinden toplam atıf, h-index ve i10-index alınır.
5. `dashboard_data.json` ve `dashboard_data.js` güncellenir; dashboard HTML dosyası bu veri dosyalarını okur.
6. İstenirse git commit + push yapılarak GitHub Pages sayfası otomatik yenilenir.

## 1) İlk kurulum
Aynı klasörde terminal açın.

### Sanal ortam önerisi
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2) .env oluşturma
`.env.example` dosyasını `.env` adıyla kopyalayın.

```powershell
copy .env.example .env
```

Sonra `.env` içine şu alanları doldurun:
- `SCOPUS_API_KEY` = yeni ürettiğiniz **gizli** Elsevier key
- `SCOPUS_AUTHOR_ID` = `55877289000`
- `ORCID_ID` = `0000-0002-4978-1499`
- `OPENALEX_API_KEY` = isteğe bağlı
- `OPENALEX_EMAIL` = isteğe bağlı ama tavsiye edilir

## 3) Manuel test
```powershell
python auto_sync_dashboard.py --data dashboard_data.json --out-js dashboard_data.js --verbose
```

Başarılıysa:
- `dashboard_data.json` güncellenir
- `dashboard_data.js` güncellenir
- HTML açıldığında yeni veriler görünür

## 4) Tek tık çalıştırma
`run_sync.bat` dosyasına çift tıklayın.

## 5) 3 günde bir otomatik çalışma
PowerShell'i **Yönetici** olarak açın ve proje klasöründe şu komutu verin:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_windows_task.ps1 -ProjectDir "$PWD" -PythonExe "$PWD\.venv\Scripts\python.exe" -StartTime "09:00"
```

Bu işlem görevi 3 günde bir 09:00'da çalıştırır.

## 6) Dashboardı link olarak güncel paylaşma
Birine dosya yollamak güncel kalmaz. Güncel link için en doğru yöntem GitHub Pages'tir.

Önerilen akış:
1. GitHub'da bir repo açın.
2. Bu klasörü o repoya koyun.
3. GitHub Pages'i `main` branch üzerinden açın.
4. `.env` dosyasını **repoya koymayın**.
5. `GIT_AUTO_PUSH=1` ve `GIT_BRANCH=main` ayarlarsanız script veri güncelledikten sonra otomatik push yapar.

> Not: GitHub Pages statik dosya sunar. Bu nedenle repo güncellendiğinde paylaştığınız link de güncel kalır.

## 7) Sık karşılaşılan sorunlar
### 401 / 403
- API key hatalı olabilir.
- Kurumsal Scopus erişimi gerekebilir.
- Bazı Elsevier endpointleri abonelik veya yetki kısıtı isteyebilir.

### OpenAlex bulunamadı
- ORCID kaydı OpenAlex ile eşleşmeyebilir.
- Bu durumda script yine çalışır; sadece scholar bloğu OpenAlex ile yenilenmez.

### HTML eski veri gösteriyor
- `dashboard_data.js` aynı klasörde mi kontrol edin.
- Tarayıcı önbelleğini temizleyin.

## 8) Güvenlik disiplini
- API key'i asla HTML/JS içine gömmeyin.
- API key'i asla GitHub'a push etmeyin.
- `.env` dosyasını `.gitignore` içine ekleyin.
- Daha önce paylaşılan key'i iptal edin.

## Güncel dashboard sürümü
- Bu paket içindeki HTML, kullanıcı tarafından verilen en güncel dashboard dosyasından dönüştürülmüştür.
- API anahtarı HTML içine gömülmez; yalnızca `.env` dosyasında kalmalıdır.
- Google Scholar ve JCR/Quartile alanları kontrollü manuel doğrulama gerektirir; Scopus metrikleri API ile güncellenebilir.

## 7) GitHub Pages üzerinde otomatik güncelleme

Bu paketin içinde `.github/workflows/auto-update-dashboard.yml` dosyası vardır. Bu dosya GitHub Actions ile haftada bir kez çalışır ve Scopus/OpenAlex verilerini güncelleyerek `dashboard_data.json` ve `dashboard_data.js` dosyalarını tekrar commit eder.

### GitHub'da secret ekleme
Repository sayfasında:

```text
Settings → Secrets and variables → Actions → New repository secret
```

Şunu ekleyin:

```text
Name: SCOPUS_API_KEY
Secret: Elsevier/Scopus API key'iniz
```

API key'i asla `index.html`, `dashboard_data.js`, `dashboard_data.json` veya README içine yazmayın.

### Değişkenler
Aynı bölümde `Variables` sekmesine isterseniz şunları ekleyebilirsiniz:

```text
SCOPUS_AUTHOR_ID = 55877289000
ORCID_ID = 0000-0002-4978-1499
OPENALEX_EMAIL = kendi e-posta adresiniz
```

### Manuel çalıştırma
GitHub üzerinde:

```text
Actions → Auto-update academic dashboard → Run workflow
```

Başarılı çalışırsa birkaç dakika içinde GitHub Pages linkindeki dashboard güncellenir.

### Otomatik çalışma sıklığı
Varsayılan ayar haftada bir Pazartesi 06:00 UTC'dir. Bu, Türkiye saatiyle yaklaşık 09:00'a karşılık gelir. Sıklığı değiştirmek için `.github/workflows/auto-update-dashboard.yml` içindeki `cron` satırını düzenleyebilirsiniz.

### Önemli not
Bazı Elsevier/Scopus API anahtarları yalnızca kurum IP'si veya VPN üzerinden çalışabilir. Böyle bir durumda GitHub Actions sunucusundan gelen istek 401/403 hatası verebilir. Bu olursa en güvenli yöntem yerel bilgisayarda `run_sync.bat` ile güncelleme yapıp değişen dosyaları GitHub'a push etmektir.

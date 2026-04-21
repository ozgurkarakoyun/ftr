# FizTak — Fizik Tedavi Takip Sistemi

Flask + SQLite tabanlı fizik tedavi randevu ve seans takip uygulaması.

## Özellikler
- Hasta kayıt ve yönetimi
- Randevu takvimi
- Seans girişi (SİS, HIL, ESWT, Kinezyo Bant, İnfraruj, TENS, Parafin, Lipödem, Bandajlama, Skolyoz Egz., Egzersiz, Kontrast Banyo)
- Ağrı skoru takibi
- PDF rapor

## Railway'e Deploy

### 1. GitHub'a yükle
```bash
git init
git add .
git commit -m "ilk commit"
git remote add origin https://github.com/KULLANICI/fiztак.git
git push -u origin main
```

### 2. Railway'de proje aç
1. railway.app → New Project → Deploy from GitHub repo
2. Repo'yu seç → Deploy

### 3. Ortam değişkeni (isteğe bağlı)
Railway dashboard → Variables:
```
DB_PATH=/data/fiztак.db
```

> **Not:** Railway'de SQLite dosyası her deploy'da sıfırlanabilir.
> Kalıcı veri için Railway'e **Volume** ekleyin:
> Settings → Volumes → Mount Path: `/data`
> Sonra `DB_PATH=/data/fiztак.db` ekleyin.

### Volume Ekleme (Önemli!)
Railway ücretsiz planda volume desteklemiyor.
Hobby plan ($5/ay) gereklidir.
Alternatif: SQLite yerine Railway PostgreSQL eklentisi kullanılabilir.

## Lokal Geliştirme
```bash
pip install -r requirements.txt
python app.py
# http://localhost:5000
```

## Dosya Yapısı
```
fiztак/
├── app.py              # Flask API + DB
├── templates/
│   └── index.html      # Tek sayfa uygulama
├── requirements.txt
├── Procfile
└── railway.toml
```

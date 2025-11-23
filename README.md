
# 📺 YT Screenshot Extractor PRO  
YouTube videolarından ve playlistlerden otomatik FFmpeg tabanlı 4K ekran görüntüsü alma aracı (Metro UI - Python GUI)
![Uygulama Ekran Görüntüsü](s1.png)
---

## 🌟 Özellikler

### 🎥 Video & Playlist İşleme
- YouTube video linklerinden kare çıkarma  
- Shorts URL desteği  
- Playlist URL veya sadece playlist ID desteği  
- Playlist içindeki tüm videolar otomatik işlenir  
- Saniye alanı boşsa playlist için otomatik 5 saniye uygulanır  
- Videonun çözünürlüğü GUI üzerinde gösterilir  
- Videonun süresi (mm:ss / hh:mm:ss) gösterilir  
- Çoklu URL satırı → Her satır kendi saniyeleriyle çalışır  
- Türkçe karakterler dosya adında otomatik bilinçli ASCII’ye dönüştürülür (Ş → S, Ç → C, İ → I, Ü → U, Ö → O, Ğ → G)

---

### 🖼 Frame & Thumbnail Çıkartma
- FFmpeg ile %100 doğru kare yakalama (stream üzerinden)  
- Frame alma işlemi çoklu thread (paralel) ile yapılır  
- Desteklenen saniye formatları:
  - 5  
  - 1:20 (MM:SS)  
  - 00:01:33 (HH:MM:SS)  
  - 2:15:50 (HH:MM:SS)  
- Frame isim formatı:
  {title}_{timestamp}_{id}.png
  Örn: Teskilat_158_Bolum_00-01-20_ndTlGkIZGl4.png
- Thumbnail indirir  
- Her video için ayrı klasör oluşturur  
- Son alınan frame, önizleme panelinde gösterilir  

Örnek klasör yapısı:
cikti/
 ├─ Teskilat_158_Bolum/
 │    ├─ Teskilat_158_Bolum_00-01-20_ndTlGkIZGl4.png
 │    ├─ Teskilat_158_Bolum_thumbnail.png
 ├─ Baska_Video/

---

### 📂 Playlist Özellikleri
- Playlist URL veya playlist ID ile tüm videolar otomatik alınır  
- Saniye alanı boşsa → otomatik 5 saniye kullanılır  
- Playlistteki her videoda aynı saniyeler uygulanır  
- Log panelinde playlist videoları “--- Playlist video X/Y ---” şeklinde görünür  
- Playlist indirilmiyor; kareler stream üzerinden ffmpeg ile alınır  

---

### ⚡ Paralel Frame Sistemi
- Her saniye için ayrı FFmpeg iş parçacığı  
- CPU çekirdeklerine göre otomatik optimize (2–8 worker)  
- Çok hızlı çalışır  
- UI asla donmaz  

---

### 🎨 Metro UI Arayüz
- Modern CustomTkinter arayüz  
- Tablo tarzı URL + Saniye giriş alanı  
- Sınırsız satır ekleme / silme  
- Geniş log paneli  
- Video bilgi paneli  
- Son frame küçük önizleme kutusu  
- Scrollable liste

---

## 🛠 Kullanılan Teknolojiler
- Python 3.x  
- CustomTkinter  
- Pillow  
- OpenCV (sadece önizleme için)  
- yt-dlp  
- FFmpeg (zorunlu — kare çıkarma buradan yapılır)  
- ThreadPoolExecutor  

Not: FFmpeg mutlaka yüklü olmalıdır. Windows kullanıcıları ffmpeg.exe dosyasını program klasörüne koyabilir.

---

## 📦 Kurulum

git clone https://github.com/ebubekirbastama/yt-screenshot-extractor.git
cd yt-screenshot-extractor
pip install -r requirements.txt

requirements.txt:
yt-dlp
customtkinter
opencv-python
pillow

---

## ▶️ Çalıştırma
python youtube_screenshot_extractor_pro.py

---

## 📘 Kullanım

### URL / Playlist / Playlist ID Örnekleri:
https://www.youtube.com/watch?v=Example123  
https://www.youtube.com/shorts/ABCDEF  
https://www.youtube.com/playlist?list=PLxxxxxx  
PLX4Y6y8Hmb9MCB0YsiYJvLjiIzcej2tew  

### Saniye Formatı:
5  
5, 1:20, 00:01:32, 2:15:00  

### Çalışma:
- GUI donmaz  
- Playlist’teki tüm videolar işlenir  
- Paralel ffmpeg frame çıkartma  
- Log paneli güncellenir  
- Önizleme aktif

---

## 📄 Log Paneli Gösterimleri
- Video başlığı  
- Çözünürlük ve süre  
- Playlist video indeksi (X/Y)  
- Alınan frame listesi  
- Thumbnail durumu  

---

## ⚙️ Gelecek Özellikler
- Her saniyeden kare çıkarma modu  
- Tema seçme  
- Çıktı klasörü seçme  
- Sesli bildirim  
- “İlk X videoyu işle” modu  
- Playlist videolarını indirip localden işleme modu  

---

## 👨‍💻 Geliştirici
Ebubekir Bastama  
GitHub: https://github.com/ebubekirbastama  

---

## 📜 Lisans
MIT Lisansı

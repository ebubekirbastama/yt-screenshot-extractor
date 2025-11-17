import customtkinter as ctk
import os
import cv2
import re
from tkinter import messagebox
import urllib.request
from yt_dlp import YoutubeDL
from PIL import Image
from threading import Thread

# ==========================================================
# GENEL AYARLAR
# ==========================================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BASE_OUTPUT = os.path.join(os.getcwd(), "cikti")
os.makedirs(BASE_OUTPUT, exist_ok=True)

preview_image_obj = None  # Önizleme için global referans


# ==========================================================
# YARDIMCI FONKSİYONLAR
# ==========================================================
def clean_youtube_url(url: str) -> str:
    """Shorts / youtu.be / watch?v= formatlarını normalize eder."""
    url = url.strip()

    # Shorts formatı
    if "shorts" in url:
        match = re.search(r"shorts/([A-Za-z0-9_-]{11})", url)
        if match:
            vid = match.group(1)
            return f"https://www.youtube.com/watch?v={vid}"

    # watch?v=
    match = re.search(r"v=([A-Za-z0-9_-]{11})", url)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"

    # youtu.be/ID
    match = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", url)
    if match:
        vid = match.group(1)
        return f"https://www.youtube.com/watch?v={vid}"

    return url


def format_duration(seconds):
    """Saniyeyi 00:00 veya 00:00:00 formatına çevirir."""
    if not seconds:
        return "bilinmiyor"
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "bilinmiyor"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"


def slugify_title(title: str) -> str:
    """Dosya sistemi için güvenli başlık üretir."""
    if not title:
        return "video"
    s = title.strip()
    # Windows için yasak olan karakterleri temizle
    s = re.sub(r'[\\/*?:"<>|]', "", s)
    # Boşlukları alt çizgi yap
    s = re.sub(r"\s+", "_", s)
    if not s:
        s = "video"
    # Çok uzun olmasın (örnek: 150 karakterle sınırla)
    return s[:150]


# ==========================================================
# YT-DLP İLE BİLGİ ÇEKME
# ==========================================================
def get_youtube_info(url: str):
    """Tek bir video için en iyi video formatını getirir."""
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "format": "bestvideo"
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        return None


def get_playlist_videos(playlist_url):
    """Playlist içindeki tüm video ID'lerini döndürür."""
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
            if "entries" not in info:
                return []
            return [e["id"] for e in info["entries"] if e and "id" in e]
    except Exception:
        return []


# ==========================================================
# GUI GÜNCELLEYEN YARDIMCI FONKSİYONLAR (THREAD SAFE)
# ==========================================================
def gui_log(msg: str):
    app.after(0, lambda: (_log_insert(msg)))


def _log_insert(msg: str):
    txt_log.insert("end", msg)
    txt_log.see("end")


def gui_set_video_info(text: str):
    app.after(0, lambda: lbl_video_info.configure(text=text))


def gui_set_playlist_progress(idx, total):
    def _update():
        if total <= 0:
            progressbar_playlist.set(0)
            lbl_playlist_progress.configure(text="Playlist ilerleme: -")
        else:
            p = idx / total
            progressbar_playlist.set(p)
            lbl_playlist_progress.configure(
                text=f"Playlist ilerleme: {idx}/{total} (%{int(p * 100)})"
            )

    app.after(0, _update)


def gui_set_single_video_progress():
    app.after(0, lambda: (
        progressbar_playlist.set(1),
        lbl_playlist_progress.configure(text="Playlist ilerleme: Tek video")
    ))


def gui_set_button_running(is_running: bool):
    def _update():
        if is_running:
            btn_start.configure(state="disabled", text="⏳ Çalışıyor...")
        else:
            btn_start.configure(state="normal", text="📷 Başlat (Frame + Thumbnail + Playlist)")
    app.after(0, _update)


def gui_show_done_message():
    app.after(0, lambda: messagebox.showinfo("Bitti", "Tüm işlemler başarıyla tamamlandı."))


def gui_set_preview_from_frame(frame):
    """Frame'den önizleme oluşturur (GUI thread içinde çalışır)."""
    global preview_image_obj
    try:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(frame_rgb)

        max_w = 220
        w, h = pil_img.size
        if w == 0:
            return
        new_h = int(h * (max_w / w))
        pil_img = pil_img.resize((max_w, new_h), Image.LANCZOS)

        preview_image_obj = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(max_w, new_h))
        preview_label.configure(image=preview_image_obj, text="")
    except Exception:
        pass


# ==========================================================
# FRAME ÇIKARTMA + ÖNİZLEME (THREAD İÇİNDEN ÇAĞRILIR)
# ==========================================================
def extract_frames(video_url, times, save_folder, safe_title):
    cap = cv2.VideoCapture(video_url)

    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ret, frame = cap.read()
        if ret:
            filename = f"{safe_title}_t{t}s.png"
            out_path = os.path.join(save_folder, filename)
            cv2.imwrite(out_path, frame)
            gui_log(f"[OK] {t}s frame kaydedildi → {filename}\n")

            # Önizleme güncelle
            app.after(0, lambda f=frame: gui_set_preview_from_frame(f))
        else:
            gui_log(f"[X] {t}s frame alınamadı.\n")

    cap.release()


# ==========================================================
# THUMBNAIL İNDİRME (THREAD İÇİNDEN)
# ==========================================================
def download_thumbnail(info, save_folder, safe_title):
    thumb = info.get("thumbnail")
    if not thumb:
        gui_log("[X] Thumbnail bulunamadı.\n")
        return

    try:
        filename = f"{safe_title}_thumbnail.png"
        out_path = os.path.join(save_folder, filename)
        urllib.request.urlretrieve(thumb, out_path)
        gui_log(f"[OK] Thumbnail kaydedildi → {filename}\n")
    except Exception as e:
        gui_log(f"[X] Thumbnail indirilemedi: {e}\n")


# ==========================================================
# TEK VİDEOYU İŞLE (THREAD İÇİNDEN)
# ==========================================================
def process_single_video(url, times):
    info = get_youtube_info(url)
    if not info:
        gui_log(f"[X] Video bilgisi alınamadı → {url}\n\n")
        return

    vid = info.get("id", "NOID")
    title = info.get("title", "Bilinmeyen Başlık")
    width = info.get("width")
    height = info.get("height")
    duration = info.get("duration")

    res_str = f"{width}x{height}" if width and height else "bilinmiyor"
    dur_str = format_duration(duration)
    safe_title = slugify_title(title)

    gui_set_video_info(f"Video: {title} | Çözünürlük: {res_str} | Süre: {dur_str}")
    gui_log(f"\n🎬 {title}\nID: {vid}\nÇözünürlük: {res_str} | Süre: {dur_str}\n")

    folder = os.path.join(BASE_OUTPUT, safe_title or vid)
    os.makedirs(folder, exist_ok=True)

    extract_frames(info["url"], times, folder, safe_title)
    download_thumbnail(info, folder, safe_title)

    gui_log(f"✔ Bitti → {folder}\n\n")


# ==========================================================
# ANA İŞ PARÇASI (THREAD)
# ==========================================================
def worker_process(urls, times):
    # Başlat
    gui_set_video_info("Video bilgisi: -")
    gui_set_playlist_progress(0, 0)

    for url in urls:
        gui_log(f"\n=== İşleniyor: {url} ===\n")

        # Playlist mi?
        if "list=" in url:
            gui_log("▶ Playlist algılandı, video listesi alınıyor...\n")
            playlist_ids = get_playlist_videos(url)

            if not playlist_ids:
                gui_log("[X] Playlist okunamadı veya boş.\n")
                continue

            total = len(playlist_ids)
            gui_log(f"Toplam video: {total}\n\n")

            for idx, vid in enumerate(playlist_ids, start=1):
                vurl = f"https://www.youtube.com/watch?v={vid}"
                gui_set_playlist_progress(idx, total)
                process_single_video(vurl, times)

            gui_set_playlist_progress(total, total)
        else:
            gui_set_single_video_progress()
            process_single_video(url, times)

    gui_log(f"\n✔ TÜM İŞLEM TAMAMLANDI\nÇıktı klasörü: {BASE_OUTPUT}\n")
    gui_set_button_running(False)
    gui_show_done_message()


# ==========================================================
# BUTON TIK: PARAM HAZIRLA + THREAD BAŞLAT
# ==========================================================
def start_process():
    urls_raw = txt_urls.get("0.0", "end").strip()
    if not urls_raw:
        messagebox.showwarning("Uyarı", "Lütfen en az bir URL veya playlist ID gir.")
        return

    raw_lines = [u.strip() for u in urls_raw.splitlines() if u.strip()]
    urls = []

    # HTTP yoksa playlist ID kabul et
    for line in raw_lines:
        if line.startswith("http"):
            urls.append(clean_youtube_url(line))
        else:
            urls.append(f"https://www.youtube.com/playlist?list={line}")

    # Saniyeler
    try:
        times = [int(x.strip()) for x in entry_times.get().split(",") if x.strip()]
    except Exception:
        messagebox.showerror("Hata", "Saniyeler yanlış formatta. Ör: 0,1,3,5")
        return

    # Log ve info temizle
    txt_log.configure(state="normal")
    txt_log.delete("0.0", "end")
    lbl_video_info.configure(text="Video bilgisi: -")
    progressbar_playlist.set(0)
    lbl_playlist_progress.configure(text="Playlist ilerleme: -")

    gui_set_button_running(True)

    # Ağır işlemi thread'e al
    t = Thread(target=worker_process, args=(urls, times), daemon=True)
    t.start()


# ==========================================================
# 🎨 METRO TASARIMLI GUI
# ==========================================================
app = ctk.CTk()
app.title("YouTube Screenshot Extractor PRO")
app.geometry("900x700")
app.minsize(900, 700)

# HEADER
header = ctk.CTkFrame(app, height=60, corner_radius=0)
header.pack(fill="x")

ctk.CTkLabel(
    header,
    text="📺 YouTube Screenshot Extractor PRO",
    font=("Segoe UI Semibold", 22)
).pack(side="left", padx=20)

ctk.CTkLabel(
    header,
    text="4K Frames + Thumbnail · Playlist Destekli · Metro UI",
    font=("Segoe UI", 13)
).pack(side="right", padx=20)

# MAIN FRAME
main = ctk.CTkFrame(app, corner_radius=16)
main.pack(fill="both", expand=True, padx=20, pady=20)

# URL BOX
box1 = ctk.CTkFrame(main, corner_radius=12)
box1.pack(fill="x", padx=12, pady=(15, 10))

ctk.CTkLabel(
    box1,
    text="YouTube URL veya Playlist ID Listesi (Her satıra 1 tane):",
    font=("Segoe UI Semibold", 14)
).pack(anchor="w", padx=10, pady=8)

txt_urls = ctk.CTkTextbox(box1, height=120, font=("Segoe UI", 13))
txt_urls.pack(fill="x", padx=10, pady=(0, 10))

# ALT FRAME (sol: ayarlar/log, sağ: önizleme)
bottom_frame = ctk.CTkFrame(main, corner_radius=12)
bottom_frame.pack(fill="both", expand=True, padx=12, pady=(10, 10))

left_frame = ctk.CTkFrame(bottom_frame, corner_radius=12)
left_frame.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=10)

right_frame = ctk.CTkFrame(bottom_frame, corner_radius=12, width=240)
right_frame.pack(side="right", fill="y", padx=(8, 0), pady=10)

# SOL: Saniye + buton + progress + log
box2 = ctk.CTkFrame(left_frame, corner_radius=12)
box2.pack(fill="x", padx=10, pady=(10, 10))

ctk.CTkLabel(
    box2,
    text="Kaçıncı saniyelerden frame alınacak? (örn: 0,1,3,5)",
    font=("Segoe UI Semibold", 14)
).pack(anchor="w", padx=10, pady=8)

entry_times = ctk.CTkEntry(box2, height=36, font=("Segoe UI", 14))
entry_times.insert(0, "0,1,3,5")
entry_times.pack(fill="x", padx=10, pady=(0, 10))

# Playlist progress bar
progress_frame = ctk.CTkFrame(box2, corner_radius=8)
progress_frame.pack(fill="x", padx=10, pady=(0, 10))

lbl_playlist_progress = ctk.CTkLabel(
    progress_frame,
    text="Playlist ilerleme: -",
    font=("Segoe UI", 12)
)
lbl_playlist_progress.pack(anchor="w", padx=6, pady=(4, 2))

progressbar_playlist = ctk.CTkProgressBar(progress_frame, height=10)
progressbar_playlist.pack(fill="x", padx=6, pady=(0, 6))
progressbar_playlist.set(0)

# Başlat butonu
btn_start = ctk.CTkButton(
    box2,
    text="📷 Başlat (Frame + Thumbnail + Playlist)",
    font=("Segoe UI Semibold", 16),
    height=40,
    fg_color="#0078D7",
    hover_color="#005A9E",
    command=start_process
)
btn_start.pack(pady=(0, 10), padx=10)

# Video info + log
box3 = ctk.CTkFrame(left_frame, corner_radius=12)
box3.pack(fill="both", expand=True, padx=10, pady=(0, 10))

lbl_video_info = ctk.CTkLabel(
    box3,
    text="Video bilgisi: -",
    font=("Segoe UI", 12)
)
lbl_video_info.pack(anchor="w", padx=10, pady=8)

ctk.CTkLabel(
    box3,
    text="İşlem Logu:",
    font=("Segoe UI Semibold", 14)
).pack(anchor="w", padx=10, pady=(0, 4))

txt_log = ctk.CTkTextbox(box3, font=("Consolas", 11))
txt_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))

# SAĞ: ÖNİZLEME PANELİ
ctk.CTkLabel(
    right_frame,
    text="Son Frame Önizleme",
    font=("Segoe UI Semibold", 14)
).pack(anchor="center", pady=(10, 5))

preview_label = ctk.CTkLabel(
    right_frame,
    text="Henüz önizleme yok",
    width=220,
    height=140,
    corner_radius=12
)
preview_label.pack(pady=(5, 10), padx=10)

ctk.CTkLabel(
    right_frame,
    text="Her işlenen videoda\nson alınan frame burada görünür.",
    font=("Segoe UI", 11),
    justify="center"
).pack(pady=(0, 10))

# UYGULAMAYI BAŞLAT
app.mainloop()

import customtkinter as ctk
import os
import cv2
import re
import subprocess
import shutil
from tkinter import messagebox
import urllib.request
from yt_dlp import YoutubeDL
from PIL import Image
from threading import Thread
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================================================
# GENEL AYARLAR
# ==========================================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BASE_OUTPUT = os.path.join(os.getcwd(), "cikti")
os.makedirs(BASE_OUTPUT, exist_ok=True)

preview_image_obj = None
url_rows = []  # (url_entry, times_entry, row_frame)

MAX_FRAME_WORKERS = max(2, min(8, (os.cpu_count() or 4)))
DEFAULT_TIME_IF_EMPTY = [5]  # saniye kutusu boşsa playlist veya tek video için fallback


# ==========================================================
# TÜRKÇE -> ASCII + DOSYA GÜVENLİ SLUG
# ==========================================================
TR_MAP = str.maketrans({
    "ç": "c", "Ç": "C",
    "ğ": "g", "Ğ": "G",
    "ı": "i", "İ": "I",
    "ö": "o", "Ö": "O",
    "ş": "s", "Ş": "S",
    "ü": "u", "Ü": "U",
})

def turkish_to_ascii(s: str) -> str:
    return (s or "").translate(TR_MAP)

def slugify_title(title: str) -> str:
    """Türkçe karakterleri düzeltir, dosya sistemi için temizler."""
    s = turkish_to_ascii(title).strip()
    s = re.sub(r'[\\/*?:"<>|]', "", s)  # yasak karakterler
    s = re.sub(r"\s+", "_", s)          # boşluk -> _
    s = re.sub(r"_+", "_", s)
    if not s:
        s = "video"
    return s[:150]


# ==========================================================
# ZAMAN PARSE (10, 1:32, 00:01:32, 2:15:50)
# ==========================================================
def parse_time_to_seconds(tstr):
    tstr = tstr.strip()
    if ":" not in tstr:
        return int(tstr)

    parts = [p.strip() for p in tstr.split(":")]
    if len(parts) == 2:  # MM:SS
        m, s = parts
        return int(m) * 60 + int(s)
    if len(parts) == 3:  # HH:MM:SS
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + int(s)

    raise ValueError(f"Geçersiz zaman formatı: {tstr}")

def parse_time_list(times_text):
    """
    "5, 1:20, 00:02:30" gibi listeyi parse eder.
    Boşsa DEFAULT_TIME_IF_EMPTY döndürür.
    """
    times_text = (times_text or "").strip()
    if not times_text:
        return DEFAULT_TIME_IF_EMPTY[:]

    items = [x.strip() for x in times_text.split(",") if x.strip()]
    if not items:
        return DEFAULT_TIME_IF_EMPTY[:]

    out = []
    for it in items:
        out.append(parse_time_to_seconds(it))
    return out

def seconds_to_timestamp(sec: int) -> str:
    """00-01-32 formatı (dosya adı güvenli)."""
    sec = int(sec)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}-{m:02d}-{s:02d}"


# ==========================================================
# YARDIMCI — YouTube URL normalize
# ==========================================================
def clean_youtube_url(url: str) -> str:
    url = url.strip()

    if "shorts" in url:
        m = re.search(r"shorts/([A-Za-z0-9_-]{11})", url)
        if m:
            return f"https://www.youtube.com/watch?v={m.group(1)}"

    m = re.search(r"v=([A-Za-z0-9_-]{11})", url)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"

    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", url)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"

    return url


# ==========================================================
# ffmpeg yolu
# ==========================================================
def get_ffmpeg_path():
    fn = shutil.which("ffmpeg")
    if fn:
        return fn

    local = os.path.join(os.getcwd(), "ffmpeg.exe")
    if os.path.exists(local):
        return local

    return None


# ==========================================================
# YT-DLP — info + playlist
# ==========================================================
def get_youtube_info(url: str):
    try:
        with YoutubeDL({
            "quiet": True,
            "skip_download": True,
            "format": "best"
        }) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        return None

def get_playlist_videos(url):
    """
    Playlist içindeki tüm video ID'lerini döndürür.
    Playlist URL'si watch+list içerebilir: yine playlist olarak ele alınacak.
    """
    try:
        with YoutubeDL({
            "quiet": True,
            "extract_flat": True,
            "skip_download": True
        }) as ydl:
            info = ydl.extract_info(url, download=False)
            if "entries" not in info:
                return []
            return [e["id"] for e in info["entries"] if e and "id" in e]
    except:
        return []


def format_duration(seconds):
    if not seconds:
        return "bilinmiyor"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02}:{m:02}:{s:02}"
    else:
        return f"{m:02}:{s:02}"


# ==========================================================
# GUI yardımcıları (thread-safe)
# ==========================================================
def gui_log(msg: str):
    app.after(0, lambda: _log(msg))

def _log(msg: str):
    txt_log.insert("end", msg)
    txt_log.see("end")

def gui_set_button_running(running: bool):
    app.after(0, lambda: _btn_state(running))

def _btn_state(running):
    btn_start.configure(state="disabled" if running else "normal")
    btn_add_row.configure(state="disabled" if running else "normal")

def gui_set_video_info(t):
    app.after(0, lambda: lbl_video_info.configure(text=t))

def gui_set_preview(frame):
    global preview_image_obj
    try:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        w, h = pil.size
        maxw = 220
        new_h = int(h * (maxw / w))
        pil = pil.resize((maxw, new_h), Image.LANCZOS)

        preview_image_obj = ctk.CTkImage(light_image=pil, dark_image=pil, size=(maxw, new_h))
        preview_label.configure(image=preview_image_obj, text="")
    except:
        pass


# ==========================================================
# FFmpeg ile TEK frame çıkarma (worker)
# ==========================================================
def _ffmpeg_grab_one(ffmpeg, stream_url, sec, out_path):
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel", "error",
        "-ss", str(sec),
        "-i", stream_url,
        "-frames:v", "1",
        "-q:v", "2",
        "-y",
        out_path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = (r.returncode == 0 and os.path.exists(out_path))
    return ok, (r.stderr or "").strip()


# ==========================================================
# FFmpeg ile frame çıkarma (PARALEL)
# Dosya adı: {title}_{timestamp}_{id}.png
# ==========================================================
def extract_frames_ffmpeg_parallel(stream_url, times, save_folder, safe_title, video_id):
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        gui_log("[X] ffmpeg bulunamadı! Program klasörüne ffmpeg.exe koy veya PATH'e ekle.\n")
        return

    futures = []
    with ThreadPoolExecutor(max_workers=MAX_FRAME_WORKERS) as ex:
        for sec in times:
            ts = seconds_to_timestamp(sec)
            filename = f"{safe_title}_{ts}_{video_id}.png"
            out_path = os.path.join(save_folder, filename)
            futures.append(ex.submit(_ffmpeg_grab_one, ffmpeg, stream_url, sec, out_path))

        for fut in as_completed(futures):
            try:
                ok, err = fut.result()
                # futures içinde çıkış yolu yoksa yeniden bulmak için sec'yi maplemek gerekir.
                # Bu yüzden basitçe klasörde en son yazılanı preview'a basıyoruz.
                if ok:
                    gui_log("[OK] Frame kaydedildi.\n")
                    # preview için son dosyayı bul
                    try:
                        newest = max(
                            (os.path.join(save_folder, f) for f in os.listdir(save_folder) if f.endswith(".png")),
                            key=os.path.getmtime
                        )
                        frame = cv2.imread(newest)
                        if frame is not None:
                            app.after(0, lambda f=frame: gui_set_preview(f))
                    except:
                        pass
                else:
                    gui_log(f"[X] Frame alınamadı. {err}\n")
            except Exception as e:
                gui_log(f"[X] Worker hata: {e}\n")


# ==========================================================
# Thumbnail indir
# ==========================================================
def download_thumbnail(info, folder, safe_title):
    t = info.get("thumbnail")
    if not t:
        gui_log("[X] Thumbnail yok.\n")
        return

    out = os.path.join(folder, f"{safe_title}_thumbnail.png")
    try:
        urllib.request.urlretrieve(t, out)
        gui_log(f"[OK] Thumbnail → {os.path.basename(out)}\n")
    except Exception as e:
        gui_log(f"[X] Thumbnail hata: {e}\n")


# ==========================================================
# Tek video işleme
# ==========================================================
def process_single_video(url, times):
    info = get_youtube_info(url)
    if not info:
        gui_log(f"[X] Video info alınamadı → {url}\n")
        return

    title = info.get("title", "Video")
    safe_title = slugify_title(title)
    video_id = info.get("id", "NOID")

    width = info.get("width")
    height = info.get("height")
    dur = info.get("duration")

    gui_set_video_info(f"{title} | {width}x{height} | {format_duration(dur)}")
    gui_log(f"\n🎬 {title}\nID: {video_id}\n")

    folder = os.path.join(BASE_OUTPUT, safe_title)
    os.makedirs(folder, exist_ok=True)

    stream_url = info.get("url")
    if not stream_url:
        gui_log("[X] Stream URL yok (YouTube korumalı olabilir).\n")
        return

    # Paralel frame çıkarma
    extract_frames_ffmpeg_parallel(stream_url, times, folder, safe_title, video_id)

    # Thumbnail
    download_thumbnail(info, folder, safe_title)

    gui_log(f"✔ Tamam → {folder}\n")


# ==========================================================
# Playlist / Çoklu işleyici
# Playlist verilirse: önce tüm video URL'leri alınır,
# sonra satırdaki saniyeler (boşsa 5) hepsine uygulanır.
# ==========================================================
def worker_process(rows):
    for url, times in rows:
        gui_log(f"\n=== İşleniyor: {url} | Saniyeler: {times} ===\n")

        if "list=" in url:
            gui_log("▶ Playlist algılandı, tüm video URL'leri alınıyor...\n")
            ids = get_playlist_videos(url)

            if not ids:
                gui_log("[X] Playlist boş veya okunamadı.\n")
                continue

            total = len(ids)
            gui_log(f"Toplam video: {total}\n")

            for idx, vid in enumerate(ids, start=1):
                vurl = f"https://www.youtube.com/watch?v={vid}"
                gui_log(f"\n--- Playlist video {idx}/{total} ---\n")
                process_single_video(vurl, times)
        else:
            process_single_video(url, times)

    gui_log("\n✔ TÜM İŞLEM BİTTİ.\n")
    gui_set_button_running(False)
    messagebox.showinfo("Bitti", "İşlem tamamlandı.")


# ==========================================================
# Başlat tıklandı
# ==========================================================
def start_process():
    collected = []

    for url_entry, time_entry, _rf in url_rows:
        u = url_entry.get().strip()
        t = time_entry.get().strip()
        if not u:
            continue

        if u.startswith("http"):
            url = clean_youtube_url(u)
        else:
            url = f"https://www.youtube.com/playlist?list={u}"

        try:
            times = parse_time_list(t)  # boşsa [5]
        except Exception as e:
            messagebox.showerror("Hata", str(e))
            return

        collected.append((url, times))

    if not collected:
        messagebox.showwarning("Uyarı", "En az 1 satır doldur.")
        return

    txt_log.delete("0.0", "end")
    gui_set_button_running(True)

    th = Thread(target=worker_process, args=(collected,), daemon=True)
    th.start()


# ==========================================================
# Dinamik satır ekle/sil
# Varsayılan saniye kutusu: 5
# ==========================================================
def add_url_row(url_text="", time_text="5"):
    row = ctk.CTkFrame(url_scroll, corner_radius=8)
    row.pack(fill="x", pady=5, padx=5)

    url_entry = ctk.CTkEntry(row, height=34, font=("Segoe UI", 13))
    url_entry.insert(0, url_text)
    url_entry.pack(side="left", fill="x", expand=True, padx=5)

    time_entry = ctk.CTkEntry(row, width=180, height=34, font=("Segoe UI", 13))
    time_entry.insert(0, time_text)
    time_entry.pack(side="left", padx=5)

    def remove_row():
        row.destroy()
        for idx, (ue, te, rf) in enumerate(url_rows):
            if rf == row:
                url_rows.pop(idx)
                break

    del_btn = ctk.CTkButton(
        row, text="Sil", width=60,
        fg_color="#AA0000", hover_color="#770000",
        command=remove_row
    )
    del_btn.pack(side="left", padx=5)

    url_rows.append((url_entry, time_entry, row))


# ==========================================================
# GUI
# ==========================================================
app = ctk.CTk()
app.title("YouTube Screenshot Extractor PRO — FFmpeg + Paralel Frame")
app.geometry("1020x780")

header = ctk.CTkFrame(app, height=60, corner_radius=0)
header.pack(fill="x")
ctk.CTkLabel(
    header,
    text="📺 YouTube Screenshot Extractor PRO (FFmpeg + Paralel)",
    font=("Segoe UI Semibold", 23)
).pack(side="left", padx=15)

main = ctk.CTkFrame(app)
main.pack(fill="both", expand=True, padx=20, pady=20)

# URL LIST TABLE
box1 = ctk.CTkFrame(main)
box1.pack(fill="x", pady=10)

ctk.CTkLabel(box1, text="URL + Saniyeler:", font=("Segoe UI Semibold", 15)).pack(anchor="w", padx=10)

header_row = ctk.CTkFrame(box1)
header_row.pack(fill="x", padx=8, pady=5)

ctk.CTkLabel(header_row, text="YouTube URL / Playlist", width=500, anchor="w")\
    .pack(side="left", padx=10)
ctk.CTkLabel(header_row, text="Saniyeler (5, 1:20, 00:01:30)", width=250, anchor="w")\
    .pack(side="left", padx=10)

url_scroll = ctk.CTkScrollableFrame(box1, height=200)
url_scroll.pack(fill="x", padx=10, pady=5)

btn_add_row = ctk.CTkButton(
    box1, text="+ Satır Ekle", width=120,
    fg_color="#0066CC", hover_color="#004C99",
    command=lambda: add_url_row()
)
btn_add_row.pack(padx=10, pady=5)

# İlk satır
add_url_row()

# Bottom area
bottom_frame = ctk.CTkFrame(main)
bottom_frame.pack(fill="both", expand=True, pady=10)

left = ctk.CTkFrame(bottom_frame)
left.pack(side="left", fill="both", expand=True, padx=5)

right = ctk.CTkFrame(bottom_frame, width=250)
right.pack(side="right", fill="y", padx=5)

btn_start = ctk.CTkButton(
    left, text="📸 Başlat", height=45,
    fg_color="#0078D7", hover_color="#005A9E",
    command=start_process
)
btn_start.pack(fill="x", padx=10, pady=10)

lbl_video_info = ctk.CTkLabel(left, text="Video bilgisi: -", anchor="w")
lbl_video_info.pack(fill="x", padx=10, pady=5)

txt_log = ctk.CTkTextbox(left, font=("Consolas", 11))
txt_log.pack(fill="both", expand=True, padx=10, pady=10)

ctk.CTkLabel(right, text="Önizleme:", font=("Segoe UI Semibold", 14)).pack(pady=5)
preview_label = ctk.CTkLabel(
    right, text="Henüz yok", width=220, height=140, corner_radius=12
)
preview_label.pack(pady=10)

ctk.CTkLabel(
    right,
    text=f"Frame'ler paralel alınır.\nWorkers: {MAX_FRAME_WORKERS}",
    font=("Segoe UI", 11),
    justify="center"
).pack(pady=5)

app.mainloop()

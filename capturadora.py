#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lanzador portable para visualizar una capturadora (UGREEN / cualquier UVC)
mediante ffplay. Pensado para mostrar en tiempo real y con buena definicion
la pantalla compartida de un Mac (animaciones y video incluidos) en un PC
Windows bloqueado, sin instalacion ni permisos de administrador.

Requiere ffmpeg.exe y ffplay.exe:
  - Compila con PyInstaller en modo --onedir y deja los .exe junto al programa,
    o metelos con --add-binary.
  - Si no compilas, basta con dejar ffmpeg.exe y ffplay.exe en la MISMA carpeta.

CONSEJOS DE CALIDAD (Mac -> capturadora):
  - Pon el Mac a 1920x1080 EXACTOS en la salida hacia la capturadora (sin escalado Retina).
  - Usa formato MJPEG para lograr 1080p60 fluido por USB.
  - Boton "Ver modos" para saber que combinaciones admite tu tarjeta.
"""

import os
import re
import sys
import json
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# ---------- Localizacion de binarios y config ----------

def bundle_dir():
    """Carpeta de los .exe (bundle PyInstaller o carpeta del script)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def config_dir():
    """Carpeta escribible para guardar la ultima configuracion (junto al .exe)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def find_bin(name):
    candidates = [bundle_dir()]
    if getattr(sys, "frozen", False):
        candidates.append(os.path.dirname(sys.executable))
    for d in candidates:
        p = os.path.join(d, name + ".exe")
        if os.path.isfile(p):
            return p
    return name + ".exe"  # confiar en el PATH como ultimo recurso

FFMPEG = find_bin("ffmpeg")
FFPLAY = find_bin("ffplay")
CONFIG = os.path.join(config_dir(), "capturadora.json")
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# ---------- Deteccion de dispositivos y modos ----------

def list_devices():
    try:
        r = subprocess.run(
            [FFMPEG, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore",
            creationflags=CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        return None, None
    salida = (r.stderr or "") + (r.stdout or "")
    videos, audios = [], []
    for linea in salida.splitlines():
        m = re.search(r'"([^"]+)"\s*\((video|audio)\)', linea)
        if m:
            (videos if m.group(2) == "video" else audios).append(m.group(1))
    return list(dict.fromkeys(videos)), list(dict.fromkeys(audios))

def list_options(video):
    """Devuelve el texto con resoluciones/fps/formatos que admite la tarjeta."""
    try:
        r = subprocess.run(
            [FFMPEG, "-hide_banner", "-f", "dshow", "-list_options", "true", "-i", f"video={video}"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore",
            creationflags=CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        return "No se encontro ffmpeg.exe."
    return (r.stderr or "") + (r.stdout or "")

# ---------- Comando ffplay ----------

def construir_comando(video, audio, size, fps, formato, modo):
    cmd = [FFPLAY, "-hide_banner", "-f", "dshow"]
    # Formato de entrada: clave para 1080p60 fluido
    if formato == "MJPEG":
        cmd += ["-vcodec", "mjpeg"]
    elif formato == "YUYV (crudo)":
        cmd += ["-pixel_format", "yuyv422"]
    # Resolucion y FPS
    if size and size != "Automatica":
        cmd += ["-video_size", size]
    if fps and fps != "Auto":
        cmd += ["-framerate", str(fps)]
    # Perfil
    if modo == "Baja latencia":
        cmd += ["-rtbufsize", "64M", "-probesize", "32", "-analyzeduration", "0",
                "-fflags", "nobuffer", "-flags", "low_delay"]
    else:  # Calidad (por defecto): buffer holgado para no soltar frames
        cmd += ["-rtbufsize", "256M"]
    # Entrada (video, y audio si procede)
    entrada = f"video={video}"
    if audio and audio != "(sin audio)":
        entrada += f":audio={audio}"
    cmd += ["-i", entrada]
    # Salida: descartar frames retrasados mantiene sincronia y fluidez
    cmd += ["-framedrop", "-window_title", "Capturadora"]
    return cmd

def reproducir():
    video = combo_video.get()
    if not video:
        messagebox.showwarning("Falta dispositivo", "Selecciona una entrada de video.")
        return
    cmd = construir_comando(video, combo_audio.get(), combo_res.get(),
                            combo_fps.get(), combo_fmt.get(), combo_modo.get())
    try:
        subprocess.Popen(cmd, creationflags=CREATE_NO_WINDOW)
        guardar_config()
    except FileNotFoundError:
        messagebox.showerror(
            "ffplay no encontrado",
            "No encuentro ffplay.exe.\nDejalo junto a este programa o compilalo con --add-binary."
        )

# ---------- Diagnostico de modos ----------

def ver_modos():
    video = combo_video.get()
    if not video:
        messagebox.showwarning("Falta dispositivo", "Selecciona primero una entrada de video.")
        return
    texto = list_options(video)
    win = tk.Toplevel(app)
    win.title(f"Modos soportados - {video}")
    st = scrolledtext.ScrolledText(win, width=90, height=25, wrap="none")
    st.pack(fill="both", expand=True)
    st.insert("1.0", texto)
    st.configure(state="disabled")

# ---------- Persistencia ----------

def guardar_config():
    data = {
        "video": combo_video.get(), "audio": combo_audio.get(),
        "res": combo_res.get(), "fps": combo_fps.get(),
        "fmt": combo_fmt.get(), "modo": combo_modo.get(),
    }
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass  # si el USB es de solo lectura, simplemente no persiste

def cargar_config():
    try:
        with open(CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

def aplicar(combo, valor):
    if valor and valor in combo["values"]:
        combo.set(valor)

# ---------- Refresco / arranque ----------

def refrescar():
    videos, audios = list_devices()
    if videos is None:
        messagebox.showerror("ffmpeg no encontrado",
                             "No encuentro ffmpeg.exe.\nDejalo junto a este programa.")
        return
    combo_video["values"] = videos
    combo_audio["values"] = ["(sin audio)"] + audios
    cfg = cargar_config()
    if videos:
        combo_video.current(0)
    combo_audio.current(0)
    # Reaplica la ultima configuracion guardada
    aplicar(combo_video, cfg.get("video"))
    aplicar(combo_audio, cfg.get("audio"))
    aplicar(combo_res, cfg.get("res"))
    aplicar(combo_fps, cfg.get("fps"))
    aplicar(combo_fmt, cfg.get("fmt"))
    aplicar(combo_modo, cfg.get("modo"))

# ---------- Interfaz ----------

app = tk.Tk()
app.title("Capturadora")
app.resizable(False, False)

frm = ttk.Frame(app, padding=16)
frm.grid()

def fila(r, etiqueta, widget):
    ttk.Label(frm, text=etiqueta).grid(row=r, column=0, sticky="w", pady=4)
    widget.grid(row=r, column=1, columnspan=2, sticky="w", pady=4, padx=(8, 0))

combo_video = ttk.Combobox(frm, width=42, state="readonly"); fila(0, "Video", combo_video)
combo_audio = ttk.Combobox(frm, width=42, state="readonly"); fila(1, "Audio", combo_audio)

combo_res = ttk.Combobox(frm, width=18, state="readonly",
    values=["Automatica", "1920x1080", "1280x720", "720x480", "640x480"])
combo_res.current(1); fila(2, "Resolucion", combo_res)

combo_fps = ttk.Combobox(frm, width=18, state="readonly",
    values=["Auto", "60", "50", "30", "25"])
combo_fps.current(1); fila(3, "FPS", combo_fps)

combo_fmt = ttk.Combobox(frm, width=18, state="readonly",
    values=["MJPEG", "YUYV (crudo)", "Automatico"])
combo_fmt.current(0); fila(4, "Formato", combo_fmt)

combo_modo = ttk.Combobox(frm, width=18, state="readonly",
    values=["Calidad", "Baja latencia"])
combo_modo.current(0); fila(5, "Perfil", combo_modo)

btns = ttk.Frame(frm)
btns.grid(row=6, column=0, columnspan=3, pady=(14, 0))
ttk.Button(btns, text="Detectar", command=refrescar).grid(row=0, column=0, padx=4)
ttk.Button(btns, text="Ver modos", command=ver_modos).grid(row=0, column=1, padx=4)
ttk.Button(btns, text="Reproducir", command=reproducir).grid(row=0, column=2, padx=4)

ttk.Label(frm, text="F = pantalla completa - Q/Esc = salir - usa 1080p exactos en el Mac",
          foreground="#888").grid(row=7, column=0, columnspan=3, pady=(12, 0))

refrescar()
app.mainloop()

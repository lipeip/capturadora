#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lanzador portable para una capturadora (UGREEN / cualquier UVC) con ffplay.

  - Lee los modos REALES de la capturadora y solo ofrece combinaciones válidas
    en cascada: Formato -> Resolución -> FPS.
  - Excluye MJPEG (en esta capturadora el decodificador MJPEG de ffplay se
    cuelga; YUYV da el mismo 1080p y más nitidez). Para reactivarlo, quita
    "MJPEG" de FORMATOS_EXCLUIDOS más abajo.
  - Audio con buffer mínimo: al activarlo, evita el retardo de varios segundos.
  - Cierra cualquier ffplay anterior antes de reproducir (sin Administrador de tareas).
  - Si algo falla, muestra el error en una ventana.

Requiere ffmpeg.exe y ffplay.exe en la MISMA carpeta que este programa.
"""

import os
import re
import sys
import json
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# Formatos que NO se ofrecen aunque la tarjeta los anuncie (por no funcionar bien)
FORMATOS_EXCLUIDOS = {"MJPEG"}

# ---------- Binarios y archivos de apoyo ----------

def bundle_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def config_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def find_bin(name):
    cands = [bundle_dir()]
    if getattr(sys, "frozen", False):
        cands.append(os.path.dirname(sys.executable))
    for d in cands:
        p = os.path.join(d, name + ".exe")
        if os.path.isfile(p):
            return p
    return name + ".exe"

FFMPEG = find_bin("ffmpeg")
FFPLAY = find_bin("ffplay")
CONFIG = os.path.join(config_dir(), "capturadora.json")
LOG = os.path.join(config_dir(), "ffplay_last.log")
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

proc_actual = None
MODOS = {}

# ---------- Consultas a ffmpeg ----------

def list_devices():
    try:
        r = subprocess.run(
            [FFMPEG, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore",
            creationflags=CREATE_NO_WINDOW)
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
    try:
        r = subprocess.run(
            [FFMPEG, "-hide_banner", "-f", "dshow", "-list_options", "true", "-i", f"video={video}"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore",
            creationflags=CREATE_NO_WINDOW)
    except FileNotFoundError:
        return ""
    return (r.stderr or "") + (r.stdout or "")

# ---------- Análisis de modos válidos ----------

def parse_modos(texto):
    modos = {}
    for linea in texto.splitlines():
        mfmt = re.search(r'(?:vcodec|pixel_format)=(\S+)', linea)
        mres = re.search(r'max\s+s=(\d+)x(\d+)', linea)
        fps_vals = re.findall(r'fps=([\d.]+)', linea)
        if not (mfmt and mres and fps_vals):
            continue
        tok = mfmt.group(1).lower()
        if "mjpeg" in tok:
            label = "MJPEG"
        elif "yuyv" in tok:
            label = "YUYV"
        else:
            label = tok.upper()
        res = f"{int(mres.group(1))}x{int(mres.group(2))}"
        fmn = int(float(fps_vals[0]))
        fmx = int(round(float(fps_vals[-1])))
        d = modos.setdefault(label, {})
        if res in d:
            omn, omx = d[res]
            d[res] = (min(omn, fmn), max(omx, fmx))
        else:
            d[res] = (fmn, fmx)
    return modos

def area(res):
    w, h = res.split("x")
    return int(w) * int(h)

def fps_candidatas(mn, mx):
    base = [60, 50, 30, 25, 24, 15, 10]
    c = [f for f in base if mn <= f <= mx]
    if mx not in c:
        c.append(mx)
    return [str(f) for f in sorted(set(c), reverse=True)]

# ---------- Cascada de desplegables ----------

def cargar_modos(video):
    global MODOS
    estado.set("Detectando modos de la capturadora…")
    app.update_idletasks()
    MODOS = parse_modos(list_options(video))
    disponibles = [f for f in sorted(MODOS.keys()) if f not in FORMATOS_EXCLUIDOS]
    combo_fmt["values"] = ["Automático"] + disponibles
    combo_fmt.set("Automático")
    poblar_resoluciones()
    estado.set("Listo. Elige la fuente y pulsa Reproducir.")

def poblar_resoluciones(*_):
    fmt = combo_fmt.get()
    if fmt == "Automático" or fmt not in MODOS:
        combo_res["values"] = ["Automática"]
        combo_res.set("Automática")
        poblar_fps()
        return
    res_list = sorted(MODOS[fmt].keys(), key=area, reverse=True)
    combo_res["values"] = res_list
    combo_res.set(res_list[0])
    poblar_fps()

def poblar_fps(*_):
    fmt, res = combo_fmt.get(), combo_res.get()
    if fmt == "Automático" or fmt not in MODOS or res not in MODOS.get(fmt, {}):
        combo_fps["values"] = ["Auto"]
        combo_fps.set("Auto")
        return
    mn, mx = MODOS[fmt][res]
    cand = fps_candidatas(mn, mx)
    combo_fps["values"] = ["Auto"] + cand
    combo_fps.set("30" if "30" in cand else (cand[0] if cand else "Auto"))

# ---------- Limpieza de ffplay previos ----------

def matar_anteriores():
    global proc_actual
    if proc_actual is not None:
        try:
            if proc_actual.poll() is None:
                proc_actual.terminate()
        except Exception:
            pass
        proc_actual = None
    try:
        subprocess.run(["taskkill", "/F", "/IM", "ffplay.exe"],
                       capture_output=True, creationflags=CREATE_NO_WINDOW)
    except Exception:
        pass

def reiniciar():
    # Cierra cualquier ffplay colgado sin tocar las selecciones actuales
    matar_anteriores()
    estado.set("Reproducciones cerradas. Pulsa Reproducir cuando quieras.")

# ---------- Reproducir ----------

def construir_comando(video, audio, size, fps, formato, modo):
    usa_audio = bool(audio and audio != "(sin audio)")
    cmd = [FFPLAY, "-hide_banner", "-loglevel", "warning", "-f", "dshow"]
    if formato == "YUYV":
        cmd += ["-pixel_format", "yuyv422"]
    if size and size != "Automática":
        cmd += ["-video_size", size]
    if fps and fps != "Auto":
        cmd += ["-framerate", str(fps)]
    # Con audio, o en perfil de baja latencia, forzamos buffers mínimos.
    if usa_audio or modo == "Baja latencia":
        cmd += ["-probesize", "32", "-analyzeduration", "0",
                "-fflags", "nobuffer", "-flags", "low_delay"]
        cmd += ["-rtbufsize", "64M" if modo == "Baja latencia" else "128M"]
    else:
        cmd += ["-rtbufsize", "256M"]
    if usa_audio:
        # buffer de captura de audio en ms: mata el retardo de varios segundos
        cmd += ["-audio_buffer_size", "80"]
    entrada = f"video={video}"
    if usa_audio:
        entrada += f":audio={audio}"
    cmd += ["-i", entrada, "-framedrop", "-window_title", "Capturadora"]
    return cmd

def reproducir():
    global proc_actual
    video = combo_video.get()
    if not video:
        messagebox.showwarning("Falta dispositivo", "Selecciona una entrada de vídeo.")
        return
    estado.set("Preparando… (cerrando reproducciones anteriores)")
    app.update_idletasks()
    matar_anteriores()
    cmd = construir_comando(video, combo_audio.get(), combo_res.get(),
                            combo_fps.get(), combo_fmt.get(), combo_modo.get())
    try:
        log = open(LOG, "w", encoding="utf-8", errors="ignore")
        proc_actual = subprocess.Popen(cmd, stdout=log, stderr=log,
                                       creationflags=CREATE_NO_WINDOW)
    except FileNotFoundError:
        estado.set("No se encontró ffplay.exe.")
        messagebox.showerror("ffplay no encontrado",
                             "No encuentro ffplay.exe.\nDéjalo junto a este programa.")
        return
    estado.set("Reproduciendo…  (F = pantalla completa · Q = cerrar el vídeo)")
    guardar_config()
    app.after(2500, lambda p=proc_actual: comprobar_arranque(p))

def comprobar_arranque(proc):
    if proc is None:
        return
    if proc.poll() is None:
        estado.set("Reproduciendo correctamente.")
        return
    texto = ""
    try:
        with open(LOG, "r", encoding="utf-8", errors="ignore") as f:
            texto = f.read().strip()
    except OSError:
        pass
    estado.set("No se pudo reproducir. Mira el detalle.")
    mostrar_error(texto)

def mostrar_error(texto):
    bajo = (texto or "").lower()
    pista = ""
    if "already in use" in bajo or "could not run graph" in bajo or "i/o error" in bajo:
        pista = ("La capturadora está ocupada por otra aplicación (Cámara, Teams, "
                 "Zoom, OBS o el navegador). Ciérrala y pulsa Reproducir otra vez.")
    elif "could not find" in bajo or "no such" in bajo:
        pista = "No se encuentra el dispositivo. Pulsa Detectar y vuelve a elegirlo."
    elif "not supported" in bajo or "invalid" in bajo or "unable to" in bajo:
        pista = "Prueba con Formato = Automático."
    win = tk.Toplevel(app)
    win.title("No se pudo reproducir")
    if pista:
        ttk.Label(win, text=pista, wraplength=580, justify="left").pack(
            padx=12, pady=(12, 6), anchor="w")
    st = scrolledtext.ScrolledText(win, width=82, height=14, wrap="word")
    st.pack(fill="both", expand=True, padx=12, pady=(4, 12))
    st.insert("1.0", texto or "ffplay no devolvió ningún mensaje.")
    st.configure(state="disabled")

# ---------- Ver modos (texto crudo) ----------

def ver_modos():
    video = combo_video.get()
    if not video:
        messagebox.showwarning("Falta dispositivo", "Selecciona una entrada de vídeo.")
        return
    win = tk.Toplevel(app)
    win.title(f"Modos soportados · {video}")
    ttk.Label(win, text="(La línea final 'Error opening input file' es normal aquí.)",
              foreground="#666").pack(padx=8, pady=(8, 2), anchor="w")
    st = scrolledtext.ScrolledText(win, width=90, height=25, wrap="none")
    st.pack(fill="both", expand=True)
    st.insert("1.0", list_options(video))
    st.configure(state="disabled")

# ---------- Persistencia ----------

def guardar_config():
    data = {"video": combo_video.get(), "audio": combo_audio.get(),
            "res": combo_res.get(), "fps": combo_fps.get(),
            "fmt": combo_fmt.get(), "modo": combo_modo.get()}
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass

def cargar_config():
    try:
        with open(CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

def poner_si_valido(combo, valor):
    if valor and valor in combo["values"]:
        combo.set(valor)
        return True
    return False

# ---------- Detectar ----------

def refrescar():
    videos, audios = list_devices()
    if videos is None:
        messagebox.showerror("ffmpeg no encontrado",
                             "No encuentro ffmpeg.exe.\nDéjalo junto a este programa.")
        return
    combo_video["values"] = videos
    combo_audio["values"] = ["(sin audio)"] + audios
    combo_audio.current(0)
    cfg = cargar_config()
    if videos:
        combo_video.current(0)
        poner_si_valido(combo_video, cfg.get("video"))
        cargar_modos(combo_video.get())
        poner_si_valido(combo_audio, cfg.get("audio"))
        if poner_si_valido(combo_fmt, cfg.get("fmt")):
            poblar_resoluciones()
            if poner_si_valido(combo_res, cfg.get("res")):
                poblar_fps()
                poner_si_valido(combo_fps, cfg.get("fps"))
        poner_si_valido(combo_modo, cfg.get("modo"))

def cambiar_dispositivo(*_):
    if combo_video.get():
        cargar_modos(combo_video.get())

# ---------- Cierre limpio ----------

def al_cerrar():
    matar_anteriores()
    app.destroy()

# ---------- Interfaz ----------

app = tk.Tk()
app.title("Capturadora")
app.resizable(False, False)
app.protocol("WM_DELETE_WINDOW", al_cerrar)

estado = tk.StringVar(value="Iniciando…")

frm = ttk.Frame(app, padding=16)
frm.grid()

def fila(r, etiqueta, widget):
    ttk.Label(frm, text=etiqueta).grid(row=r, column=0, sticky="w", pady=4)
    widget.grid(row=r, column=1, columnspan=2, sticky="w", pady=4, padx=(8, 0))

combo_video = ttk.Combobox(frm, width=42, state="readonly"); fila(0, "Vídeo", combo_video)
combo_audio = ttk.Combobox(frm, width=42, state="readonly"); fila(1, "Audio", combo_audio)
combo_fmt = ttk.Combobox(frm, width=18, state="readonly"); fila(2, "Formato", combo_fmt)
combo_res = ttk.Combobox(frm, width=18, state="readonly"); fila(3, "Resolución", combo_res)
combo_fps = ttk.Combobox(frm, width=18, state="readonly"); fila(4, "FPS", combo_fps)
combo_modo = ttk.Combobox(frm, width=18, state="readonly",
    values=["Calidad", "Baja latencia"]); combo_modo.current(0); fila(5, "Perfil", combo_modo)

combo_video.bind("<<ComboboxSelected>>", cambiar_dispositivo)
combo_fmt.bind("<<ComboboxSelected>>", poblar_resoluciones)
combo_res.bind("<<ComboboxSelected>>", poblar_fps)

btns = ttk.Frame(frm)
btns.grid(row=6, column=0, columnspan=3, pady=(14, 0))
ttk.Button(btns, text="Detectar", command=refrescar).grid(row=0, column=0, padx=4)
ttk.Button(btns, text="Ver modos", command=ver_modos).grid(row=0, column=1, padx=4)
ttk.Button(btns, text="↻ Reiniciar", command=reiniciar).grid(row=0, column=2, padx=4)
ttk.Button(btns, text="▶ Reproducir", command=reproducir).grid(row=0, column=3, padx=4)

ttk.Separator(frm, orient="horizontal").grid(
    row=7, column=0, columnspan=3, sticky="ew", pady=(14, 6))
ttk.Label(frm, textvariable=estado, wraplength=360, foreground="#333").grid(
    row=8, column=0, columnspan=3, sticky="w")

refrescar()
app.mainloop()

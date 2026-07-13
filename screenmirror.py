import os
import sys
import subprocess
import time
import shutil
import json
import zipfile
import threading
import urllib.request
import webbrowser
import socket
import re
from datetime import datetime
from urllib.error import URLError
from colorama import init, Fore, Style
import ctypes

# Initialize colorama
init(autoreset=True)

import platform as _platform

CURRENT_VERSION = "v6.1.0"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

def _get_preset_dir():
    if os.name == "nt":
        return os.path.expandvars(r"%APPDATA%")
    elif sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        return os.path.join(os.path.expanduser("~"), ".config")

def _get_os_edition():
    if os.name == "nt":      return "Windows Edition"
    elif sys.platform == "darwin": return "macOS Edition"
    else:                    return "Linux Edition"

PRESET_FILE  = os.path.join(_get_preset_dir(), "screenmirror_presets.json")
SESSION_LOG  = os.path.join(PROJECT_DIR, "screenmirror_sessions.log")
OS_EDITION   = _get_os_edition()

# Globals
ADB_EXE    = "adb"
SCRCPY_EXE = "scrcpy"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def set_console_icon():
    icon_path = resource_path("icon.ico")
    if os.name == 'nt' and os.path.exists(icon_path):
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                hicon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x00000010 | 0x00000040)
                if hicon:
                    ctypes.windll.user32.SendMessageW(hwnd, 0x80, 0, hicon) # ICON_SMALL
                    ctypes.windll.user32.SendMessageW(hwnd, 0x80, 1, hicon) # ICON_BIG
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
#   UTILITY
# ═══════════════════════════════════════════════════════════

def get_input(prompt_text, valid_choices=None, default=None):
    while True:
        try:
            val = input(prompt_text).strip()
            if not val and default is not None:
                return default
            if valid_choices and val.lower() not in [v.lower() for v in valid_choices]:
                print(f"{Fore.RED}  [X] Pilihan tidak valid. Coba lagi.")
                continue
            return val.lower() if valid_choices else val
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.CYAN}  Sampai jumpa! 👋")
            sys.exit(0)


def print_banner(lang="en"):
    os.system("cls" if os.name == "nt" else "clear")
    print(f"\n{Fore.BLUE}  ╔══════════════════════════════════════════════════════════╗")
    print(f"{Fore.CYAN}  ║    Android to Laptop Screen Mirror  ·  by Xnuvers007     ║")
    if lang == "id":
        text = f"{OS_EDITION}  │  Indonesia  │  {CURRENT_VERSION}"
    else:
        text = f"{OS_EDITION}  │  English    │  {CURRENT_VERSION}"
    padding = " " * max(0, 58 - 7 - len(text))
    print(f"{Fore.CYAN}  ║       {text}{padding}║")
    print(f"{Fore.BLUE}  ╚══════════════════════════════════════════════════════════╝\n")


def log_ok(msg):   print(f"{Fore.GREEN}  [OK] {msg}")
def log_warn(msg): print(f"{Fore.YELLOW}  [!]  {msg}")
def log_err(msg):  print(f"{Fore.RED}  [X]  {msg}")
def log_info(msg): print(f"{Fore.WHITE}  [i]  {msg}")
def log_note(msg): print(f"{Fore.MAGENTA}  [~]  {msg}")


def _spinner_loop(msg, stop_event):
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while not stop_event.is_set():
        print(f"\r{Fore.CYAN}  {frames[i % len(frames)]}  {msg}   ", end="", flush=True)
        i += 1
        time.sleep(0.08)
    print(f"\r{Fore.GREEN}  ✔  {msg}{'':40}", flush=True)


def with_spinner(msg, func, *args, **kwargs):
    stop = threading.Event()
    t = threading.Thread(target=_spinner_loop, args=(msg, stop), daemon=True)
    t.start()
    try:
        result = func(*args, **kwargs)
    finally:
        stop.set()
        t.join()
    return result


# ═══════════════════════════════════════════════════════════
#   UPDATE CHECKER
# ═══════════════════════════════════════════════════════════

def _github_latest(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "ScreenMirror-Updater"})
    with urllib.request.urlopen(req, timeout=6) as resp:
        data = json.loads(resp.read().decode())
        return data.get("tag_name", ""), data.get("assets", [])


def _get_scrcpy_version():
    try:
        res = subprocess.run([SCRCPY_EXE, "--version"], capture_output=True, text=True, timeout=5)
        for line in (res.stdout + res.stderr).splitlines():
            if "scrcpy" in line.lower():
                for p in line.split():
                    if p.startswith("v") or (p and p[0].isdigit()):
                        return p.strip("v,;")
    except Exception:
        return None


def check_updates(lang="en"):
    print()
    try:
        def _fetch():
            sm_tag, _ = _github_latest("Xnuvers007/screenmirror-python")
            sc_tag, sc_assets = _github_latest("Genymobile/scrcpy")
            return sm_tag, sc_tag, sc_assets

        label = "Mengecek pembaruan..." if lang == "id" else "Checking for updates..."
        sm_tag, sc_tag, sc_assets = with_spinner(label, _fetch)

        # ── ScreenMirror update ──
        sm_cur = CURRENT_VERSION.lstrip("v")
        sm_new = sm_tag.lstrip("v")
        if sm_new and sm_new != sm_cur:
            print(f"{Fore.YELLOW}  ╔══════════════════════════════════════════════════════════╗")
            if lang == "id":
                print(f"{Fore.YELLOW}  ║  UPDATE SCREENMIRROR: {sm_tag:<10} (sekarang: {CURRENT_VERSION}){' ':>5}║")
                print(f"{Fore.YELLOW}  ║  https://github.com/Xnuvers007/screenmirror-python{' ':>8}║")
            else:
                print(f"{Fore.YELLOW}  ║  SCREENMIRROR UPDATE: {sm_tag:<10} (current: {CURRENT_VERSION}){' ':>6}║")
                print(f"{Fore.YELLOW}  ║  https://github.com/Xnuvers007/screenmirror-python{' ':>8}║")
            print(f"{Fore.YELLOW}  ╚══════════════════════════════════════════════════════════╝")
            ans = get_input("  Download & update sekarang? [y/n]: " if lang == "id" else "  Download & update now? [y/n]: ", ["y","n"], "n")
            if ans == "y":
                download_screenmirror_update(sm_tag, lang)
        else:
            log_ok("ScreenMirror sudah versi terbaru." if lang == "id" else "ScreenMirror is up to date.")

        # ── scrcpy update ──
        sc_installed = _get_scrcpy_version()
        sc_new = sc_tag.lstrip("v")
        if sc_new and sc_installed and sc_installed != sc_new:
            print()
            print(f"{Fore.YELLOW}  ╔══════════════════════════════════════════════════════════╗")
            if lang == "id":
                print(f"{Fore.YELLOW}  ║  UPDATE SCRCPY tersedia: v{sc_new:<10} (terpasang: v{sc_installed}){' ':>3}║")
            else:
                print(f"{Fore.YELLOW}  ║  SCRCPY UPDATE available: v{sc_new:<10} (installed: v{sc_installed}){' ':>2}║")
            print(f"{Fore.YELLOW}  ╚══════════════════════════════════════════════════════════╝")
            ans = get_input("  Download & install scrcpy terbaru? [y/n]: " if lang == "id" else "  Download & install latest scrcpy? [y/n]: ", ["y","n"], "n")
            if ans == "y":
                download_scrcpy(sc_tag, sc_assets, lang)
        elif sc_installed:
            log_ok(f"scrcpy v{sc_installed} sudah terbaru." if lang == "id" else f"scrcpy v{sc_installed} is up to date.")

    except Exception:
        log_warn("Gagal mengecek pembaruan. Cek koneksi internet." if lang == "id" else "Failed to check updates. Check internet connection.")


def download_screenmirror_update(tag, lang="en"):
    url = f"https://raw.githubusercontent.com/Xnuvers007/screenmirror-python/{tag}/screenmirror.py"
    target_path = os.path.abspath(__file__)
    tmp_path = target_path + ".tmp"

    log_info(f"URL: {url}")
    try:
        with_spinner("Mengunduh pembaruan ScreenMirror..." if lang == "id" else "Downloading ScreenMirror update...",
                     urllib.request.urlretrieve, url, tmp_path)

        with open(tmp_path, "r", encoding="utf-8") as f:
            if "def main():" not in f.read():
                raise ValueError("Invalid script downloaded.")

        shutil.move(tmp_path, target_path)
        log_ok("Pembaruan berhasil! Silakan jalankan ulang script ini." if lang == "id" else "Update successful! Please restart the script.")
        sys.exit(0)
    except Exception as e:
        log_err(f"Gagal mengunduh pembaruan: {e}" if lang == "id" else f"Failed to download update: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def download_scrcpy(tag, assets, lang="en"):
    machine = _platform.machine().lower()
    system  = _platform.system().lower()  # 'windows', 'linux', 'darwin'

    # Build keywords to match the right asset
    if system == "windows":
        is_64bits = "64" in machine or "amd64" in machine or "PROCESSOR_ARCHITEW6432" in os.environ
        os_key  = "win64" if is_64bits else "win32"
        ext_key = ".zip"
        adb_name = "adb.exe"
        scrcpy_name = "scrcpy.exe"
        dest_dir = os.path.join(os.path.expandvars("%LOCALAPPDATA%"), "scrcpy")
    elif system == "darwin":
        os_key  = "macos"
        ext_key = ".tar.gz"
        adb_name = "adb"
        scrcpy_name = "scrcpy"
        dest_dir = os.path.join(os.path.expanduser("~"), ".local", "bin", "scrcpy")
    else:  # linux
        arch = "x86_64" if ("64" in machine or "amd64" in machine) else "arm64"
        os_key  = f"linux-{arch}"
        ext_key = ".tar.gz"
        adb_name = "adb"
        scrcpy_name = "scrcpy"
        dest_dir = os.path.join(os.path.expanduser("~"), ".local", "bin", "scrcpy")

    target = None
    for a in assets:
        n = a["name"].lower()
        if os_key in n and n.endswith(ext_key):
            target = a
            break
    if not target:
        for a in assets:
            n = a["name"].lower()
            if system[:3] in n and n.endswith(ext_key):
                target = a
                break
    if not target:
        log_err("File unduhan tidak ditemukan." if lang == "id" else "No suitable download asset found.")
        return

    url      = target["browser_download_url"]
    filename = target["name"]
    zip_path = os.path.join(PROJECT_DIR, filename)

    log_info(f"URL: {url}")
    try:
        with_spinner(f"Mengunduh {filename}" if lang == "id" else f"Downloading {filename}",
                     urllib.request.urlretrieve, url, zip_path)

        log_info(f"Mengekstrak ke {dest_dir}..." if lang == "id" else f"Extracting to {dest_dir}...")
        os.makedirs(dest_dir, exist_ok=True)

        if filename.endswith(".zip"):
            with zipfile.ZipFile(zip_path, "r") as z:
                for member in z.namelist():
                    parts = member.split("/", 1)
                    target_name = parts[1] if len(parts) > 1 else member
                    if not target_name:
                        continue
                    target_path = os.path.join(dest_dir, target_name)
                    if member.endswith("/"):
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with z.open(member) as src, open(target_path, "wb") as dst:
                            dst.write(src.read())
        elif filename.endswith(".tar.gz") or filename.endswith(".tgz"):
            import tarfile
            with tarfile.open(zip_path, "r:gz") as t:
                for member in t.getmembers():
                    parts = member.name.split("/", 1)
                    target_name = parts[1] if len(parts) > 1 else member.name
                    if not target_name:
                        continue
                    member.name = target_name
                    t.extract(member, dest_dir)
        os.remove(zip_path)

        global SCRCPY_EXE, ADB_EXE
        new_sc = os.path.join(dest_dir, scrcpy_name)
        new_ad = os.path.join(dest_dir, adb_name)
        if os.path.exists(new_sc):
            SCRCPY_EXE = new_sc
            if system != "windows":
                os.chmod(new_sc, 0o755)
            log_ok(f"scrcpy berhasil diinstall di: {dest_dir}" if lang == "id" else f"scrcpy installed at: {dest_dir}")
        if os.path.exists(new_ad):
            ADB_EXE = new_ad
            if system != "windows":
                os.chmod(new_ad, 0o755)
        log_note("Tambahkan folder ke PATH agar bisa dipakai global." if lang == "id" else "Add the folder to PATH for global access.")
    except Exception as e:
        log_err(f"Gagal: {e}" if lang == "id" else f"Failed: {e}")


# ═══════════════════════════════════════════════════════════
#   EXECUTABLES
# ═══════════════════════════════════════════════════════════

def find_executables():
    global ADB_EXE, SCRCPY_EXE
    ap = shutil.which("adb")
    sp = shutil.which("scrcpy")
    if ap: ADB_EXE    = ap
    if sp: SCRCPY_EXE = sp

    if sp and not ap:
        adb_name = "adb.exe" if os.name == "nt" else "adb"
        local_adb = os.path.join(os.path.dirname(sp), adb_name)
        if os.path.exists(local_adb):
            ADB_EXE = local_adb

    if sp: return True

    # ── Platform-specific fallback search ──
    if os.name == "nt":
        search_bases = [
            os.environ.get("SystemDrive", "C:\\"),
            os.path.expanduser("~"),
            os.path.expandvars("%LOCALAPPDATA%"),
        ]
        exe_name = "scrcpy.exe"
        adb_name  = "adb.exe"
    elif sys.platform == "darwin":
        search_bases = [
            "/usr/local/bin",
            "/opt/homebrew/bin",
            os.path.expanduser("~/Applications"),
            "/Applications",
        ]
        exe_name = "scrcpy"
        adb_name  = "adb"
    else:  # Linux
        search_bases = [
            "/usr/bin",
            "/usr/local/bin",
            "/snap/bin",
            os.path.expanduser("~/.local/bin"),
        ]
        exe_name = "scrcpy"
        adb_name  = "adb"

    for base in search_bases:
        try:
            if os.path.isfile(base) and "scrcpy" in base:
                SCRCPY_EXE = base
                a = os.path.join(os.path.dirname(base), adb_name)
                if os.path.exists(a): ADB_EXE = a
                return True
            for d in os.listdir(base):
                if "scrcpy" in d.lower():
                    p = os.path.join(base, d, exe_name)
                    if os.path.exists(p):
                        SCRCPY_EXE = p
                        a = os.path.join(os.path.dirname(p), adb_name)
                        if os.path.exists(a): ADB_EXE = a
                        return True
                # also check if the dir itself is the binary
                p = os.path.join(base, d)
                if d == exe_name and os.path.isfile(p):
                    SCRCPY_EXE = p
                    return True
        except Exception:
            pass
    return False


# ═══════════════════════════════════════════════════════════
#   DEVICE
# ═══════════════════════════════════════════════════════════

def _adb_getprop(device_id, prop):
    try:
        r = subprocess.run([ADB_EXE, "-s", device_id, "shell", "getprop", prop],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except Exception:
        return ""


def _get_resolution(device_id):
    try:
        r = subprocess.run([ADB_EXE, "-s", device_id, "shell", "wm", "size"], capture_output=True, text=True, timeout=5)
        if "Physical size:" in r.stdout:
            return r.stdout.split(":")[1].strip()
    except Exception:
        pass
    return "?"

def _get_ram(device_id):
    try:
        r = subprocess.run([ADB_EXE, "-s", device_id, "shell", "cat", "/proc/meminfo"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if "MemTotal:" in line:
                kb = int(line.split()[1])
                gb = round(kb / (1024*1024), 2)
                return f"{gb} GB"
    except Exception:
        pass
    return "?"

def _get_ip(device_id):
    try:
        r = subprocess.run([ADB_EXE, "-s", device_id, "shell", "ip", "route"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if "src" in line and "wlan" in line:
                return line.split("src")[1].split()[0].strip()
    except Exception:
        pass
    return "-"

def _get_device_info(device_id):
    sdk_str  = _adb_getprop(device_id, "ro.build.version.sdk")
    sdk_ver  = int(sdk_str) if sdk_str.isdigit() else 30
    return {
        "id":          device_id,
        "sdk":         sdk_ver,
        "android":     _adb_getprop(device_id, "ro.build.version.release"),
        "brand":       _adb_getprop(device_id, "ro.product.brand"),
        "model":       _adb_getprop(device_id, "ro.product.model"),
        "device":      _adb_getprop(device_id, "ro.product.device"),
        "manufacturer":_adb_getprop(device_id, "ro.product.manufacturer"),
        "platform":    _adb_getprop(device_id, "ro.board.platform") or _adb_getprop(device_id, "ro.hardware"),
        "cpu_abi":     _adb_getprop(device_id, "ro.product.cpu.abi"),
        "battery":     _get_battery(device_id),
        "resolution":  _get_resolution(device_id),
        "ram":         _get_ram(device_id),
        "ip":          _get_ip(device_id),
    }


def _get_battery(device_id):
    level = "?"
    temp = "?"
    try:
        r = subprocess.run([ADB_EXE, "-s", device_id, "shell", "dumpsys", "battery"],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if "level:" in line:
                level = line.split(":")[-1].strip() + "%"
            elif "temperature:" in line:
                t = int(line.split(":")[-1].strip())
                temp = f"{t/10.0}°C"
    except Exception:
        pass
    if temp != "?": return f"{level} ({temp})"
    return level


def _print_device_info(d, lang="en"):
    print(f"\n{Fore.CYAN}  ╔══════════════════════════════════════════════════════════╗")
    print(f"{Fore.CYAN}  ║  {'INFORMASI PERANGKAT' if lang=='id' else 'DEVICE INFORMATION':<56}║")
    print(f"{Fore.CYAN}  ╠══════════════════════════════════════════════════════════╣")
    def _pr(lbl, val):
        val_str = str(val)[:36]
        vis_len = 21 + len(val_str)
        pad = " " * max(0, 58 - vis_len)
        print(f"{Fore.CYAN}  ║  {Fore.WHITE}{lbl:<14}{Fore.CYAN}│ {Fore.GREEN}{val_str}{pad}{Fore.CYAN}║")

    _pr("Model/Brand", f"{d.get('brand','?').capitalize()} {d.get('model','')}")
    _pr("Codename", d.get('device','?'))
    _pr("OS Version", f"Android {d.get('android','?')} (SDK {d.get('sdk','?')})")
    _pr("Chipset", d.get('platform','?').upper())
    _pr("CPU Arch", d.get('cpu_abi','?'))
    _pr("Screen Res", d.get('resolution','?'))
    _pr("RAM Total", d.get('ram','?'))
    _pr("Battery", d.get('battery','?'))
    _pr("IP Address", d.get('ip','?'))
    _pr("Device ID", d.get('id','?'))
    print(f"{Fore.CYAN}  ╚══════════════════════════════════════════════════════════╝\n")


def check_device(lang="en", allow_multi=False):
    with_spinner("Memulai ADB server..." if lang == "id" else "Starting ADB server...",
                 lambda: subprocess.run([ADB_EXE, "start-server"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

    result  = subprocess.run([ADB_EXE, "devices"], capture_output=True, text=True)
    lines   = result.stdout.strip().split("\n")
    devices = [l.split()[0] for l in lines if len(l.split()) >= 2 and l.split()[1] == "device"]

    if not devices:
        log_err("Tidak ada perangkat Android yang terdeteksi!" if lang == "id" else "No Android device detected!")
        if lang == "id":
            print("    • Kabel USB belum terhubung / USB Debugging belum aktif")
            print("    • Tekan 'Izinkan' di HP saat muncul prompt USB Debugging")
        else:
            print("    • USB cable not connected / USB Debugging is disabled")
            print("    • Tap 'Allow' on the phone when USB Debugging prompt appears")
        input("  Tekan Enter untuk kembali..." if lang == "id" else "  Press Enter to go back...")
        return None

    if len(devices) > 1:
        print(f"\n{Fore.CYAN}  {'Ditemukan' if lang=='id' else 'Found'} {len(devices)} {'perangkat:' if lang=='id' else 'devices:'}")
        device_infos = []
        for i, dev_id in enumerate(devices, 1):
            info = with_spinner(f"Membaca info perangkat {i}..." if lang == "id" else f"Reading device {i} info...",
                                _get_device_info, dev_id)
            device_infos.append(info)
            print(f"    {Fore.YELLOW}[{i}] {Fore.WHITE}{info['brand']} {info['model']}  "
                  f"{Fore.CYAN}({dev_id})  {Fore.GREEN}Android {info['android']}")
        if allow_multi:
            print(f"    {Fore.YELLOW}[0] {Fore.WHITE}{'Pilih Semua Perangkat (Multi-Mirror)' if lang == 'id' else 'Select All Devices (Multi-Mirror)'}")
            ch = get_input(f"  Pilih perangkat [0-{len(devices)}]: " if lang == "id" else f"  Select device [0-{len(devices)}]: ",
                           [str(i) for i in range(0, len(devices)+1)], "1")
            if ch == "0":
                return device_infos
        else:
            ch = get_input(f"  Pilih perangkat [1-{len(devices)}]: " if lang == "id" else f"  Select device [1-{len(devices)}]: ",
                           [str(i) for i in range(1, len(devices)+1)], "1")
        device_info = device_infos[int(ch) - 1]
    else:
        device_info = with_spinner("Membaca info perangkat..." if lang == "id" else "Reading device info...",
                                   _get_device_info, devices[0])

    if device_info["sdk"] < 21:
        log_err("Android terlalu lama (API < 21). Tidak didukung." if lang == "id" else "Android too old (API < 21). Not supported.")
        return None

    _print_device_info(device_info, lang)
    return device_info


# ═══════════════════════════════════════════════════════════
#   SMART RECOMMENDATION
# ═══════════════════════════════════════════════════════════

def _smart_recommend(device_info):
    sdk      = device_info.get("sdk", 30)
    platform = device_info.get("platform", "").lower()
    gaming   = any(c in platform for c in ["sm8","sm7","sd8","sd7","mt6895","mt6983","mt6897","kirin9"])
    codec    = "av1" if sdk >= 34 else ("h265" if sdk >= 29 else "h264")
    fps      = "120" if gaming else "60"
    bitrate  = "16M" if gaming else "8M"
    reason   = f"SDK {sdk} · {platform} · {'Gaming Chipset' if gaming else 'Standard Chipset'}"
    return {"codec": codec, "fps": fps, "bitrate": bitrate, "reason": reason}


# ═══════════════════════════════════════════════════════════
#   PRESET SYSTEM
# ═══════════════════════════════════════════════════════════

_BUILTIN_PRESETS = {
    "🎮 Gaming": {
        "fps":"120","bitrate":"16M","resolution":"0","codec":"h265",
        "mirror_cam":"n","camera_facing":"","enable_otg":"n","virtual_display":"n",
        "window_opt":"1","audio_mode":"1","advanced_kb":"y","stay_awake":"y",
        "turn_screen_off":"n","no_control":"n","record_filename":"","crop":"","shortcut_mod":"n",
    },
    "📊 Presentasi": {
        "fps":"30","bitrate":"4M","resolution":"1080","codec":"h264",
        "mirror_cam":"n","camera_facing":"","enable_otg":"n","virtual_display":"n",
        "window_opt":"2","audio_mode":"3","advanced_kb":"n","stay_awake":"y",
        "turn_screen_off":"n","no_control":"y","record_filename":"","crop":"","shortcut_mod":"n",
    },
    "🔋 Hemat Baterai": {
        "fps":"30","bitrate":"4M","resolution":"720","codec":"h264",
        "mirror_cam":"n","camera_facing":"","enable_otg":"n","virtual_display":"n",
        "window_opt":"1","audio_mode":"1","advanced_kb":"n","stay_awake":"y",
        "turn_screen_off":"y","no_control":"n","record_filename":"","crop":"","shortcut_mod":"n",
    },
    "🎬 Rekam Layar": {
        "fps":"60","bitrate":"16M","resolution":"1080","codec":"h264",
        "mirror_cam":"n","camera_facing":"","enable_otg":"n","virtual_display":"n",
        "window_opt":"1","audio_mode":"1","advanced_kb":"n","stay_awake":"y",
        "turn_screen_off":"n","no_control":"n",
        "record_filename":"__auto__","crop":"","shortcut_mod":"n",
    },
}


def _load_presets():
    presets = dict(_BUILTIN_PRESETS)
    try:
        if os.path.exists(PRESET_FILE):
            with open(PRESET_FILE, "r", encoding="utf-8") as f:
                presets.update(json.load(f))
    except Exception:
        pass
    return presets


def _save_preset(name, config):
    try:
        custom = {}
        if os.path.exists(PRESET_FILE):
            with open(PRESET_FILE, "r", encoding="utf-8") as f:
                custom = json.load(f)
        custom[name] = config
        with open(PRESET_FILE, "w", encoding="utf-8") as f:
            json.dump(custom, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

def _save_presets(all_presets):
    try:
        custom = {k: v for k, v in all_presets.items() if k not in _BUILTIN_PRESETS}
        with open(PRESET_FILE, "w", encoding="utf-8") as f:
            json.dump(custom, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def _delete_preset(name):
    try:
        if os.path.exists(PRESET_FILE):
            with open(PRESET_FILE, "r", encoding="utf-8") as f:
                custom = json.load(f)
            if name in custom:
                del custom[name]
                with open(PRESET_FILE, "w", encoding="utf-8") as f:
                    json.dump(custom, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════
#   CONFIGURATION
# ═══════════════════════════════════════════════════════════

def configure_scrcpy(lang, device_info=None):
    rec = _smart_recommend(device_info) if device_info else {}
    sdk = device_info.get("sdk", 30) if device_info else 30

    print(f"\n{Fore.MAGENTA}  ╔══════════════════════════════════════════════════════════╗")
    print(f"{Fore.MAGENTA}  ║  {'PENGATURAN SCRCPY' if lang=='id' else 'SCRCPY SETTINGS':<56}║")
    print(f"{Fore.MAGENTA}  ╚══════════════════════════════════════════════════════════╝")

    if rec:
        print(f"\n{Fore.GREEN}  [★] {'Rekomendasi otomatis berdasarkan perangkat:' if lang=='id' else 'Smart recommendation based on your device:'}")
        print(f"      Codec: {rec['codec'].upper()} │ FPS: {rec['fps']} │ Bitrate: {rec['bitrate']}")
        print(f"      {'Alasan' if lang=='id' else 'Reason'}: {rec['reason']}\n")

    # ── FPS ──────────────────────────────────────────────
    if lang == "id":
        print(f"{Fore.CYAN}  Pilih FPS:")
        print("    [1] 30 FPS  — Hemat baterai, cocok untuk presentasi & screen share")
        print("    [2] 60 FPS  — Mulus, cocok untuk pemakaian sehari-hari (REKOMENDASI)")
        print("    [3] 120 FPS — Sangat mulus, butuh HP gaming kelas atas")
        print("    [4] Custom  — Masukkan nilai FPS sendiri")
    else:
        print(f"{Fore.CYAN}  Choose FPS:")
        print("    [1] 30 FPS  — Battery saver, great for presentations & screen share")
        print("    [2] 60 FPS  — Smooth, great for everyday use (RECOMMENDED)")
        print("    [3] 120 FPS — Very smooth, requires a gaming-class phone")
        print("    [4] Custom  — Enter your own FPS value")
    if rec: print(f"    {Fore.GREEN}[★] Rekomendasi/Recommended: {rec['fps']} FPS")
    fps_c = get_input("  Choice [1-4] (default: 2): ", ["1","2","3","4"], "2")
    fps = {"1":"30","2":"60","3":"120"}.get(fps_c)
    if fps is None: fps = get_input("  Enter FPS: ", default="60")
    log_ok(f"FPS: {fps}")

    # ── Bitrate ───────────────────────────────────────────
    print()
    if lang == "id":
        print(f"{Fore.CYAN}  Pilih Bitrate (kualitas video):")
        print("    [1] 4M   — Standar, koneksi lambat atau WiFi jauh")
        print("    [2] 8M   — Bagus, untuk pemakaian umum (REKOMENDASI)")
        print("    [3] 16M  — Sangat bagus, butuh WiFi 5GHz atau kencang")
        print("    [4] 40M  — Maksimal, khusus kabel USB langsung")
        print("    [5] 100M — Ekstrim (Sangat tinggi)")
        print("    [6] Custom")
    else:
        print(f"{Fore.CYAN}  Choose Bitrate (video quality):")
        print("    [1] 4M   — Standard, for slow/distant WiFi connections")
        print("    [2] 8M   — Good, recommended for general use")
        print("    [3] 16M  — Very good, requires fast 5GHz WiFi")
        print("    [4] 40M  — Maximum quality, USB cable only")
        print("    [5] 100M — Extreme quality")
        print("    [6] Custom")
    if rec: print(f"    {Fore.GREEN}[★] Rekomendasi/Recommended: {rec['bitrate']}")
    br_c = get_input("  Choice [1-6] (default: 2): ", ["1","2","3","4","5","6"], "2")
    bitrate = {"1":"4M","2":"8M","3":"16M","4":"40M","5":"100M"}.get(br_c)
    if bitrate is None: bitrate = get_input("  Enter bitrate (e.g. 10M, 100M): ", default="8M")
    log_ok(f"Bitrate: {bitrate}")

    # ── Resolution ────────────────────────────────────────
    print()
    if lang == "id":
        print(f"{Fore.CYAN}  Pilih Resolusi:")
        print("    [1] 720p   — Ringan, cocok untuk koneksi lambat atau HP lama")
        print("    [2] 1080p  — Direkomendasikan untuk pemakaian umum")
        print("    [3] 1440p  — Kualitas tinggi, butuh koneksi yang baik")
        print("    [4] 4K     — Kualitas tertinggi, butuh HP & koneksi sangat kencang")
        print("    [5] 32K    — 32KFHD (Resolusi mentok / Ekstrim)")
        print("    [6] Full   — Resolusi penuh asli HP, tanpa diperkecil")
        print("    [7] Custom — Masukkan resolusi sendiri")
    else:
        print(f"{Fore.CYAN}  Choose Resolution:")
        print("    [1] 720p   — Lightweight, great for slow connections or older phones")
        print("    [2] 1080p  — Recommended for general use")
        print("    [3] 1440p  — High quality, needs a good connection")
        print("    [4] 4K     — Highest quality, needs a powerful phone & fast connection")
        print("    [5] 32K    — 32KFHD (Extreme max resolution)")
        print("    [6] Full   — Native phone resolution, no downscaling")
        print("    [7] Custom — Enter your own resolution")
    res_c = get_input("  Choice [1-7] (default: 2): ", ["1","2","3","4","5","6","7"], "2")
    resolution = {"1":"720","2":"1080","3":"1440","4":"2160","5":"32768","6":"0"}.get(res_c)
    if resolution is None: resolution = get_input("  Enter max size (e.g. 1920): ", default="1080")
    log_ok(f"Resolution: {'Full/Native' if resolution=='0' else resolution + ('p' if res_c in ['1','2','3'] else '')}")

    # ── Codec ─────────────────────────────────────────────
    print()
    if lang == "id":
        print(f"{Fore.CYAN}  Pilih Video Codec:")
        print("    [1] H.264 — Kompatibilitas terluas, semua versi Android (DEFAULT)")
        print("    [2] H.265 — Lebih efisien & hemat bandwidth (butuh Android 10+ / SDK 29+)")
        print("    [3] AV1   — Kualitas terbaik, eksperimental (butuh Android 14+ / SDK 34+)")
    else:
        print(f"{Fore.CYAN}  Choose Video Codec:")
        print("    [1] H.264 — Widest compatibility, all Android versions (DEFAULT)")
        print("    [2] H.265 — More efficient & saves bandwidth (requires Android 10+ / SDK 29+)")
        print("    [3] AV1   — Best quality, experimental (requires Android 14+ / SDK 34+)")
    if rec: print(f"    {Fore.GREEN}[★] Rekomendasi/Recommended: {rec['codec'].upper()}")
    codec_c = get_input("  Choice [1-3] (default: 1): ", ["1","2","3"], "1")
    codec = "h264"
    if codec_c == "2":
        if sdk < 29: log_warn("H.265 butuh Android 10+. Menggunakan H.264." if lang=="id" else "H.265 requires Android 10+. Falling back to H.264.")
        else: codec = "h265"
    elif codec_c == "3":
        if sdk < 34: log_warn("AV1 butuh Android 14+. Menggunakan H.264." if lang=="id" else "AV1 requires Android 14+. Falling back to H.264.")
        else: codec = "av1"
    log_ok(f"Codec: {codec.upper()}")

    # ══════ ADDITIONAL FEATURES ══════════════════════════

    print(f"\n{Fore.MAGENTA}  ╔══════════════════════════════════════════════════════════╗")
    print(f"{Fore.MAGENTA}  ║  {'FITUR TAMBAHAN' if lang=='id' else 'ADDITIONAL FEATURES':<56}║")
    print(f"{Fore.MAGENTA}  ╚══════════════════════════════════════════════════════════╝")

    # ── Camera Mirroring ──────────────────────────────────
    print()
    if lang == "id":
        print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
        print(f"{Fore.CYAN}  │  [KAMERA SEBAGAI WEBCAM]                             │")
        print(f"{Fore.CYAN}  │  Alih-alih menampilkan layar HP, laptop akan        │")
        print(f"{Fore.CYAN}  │  menampilkan output LANGSUNG dari kamera HP.         │")
        print(f"{Fore.CYAN}  │  Berguna untuk: Video call, siaran live, CCTV.      │")
        print(f"{Fore.CYAN}  │  ⚠ JIKA 'y': Layar HP TIDAK akan ditampilkan.      │")
        print(f"{Fore.CYAN}  │  ✔ JIKA 'n': Layar HP ditampilkan seperti biasa.   │")
        print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
        mirror_cam = get_input("  Aktifkan Kamera sebagai Webcam? [y/n] (default: n): ", ["y","n"], "n")
    else:
        print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
        print(f"{Fore.CYAN}  │  [CAMERA AS WEBCAM]                                  │")
        print(f"{Fore.CYAN}  │  Instead of the phone screen, the laptop will       │")
        print(f"{Fore.CYAN}  │  display LIVE output from the phone's camera.        │")
        print(f"{Fore.CYAN}  │  Useful for: Video calls, live streaming, CCTV.     │")
        print(f"{Fore.CYAN}  │  ⚠ IF 'y': Phone screen will NOT be mirrored.      │")
        print(f"{Fore.CYAN}  │  ✔ IF 'n': Phone screen is shown normally.         │")
        print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
        mirror_cam = get_input("  Enable Camera as Webcam? [y/n] (default: n): ", ["y","n"], "n")

    camera_facing = ""
    if mirror_cam == "y":
        print(f"  {Fore.YELLOW}  [front]    = Kamera depan / Front camera (selfie)")
        print(f"  {Fore.YELLOW}  [back]     = Kamera belakang / Rear camera (main)")
        print(f"  {Fore.YELLOW}  [external] = Kamera eksternal / External camera (USB/OTG)")
        camera_facing = get_input("  Pilih lensa [front/back/external] (default: back): " if lang=="id" else "  Choose lens [front/back/external] (default: back): ",
                                  ["front","back","external"], "back")

    # ── OTG Mode ──────────────────────────────────────────
    print()
    if lang == "id":
        print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
        print(f"{Fore.CYAN}  │  [MODE OTG — Hanya Kontrol, TANPA Tampilan Layar]   │")
        print(f"{Fore.CYAN}  │                                                      │")
        print(f"{Fore.CYAN}  │  Mode ini TIDAK menampilkan layar HP di laptop.      │")
        print(f"{Fore.CYAN}  │  Laptop bertindak seperti keyboard & mouse fisik     │")
        print(f"{Fore.CYAN}  │  yang langsung terhubung ke HP via kabel USB.        │")
        print(f"{Fore.CYAN}  │                                                      │")
        print(f"{Fore.CYAN}  │  ✔ GUNAKAN jika: Aplikasi Bank/Game tampilkan layar │")
        print(f"{Fore.CYAN}  │    hitam saat di-mirror secara normal.               │")
        print(f"{Fore.CYAN}  │  ✔ GUNAKAN jika: Ingin kontrol HP dari laptop tanpa │")
        print(f"{Fore.CYAN}  │    screen casting (lebih aman & privat).             │")
        print(f"{Fore.CYAN}  │  ✗ JANGAN gunakan jika: Ingin MELIHAT layar HP di   │")
        print(f"{Fore.CYAN}  │    laptop — gunakan mode Normal/biasa saja.          │")
        print(f"{Fore.CYAN}  │  ⚠ WAJIB pakai kabel USB. WiFi TIDAK didukung.     │")
        print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
        enable_otg = get_input("  Aktifkan Mode OTG? [y/n] (default: n): ", ["y","n"], "n")
    else:
        print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
        print(f"{Fore.CYAN}  │  [OTG MODE — Control Only, NO Screen Display]       │")
        print(f"{Fore.CYAN}  │                                                      │")
        print(f"{Fore.CYAN}  │  This mode does NOT show the phone screen on laptop. │")
        print(f"{Fore.CYAN}  │  Your laptop acts as a physical keyboard & mouse     │")
        print(f"{Fore.CYAN}  │  directly connected to the phone via USB cable.      │")
        print(f"{Fore.CYAN}  │                                                      │")
        print(f"{Fore.CYAN}  │  ✔ USE IF: Banking/Gaming apps show a black screen   │")
        print(f"{Fore.CYAN}  │    when mirrored normally.                           │")
        print(f"{Fore.CYAN}  │  ✔ USE IF: You want to control phone without screen  │")
        print(f"{Fore.CYAN}  │    casting (safer & more private).                   │")
        print(f"{Fore.CYAN}  │  ✗ DO NOT USE IF: You want to SEE the phone screen   │")
        print(f"{Fore.CYAN}  │    on laptop — use Normal mode instead.              │")
        print(f"{Fore.CYAN}  │  ⚠ REQUIRES USB cable. WiFi is NOT supported.      │")
        print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
        enable_otg = get_input("  Enable OTG Mode? [y/n] (default: n): ", ["y","n"], "n")

    virtual_display = "n"; window_opt = "1"; audio_mode = "1"
    advanced_kb = "n"; stay_awake = "y"; turn_screen_off = "n"
    no_control = "n"; crop = ""; shortcut_mod = "n"
    win_x = ""; win_y = ""; gamepad = "n"

    if enable_otg != "y":
        # ── Virtual Display ───────────────────────────────
        print()
        if lang == "id":
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [VIRTUAL DISPLAY — Layar Virtual Baru di HP]       │")
            print(f"{Fore.CYAN}  │  Membuat layar VIRTUAL terpisah di HP. Layar        │")
            print(f"{Fore.CYAN}  │  fisik HP tetap bisa dipakai orang lain, sementara  │")
            print(f"{Fore.CYAN}  │  Anda pakai layar virtualnya di laptop.             │")
            print(f"{Fore.CYAN}  │  ✔ Cocok untuk: Multitasking, privasi, developer   │")
            print(f"{Fore.CYAN}  │  ⚠ Fitur eksperimental, tidak semua HP mendukung   │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            virtual_display = get_input("  Aktifkan Virtual Display? [y/n] (default: n): ", ["y","n"], "n")
        else:
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [VIRTUAL DISPLAY — New Virtual Screen on Phone]    │")
            print(f"{Fore.CYAN}  │  Creates a separate VIRTUAL screen on the phone.    │")
            print(f"{Fore.CYAN}  │  The physical phone screen remains usable by others │")
            print(f"{Fore.CYAN}  │  while you use the virtual one on your laptop.      │")
            print(f"{Fore.CYAN}  │  ✔ Great for: Multitasking, privacy, developers    │")
            print(f"{Fore.CYAN}  │  ⚠ Experimental — not all phones support this      │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            virtual_display = get_input("  Enable Virtual Display? [y/n] (default: n): ", ["y","n"], "n")

        # ── Crop Display ──────────────────────────────────
        print()
        if lang == "id":
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [CROP DISPLAY — Tampilkan Sebagian Layar]          │")
            print(f"{Fore.CYAN}  │  Mirror hanya sebagian dari layar HP, bukan         │")
            print(f"{Fore.CYAN}  │  seluruh layar. Format input: LebarxTinggi:X:Y      │")
            print(f"{Fore.CYAN}  │  Contoh: 540x960:0:0 → kiri atas, setengah layar   │")
            print(f"{Fore.CYAN}  │  ✔ Cocok untuk: Streamer, demo fitur tertentu saja  │")
            print(f"{Fore.CYAN}  │  ↵ Kosongkan (Enter) untuk mirror layar penuh      │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            crop = get_input("  Masukkan area crop (Enter = skip): ", default="")
        else:
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [CROP DISPLAY — Mirror a Part of the Screen]       │")
            print(f"{Fore.CYAN}  │  Mirror only a portion of the phone screen instead  │")
            print(f"{Fore.CYAN}  │  of the full screen. Format: WidthxHeight:X:Y       │")
            print(f"{Fore.CYAN}  │  Example: 540x960:0:0 → top-left, half the screen  │")
            print(f"{Fore.CYAN}  │  ✔ Great for: Streamers, specific feature demos     │")
            print(f"{Fore.CYAN}  │  ↵ Leave empty (Enter) to mirror the full screen   │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            crop = get_input("  Enter crop area (Enter = skip): ", default="")

        # ── Window Options ────────────────────────────────
        print()
        if lang == "id":
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [TAMPILAN JENDELA MIRRORING DI LAPTOP]             │")
            print(f"{Fore.CYAN}  │  [1] Normal       — Jendela biasa, bisa dipindah    │")
            print(f"{Fore.CYAN}  │  [2] Always Top   — Jendela SELALU di depan app lain│")
            print(f"{Fore.CYAN}  │  [3] Borderless   — Tanpa bingkai (tampilan bersih) │")
            print(f"{Fore.CYAN}  │  [4] Top+Borderless — Kombinasi keduanya            │")
            print(f"{Fore.CYAN}  │  [5] Fullscreen   — Layar Penuh memenuhi monitor    │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            window_opt = get_input("  Pilihan Anda [1-5] (default: 1): ", ["1","2","3","4","5"], "1")
        else:
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [MIRROR WINDOW DISPLAY MODE]                       │")
            print(f"{Fore.CYAN}  │  [1] Normal       — Regular movable window          │")
            print(f"{Fore.CYAN}  │  [2] Always Top   — Window ALWAYS above other apps  │")
            print(f"{Fore.CYAN}  │  [3] Borderless   — No frame/border (cleaner look)  │")
            print(f"{Fore.CYAN}  │  [4] Top+Borderless — Always on top AND borderless  │")
            print(f"{Fore.CYAN}  │  [5] Fullscreen   — Fills the entire monitor        │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            window_opt = get_input("  Your choice [1-5] (default: 1): ", ["1","2","3","4","5"], "1")

        if window_opt != "5":
            print()
            set_pos = get_input("  Atur posisi jendela awal (X/Y)? [y/n] (default: n): " if lang=="id" else "  Set initial window position (X/Y)? [y/n] (default: n): ", ["y","n"], "n")
            if set_pos == "y":
                win_x = get_input("  X (contoh/e.g. 100): ", default="100")
                win_y = get_input("  Y (contoh/e.g. 100): ", default="100")

        # ── Audio ─────────────────────────────────────────
        print()
        if lang == "id":
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [PENGATURAN SUARA]  Syarat: Android 11+ (SDK 30+) │")
            print(f"{Fore.CYAN}  │  [1] Suara di Laptop saja — default, untuk nonton   │")
            print(f"{Fore.CYAN}  │  [2] Suara di HP & Laptop — keluar di dua perangkat │")
            print(f"{Fore.CYAN}  │  [3] Suara di HP saja     — laptop dibisukan        │")
            print(f"{Fore.CYAN}  │      (cocok jika pakai earphone di HP)              │")
            print(f"{Fore.CYAN}  │  [4] Mikrofon HP → Laptop — HP jadi mic laptop      │")
            print(f"{Fore.CYAN}  │      (berguna untuk meeting/rekaman di laptop)       │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            audio_mode = get_input("  Pilihan Anda [1-4] (default: 1): ", ["1","2","3","4"], "1")
        else:
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [AUDIO SETTINGS]  Requires: Android 11+ (SDK 30+) │")
            print(f"{Fore.CYAN}  │  [1] Laptop only   — default, great for media       │")
            print(f"{Fore.CYAN}  │  [2] Phone & Laptop — audio on both devices         │")
            print(f"{Fore.CYAN}  │  [3] Phone only    — laptop muted                   │")
            print(f"{Fore.CYAN}  │      (good if you use earphones on your phone)      │")
            print(f"{Fore.CYAN}  │  [4] Phone Mic → Laptop — use phone as microphone   │")
            print(f"{Fore.CYAN}  │      (great for meetings or recordings on laptop)   │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            audio_mode = get_input("  Your choice [1-4] (default: 1): ", ["1","2","3","4"], "1")

        # ── UHID Keyboard ─────────────────────────────────
        print()
        if lang == "id":
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [KEYBOARD UHID — Mode Keyboard Fisik]              │")
            print(f"{Fore.CYAN}  │  Secara default, scrcpy pakai injeksi teks biasa.   │")
            print(f"{Fore.CYAN}  │  UHID mensimulasikan keyboard USB fisik sungguhan   │")
            print(f"{Fore.CYAN}  │  sehingga SEMUA tombol (Ctrl, Alt, shortcut, game) │")
            print(f"{Fore.CYAN}  │  berfungsi 100% akurat dan tanpa delay sama sekali. │")
            print(f"{Fore.CYAN}  │  ✔ Aktifkan jika: Sering mengetik atau main game    │")
            print(f"{Fore.CYAN}  │    yang butuh input keyboard yang presisi & cepat.  │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            advanced_kb = get_input("  Aktifkan UHID Keyboard? [y/n] (default: n): ", ["y","n"], "n")
        else:
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [UHID KEYBOARD — Physical Keyboard Mode]           │")
            print(f"{Fore.CYAN}  │  By default, scrcpy uses basic text injection.      │")
            print(f"{Fore.CYAN}  │  UHID simulates a real physical USB keyboard so     │")
            print(f"{Fore.CYAN}  │  ALL keys (Ctrl, Alt, shortcuts, game keys) work    │")
            print(f"{Fore.CYAN}  │  100% accurately with absolutely zero delay.        │")
            print(f"{Fore.CYAN}  │  ✔ Enable if: You type often or play games that     │")
            print(f"{Fore.CYAN}  │    require precise & fast keyboard input.           │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            advanced_kb = get_input("  Enable UHID Keyboard? [y/n] (default: n): ", ["y","n"], "n")

        # ── Gamepad Mapping ───────────────────────────────
        print()
        if lang == "id":
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [GAMEPAD MAPPING — UHID]                           │")
            print(f"{Fore.CYAN}  │  Teruskan input dari Gamepad/Controller fisik yang  │")
            print(f"{Fore.CYAN}  │  dicolok ke laptop langsung ke HP secara native.    │")
            print(f"{Fore.CYAN}  │  ✔ Cocok untuk: Main game Android dengan Joystick   │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            gamepad = get_input("  Aktifkan Gamepad Mapping? [y/n] (default: n): ", ["y","n"], "n")
        else:
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [GAMEPAD MAPPING — UHID]                           │")
            print(f"{Fore.CYAN}  │  Forward input from physical Gamepad/Controller     │")
            print(f"{Fore.CYAN}  │  connected to laptop directly to phone natively.    │")
            print(f"{Fore.CYAN}  │  ✔ Great for: Playing Android games with a Joystick │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            gamepad = get_input("  Enable Gamepad Mapping? [y/n] (default: n): ", ["y","n"], "n")

        # ── Screenshot Shortcut ───────────────────────────
        print()
        if lang == "id":
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [SCREENSHOT SHORTCUT — Tombol 'S' di Terminal]     │")
            print(f"{Fore.CYAN}  │  Tekan tombol 'S' pada jendela terminal ini saat    │")
            print(f"{Fore.CYAN}  │  mirror aktif untuk mengambil screenshot layar HP.  │")
            print(f"{Fore.CYAN}  │  File disimpan di folder saat ini dengan format:    │")
            print(f"{Fore.CYAN}  │  screenshot_YYYYMMDD_HHMMSS.png                     │")
            print(f"{Fore.CYAN}  │  ✔ Cocok untuk: Ambil bukti, dokumentasi, debug    │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            shortcut_mod = get_input("  Aktifkan Screenshot Shortcut? [y/n] (default: n): ", ["y","n"], "n")
        else:
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [SCREENSHOT SHORTCUT — Press 'S' in Terminal]      │")
            print(f"{Fore.CYAN}  │  Press 'S' in this terminal window while the mirror │")
            print(f"{Fore.CYAN}  │  is active to take a screenshot of the phone screen.│")
            print(f"{Fore.CYAN}  │  File saved in the current folder as:               │")
            print(f"{Fore.CYAN}  │  screenshot_YYYYMMDD_HHMMSS.png                     │")
            print(f"{Fore.CYAN}  │  ✔ Great for: Capturing evidence, docs, debugging   │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            shortcut_mod = get_input("  Enable Screenshot Shortcut? [y/n] (default: n): ", ["y","n"], "n")

        # ── Stay Awake ────────────────────────────────────
        print()
        if lang == "id":
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [STAY AWAKE — Jaga Layar HP Tetap Menyala]         │")
            print(f"{Fore.CYAN}  │  Secara default, layar HP akan mati otomatis sesuai │")
            print(f"{Fore.CYAN}  │  timer screen-off di pengaturan HP Anda.            │")
            print(f"{Fore.CYAN}  │  Fitur ini memaksa layar HP agar TIDAK mati selama  │")
            print(f"{Fore.CYAN}  │  kabel USB/charger terhubung dan mirroring aktif.   │")
            print(f"{Fore.CYAN}  │  ✔ Aktifkan agar sesi mirroring tidak terputus tiba │")
            print(f"{Fore.CYAN}  │    tiba karena layar HP mati/terkunci.              │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            stay_awake = get_input("  Aktifkan Stay Awake? [y/n] (default: y): ", ["y","n"], "y")
        else:
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [STAY AWAKE — Keep Phone Screen On]                │")
            print(f"{Fore.CYAN}  │  By default, the phone screen turns off based on    │")
            print(f"{Fore.CYAN}  │  the auto-lock timer in your phone settings.        │")
            print(f"{Fore.CYAN}  │  This feature forces the screen to STAY ON as long  │")
            print(f"{Fore.CYAN}  │  as a USB/charger cable is connected & mirroring    │")
            print(f"{Fore.CYAN}  │  is active.                                         │")
            print(f"{Fore.CYAN}  │  ✔ Enable to prevent mirroring from being suddenly  │")
            print(f"{Fore.CYAN}  │    interrupted due to the phone screen locking.     │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            stay_awake = get_input("  Enable Stay Awake? [y/n] (default: y): ", ["y","n"], "y")

        # ── Turn Screen Off ───────────────────────────────
        print()
        if lang == "id":
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [MATIKAN LAYAR HP — Hemat Baterai]                 │")
            print(f"{Fore.CYAN}  │  Layar fisik HP akan menjadi hitam/mati, NAMUN      │")
            print(f"{Fore.CYAN}  │  mirroring di laptop tetap berjalan normal.         │")
            print(f"{Fore.CYAN}  │  Berguna untuk: Menghemat baterai HP saat mirroring │")
            print(f"{Fore.CYAN}  │  jangka panjang, atau menjaga privasi layar HP.     │")
            print(f"{Fore.CYAN}  │  ⚠ Gabungkan dengan Stay Awake: HP tidak terkunci  │")
            print(f"{Fore.CYAN}  │    meski layar mati (tetap bisa dikontrol laptop).  │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            turn_screen_off = get_input("  Matikan layar HP saat mirroring? [y/n] (default: n): ", ["y","n"], "n")
        else:
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [TURN SCREEN OFF — Save Battery]                   │")
            print(f"{Fore.CYAN}  │  The physical phone screen will go dark/off, BUT    │")
            print(f"{Fore.CYAN}  │  mirroring on the laptop continues running normally. │")
            print(f"{Fore.CYAN}  │  Useful for: Saving phone battery during long        │")
            print(f"{Fore.CYAN}  │  mirroring sessions, or keeping phone screen private.│")
            print(f"{Fore.CYAN}  │  ⚠ Combine with Stay Awake: phone won't lock even   │")
            print(f"{Fore.CYAN}  │    with screen off (still controllable from laptop). │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            turn_screen_off = get_input("  Turn off phone screen? [y/n] (default: n): ", ["y","n"], "n")

        # ── No Control ────────────────────────────────────
        print()
        if lang == "id":
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [NO CONTROL — Mode Lihat Saja / View Only]         │")
            print(f"{Fore.CYAN}  │  Anda HANYA BISA MELIHAT layar HP di laptop,        │")
            print(f"{Fore.CYAN}  │  TIDAK BISA mengklik, mengetik, atau mengontrol HP  │")
            print(f"{Fore.CYAN}  │  dari laptop sama sekali.                            │")
            print(f"{Fore.CYAN}  │  ✔ Gunakan untuk: Presentasi — audience lihat HP    │")
            print(f"{Fore.CYAN}  │    Anda di layar besar tanpa risiko klik tidak sengaja│")
            print(f"{Fore.CYAN}  │  ✔ Gunakan untuk: Streaming/demo yang tidak ingin   │")
            print(f"{Fore.CYAN}  │    HP-nya tersentuh secara tidak sengaja.            │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            no_control = get_input("  Aktifkan No Control (View Only)? [y/n] (default: n): ", ["y","n"], "n")
        else:
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [NO CONTROL — View Only Mode]                      │")
            print(f"{Fore.CYAN}  │  You can ONLY WATCH the phone screen on the laptop, │")
            print(f"{Fore.CYAN}  │  but CANNOT click, type, or control the phone at    │")
            print(f"{Fore.CYAN}  │  all from the laptop.                                │")
            print(f"{Fore.CYAN}  │  ✔ Use for: Presentations — audience sees your phone │")
            print(f"{Fore.CYAN}  │    on a big screen, no risk of accidental taps.     │")
            print(f"{Fore.CYAN}  │  ✔ Use for: Streaming or demos where you don't want │")
            print(f"{Fore.CYAN}  │    the phone to be accidentally interacted with.    │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            no_control = get_input("  Enable No Control (View Only)? [y/n] (default: n): ", ["y","n"], "n")

        # ── Picture-in-Picture (PiP) ──────────────────────
        print()
        if lang == "id":
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [PICTURE-IN-PICTURE — Layar Mengambang]            │")
            print(f"{Fore.CYAN}  │  Jendela HP tidak akan memiliki bingkai (borderless)│")
            print(f"{Fore.CYAN}  │  dan SELALU BERAADA DI ATAS aplikasi lain (always   │")
            print(f"{Fore.CYAN}  │  on top). Cocok sambil kerja/nonton.                │")
            print(f"{Fore.CYAN}  │  ⚠ Geser jendela: Tahan tombol Alt + Klik & Tarik   │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            window_pip = get_input("  Aktifkan Mode PiP? [y/n] (default: n): ", ["y","n"], "n")
        else:
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [PICTURE-IN-PICTURE — Floating Window]             │")
            print(f"{Fore.CYAN}  │  The phone window will be borderless and ALWAYS ON  │")
            print(f"{Fore.CYAN}  │  TOP of other applications. Great for multitasking. │")
            print(f"{Fore.CYAN}  │  ⚠ Move window: Hold Alt key + Click & Drag         │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            window_pip = get_input("  Enable PiP Mode? [y/n] (default: n): ", ["y","n"], "n")

        # ── Auto-Lock on Close ────────────────────────────
        print()
        if lang == "id":
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [AUTO-LOCK — Kunci HP Saat Keluar]                 │")
            print(f"{Fore.CYAN}  │  Saat Anda menutup jendela scrcpy (mirroring tamat),│")
            print(f"{Fore.CYAN}  │  program akan otomatis mematikan layar HP Anda untuk│")
            print(f"{Fore.CYAN}  │  menjaga keamanan dan privasi.                      │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            auto_lock = get_input("  Kunci HP otomatis saat ditutup? [y/n] (default: y): ", ["y","n"], "y")
        else:
            print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
            print(f"{Fore.CYAN}  │  [AUTO-LOCK — Lock Phone on Close]                  │")
            print(f"{Fore.CYAN}  │  When you close the scrcpy window, the program will │")
            print(f"{Fore.CYAN}  │  automatically turn off the phone screen for privacy│")
            print(f"{Fore.CYAN}  │  and security.                                      │")
            print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
            auto_lock = get_input("  Auto-lock phone on close? [y/n] (default: y): ", ["y","n"], "y")

    # ── Record Screen ─────────────────────────────────────
    print()
    if lang == "id":
        print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
        print(f"{Fore.CYAN}  │  [REKAM LAYAR — Screen Record]                      │")
        print(f"{Fore.CYAN}  │  Seluruh sesi mirroring akan direkam dan disimpan   │")
        print(f"{Fore.CYAN}  │  sebagai file video (.mp4) di folder saat ini.      │")
        print(f"{Fore.CYAN}  │  ✔ Cocok untuk: Tutorial, gameplay, demo aplikasi   │")
        print(f"{Fore.CYAN}  │  ⚠ Ukuran file bisa besar tergantung durasi &      │")
        print(f"{Fore.CYAN}  │    resolusi yang dipilih. Pastikan ada ruang disk.  │")
        print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
        record_screen = get_input("  Aktifkan Rekam Layar? [y/n] (default: n): ", ["y","n"], "n")
    else:
        print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────┐")
        print(f"{Fore.CYAN}  │  [SCREEN RECORD]                                    │")
        print(f"{Fore.CYAN}  │  The entire mirroring session will be recorded and  │")
        print(f"{Fore.CYAN}  │  saved as a video file (.mp4) in the current folder.│")
        print(f"{Fore.CYAN}  │  ✔ Great for: Tutorials, gameplay, app demos        │")
        print(f"{Fore.CYAN}  │  ⚠ File size can be large depending on duration    │")
        print(f"{Fore.CYAN}  │    and resolution. Ensure you have enough disk space.│")
        print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────┘")
        record_screen = get_input("  Enable Screen Record? [y/n] (default: n): ", ["y","n"], "n")

    record_filename = ""
    if record_screen == "y":
        default_name = f"screenmirror_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
        if lang == "id":
            record_filename = get_input(f"  Nama file (Enter untuk '{default_name}'): ", default=default_name)
            log_ok(f"Merekam ke: {record_filename}")
        else:
            record_filename = get_input(f"  File name (Enter for '{default_name}'): ", default=default_name)
            log_ok(f"Recording to: {record_filename}")

    config = {
        "fps": fps, "bitrate": bitrate, "resolution": resolution, "codec": codec,
        "mirror_cam": mirror_cam, "camera_facing": camera_facing,
        "enable_otg": enable_otg, "virtual_display": virtual_display,
        "window_opt": window_opt, "win_x": win_x, "win_y": win_y, "gamepad": gamepad,
        "audio_mode": audio_mode,
        "advanced_kb": advanced_kb, "stay_awake": stay_awake,
        "turn_screen_off": turn_screen_off, "no_control": no_control,
        "record_filename": record_filename, "crop": crop,
        "shortcut_mod": shortcut_mod, "window_pip": window_pip,
        "auto_lock": auto_lock,
    }

    # ── Save preset? ──────────────────────────────────────
    print()
    if lang == "id":
        print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────────────┐")
        print(f"{Fore.CYAN}  │  [SIMPAN PRESET]                                            │")
        print(f"{Fore.CYAN}  │  Pengaturan ini bisa disimpan agar tidak perlu diatur ulang │")
        print(f"{Fore.CYAN}  │  setiap kali. File konfigurasi akan disimpan secara aman di:│")
        print(f"{Fore.CYAN}  │  {Fore.YELLOW}{PRESET_FILE:<55}{Fore.CYAN}│")
        print(f"{Fore.CYAN}  │  (%APPDATA% adalah folder bawaan Windows untuk data aplikasi│")
        print(f"{Fore.CYAN}  │  sehingga data tidak hilang meski file script dipindahkan). │")
        print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────────────┘")
        prompt = "  Simpan sebagai preset? [y/n] (default: n): "
    else:
        print(f"{Fore.CYAN}  ┌─────────────────────────────────────────────────────────────┐")
        print(f"{Fore.CYAN}  │  [SAVE PRESET]                                              │")
        print(f"{Fore.CYAN}  │  You can save these settings to avoid configuring them next │")
        print(f"{Fore.CYAN}  │  time. The config file will be safely stored in:            │")
        print(f"{Fore.CYAN}  │  {Fore.YELLOW}{PRESET_FILE:<55}{Fore.CYAN}│")
        print(f"{Fore.CYAN}  │  (%APPDATA% is a built-in Windows folder for app data, so   │")
        print(f"{Fore.CYAN}  │  your presets won't be lost if you move the script file).   │")
        print(f"{Fore.CYAN}  └─────────────────────────────────────────────────────────────┘")
        prompt = "  Save as preset? [y/n] (default: n): "

    if get_input(prompt, ["y","n"], "n") == "y":
        pname = get_input("  Nama preset: " if lang == "id" else "  Preset name: ", default="My Preset")
        if _save_preset(pname, config):
            log_ok(f"Preset '{pname}' disimpan!" if lang == "id" else f"Preset '{pname}' saved!")
        else:
            log_warn("Gagal menyimpan preset." if lang == "id" else "Failed to save preset.")

    return config


def select_or_configure(lang, device_info=None):
    presets = _load_presets()
    names   = list(presets.keys())

    print(f"\n{Fore.MAGENTA}  ╔══════════════════════════════════════════════════════════╗")
    print(f"{Fore.MAGENTA}  ║  {'PILIH PRESET ATAU KONFIGURASI SENDIRI' if lang=='id' else 'SELECT PRESET OR CONFIGURE MANUALLY':<56}║")
    print(f"{Fore.MAGENTA}  ╚══════════════════════════════════════════════════════════╝\n")

    for i, name in enumerate(names, 1):
        p = presets[name]
        tag = f"[{i}] {name}"
        det = f"{p.get('fps','?')}fps · {p.get('bitrate','?')} · {p.get('codec','?').upper()}"
        builtin = "  (built-in)" if name in _BUILTIN_PRESETS else ""
        print(f"    {Fore.YELLOW}{tag:<30}{Fore.WHITE}{det}{Fore.CYAN}{builtin}")

    nxt = len(names) + 1
    custom_label = "Konfigurasi Manual" if lang == "id" else "Custom Configuration"
    print(f"\n    {Fore.GREEN}[{nxt}] {custom_label}")

    custom_names = [n for n in names if n not in _BUILTIN_PRESETS]
    if custom_names:
        del_lbl = "[D] Hapus Preset Custom" if lang == "id" else "[D] Delete Custom Preset"
        print(f"    {Fore.RED}{del_lbl}")

    choices = [str(i) for i in range(1, nxt+1)] + (["d"] if custom_names else [])
    ch = get_input(f"\n  Pilihan: " if lang == "id" else f"\n  Choice: ", choices, str(nxt))

    if ch == "d":
        for i, n in enumerate(custom_names, 1):
            print(f"    [{i}] {n}")
        dc = get_input("  Pilih untuk dihapus: " if lang == "id" else "  Select to delete: ",
                       [str(i) for i in range(1, len(custom_names)+1)], "1")
        dname = custom_names[int(dc)-1]
        _delete_preset(dname)
        log_ok(f"Preset '{dname}' dihapus." if lang == "id" else f"Preset '{dname}' deleted.")
        return select_or_configure(lang, device_info)

    idx = int(ch) - 1
    if idx < len(names):
        sel = dict(presets[names[idx]])
        if sel.get("record_filename") == "__auto__":
            sel["record_filename"] = f"screenmirror_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
        log_ok(f"Preset '{names[idx]}' dipilih." if lang == "id" else f"Preset '{names[idx]}' selected.")
        return sel
    else:
        return configure_scrcpy(lang, device_info)


# ═══════════════════════════════════════════════════════════
#   CONFIGURATION SUMMARY
# ═══════════════════════════════════════════════════════════

def show_config_summary(config, device_info, lang="en"):
    c = config
    d = device_info or {}

    def yn(v, default_yes=False):
        val = v if v else ("y" if default_yes else "n")
        return ("YA" if lang=="id" else "YES") if val=="y" else ("Tidak" if lang=="id" else "No")

    audio_lbl = {"1":"Laptop saja/only","2":"HP & Laptop","3":"HP saja/only","4":"Mikrofon HP/Phone Mic"}.get(c.get("audio_mode","1"),"?")
    win_lbl   = {"1":"Normal","2":"Always on Top","3":"Borderless","4":"Top+Borderless"}.get(c.get("window_opt","1"),"?")
    res       = c.get("resolution","1080")
    res_lbl   = "Full/Native" if res=="0" else f"{res}p"

    def _pr(lbl, val, col=Fore.WHITE):
        val_str = str(val)
        vis_len = 24 + len(val_str)
        pad = " " * max(0, 58 - vis_len)
        if val_str in ["YA", "YES"]: col = Fore.GREEN
        elif val_str in ["Tidak", "No"]: col = Fore.RED
        print(f"{Fore.BLUE}  ║  {Fore.WHITE}{lbl:<17}{Fore.CYAN}│ {col}{val_str}{pad}{Fore.BLUE}║")

    print(f"\n{Fore.BLUE}  ╔══════════════════════════════════════════════════════════╗")
    print(f"{Fore.BLUE}  ║  {'RINGKASAN KONFIGURASI' if lang=='id' else 'CONFIGURATION SUMMARY':<56}║")
    print(f"{Fore.BLUE}  ╠══════════════════════════════════════════════════════════╣")
    _pr('Perangkat' if lang=='id' else 'Device', f"{d.get('brand','?')} {d.get('model','')}", Fore.GREEN)
    _pr('Android', f"{d.get('android','?')} (SDK {d.get('sdk','?')})", Fore.GREEN)
    print(f"{Fore.BLUE}  ╠══════════════════════════════════════════════════════════╣")
    _pr('FPS', c.get('fps','60'), Fore.YELLOW)
    _pr('Bitrate', c.get('bitrate','8M'), Fore.YELLOW)
    _pr('Resolusi/Resolution', res_lbl, Fore.YELLOW)
    _pr('Codec', c.get('codec','h264').upper(), Fore.YELLOW)
    print(f"{Fore.BLUE}  ╠══════════════════════════════════════════════════════════╣")
    _pr('Audio', audio_lbl, Fore.WHITE)
    _pr('Window', win_lbl, Fore.WHITE)
    _pr('UHID Keyboard', yn(c.get('advanced_kb','n')))
    _pr('Stay Awake', yn(c.get('stay_awake','y'), default_yes=True))
    _pr('Screen Off', yn(c.get('turn_screen_off','n')))
    _pr('No Control', yn(c.get('no_control','n')))
    _pr('OTG Mode', yn(c.get('enable_otg','n')))
    _pr('Virtual Display', yn(c.get('virtual_display','n')))
    if c.get("crop"):
        _pr('Crop', c.get('crop'))
    if c.get("shortcut_mod") == "y":
        _pr('Screenshot', 'Ctrl+Shift+S', Fore.GREEN)
    if c.get("record_filename"):
        _pr('Recording', c.get('record_filename'), Fore.RED)
    print(f"{Fore.BLUE}  ╚══════════════════════════════════════════════════════════╝\n")

    prompt = "  Lanjutkan dan mulai mirroring? [y/n] (default: y): " if lang=="id" else "  Proceed and start mirroring? [y/n] (default: y): "
    return get_input(prompt, ["y","n"], "y")


# ═══════════════════════════════════════════════════════════
#   SESSION LOG
# ═══════════════════════════════════════════════════════════

def _log_session(config, device_info, duration_sec):
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        d   = device_info or {}
        c   = config
        mins, secs = int(duration_sec//60), int(duration_sec%60)
        with open(SESSION_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n{'═'*62}\n")
            f.write(f"Session  : {now}\n")
            f.write(f"Device   : {d.get('brand','')} {d.get('model','')} │ Android {d.get('android','')} (SDK {d.get('sdk','')})\n")
            f.write(f"Platform : {d.get('platform','')} │ {d.get('cpu_abi','')} │ Battery: {d.get('battery','?')}\n")
            f.write(f"Mode     : {c.get('mode','?').upper()}\n")
            f.write(f"Video    : {c.get('fps','?')}fps · {c.get('bitrate','?')} · {c.get('resolution','?')}p · {c.get('codec','?').upper()}\n")
            feats = []
            if c.get("enable_otg")=="y":     feats.append("OTG")
            if c.get("advanced_kb")=="y":    feats.append("UHID-KB")
            if c.get("stay_awake")=="y":     feats.append("StayAwake")
            if c.get("turn_screen_off")=="y":feats.append("ScreenOff")
            if c.get("no_control")=="y":     feats.append("NoControl")
            if c.get("virtual_display")=="y":feats.append("VirtualDisplay")
            if c.get("crop"):                feats.append(f"Crop({c.get('crop')})")
            f.write(f"Features : {', '.join(feats) if feats else 'none'}\n")
            if c.get("record_filename"):
                f.write(f"Recording: {c.get('record_filename')}\n")
            f.write(f"Duration : {mins}m {secs}s\n")
    except Exception:
        pass


def show_session_log(lang):
    if not os.path.exists(SESSION_LOG):
        log_warn("Belum ada riwayat sesi." if lang=="id" else "No session history yet.")
        input("  Enter...")
        return

    print(f"\n{Fore.CYAN}  {'═'*20} {'RIWAYAT SESI' if lang=='id' else 'SESSION HISTORY'} {'═'*20}\n")
    try:
        with open(SESSION_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines[-70:]:
            print(f"  {Fore.WHITE}{line}", end="")
    except Exception as e:
        log_err(str(e))
    print()
    input("  Tekan Enter untuk kembali..." if lang=="id" else "  Press Enter to go back...")


# ═══════════════════════════════════════════════════════════
#   CLIPBOARD SYNC
# ═══════════════════════════════════════════════════════════

def _get_laptop_clipboard():
    """Read current laptop clipboard content (cross-platform)."""
    try:
        if os.name == "nt":
            import ctypes
            ctypes.windll.user32.OpenClipboard(0)
            handle = ctypes.windll.user32.GetClipboardData(13)  # CF_UNICODETEXT
            ctypes.windll.user32.CloseClipboard()
            if handle:
                ptr = ctypes.cdll.msvcrt.wcsdup(ctypes.cast(handle, ctypes.c_wchar_p))
                text = ctypes.cast(ptr, ctypes.c_wchar_p).value
                ctypes.windll.kernel32.GlobalFree(ptr)
                return text or ""
        elif sys.platform == "darwin":
            r = subprocess.run(["pbpaste"], capture_output=True, text=True)
            return r.stdout
        else:  # Linux
            for cmd in [["xclip","-sel","clip","-o"], ["xsel","--clipboard","--output"], ["wl-paste"]]:
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                    if r.returncode == 0: return r.stdout
                except Exception: pass
    except Exception:
        pass
    return ""


def _set_laptop_clipboard(text):
    """Write text to laptop clipboard (cross-platform)."""
    try:
        if os.name == "nt":
            subprocess.run(["clip"], input=text.encode("utf-16", errors="replace"), check=True)
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
        else:
            for cmd in [["xclip","-sel","clip"], ["xsel","--clipboard","--input"], ["wl-copy"]]:
                try:
                    subprocess.run(cmd, input=text.encode(), check=True, timeout=2)
                    return True
                except Exception: pass
    except Exception:
        pass


def _get_phone_clipboard(device_id):
    """Read clipboard from Android phone via adb."""
    try:
        r = subprocess.run(
            [ADB_EXE, "-s", device_id, "shell",
             "am", "broadcast", "-a", "clipper.get"],
            capture_output=True, text=True, timeout=5
        )
        # Clipper app response: data="text"
        m = re.search(r'data="(.+?)"', r.stdout, re.DOTALL)
        if m: return m.group(1)
        # Fallback: dumpsys clipboard (Android 10+)
        r2 = subprocess.run(
            [ADB_EXE, "-s", device_id, "shell", "dumpsys", "clipboard"],
            capture_output=True, text=True, timeout=5
        )
        for line in r2.stdout.splitlines():
            if "text=" in line.lower():
                return line.split("text=", 1)[-1].strip().strip('"')
    except Exception:
        pass
    return None


def _set_phone_clipboard(device_id, text):
    """Send text to Android phone clipboard via adb."""
    escaped = text.replace('"', '\\"').replace("'", "\\'").replace("\n", " ")
    try:
        # Method 1: input keyevent approach (universal)
        subprocess.run(
            [ADB_EXE, "-s", device_id, "shell",
             "am", "broadcast", "-a", "clipper.set", "-e", "text", escaped],
            capture_output=True, timeout=5
        )
        # Method 2: AM start clipboard service (works without Clipper on Android 10+)
        subprocess.run(
            [ADB_EXE, "-s", device_id, "shell",
             f"input text '{escaped}'"],
            capture_output=True, timeout=5
        )
        return True
    except Exception:
        return False


def clipboard_sync_menu(device_info, lang="en"):
    device_id = device_info.get("id", "")
    while True:
        print_banner(lang)
        print(f"\n{Fore.CYAN}  ╔══════════════════════════════════════════════════════════╗")
        if lang == "id":
            print(f"{Fore.CYAN}  ║  📋 SINKRON CLIPBOARD                                       ║")
            print(f"{Fore.CYAN}  ╠══════════════════════════════════════════════════════════╣")
            print(f"{Fore.CYAN}  ║  {Fore.YELLOW}[1]{Fore.WHITE} Laptop → HP    Kirim teks dari clipboard laptop ke HP   {Fore.CYAN}║")
            print(f"{Fore.CYAN}  ║  {Fore.YELLOW}[2]{Fore.WHITE} HP → Laptop    Ambil teks dari clipboard HP ke laptop    {Fore.CYAN}║")
            print(f"{Fore.CYAN}  ║  {Fore.YELLOW}[3]{Fore.WHITE} Ketik manual   Tulis teks dan kirim ke HP               {Fore.CYAN}║")
            print(f"{Fore.CYAN}  ║  {Fore.RED}[0]{Fore.WHITE} Kembali                                              {Fore.CYAN}║")
        else:
            print(f"{Fore.CYAN}  ║  📋 CLIPBOARD SYNC                                          ║")
            print(f"{Fore.CYAN}  ╠══════════════════════════════════════════════════════════╣")
            print(f"{Fore.CYAN}  ║  {Fore.YELLOW}[1]{Fore.WHITE} Laptop → Phone  Push laptop clipboard text to phone    {Fore.CYAN}║")
            print(f"{Fore.CYAN}  ║  {Fore.YELLOW}[2]{Fore.WHITE} Phone → Laptop  Pull phone clipboard text to laptop    {Fore.CYAN}║")
            print(f"{Fore.CYAN}  ║  {Fore.YELLOW}[3]{Fore.WHITE} Type & Send    Type text manually and send to phone    {Fore.CYAN}║")
            print(f"{Fore.CYAN}  ║  {Fore.RED}[0]{Fore.WHITE} Back                                                 {Fore.CYAN}║")
        print(f"{Fore.CYAN}  ╚══════════════════════════════════════════════════════════╝")

        ch = get_input("  Choice [0-3]: ", ["0","1","2","3"])
        if ch == "0":
            break
        elif ch == "1":
            text = _get_laptop_clipboard()
            if not text:
                log_warn("Clipboard laptop kosong!" if lang=="id" else "Laptop clipboard is empty!")
            else:
                preview = text[:60].replace("\n","\\n")
                print(f"  {Fore.WHITE}Preview: {Fore.YELLOW}\"{preview}{'...' if len(text)>60 else ''}\"") 
                if get_input("  Kirim ke HP? [y/n]: " if lang=="id" else "  Send to phone? [y/n]: ", ["y","n"], "y") == "y":
                    _set_phone_clipboard(device_id, text)
                    log_ok("Teks dikirim ke HP!" if lang=="id" else "Text sent to phone!")
        elif ch == "2":
            text = _get_phone_clipboard(device_id)
            if not text:
                log_warn("Clipboard HP kosong atau tidak bisa dibaca." if lang=="id" else "Phone clipboard is empty or unreadable.")
                log_info("Tip: Install app 'Clipper' di HP untuk akses clipboard penuh." if lang=="id" else "Tip: Install 'Clipper' app on phone for full clipboard access.")
            else:
                preview = text[:60].replace("\n","\\n")
                print(f"  {Fore.WHITE}Preview: {Fore.YELLOW}\"{preview}{'...' if len(text)>60 else ''}\"")
                _set_laptop_clipboard(text)
                log_ok("Teks disalin ke clipboard laptop!" if lang=="id" else "Text copied to laptop clipboard!")
        elif ch == "3":
            text = get_input("  Masukkan teks (lalu Enter): " if lang=="id" else "  Enter text (then Enter): ")
            if text:
                _set_phone_clipboard(device_id, text)
                log_ok(f"Teks dikirim ke HP!" if lang=="id" else f"Text sent to phone!")
        input(f"\n  {'Tekan Enter untuk lanjut...' if lang=='id' else 'Press Enter to continue...'}")


# ═══════════════════════════════════════════════════════════
#   FILE TRANSFER
# ═══════════════════════════════════════════════════════════

def _fmt_size(b):
    for unit in ["B","KB","MB","GB"]:
        if b < 1024: return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} GB"


def _adb_transfer_progress(cmd_args, label):
    """Run an adb push/pull and show live progress from its output."""
    try:
        proc = subprocess.Popen(
            cmd_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace"
        )
        for line in proc.stdout:
            line = line.strip()
            # adb push/pull output: "path: X%"
            m = re.search(r'(\d+)%', line)
            if m:
                pct = int(m.group(1))
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                print(f"\r  {Fore.CYAN}[{bar}] {Fore.WHITE}{pct:3d}%  {label[:30]}", end="", flush=True)
            elif line and not line.startswith("["):
                print(f"\r  {Fore.WHITE}{line:<60}", end="", flush=True)
        proc.wait()
        print()
        return proc.returncode == 0
    except Exception as e:
        print()
        log_err(str(e))
        return False


def _adb_list_files(device_id, path="/sdcard/"):
    try:
        r = subprocess.run(
            [ADB_EXE, "-s", device_id, "shell", "ls", "-lh", path],
            capture_output=True, text=True, timeout=8
        )
        return r.stdout.strip()
    except Exception:
        return ""


def file_transfer_menu(device_info, lang="en"):
    device_id = device_info.get("id", "")
    download_dir = os.path.join(os.path.expanduser("~"), "Downloads")

    while True:
        print_banner(lang)
        print(f"\n{Fore.GREEN}  ╔══════════════════════════════════════════════════════════╗")
        if lang == "id":
            print(f"{Fore.GREEN}  ║  📁 PANEL TRANSFER FILE                                     ║")
            print(f"{Fore.GREEN}  ╠══════════════════════════════════════════════════════════╣")
            print(f"{Fore.GREEN}  ║  {Fore.YELLOW}[1]{Fore.WHITE} Kirim ke HP   Laptop → HP (/sdcard/Download/)          {Fore.GREEN}║")
            print(f"{Fore.GREEN}  ║  {Fore.YELLOW}[2]{Fore.WHITE} Ambil dari HP HP → Laptop (folder Downloads)           {Fore.GREEN}║")
            print(f"{Fore.GREEN}  ║  {Fore.YELLOW}[3]{Fore.WHITE} Lihat file HP  Tampilkan isi /sdcard/                   {Fore.GREEN}║")
            print(f"{Fore.GREEN}  ║  {Fore.RED}[0]{Fore.WHITE} Kembali                                              {Fore.GREEN}║")
        else:
            print(f"{Fore.GREEN}  ║  📁 FILE TRANSFER PANEL                                      ║")
            print(f"{Fore.GREEN}  ╠══════════════════════════════════════════════════════════╣")
            print(f"{Fore.GREEN}  ║  {Fore.YELLOW}[1]{Fore.WHITE} Send to Phone  Laptop → Phone (/sdcard/Download/)      {Fore.GREEN}║")
            print(f"{Fore.GREEN}  ║  {Fore.YELLOW}[2]{Fore.WHITE} Get from Phone Phone → Laptop (Downloads folder)       {Fore.GREEN}║")
            print(f"{Fore.GREEN}  ║  {Fore.YELLOW}[3]{Fore.WHITE} Browse Phone   List files on /sdcard/                   {Fore.GREEN}║")
            print(f"{Fore.GREEN}  ║  {Fore.RED}[0]{Fore.WHITE} Back                                                 {Fore.GREEN}║")
        print(f"{Fore.GREEN}  ╚══════════════════════════════════════════════════════════╝")

        ch = get_input("  Choice [0-3]: ", ["0","1","2","3"])
        if ch == "0":
            break
        elif ch == "1":  # Laptop → Phone
            local = get_input("  Path file di laptop: " if lang=="id" else "  Local file path: ")
            if not local or not os.path.exists(local):
                log_err("File tidak ditemukan!" if lang=="id" else "File not found!")
            else:
                fname = os.path.basename(local)
                remote = f"/sdcard/Download/{fname}"
                sz = _fmt_size(os.path.getsize(local))
                log_info(f"Mengirim {fname} ({sz}) → {remote}..." if lang=="id" else f"Sending {fname} ({sz}) → {remote}...")
                ok = _adb_transfer_progress([ADB_EXE, "-s", device_id, "push", local, remote], fname)
                if ok: log_ok("Transfer berhasil!" if lang=="id" else "Transfer successful!")
                else:  log_err("Transfer gagal!" if lang=="id" else "Transfer failed!")
        elif ch == "2":  # Phone → Laptop
            remote = get_input("  Path file di HP (misal /sdcard/DCIM/foto.jpg): " if lang=="id" else "  Phone file path (e.g. /sdcard/DCIM/photo.jpg): ")
            if not remote:
                continue
            fname   = os.path.basename(remote)
            os.makedirs(download_dir, exist_ok=True)
            local   = os.path.join(download_dir, fname)
            log_info(f"Mengambil {fname} → {local}..." if lang=="id" else f"Pulling {fname} → {local}...")
            ok = _adb_transfer_progress([ADB_EXE, "-s", device_id, "pull", remote, local], fname)
            if ok: log_ok(f"Disimpan di: {local}" if lang=="id" else f"Saved to: {local}")
            else:  log_err("Transfer gagal! Periksa path file." if lang=="id" else "Transfer failed! Check file path.")
        elif ch == "3":  # Browse phone
            path = get_input("  Path folder (default /sdcard/): ", default="/sdcard/")
            print(f"\n{Fore.CYAN}  {'Isi' if lang=='id' else 'Contents'}: {path}\n")
            listing = _adb_list_files(device_id, path)
            for line in listing.splitlines()[:30]:
                print(f"  {Fore.WHITE}{line}")
        input(f"\n  {'Tekan Enter untuk lanjut...' if lang=='id' else 'Press Enter to continue...'}")


# ═══════════════════════════════════════════════════════════
#   WIFI PAIRING DISPLAY
# ═══════════════════════════════════════════════════════════

def show_wifi_pairing_info(lang="en"):
    """Display WiFi Pairing info visually to guide users without typing."""
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "?"

    print_banner(lang)
    print(f"\n{Fore.CYAN}  ╔══════════════════════════════════════════════════════════╗")
    if lang == "id":
        print(f"{Fore.CYAN}  ║  🌐 PANDUAN WIRELESS DEBUGGING (Android 11+)               ║")
        print(f"{Fore.CYAN}  ╠══════════════════════════════════════════════════════════╣")
        print(f"{Fore.CYAN}  ║                                                          ║")
        print(f"{Fore.CYAN}  ║  Langkah-langkah di HP:                                 ║")
        print(f"{Fore.CYAN}  ║  {Fore.YELLOW}1.{Fore.WHITE} Buka Pengaturan → Opsi Pengembang                   {Fore.CYAN}║")
        print(f"{Fore.CYAN}  ║  {Fore.YELLOW}2.{Fore.WHITE} Aktifkan: ‘Wireless Debugging’                       {Fore.CYAN}║")
        print(f"{Fore.CYAN}  ║  {Fore.YELLOW}3.{Fore.WHITE} Ketuk: ‘Pasangkan perangkat dengan kode pairing’    {Fore.CYAN}║")
        print(f"{Fore.CYAN}  ║  {Fore.YELLOW}4.{Fore.WHITE} Catat IP:PORT dan kode 6 digit yang muncul         {Fore.CYAN}║")
        print(f"{Fore.CYAN}  ║  {Fore.YELLOW}5.{Fore.WHITE} Masukkan di bawah ini ↓                            {Fore.CYAN}║")
    else:
        print(f"{Fore.CYAN}  ║  🌐 WIRELESS DEBUGGING GUIDE (Android 11+)                  ║")
        print(f"{Fore.CYAN}  ╠══════════════════════════════════════════════════════════╣")
        print(f"{Fore.CYAN}  ║                                                          ║")
        print(f"{Fore.CYAN}  ║  Steps on your phone:                                   ║")
        print(f"{Fore.CYAN}  ║  {Fore.YELLOW}1.{Fore.WHITE} Go to Settings → Developer Options                  {Fore.CYAN}║")
        print(f"{Fore.CYAN}  ║  {Fore.YELLOW}2.{Fore.WHITE} Enable: ‘Wireless debugging’                         {Fore.CYAN}║")
        print(f"{Fore.CYAN}  ║  {Fore.YELLOW}3.{Fore.WHITE} Tap: ‘Pair device with pairing code’                {Fore.CYAN}║")
        print(f"{Fore.CYAN}  ║  {Fore.YELLOW}4.{Fore.WHITE} Note the IP:PORT and 6-digit code shown             {Fore.CYAN}║")
        print(f"{Fore.CYAN}  ║  {Fore.YELLOW}5.{Fore.WHITE} Enter them below ↓                                 {Fore.CYAN}║")
    print(f"{Fore.CYAN}  ║                                                          ║")
    print(f"{Fore.CYAN}  ║  {Fore.GREEN}Laptop IP : {Fore.YELLOW}{local_ip:<44}{Fore.CYAN}║")
    print(f"{Fore.CYAN}  ║  {Fore.WHITE}(Pastikan HP dan Laptop 1 jaringan WiFi / Same network)  ║")
    print(f"{Fore.CYAN}  ╚══════════════════════════════════════════════════════════╝\n")


# ═══════════════════════════════════════════════════════════
#   INPUT MACRO
# ═══════════════════════════════════════════════════════════

_MACRO_BUILTINS = {
    "Screenshot"      : [("keyevent", "120")],
    "Home"            : [("keyevent", "3")],
    "Back"            : [("keyevent", "4")],
    "Recent Apps"     : [("keyevent", "187")],
    "Volume Up"       : [("keyevent", "24")],
    "Volume Down"     : [("keyevent", "25")],
    "Screen On/Off"   : [("keyevent", "26")],
    "Media Play/Pause": [("keyevent", "85")],
    "Swipe Up"        : [("swipe",  "540 1600 540 400 300")],
    "Swipe Down"      : [("swipe",  "540 400 540 1600 300")],
    "Swipe Right"     : [("swipe",  "200 900 900 900 300")],
    "Swipe Left"      : [("swipe",  "900 900 200 900 300")],
}


def _run_macro_action(device_id, action_type, action_val):
    """Execute a single adb input action."""
    try:
        if action_type == "keyevent":
            subprocess.run([ADB_EXE, "-s", device_id, "shell", "input", "keyevent", action_val],
                           capture_output=True, timeout=5)
        elif action_type == "swipe":
            parts = action_val.split()
            subprocess.run([ADB_EXE, "-s", device_id, "shell", "input", "swipe"] + parts,
                           capture_output=True, timeout=5)
        elif action_type == "tap":
            x, y = action_val.split()
            subprocess.run([ADB_EXE, "-s", device_id, "shell", "input", "tap", x, y],
                           capture_output=True, timeout=5)
        elif action_type == "text":
            subprocess.run([ADB_EXE, "-s", device_id, "shell", "input", "text", action_val],
                           capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def input_macro_menu(device_info, lang="en"):
    device_id = device_info.get("id", "")
    custom_macros = {}  # name → list of (type, val)

    while True:
        print_banner(lang)
        print(f"\n{Fore.MAGENTA}  ╔══════════════════════════════════════════════════════════╗")
        print(f"{Fore.MAGENTA}  ║  🎮 INPUT MACRO / BUTTON MAPPER                              ║")
        print(f"{Fore.MAGENTA}  ╠══════════════════════════════════════════════════════════╣")

        all_macros = list(_MACRO_BUILTINS.keys()) + list(custom_macros.keys())
        for i, name in enumerate(all_macros, 1):
            tag = "(built-in)" if name in _MACRO_BUILTINS else "(custom)"
            pad = " " * max(0, 42 - len(name) - len(tag))
            print(f"{Fore.MAGENTA}  ║  {Fore.YELLOW}[{i:2}]{Fore.WHITE} {name} {Fore.CYAN}{tag}{pad}{Fore.MAGENTA}║")

        print(f"{Fore.MAGENTA}  ╠══════════════════════════════════════════════════════════╣")
        print(f"{Fore.MAGENTA}  ║  {Fore.YELLOW}[T]{Fore.WHITE} Kirim teks ke HP {'/ Send text to phone':<36}{Fore.MAGENTA}║")
        print(f"{Fore.MAGENTA}  ║  {Fore.YELLOW}[X]{Fore.WHITE} Tap koordinat (X Y) {'/ Tap at coordinate':<33}{Fore.MAGENTA}║")
        print(f"{Fore.MAGENTA}  ║  {Fore.YELLOW}[C]{Fore.WHITE} Buat macro custom {'/ Create custom macro':<34}{Fore.MAGENTA}║")
        print(f"{Fore.MAGENTA}  ║  {Fore.RED}[0]{Fore.WHITE} {'Kembali / Back':<52}{Fore.MAGENTA}║")
        print(f"{Fore.MAGENTA}  ╚══════════════════════════════════════════════════════════╝")

        valid = ["0", "t", "x", "c"] + [str(i) for i in range(1, len(all_macros)+1)]
        ch = get_input("  Choice: ", valid)

        if ch == "0":
            break
        elif ch == "t":
            text = get_input("  Masukkan teks: " if lang=="id" else "  Enter text: ")
            if text:
                _run_macro_action(device_id, "text", text)
                log_ok(f"Teks dikirim!" if lang=="id" else f"Text sent!")
        elif ch == "x":
            coords = get_input("  Masukkan X Y (misal: 540 960): " if lang=="id" else "  Enter X Y (e.g. 540 960): ")
            if coords:
                _run_macro_action(device_id, "tap", coords)
                log_ok(f"Tap dikirim ke {coords}!" if lang=="id" else f"Tapped at {coords}!")
        elif ch == "c":
            mname = get_input("  Nama macro: " if lang=="id" else "  Macro name: ")
            if not mname: continue
            actions = []
            log_info("Tambahkan aksi (ketik 'done' untuk selesai):" if lang=="id" else "Add actions (type 'done' to finish):")
            log_info("Format: keyevent <code> | swipe <x1 y1 x2 y2 dur> | tap <x y> | text <str> | delay <ms>")
            while True:
                line = get_input("  > ")
                if line.lower() == "done": break
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    actions.append((parts[0], parts[1]))
            if actions:
                custom_macros[mname] = actions
                log_ok(f"Macro '{mname}' disimpan!" if lang=="id" else f"Macro '{mname}' saved!")
        else:
            idx = int(ch) - 1
            name = all_macros[idx]
            actions = _MACRO_BUILTINS.get(name) or custom_macros.get(name, [])
            log_info(f"Menjalankan macro: {name}..." if lang=="id" else f"Running macro: {name}...")
            for act_type, act_val in actions:
                if act_type == "delay":
                    time.sleep(int(act_val) / 1000)
                else:
                    _run_macro_action(device_id, act_type, act_val)
                    time.sleep(0.1)
            log_ok(f"Macro '{name}' selesai!" if lang=="id" else f"Macro '{name}' done!")
        input(f"  {'Tekan Enter...' if lang=='id' else 'Press Enter...'}")


# ═══════════════════════════════════════════════════════════
#   LAUNCH
# ═══════════════════════════════════════════════════════════

def _live_stats_thread(device_id, start_time, stop_event, lang):
    """Background thread that prints live session stats periodically."""
    try:
        while not stop_event.is_set():
            elapsed = time.time() - start_time
            m, s = int(elapsed // 60), int(elapsed % 60)

            # Get battery
            battery = "?"
            try:
                r = subprocess.run([ADB_EXE, "-s", device_id, "shell",
                                    "dumpsys", "battery"],
                                   capture_output=True, text=True, timeout=3)
                for line in r.stdout.splitlines():
                    if "level:" in line:
                        battery = line.split(":")[-1].strip() + "%"
                        break
            except Exception:
                pass

            label = f"  \u001b[36m[\u001b[33m\u26a1 {battery}\u001b[36m] [\u001b[32m\u23f1 {m:02d}m{s:02d}s\u001b[36m] [\u001b[37mCtrl+C to stop\u001b[36m]"
            print(f"\r{label}          ", end="", flush=True)
            for _ in range(50):  # sleep 5s in 0.1s intervals checking stop_event
                if stop_event.is_set():
                    break
                time.sleep(0.1)
    except Exception:
        pass
    finally:
        print()  # newline after stats


def launch_scrcpy(config, device_info, lang="id", max_retries=3, multi=False):
    log_info("Menyiapkan scrcpy..." if lang == "id" else "Preparing scrcpy...")
    args = [SCRCPY_EXE]

    mode = config.get("mode", "usb")
    if mode == "usb" and device_info and "id" in device_info:
        args.extend(["-s", device_info["id"]])
    elif mode in ["wifi", "wd"]:
        args.extend(["-s", f"{config['ip']}:{config['port']}"])

    args += [
        f"--video-codec={config.get('codec','h264')}",
        f"--video-bit-rate={config.get('bitrate','8M')}",
        f"--max-fps={config.get('fps','60')}",
    ]
    if config.get("resolution","0") != "0":
        args.append(f"--max-size={config.get('resolution')}")

    if config.get("mirror_cam") == "y":
        args.append("--video-source=camera")
        if config.get("camera_facing"):
            args.append(f"--camera-facing={config['camera_facing']}")

    if config.get("crop"):
        args.append(f"--crop={config['crop']}")

    if config.get("enable_otg") == "y":
        args.append("--otg")
    else:
        if config.get("virtual_display") == "y": args.append("--new-display")

        wo = config.get("window_opt","1")
        if wo in ["2","4"] or config.get("window_pip") == "y": args.append("--always-on-top")
        if wo in ["3","4"] or config.get("window_pip") == "y": args.append("--window-borderless")
        if wo == "5": args.append("--fullscreen")

        win_x = config.get("win_x", "")
        win_y = config.get("win_y", "")
        if win_x and win_x.lstrip("-").isdigit(): args.append(f"--window-x={win_x}")
        if win_y and win_y.lstrip("-").isdigit(): args.append(f"--window-y={win_y}")

        if config.get("advanced_kb")    == "y": args.append("--keyboard=uhid")
        if config.get("stay_awake")     == "y": args.append("--stay-awake")
        if config.get("turn_screen_off")== "y": args.append("--turn-screen-off")
        if config.get("no_control")     == "y": args.append("--no-control")
        if config.get("auto_lock")      == "y": args.append("--power-off-on-close")

    if config.get("gamepad") == "y": args.append("--gamepad=uhid")

    if config.get("record_filename"):
        args.append(f"--record={config['record_filename']}")

    sdk = device_info.get("sdk", 30) if device_info else 30
    if config.get("enable_otg") != "y":
        if sdk < 30 or config.get("audio_mode") == "3":
            log_warn("Audio forwarding tidak didukung atau dinonaktifkan — menonaktifkan audio.")
            args.append("--no-audio")
        else:
            am = config.get("audio_mode","1")
            if am == "2": args.append("--audio-dup")
            elif am == "4": args.append("--audio-source=mic")
            args.append("--audio-codec=aac")
            log_info("Audio forwarding aktif (native scrcpy).")

    log_ok("Jendela mirror akan muncul sebentar lagi..." if lang == "id" else "Mirror window appearing shortly...")
    log_note(f"CMD: {' '.join(args)}")
    print()

    device_id = device_info.get("id", "") if device_info else ""
    attempt   = 0
    start     = time.time()

    if multi:
        try:
            return subprocess.Popen(args)
        except Exception as e:
            log_err(f"Failed to launch scrcpy: {e}")
            return None

    while True:
        attempt += 1
        # ── Live stats thread ──
        stop_stats = threading.Event()
        stats_t = threading.Thread(
            target=_live_stats_thread,
            args=(device_id, start, stop_stats, lang),
            daemon=True
        )
        stats_t.start()

        try:
            p = subprocess.Popen(args)
            if os.name == "nt" and config.get("shortcut_mod") == "y":
                import msvcrt
                while p.poll() is None:
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key.lower() == b's':
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            fn = f"screenshot_{ts}.png"
                            print(f"\n{Fore.CYAN}  📸 Mengambil screenshot ke {fn}..." if lang == "id" else f"\n{Fore.CYAN}  📸 Taking screenshot to {fn}...")
                            cmd = [ADB_EXE]
                            if device_id: cmd.extend(["-s", device_id])
                            cmd.extend(["exec-out", "screencap", "-p"])
                            with open(fn, "wb") as f:
                                subprocess.run(cmd, stdout=f)
                            print(f"  {Fore.GREEN}Berhasil disimpan!\n")
                    time.sleep(0.05)
            else:
                p.wait()
            ret = p.returncode
        except KeyboardInterrupt:
            ret = 0  # user manually stopped, no reconnect
            try:
                p.terminate()
            except:
                pass
        finally:
            stop_stats.set()
            stats_t.join()

        dur = time.time() - start
        m, s = int(dur // 60), int(dur % 60)

        if ret == 0:
            # Clean exit — no reconnect
            break

        # ── Auto-Reconnect ──
        if mode in ["wifi", "wd"] and attempt < max_retries:
            print(f"\n{Fore.YELLOW}  [!]  Koneksi terputus (exit code {ret}). Mencoba reconnect..." if lang == "id"
                  else f"\n{Fore.YELLOW}  [!]  Connection lost (exit code {ret}). Attempting reconnect...")
            for countdown in range(5, 0, -1):
                print(f"\r  {Fore.CYAN}Reconnect dalam {countdown}s...  ", end="", flush=True)
                time.sleep(1)
            print()
            # Try adb reconnect
            subprocess.run([ADB_EXE, "connect", f"{config.get('ip')}:{config.get('port')}"],
                           capture_output=True, timeout=8)
            time.sleep(2)
            log_info(f"Percobaan ke-{attempt+1}/{max_retries}..." if lang == "id"
                     else f"Attempt {attempt+1}/{max_retries}...")
            continue
        break

    _log_session(config, device_info, dur)
    print(f"\n{Fore.CYAN}  Sesi berakhir. Durasi: {m}m {s}s" if lang == "id"
          else f"\n{Fore.CYAN}  Session ended. Duration: {m}m {s}s")
    input("  Tekan Enter untuk kembali ke menu..." if lang == "id" else "  Press Enter to return to menu...")


# ═══════════════════════════════════════════════════════════
#   CONNECTION MODES
# ═══════════════════════════════════════════════════════════

def connect_usb(lang):
    print_banner(lang)
    devices = check_device(lang, allow_multi=True)
    if not devices: return

    is_multi = isinstance(devices, list)
    if not is_multi:
        devices = [devices]

    conf = select_or_configure(lang, devices[0])
    
    if is_multi:
        conf["record_filename"] = "" # Disable recording for multi
        log_note("Fitur recording dinonaktifkan dalam mode Multi-Device." if lang == "id" else "Recording disabled in Multi-Device mode.")
        if get_input("  Lanjutkan? [y/n]: " if lang == "id" else "  Continue? [y/n]: ", ["y","n"], "y") != "y": return
    else:
        if show_config_summary(conf, devices[0], lang) != "y": return

    conf["mode"] = "usb"
    
    if is_multi:
        processes = []
        for d in devices:
            p = launch_scrcpy(conf, d, lang, multi=True)
            if p: processes.append(p)
        print(f"\n{Fore.CYAN}  Multi-Mirror berjalan. Tekan Enter untuk menghentikan semua sesi." if lang=="id" else f"\n{Fore.CYAN}  Multi-Mirror running. Press Enter to stop all sessions.")
        input()
        for p in processes:
            try: p.terminate()
            except: pass
    else:
        launch_scrcpy(conf, devices[0], lang)


def _scan_mdns(service_type, lang="en"):
    print(f"  {Fore.CYAN}Memindai jaringan (mDNS)..." if lang == "id" else f"  {Fore.CYAN}Scanning network (mDNS)...")
    try:
        subprocess.run([ADB_EXE, "start-server"], capture_output=True)
        time.sleep(1)
        res = subprocess.run([ADB_EXE, "mdns", "services"], capture_output=True, text=True, timeout=5)
        lines = res.stdout.strip().splitlines()
        devices = []
        for line in lines:
            if service_type in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    devices.append(parts[0])
        return devices
    except Exception:
        return []

def auto_connect_wifi(lang):
    print_banner(lang)
    presets = _load_presets()
    last_ip = presets.get("last_wifi_ip")
    last_port = presets.get("last_wifi_port", "5555")

    if not last_ip:
        log_err("Belum ada riwayat koneksi WiFi." if lang=="id" else "No WiFi connection history found.")
        input("  Enter...")
        return

    log_info(f"Mencoba koneksi otomatis ke {last_ip}:{last_port}..." if lang=="id" else f"Auto-connecting to {last_ip}:{last_port}...")
    res = subprocess.run([ADB_EXE, "connect", f"{last_ip}:{last_port}"], capture_output=True, text=True)
    if "connected to" in res.stdout.lower() or "already connected" in res.stdout.lower():
        log_ok("Berhasil terhubung!" if lang=="id" else "Connected successfully!")
    else:
        log_err(f"Gagal: {res.stdout.strip()}")
        input("  Enter...")
        return
        
    # Check device to populate device info
    device_info = check_device(lang, allow_multi=False)
    if not device_info: return
    
    conf = select_or_configure(lang, device_info)
    if show_config_summary(conf, device_info, lang) != "y": return
    conf.update({"mode":"wifi","ip":last_ip,"port":last_port})
    launch_scrcpy(conf, device_info)


def connect_wifi(lang):
    print_banner(lang)
    log_info("Pastikan kabel USB terhubung untuk setup awal!" if lang=="id" else "Make sure USB cable is connected for initial setup!")
    device_info = check_device(lang)
    if not device_info: return

    presets = _load_presets()
    last_ip = presets.get("last_wifi_ip")
    last_port = presets.get("last_wifi_port", "5555")
    
    ip, port = "", ""
    if last_ip:
        use_last = get_input(f"  Gunakan IP sebelumnya ({last_ip}:{last_port})? [y/n]: " if lang=="id" else f"  Use previous IP ({last_ip}:{last_port})? [y/n]: ", ["y","n"], "y")
        if use_last == "y":
            ip, port = last_ip, last_port
            
    if not ip:
        port = get_input("  Port TCP (default 5555): ", default="5555")
        subprocess.run([ADB_EXE, "-s", device_info["id"], "tcpip", port])
        time.sleep(2)
        ip = get_input("  Masukkan IP HP Android: " if lang=="id" else "  Enter Android phone IP address: ")
        if not ip: return

    log_warn("Cabut kabel USB sekarang!" if lang=="id" else "Unplug the USB cable now!")
    input("  Tekan Enter saat siap..." if lang=="id" else "  Press Enter when ready...")

    log_info(f"Menghubungkan ke {ip}:{port}..." if lang=="id" else f"Connecting to {ip}:{port}...")
    subprocess.run([ADB_EXE, "connect", f"{ip}:{port}"])
    time.sleep(2)
    
    presets["last_wifi_ip"] = ip
    presets["last_wifi_port"] = port
    _save_presets(presets)

    conf = select_or_configure(lang, device_info)
    if show_config_summary(conf, device_info, lang) != "y": return
    conf.update({"mode":"wifi","ip":ip,"port":port})
    launch_scrcpy(conf, device_info)


def connect_wd(lang):
    print_banner(lang)
    log_info("Android 11+ diperlukan untuk Wireless Debugging!" if lang=="id" else "Android 11+ Required for Wireless Debugging!")

    do_pair = get_input("  Pertama kali pairing? [y/n] (default: y): " if lang=="id" else "  First time pairing? [y/n] (default: y): ", ["y","n"], "y")
    if do_pair == "y":
        pair_addr = ""
        devices = _scan_mdns("_adb-tls-pairing", lang)
        if devices:
            print(f"\n  {Fore.CYAN}Perangkat Ditemukan (Pairing):")
            for i, d in enumerate(devices, 1):
                print(f"    {Fore.YELLOW}[{i}] {Fore.WHITE}{d}")
            print(f"    {Fore.YELLOW}[0] {Fore.WHITE}Input Manual")
            ch = get_input(f"  Pilih [0-{len(devices)}]: ", [str(x) for x in range(len(devices)+1)])
            if ch != "0":
                pair_addr = devices[int(ch)-1]
        
        if not pair_addr:
            pair_addr = get_input("  Masukkan IP:PORT pairing: " if lang=="id" else "  Enter pairing IP:PORT (e.g. 192.168.1.5:43521): ")
        pair_code = get_input("  Masukkan kode 6 digit dari HP: " if lang=="id" else "  Enter 6-digit code from phone: ")
        if not pair_addr or not pair_code: return
        subprocess.run([ADB_EXE, "start-server"], stdout=subprocess.DEVNULL)
        time.sleep(2)
        res = subprocess.run([ADB_EXE, "pair", pair_addr, pair_code])
        if res.returncode != 0:
            log_err("Pairing gagal! Periksa kode dan alamat." if lang=="id" else "Pairing failed! Check code and address.")
            input("  Enter...")
            return
        log_ok("Pairing berhasil!" if lang=="id" else "Pairing successful!")

    ip, port = "", ""
    devices = _scan_mdns("_adb-tls-connect", lang)
    if devices:
        print(f"\n  {Fore.CYAN}Perangkat Ditemukan (Connect):")
        for i, d in enumerate(devices, 1):
            print(f"    {Fore.YELLOW}[{i}] {Fore.WHITE}{d}")
        print(f"    {Fore.YELLOW}[0] {Fore.WHITE}Input Manual")
        ch = get_input(f"  Pilih [0-{len(devices)}]: ", [str(x) for x in range(len(devices)+1)])
        if ch != "0":
            addr = devices[int(ch)-1]
            if ":" in addr:
                ip, port = addr.split(":", 1)
                
    if not ip or not port:
        ip   = get_input("  Masukkan IP HP: " if lang=="id" else "  Enter phone IP: ")
        port = get_input("  Masukkan Port (dari Wireless Debugging): " if lang=="id" else "  Enter Port (from Wireless Debugging): ")
        
    if not ip or not port: return

    log_info(f"Menghubungkan ke {ip}:{port}...")
    res = subprocess.run([ADB_EXE, "connect", f"{ip}:{port}"])
    time.sleep(2)
    if res.returncode != 0:
        log_err("Koneksi WD gagal!" if lang=="id" else "WD connection failed!")
        input("  Enter...")
        return

    device_info = check_device(lang)
    if not device_info: return

    conf = select_or_configure(lang, device_info)
    if show_config_summary(conf, device_info, lang) != "y": return
    conf.update({"mode":"wd","ip":ip,"port":port})
    launch_scrcpy(conf, device_info)


def install_apk(lang):
    print_banner(lang)
    devices = check_device(lang, allow_multi=True)
    if not devices: return

    is_multi = isinstance(devices, list)
    if not is_multi: devices = [devices]

    apk_path = get_input("  Drag & Drop file APK ke sini: " if lang=="id" else "  Drag & Drop APK file here: ")
    apk_path = apk_path.strip().strip("'").strip('"')
    if not os.path.isfile(apk_path):
        log_err("File tidak ditemukan!" if lang=="id" else "File not found!")
        input("  Enter...")
        return
    
    for d in devices:
        log_info(f"Menginstall ke {d['id']}..." if lang=="id" else f"Installing to {d['id']}...")
        subprocess.run([ADB_EXE, "-s", d["id"], "install", apk_path])
    
    log_ok("Selesai!" if lang=="id" else "Done!")
    input("  Enter...")

def push_file(lang):
    print_banner(lang)
    devices = check_device(lang, allow_multi=True)
    if not devices: return

    is_multi = isinstance(devices, list)
    if not is_multi: devices = [devices]

    file_path = get_input("  Drag & Drop file/folder ke sini: " if lang=="id" else "  Drag & Drop file/folder here: ")
    file_path = file_path.strip().strip("'").strip('"')
    if not os.path.exists(file_path):
        log_err("File/Folder tidak ditemukan!" if lang=="id" else "File/Folder not found!")
        input("  Enter...")
        return
    
    target_dir = "/storage/emulated/0/screenmirror/"
    for d in devices:
        log_info(f"Mengirim ke {d['id']}..." if lang=="id" else f"Pushing to {d['id']}...")
        subprocess.run([ADB_EXE, "-s", d["id"], "shell", "mkdir", "-p", target_dir])
        subprocess.run([ADB_EXE, "-s", d["id"], "push", file_path, target_dir])
        
    log_ok("Selesai!" if lang=="id" else "Done!")
    input("  Enter...")

def start_wireless_mic(lang):
    print_banner(lang)
    devices = check_device(lang, allow_multi=True)
    if not devices: return

    is_multi = isinstance(devices, list)
    if not is_multi: devices = [devices]

    log_info("Memulai Wireless Mic mode (tanpa video)..." if lang=="id" else "Starting Wireless Mic mode (no video)...")
    processes = []
    for d in devices:
        args = [SCRCPY_EXE, "-s", d["id"], "--no-video", "--audio-source=mic", "--audio-codec=opus"]
        try:
            p = subprocess.Popen(args)
            processes.append(p)
        except Exception as e:
            log_err(f"Gagal / Failed: {e}")
            
    print(f"\n{Fore.CYAN}  Mic berjalan. Tekan Enter untuk menghentikan." if lang=="id" else f"\n{Fore.CYAN}  Mic running. Press Enter to stop.")
    input()
    for p in processes:
        try: p.terminate()
        except: pass

def start_otg_mode(lang):
    print_banner(lang)
    devices = check_device(lang, allow_multi=True)
    if not devices: return

    is_multi = isinstance(devices, list)
    if not is_multi: devices = [devices]

    log_info("Memulai Mode OTG (Keyboard/Mouse fisik)..." if lang=="id" else "Starting OTG Mode (physical Keyboard/Mouse)...")
    processes = []
    for d in devices:
        args = [SCRCPY_EXE, "-s", d["id"], "--otg"]
        try:
            p = subprocess.Popen(args)
            processes.append(p)
        except Exception as e:
            log_err(f"Gagal / Failed: {e}")
            
    print(f"\n{Fore.CYAN}  Mode OTG berjalan (layar mati). Tekan Enter untuk menghentikan." if lang=="id" else f"\n{Fore.CYAN}  OTG Mode running (screen off). Press Enter to stop.")
    input()
    for p in processes:
        try: p.terminate()
        except: pass

def start_spy_cam(lang):
    print_banner(lang)
    device = check_device(lang, allow_multi=False)
    if not device: return

    default_name = f"spycam_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
    if lang == "id":
        print(f"{Fore.CYAN}  Catatan: Jendela kamera tidak akan muncul. Perekaman berjalan diam-diam.")
        record_filename = get_input(f"  Nama file (Enter untuk '{default_name}'): ", default=default_name)
        log_info("Memulai perekaman Spy Cam...")
    else:
        print(f"{Fore.CYAN}  Note: Camera window will not appear. Recording runs secretly.")
        record_filename = get_input(f"  File name (Enter for '{default_name}'): ", default=default_name)
        log_info("Starting Spy Cam recording...")

    args = [SCRCPY_EXE, "-s", device["id"], "--video-source=camera", "--camera-facing=back", "--no-window", f"--record={record_filename}"]
    try:
        p = subprocess.Popen(args)
        print(f"\n{Fore.CYAN}  \U0001f534 Merekam ke {record_filename}... Tekan Enter untuk BERHENTI merekam." if lang=="id" else f"\n{Fore.CYAN}  \U0001f534 Recording to {record_filename}... Press Enter to STOP recording.")
        input()
        p.terminate()
        p.wait()
        log_ok(f"Video tersimpan di: {record_filename}" if lang=="id" else f"Video saved to: {record_filename}")
    except Exception as e:
        log_err(f"Gagal / Failed: {e}")



# ═══════════════════════════════════════════════════════════
#   MAIN
# ═══════════════════════════════════════════════════════════

def main():
    set_console_icon()
    if not find_executables():
        print_banner()
        log_err("scrcpy tidak ditemukan! Pastikan sudah terinstall.")
        print()
        print(f"  {Fore.CYAN}Cara mendapatkan scrcpy:")
        print("    1. Download dari: https://github.com/Genymobile/scrcpy/releases")
        print("    2. Ekstrak ke C:\\scrcpy\\")
        print("    3. Tambahkan ke PATH, atau letakkan di folder yang sama dengan script ini.\n")
        ans = get_input("  Download scrcpy otomatis sekarang? [y/n] (default: n): ", ["y","n"], "n")
        if ans == "y":
            try:
                tag, assets = _github_latest("Genymobile/scrcpy")
                download_scrcpy(tag, assets, "id")
                if not find_executables():
                    log_err("scrcpy masih tidak ditemukan setelah download.")
                    input("  Enter untuk keluar...")
                    return
            except Exception as e:
                log_err(f"Gagal mengunduh: {e}")
                input("  Enter untuk keluar...")
                return
        else:
            input("  Tekan Enter untuk keluar...")
            return

    lang = "en"

    while True:
        print_banner(lang)
        print(f"  {Fore.CYAN}Pilih Bahasa / Choose Language:\n")
        print(f"    {Fore.YELLOW}[1] {Fore.WHITE}Indonesia  (Bahasa Indonesia)")
        print(f"    {Fore.YELLOW}[2] {Fore.WHITE}English    (English)")
        print(f"    {Fore.RED}[0] {Fore.WHITE}Exit / Keluar\n")
        lc = get_input("  Choice [1-2, 0]: ", ["0","1","2"])
        if lc == "0":
            print(f"\n{Fore.CYAN}  Terima kasih telah menggunakan ScreenMirror! 👋\n")
            break
        lang = "id" if lc == "1" else "en"

        check_updates(lang)

        while True:
            print_banner(lang)
            if lang == "id":
                print(f"  {Fore.CYAN}Menu Utama:\n")
                print(f"    {Fore.YELLOW}[1] {Fore.WHITE}Koneksi USB             {Fore.CYAN}│ {Fore.WHITE}Mirror via kabel USB")
                print(f"    {Fore.YELLOW}[2] {Fore.WHITE}Koneksi WiFi            {Fore.CYAN}│ {Fore.WHITE}Mirror via jaringan WiFi")
                print(f"    {Fore.YELLOW}[3] {Fore.WHITE}Auto-Connect WiFi       {Fore.CYAN}│ {Fore.WHITE}Konek 1-tombol ke IP terakhir")
                print(f"    {Fore.YELLOW}[4] {Fore.WHITE}Wireless Debugging      {Fore.CYAN}│ {Fore.WHITE}Mirror via Android 11+ Wireless Debug")
                print(f"    {Fore.YELLOW}[5] {Fore.WHITE}Riwayat Sesi            {Fore.CYAN}│ {Fore.WHITE}Lihat log sesi mirroring sebelumnya")
                print(f"    {Fore.YELLOW}[6] {Fore.WHITE}Install APK (Sideload)  {Fore.CYAN}│ {Fore.WHITE}Drag & drop file APK ke HP")
                print(f"    {Fore.YELLOW}[7] {Fore.WHITE}Kirim File (Push)       {Fore.CYAN}│ {Fore.WHITE}Transfer file ke HP")
                print(f"    {Fore.YELLOW}[8] {Fore.WHITE}Wireless Mic Mode       {Fore.CYAN}│ {Fore.WHITE}Gunakan HP sebagai mic PC")
                print(f"    {Fore.YELLOW}[9] {Fore.WHITE}Mode OTG                {Fore.CYAN}│ {Fore.WHITE}Keyboard/Mouse fisik tanpa layar")
                print(f"    {Fore.YELLOW}[10]{Fore.WHITE} Mode Spy Cam           {Fore.CYAN}│ {Fore.WHITE}Perekam kamera tersembunyi")
                print(f"    {Fore.RED}[0] {Fore.WHITE}Kembali ke Pilihan Bahasa\n")
            else:
                print(f"  {Fore.CYAN}Main Menu:\n")
                print(f"    {Fore.YELLOW}[1] {Fore.WHITE}USB Connection          {Fore.CYAN}│ {Fore.WHITE}Mirror via USB cable")
                print(f"    {Fore.YELLOW}[2] {Fore.WHITE}WiFi Connection         {Fore.CYAN}│ {Fore.WHITE}Mirror via WiFi network")
                print(f"    {Fore.YELLOW}[3] {Fore.WHITE}Auto-Connect WiFi       {Fore.CYAN}│ {Fore.WHITE}1-click connect to last IP")
                print(f"    {Fore.YELLOW}[4] {Fore.WHITE}Wireless Debugging      {Fore.CYAN}│ {Fore.WHITE}Mirror via Android 11+ Wireless Debug")
                print(f"    {Fore.YELLOW}[5] {Fore.WHITE}Session History         {Fore.CYAN}│ {Fore.WHITE}View previous mirroring session logs")
                print(f"    {Fore.YELLOW}[6] {Fore.WHITE}Install APK (Sideload)  {Fore.CYAN}│ {Fore.WHITE}Drag & drop APK file to phone")
                print(f"    {Fore.YELLOW}[7] {Fore.WHITE}Send File (Push)        {Fore.CYAN}│ {Fore.WHITE}Transfer file to phone")
                print(f"    {Fore.YELLOW}[8] {Fore.WHITE}Wireless Mic Mode       {Fore.CYAN}│ {Fore.WHITE}Use phone as PC mic")
                print(f"    {Fore.YELLOW}[9] {Fore.WHITE}OTG Mode                {Fore.CYAN}│ {Fore.WHITE}Physical Keyboard/Mouse without screen")
                print(f"    {Fore.YELLOW}[10]{Fore.WHITE} Spy Cam Mode           {Fore.CYAN}│ {Fore.WHITE}Hidden camera recorder")
                print(f"    {Fore.RED}[0] {Fore.WHITE}Back to Language Selection\n")

            cc = get_input("  Choice [0-10]: ", [str(i) for i in range(11)])
            if   cc == "0": break
            elif cc == "1": connect_usb(lang)
            elif cc == "2": connect_wifi(lang)
            elif cc == "3": auto_connect_wifi(lang)
            elif cc == "4": connect_wd(lang)
            elif cc == "5": show_session_log(lang)
            elif cc == "6": install_apk(lang)
            elif cc == "7": push_file(lang)
            elif cc == "8": start_wireless_mic(lang)
            elif cc == "9": start_otg_mode(lang)
            elif cc == "10": start_spy_cam(lang)


if __name__ == "__main__":
    main()

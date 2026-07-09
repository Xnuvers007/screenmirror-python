import os
import sys
import subprocess
import configparser
import time
import shutil
import urllib.request
import zipfile
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

CONFIG_FILE = os.path.expandvars(r"%APPDATA%\screenmirror_config.ini")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Globals for paths
ADB_EXE = "adb"
SCRCPY_EXE = "scrcpy"
SNDCPY_DIR = os.path.expandvars(r"%APPDATA%\screenmirror_sndcpy")
SNDCPY_EXE = os.path.join(SNDCPY_DIR, "sndcpy.bat")

def get_input(prompt_text, valid_choices=None, default=None):
    while True:
        try:
            val = input(prompt_text).strip()
            if not val and default is not None:
                return default
            if valid_choices and val not in valid_choices:
                print(f"{Fore.RED}  [X] Invalid choice. Please try again.")
                continue
            return val
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            sys.exit(0)

def print_banner(lang="en"):
    os.system("cls" if os.name == "nt" else "clear")
    print(f"\n{Fore.BLUE}  ============================================================")
    print(f"{Fore.CYAN}      Android to Laptop Screen Mirror  -  by Xnuvers007")
    if lang == "id":
        print(f"{Fore.CYAN}           Windows Edition  |  Indonesia")
    else:
        print(f"{Fore.CYAN}           Windows Edition  |  English")
    print(f"{Fore.BLUE}  ============================================================")
    print()

def log_ok(msg):
    print(f"{Fore.GREEN}  [OK] {msg}")

def log_warn(msg):
    print(f"{Fore.YELLOW}  [!]  {msg}")

def log_err(msg):
    print(f"{Fore.RED}  [X]  {msg}")

def log_info(msg):
    print(f"{Fore.WHITE}  [i]  {msg}")

def find_executables():
    global ADB_EXE, SCRCPY_EXE
    adb_path = shutil.which("adb")
    scrcpy_path = shutil.which("scrcpy")
    
    if adb_path: ADB_EXE = adb_path
    if scrcpy_path: SCRCPY_EXE = scrcpy_path
    
    # Try finding it in common windows dirs if not in path
    if not scrcpy_path:
        base_dir = "C:\\"
        try:
            for d in os.listdir(base_dir):
                if d.startswith("scrcpy-win"):
                    p = os.path.join(base_dir, d, "scrcpy.exe")
                    if os.path.exists(p):
                        SCRCPY_EXE = p
                        adb_alt = os.path.join(base_dir, d, "adb.exe")
                        if os.path.exists(adb_alt):
                            ADB_EXE = adb_alt
                        break
                    p = os.path.join(base_dir, d, d, "scrcpy.exe")
                    if os.path.exists(p):
                        SCRCPY_EXE = p
                        adb_alt = os.path.join(base_dir, d, d, "adb.exe")
                        if os.path.exists(adb_alt):
                            ADB_EXE = adb_alt
                        break
        except Exception:
            pass

    return shutil.which(SCRCPY_EXE) is not None or os.path.exists(SCRCPY_EXE)

def setup_sndcpy():
    if os.path.exists(SNDCPY_EXE):
        return True
    
    log_warn("sndcpy not found. Downloading for Audio Mirroring (Android 10 or below)...")
    try:
        os.makedirs(SNDCPY_DIR, exist_ok=True)
        zip_path = os.path.join(SNDCPY_DIR, "sndcpy.zip")
        url = "https://github.com/rom1v/sndcpy/releases/download/v1.1/sndcpy-v1.1.zip"
        urllib.request.urlretrieve(url, zip_path)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(SNDCPY_DIR)
        
        os.remove(zip_path)
        log_ok("sndcpy downloaded successfully!")
        return True
    except Exception as e:
        log_err(f"Failed to download sndcpy: {e}")
        return False

def check_device():
    log_info("Starting ADB server...")
    subprocess.run([ADB_EXE, "start-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    result = subprocess.run([ADB_EXE, "devices"], capture_output=True, text=True)
    lines = result.stdout.strip().split("\n")
    devices = [line.split()[0] for line in lines[1:] if "device" in line]
    
    if not devices:
        log_err("No Android device detected!")
        log_info("Possible causes: USB cable not connected, USB Debugging off, or tap 'Allow' on phone.")
        input("  Press Enter to continue...")
        return None
        
    device_id = devices[0]
    log_ok(f"Device detected: {device_id}")
    
    # Get device info
    try:
        sdk_res = subprocess.run([ADB_EXE, "-s", device_id, "shell", "getprop", "ro.build.version.sdk"], capture_output=True, text=True)
        sdk_ver = int(sdk_res.stdout.strip())
        brand_res = subprocess.run([ADB_EXE, "-s", device_id, "shell", "getprop", "ro.product.brand"], capture_output=True, text=True)
        brand = brand_res.stdout.strip()
        model_res = subprocess.run([ADB_EXE, "-s", device_id, "shell", "getprop", "ro.product.model"], capture_output=True, text=True)
        model = model_res.stdout.strip()
        
        log_info(f"Brand: {brand} | Model: {model} | API Level: {sdk_ver}")
        
        if sdk_ver < 21:
            log_err("Android too old (API < 21).")
            return None
            
        return {"id": device_id, "sdk": sdk_ver}
    except Exception:
        return {"id": device_id, "sdk": 30} # Default safe assumption

def configure_scrcpy(lang):
    print(f"\n{Fore.MAGENTA}  === SCRCPY SETTINGS ===")
    
    # FPS
    if lang == "id": print(f"{Fore.CYAN}  Pilih FPS:\n    1. 30 FPS\n    2. 60 FPS (REKOMENDASI)\n    3. 120 FPS\n    4. Custom")
    else: print(f"{Fore.CYAN}  Choose FPS:\n    1. 30 FPS\n    2. 60 FPS (RECOMMENDED)\n    3. 120 FPS\n    4. Custom")
    
    fps_choice = get_input("  Choice [1-4] (default: 2): ", ["1","2","3","4"], "2")
    fps = "60"
    if fps_choice == "1": fps = "30"
    elif fps_choice == "3": fps = "120"
    elif fps_choice == "4": fps = get_input("  Enter FPS: ", default="60")
    
    # Bitrate
    if lang == "id": print(f"\n{Fore.CYAN}  Pilih Bitrate:\n    1. 4M\n    2. 8M (REKOMENDASI)\n    3. 16M\n    4. 40M\n    5. Custom")
    else: print(f"\n{Fore.CYAN}  Choose Bitrate:\n    1. 4M\n    2. 8M (RECOMMENDED)\n    3. 16M\n    4. 40M\n    5. Custom")
    
    br_choice = get_input("  Choice [1-5] (default: 2): ", ["1","2","3","4","5"], "2")
    bitrate = "8M"
    if br_choice == "1": bitrate = "4M"
    elif br_choice == "3": bitrate = "16M"
    elif br_choice == "4": bitrate = "40M"
    elif br_choice == "5": bitrate = get_input("  Enter bitrate (e.g. 10M): ", default="8M")
    
    # Resolution
    if lang == "id": print(f"\n{Fore.CYAN}  Pilih Resolusi:\n    1. 720p\n    2. 1080p (REKOMENDASI)\n    3. 1440p\n    4. Full (Asli HP)")
    else: print(f"\n{Fore.CYAN}  Choose Resolution:\n    1. 720p\n    2. 1080p (RECOMMENDED)\n    3. 1440p\n    4. Full (Native)")
    
    res_choice = get_input("  Choice [1-4] (default: 2): ", ["1","2","3","4"], "2")
    resolution = "1080"
    if res_choice == "1": resolution = "720"
    elif res_choice == "3": resolution = "1440"
    elif res_choice == "4": resolution = "0"
    
    return {"fps": fps, "bitrate": bitrate, "resolution": resolution, "codec": "h264"}

def launch_scrcpy(config, device_info):
    log_info("Preparing launch...")
    
    args = [SCRCPY_EXE]
    
    if config.get('mode') == 'usb':
        args.append("-d")
    elif config.get('mode') in ['wifi', 'wd']:
        args.append(f"-s")
        args.append(f"{config['ip']}:{config['port']}")
        
    args.extend([
        "--video-codec=" + config.get("codec", "h264"),
        "-b", config.get("bitrate", "8M"),
        "--max-fps", config.get("fps", "60")
    ])
    
    if config.get("resolution", "0") != "0":
        args.extend(["--max-size", config.get("resolution")])
        
    log_ok("Mirror window will appear shortly...")
    
    sndcpy_proc = None
    if device_info and device_info.get("sdk", 30) <= 29:
        if setup_sndcpy():
            log_info("Starting sndcpy for audio forwarding...")
            sndcpy_proc = subprocess.Popen([SNDCPY_EXE], cwd=SNDCPY_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log_warn("Sndcpy might require VLC player installed on your system to play the audio stream.")
    else:
        pass

    try:
        subprocess.run(args)
    except KeyboardInterrupt:
        pass
    
    if sndcpy_proc:
        log_info("Stopping sndcpy...")
        sndcpy_proc.kill()

def connect_usb(lang):
    print_banner(lang)
    device_info = check_device()
    if not device_info: return
    
    conf = configure_scrcpy(lang)
    conf['mode'] = 'usb'
    launch_scrcpy(conf, device_info)

def connect_wifi(lang):
    print_banner(lang)
    log_info("Make sure USB cable is connected for initial setup!")
    device_info = check_device()
    if not device_info: return
    
    port = get_input("Enter TCP port (default 5555): ", default="5555")
    subprocess.run([ADB_EXE, "-s", device_info['id'], "tcpip", port])
    time.sleep(2)
    
    ip = get_input("Enter Android phone IP address: ")
    if not ip: return
    
    log_warn("Unplug the USB cable now!")
    input("Press Enter when ready...")
    
    log_info(f"Connecting to {ip}:{port}...")
    subprocess.run([ADB_EXE, "connect", f"{ip}:{port}"])
    time.sleep(2)
    
    conf = configure_scrcpy(lang)
    conf['mode'] = 'wifi'
    conf['ip'] = ip
    conf['port'] = port
    launch_scrcpy(conf, device_info)

def connect_wd(lang):
    print_banner(lang)
    log_info("Android 11+ Required for Wireless Debugging!")
    
    do_pair = get_input("First time pairing? [y/n] (default: y): ", ["y","n"], "y")
    if do_pair == "y":
        pair_addr = get_input("Enter pairing IP:PORT (e.g. 192.168.1.5:43521): ")
        pair_code = get_input("Enter 6-digit code from phone: ")
        if not pair_addr or not pair_code: return
        
        log_info("Starting ADB server...")
        subprocess.run([ADB_EXE, "start-server"], stdout=subprocess.DEVNULL)
        time.sleep(2)
        log_info(f"Pairing with {pair_addr}...")
        res = subprocess.run([ADB_EXE, "pair", pair_addr, pair_code])
        if res.returncode != 0:
            log_err("Pairing failed! Check code and address.")
            input("Press Enter to continue...")
            return
        log_ok("Pairing successful!")
    
    ip = get_input("Enter phone IP: ")
    port = get_input("Enter Port (from Wireless Debugging): ")
    if not ip or not port: return
    
    log_info(f"Connecting to {ip}:{port}...")
    res = subprocess.run([ADB_EXE, "connect", f"{ip}:{port}"])
    time.sleep(2)
    
    if res.returncode != 0:
        log_err("WD connection failed!")
        input("Press Enter to continue...")
        return
        
    device_info = check_device()
    if not device_info: return
    
    conf = configure_scrcpy(lang)
    conf['mode'] = 'wd'
    conf['ip'] = ip
    conf['port'] = port
    launch_scrcpy(conf, device_info)

def main():
    if not find_executables():
        log_err("scrcpy not found in PATH or standard directories.")
        print("Please install scrcpy first and ensure it is in your system PATH.")
        input("Press Enter to exit...")
        return
        
    lang = "en"
    
    while True:
        print_banner(lang)
        print("  Choose Language / Pilih Bahasa:")
        print("\n    1. Indonesia  (Bahasa Indonesia)")
        print("    2. English    (English)")
        print("    0. Exit / Keluar\n")
        lang_choice = get_input("  Choice [1-2, 0]: ", ["0","1","2"])
        
        if lang_choice == "0":
            break
        elif lang_choice == "1":
            lang = "id"
        elif lang_choice == "2":
            lang = "en"
            
        while True:
            print_banner(lang)
            if lang == "id":
                print("  1. Koneksi USB")
                print("  2. Koneksi WiFi")
                print("  3. Wireless Debugging")
                print("  0. Kembali")
            else:
                print("  1. USB Connection")
                print("  2. WiFi Connection")
                print("  3. Wireless Debugging")
                print("  0. Back")
                
            conn_choice = get_input("  Choice [0-3]: ", ["0","1","2","3"])
            if conn_choice == "0":
                break
            elif conn_choice == "1":
                connect_usb(lang)
            elif conn_choice == "2":
                connect_wifi(lang)
            elif conn_choice == "3":
                connect_wd(lang)

if __name__ == "__main__":
    main()

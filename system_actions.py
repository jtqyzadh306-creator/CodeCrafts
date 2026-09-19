import os
import re
import ctypes
import datetime
import threading
import subprocess
import webbrowser
import urllib.parse

import psutil
import jdatetime
import keyboard
import win32clipboard
import screen_brightness_control as sbc
from PIL import ImageGrab
from deep_translator import GoogleTranslator
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

import config
from text_utils import normalize_fa

VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3

KEYEVENTF_KEYUP = 0x0002


def _press_key(vk_code):
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)


def volume_up():
    for _ in range(4):
        _press_key(VK_VOLUME_UP)


def volume_down():
    for _ in range(4):
        _press_key(VK_VOLUME_DOWN)


def mute_toggle():
    _press_key(VK_VOLUME_MUTE)


def media_play_pause():
    _press_key(VK_MEDIA_PLAY_PAUSE)


def media_next():
    _press_key(VK_MEDIA_NEXT_TRACK)


def media_prev():
    _press_key(VK_MEDIA_PREV_TRACK)


def get_folder_path(key):
    home = os.path.expanduser("~")
    mapping = {
        "downloads": os.path.join(home, "Downloads"),
        "desktop": os.path.join(home, "Desktop"),
        "documents": os.path.join(home, "Documents"),
        "pictures": os.path.join(home, "Pictures"),
        "music": os.path.join(home, "Music"),
        "videos": os.path.join(home, "Videos"),
    }
    return mapping.get(key)


def open_folder(key):
    path = get_folder_path(key)
    if path and os.path.isdir(path):
        os.startfile(path)
        return True
    return False


def get_website_url(key):
    mapping = {
        "google": "https://google.com",
        "youtube": "https://youtube.com",
        "gmail": "https://mail.google.com",
        "instagram": "https://instagram.com",
        "telegram_web": "https://web.telegram.org",
        "twitter": "https://twitter.com",
    }
    return mapping.get(key)


def open_website(key):
    url = get_website_url(key)
    if url:
        webbrowser.open(url)
        return True
    return False


def speak_time():
    now = datetime.datetime.now()
    return f"الان ساعت {now.hour} و {now.minute} دقیقه است"


def speak_date():
    today = jdatetime.date.today()
    weekday_name = config.PERSIAN_WEEKDAYS[today.weekday()]
    month_name = config.PERSIAN_MONTHS[today.month - 1]
    return f"امروز {weekday_name}، {today.day} {month_name} {today.year} است"


def take_screenshot():
    home = os.path.expanduser("~")
    folder = os.path.join(home, "Pictures", "JarvisScreenshots")
    os.makedirs(folder, exist_ok=True)
    filename = datetime.datetime.now().strftime("screenshot_%Y%m%d_%H%M%S.png")
    path = os.path.join(folder, filename)
    image = ImageGrab.grab()
    image.save(path)
    return path


def battery_status():
    battery = psutil.sensors_battery()
    if not battery:
        return "دستگاهت باتری نداره یا نمی‌تونم بخونمش"
    percent = int(battery.percent)
    plugged = battery.power_plugged
    status = "در حال شارژه" if plugged else "شارژ نیست"
    return f"باتری {percent} درصده و {status}"


def shutdown_system():
    subprocess.Popen(["shutdown", "/s", "/t", "5"])


def restart_system():
    subprocess.Popen(["shutdown", "/r", "/t", "5"])


def add_note(text):
    home = os.path.expanduser("~")
    path = os.path.join(home, "jarvis_notes.txt")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(path, "a", encoding="utf-8") as fp:
        fp.write(f"[{timestamp}] {text}\n")
    return path


def parse_minutes(text):
    normalized = normalize_fa(text)
    match = re.search(r"\d+", normalized)
    if match:
        return int(match.group())
    for word, value in config.PERSIAN_NUMBERS.items():
        if word in normalized:
            return value
    return None


def schedule_reminder(minutes, message, on_fire):
    seconds = minutes * 60
    timer = threading.Timer(seconds, on_fire, args=[message])
    timer.daemon = True
    timer.start()
    return timer


def google_search(query):
    url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    webbrowser.open(url)


def system_status():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    return f"پردازنده {int(cpu)} درصد و رم {int(ram)} درصد در حال استفاده است"


def read_clipboard():
    try:
        win32clipboard.OpenClipboard()
        try:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        except TypeError:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_TEXT)
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="ignore")
        win32clipboard.CloseClipboard()
        return data.strip() if data else None
    except Exception:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass
        return None


def type_text(text):
    try:
        keyboard.write(text)
        return True
    except Exception:
        return False


def translate_text(text, target_lang):
    try:
        return GoogleTranslator(source="auto", target=target_lang).translate(text)
    except Exception:
        return None


def wifi_set(enabled):
    state = "enabled" if enabled else "disabled"
    try:
        result = subprocess.run(
            ["netsh", "interface", "set", "interface", "Wi-Fi", state],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def lock_screen():
    try:
        ctypes.windll.user32.LockWorkStation()
        return True
    except Exception:
        return False


def brightness_up(step=10):
    try:
        current = sbc.get_brightness()[0]
        sbc.set_brightness(min(100, current + step))
        return True
    except Exception:
        return False


def brightness_down(step=10):
    try:
        current = sbc.get_brightness()[0]
        sbc.set_brightness(max(0, current - step))
        return True
    except Exception:
        return False


def _get_mic_endpoint():
    devices = AudioUtilities.GetMicrophone()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return interface.QueryInterface(IAudioEndpointVolume)


def mic_mute(muted):
    try:
        endpoint = _get_mic_endpoint()
        endpoint.SetMute(1 if muted else 0, None)
        return True
    except Exception:
        return False


def search_files(filename_query, roots=None):
    if roots is None:
        home = os.path.expanduser("~")
        roots = [
            os.path.join(home, "Desktop"),
            os.path.join(home, "Documents"),
            os.path.join(home, "Downloads"),
        ]
    query_norm = normalize_fa(filename_query).replace(" ", "").lower()
    matches = []
    for root_dir in roots:
        if not os.path.isdir(root_dir):
            continue
        for root, _, files in os.walk(root_dir):
            for f in files:
                name_norm = normalize_fa(os.path.splitext(f)[0]).replace(" ", "").lower()
                if query_norm and query_norm in name_norm:
                    matches.append(os.path.join(root, f))
    return matches


def open_file(path):
    try:
        os.startfile(path)
        return True
    except Exception:
        return False

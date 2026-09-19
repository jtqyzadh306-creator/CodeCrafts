import sys
import os
import re
import json
import queue
import random
import datetime
import subprocess

import sounddevice as sd
import vosk
import pygame
import psutil
import requests

import config
import app_discovery
import tts_cache
import system_actions
from text_utils import normalize_fa


class JarvisCore:
    STATE_IDLE = "idle"
    STATE_LISTENING = "listening"
    STATE_SPEAKING = "speaking"

    def __init__(self, on_state_change=None, on_text_change=None):
        sys.stdout.reconfigure(line_buffering=True)
        self.on_state_change = on_state_change
        self.on_text_change = on_text_change
        self.state = self.STATE_IDLE
        self._running = False

        if not os.path.isdir(config.VOSK_MODEL_PATH):
            raise FileNotFoundError(config.VOSK_MODEL_PATH)

        self.command_model = vosk.Model(config.VOSK_MODEL_PATH)

        if os.path.isdir(config.WAKE_MODEL_PATH):
            self.wake_model = vosk.Model(config.WAKE_MODEL_PATH)
        else:
            self.wake_model = self.command_model

        self.sample_rate = 16000
        self.audio_queue = queue.Queue()

        pygame.mixer.init()

        self.apps_cache = app_discovery.load_or_scan()
        self.chat_mode = False
        self.chat_history = []
        self.pending_confirmation = None
        self.stopwatch_start = None
        self.active_reminders = []

        tts_cache.preload(
            config.GREETING_RESPONSES + [
                "متوجه نشدم، دوباره بگو",
                "همچین دستوری رو هنوز بلد نیستم",
                config.HELP_TEXT,
                config.SHUTDOWN_CONFIRM_TEXT,
                config.RESTART_CONFIRM_TEXT,
                config.CANCELLED_TEXT,
                config.NOTE_SAVED_TEXT,
                config.REMINDER_SET_TEXT,
                "صدا رو زیاد کردم",
                "صدا رو کم کردم",
                "صدا رو قطع کردم",
                "باشه",
                "باز کردم",
                "بگو بله یا نه",
            ]
        )

    def _set_state(self, new_state):
        self.state = new_state
        if self.on_state_change:
            self.on_state_change(new_state)

    def _audio_callback(self, indata, frames, time_info, status):
        self.audio_queue.put(bytes(indata))

    def _open_stream(self):
        try:
            return sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=self._audio_callback,
            )
        except Exception:
            sd._terminate()
            sd._initialize()
            try:
                return sd.RawInputStream(
                    samplerate=self.sample_rate,
                    blocksize=8000,
                    dtype="int16",
                    channels=1,
                    callback=self._audio_callback,
                )
            except Exception:
                return None

    def _listen_for_text(self, model, timeout=None):
        recognizer = vosk.KaldiRecognizer(model, self.sample_rate)
        recognizer.SetWords(False)

        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()

        stream = self._open_stream()
        if stream is None:
            return ""

        result_text = ""
        try:
            with stream:
                elapsed = 0.0
                block_seconds = 0.5
                while True:
                    try:
                        data = self.audio_queue.get(timeout=block_seconds)
                    except queue.Empty:
                        elapsed += block_seconds
                        if timeout and elapsed >= timeout:
                            break
                        continue

                    if recognizer.AcceptWaveform(data):
                        res = json.loads(recognizer.Result())
                        text = res.get("text", "").strip()
                        if text:
                            result_text = text
                            break
        except Exception:
            return ""

        return result_text

    def speak(self, text):
        self._set_state(self.STATE_SPEAKING)
        if self.on_text_change:
            self.on_text_change(reply=text)

        for attempt in range(3):
            try:
                path = tts_cache.get_or_create(text)
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(50)
                pygame.mixer.music.unload()
                break
            except Exception as e:
                print(f"[TTS Error - attempt {attempt + 1}]: {e}", flush=True)
                pygame.time.wait(300)

        self._set_state(self.STATE_IDLE)

    def _open_app(self, path):
        try:
            if path.startswith("ms-settings:"):
                os.startfile(path)
            elif "/" in path or "\\" in path or path.lower().endswith(".exe"):
                if os.name == "nt":
                    os.startfile(path)
                else:
                    subprocess.Popen([path])
            else:
                subprocess.Popen(path, shell=True)
            return True
        except Exception:
            return False

    def _is_chat_enter_request(self, text):
        normalized = normalize_fa(text)
        return any(trigger in normalized for trigger in config.CHAT_MODE_TRIGGERS)

    def _is_chat_exit_request(self, text):
        normalized = normalize_fa(text)
        return any(trigger in normalized for trigger in config.CHAT_MODE_EXIT_TRIGGERS)

    def _ask_local_model(self, user_text):
        self.chat_history.append({"role": "user", "content": user_text})
        messages = [{"role": "system", "content": config.CHAT_SYSTEM_PROMPT}] + self.chat_history[-10:]
        try:
            response = requests.post(
                config.OLLAMA_URL,
                json={"model": config.OLLAMA_MODEL, "messages": messages, "stream": False},
                timeout=60,
            )
            data = response.json()
            reply = data.get("message", {}).get("content", "").strip()
            if reply:
                self.chat_history.append({"role": "assistant", "content": reply})
                return reply
            return "متوجه نشدم، دوباره بگو"
        except Exception:
            return "نتونستم به مدل محلی وصل بشم، مطمئن شو Ollama روشنه"

    def _matches_any(self, text, triggers):
        normalized = normalize_fa(text)
        return any(normalize_fa(t) in normalized for t in triggers)

    def _match_alias(self, text, aliases_dict):
        normalized = normalize_fa(text).replace(" ", "")
        for key, keywords in aliases_dict.items():
            for kw in keywords:
                if normalize_fa(kw).replace(" ", "") in normalized:
                    return key
        return None

    def _reminder_fired(self, message):
        self.active_reminders = [r for r in self.active_reminders if r["message"] != message]
        self.speak(f"یادآوری: {message}")

    def _extract_after_triggers(self, text, triggers):
        normalized = normalize_fa(text)
        remainder = normalized
        for trigger in triggers:
            remainder = remainder.replace(normalize_fa(trigger), "")
        return remainder.strip()

    def _extract_numbers_and_operator(self, text):
        normalized = normalize_fa(text)
        numbers = [int(n) for n in re.findall(r"\d+", normalized)]
        operator = None
        if "ضربدر" in normalized or "ضرب" in normalized:
            operator = "*"
        elif "تقسیم" in normalized:
            operator = "/"
        elif "بعلاوه" in normalized or "جمع" in normalized:
            operator = "+"
        elif "منها" in normalized or "تفریق" in normalized or "منهای" in normalized:
            operator = "-"
        return numbers, operator

    def _do_math(self, text):
        numbers, operator = self._extract_numbers_and_operator(text)
        if len(numbers) < 2 or not operator:
            return None
        a, b = numbers[0], numbers[1]
        try:
            if operator == "*":
                result = a * b
            elif operator == "/":
                if b == 0:
                    return "نمیشه بر صفر تقسیم کرد"
                result = round(a / b, 2)
            elif operator == "+":
                result = a + b
            else:
                result = a - b
            return f"میشه {result}"
        except Exception:
            return None

    def _handle_system_command(self, command):
        if self._matches_any(command, config.VOLUME_UP_TRIGGERS):
            system_actions.volume_up()
            self.speak("صدا رو زیاد کردم")
            return True

        if self._matches_any(command, config.VOLUME_DOWN_TRIGGERS):
            system_actions.volume_down()
            self.speak("صدا رو کم کردم")
            return True

        if self._matches_any(command, config.MUTE_TRIGGERS):
            system_actions.mute_toggle()
            self.speak("صدا رو قطع کردم")
            return True

        if self._matches_any(command, config.MEDIA_PLAY_TRIGGERS):
            system_actions.media_play_pause()
            self.speak("باشه")
            return True

        if self._matches_any(command, config.MEDIA_PAUSE_TRIGGERS):
            system_actions.media_play_pause()
            self.speak("باشه، متوقف کردم")
            return True

        if self._matches_any(command, config.MEDIA_NEXT_TRIGGERS):
            system_actions.media_next()
            self.speak("رفتم آهنگ بعدی")
            return True

        if self._matches_any(command, config.MEDIA_PREV_TRIGGERS):
            system_actions.media_prev()
            self.speak("برگشتم آهنگ قبلی")
            return True

        if self._matches_any(command, config.TIME_TRIGGERS):
            self.speak(system_actions.speak_time())
            return True

        if self._matches_any(command, config.DATE_TRIGGERS):
            self.speak(system_actions.speak_date())
            return True

        if self._matches_any(command, config.SCREENSHOT_TRIGGERS):
            system_actions.take_screenshot()
            self.speak("اسکرین‌شات گرفتم")
            return True

        if self._matches_any(command, config.BATTERY_TRIGGERS):
            self.speak(system_actions.battery_status())
            return True

        if self._matches_any(command, config.SHUTDOWN_TRIGGERS):
            self.pending_confirmation = "shutdown"
            self.speak(config.SHUTDOWN_CONFIRM_TEXT)
            return True

        if self._matches_any(command, config.RESTART_TRIGGERS):
            self.pending_confirmation = "restart"
            self.speak(config.RESTART_CONFIRM_TEXT)
            return True

        if self._matches_any(command, config.SEARCH_TRIGGERS):
            query = self._extract_after_triggers(command, config.SEARCH_TRIGGERS)
            if query:
                system_actions.google_search(query)
                self.speak(f"دارم {query} رو توی گوگل جستجو می‌کنم")
            else:
                self.speak("چی رو جستجو کنم؟")
            return True

        folder_key = self._match_alias(command, config.FOLDER_ALIASES)
        if folder_key:
            ok = system_actions.open_folder(folder_key)
            if ok:
                self.speak("باز کردم")
            else:
                self.speak("نتونستم اون پوشه رو باز کنم")
            return True

        website_key = self._match_alias(command, config.WEBSITE_ALIASES)
        if website_key:
            system_actions.open_website(website_key)
            self.speak("باز کردم")
            return True

        if self._matches_any(command, config.NOTE_TRIGGERS):
            note_text = command
            for trigger in config.NOTE_TRIGGERS:
                note_text = note_text.replace(trigger, "")
            note_text = note_text.strip()
            system_actions.add_note(note_text if note_text else command)
            self.speak(config.NOTE_SAVED_TEXT)
            return True

        if self._matches_any(command, config.REMINDER_TRIGGERS):
            minutes = system_actions.parse_minutes(command)
            if minutes:
                system_actions.schedule_reminder(minutes, command, self._reminder_fired)
                self.active_reminders.append({"message": command, "minutes": minutes})
                self.speak(config.REMINDER_SET_TEXT)
            else:
                self.speak("نفهمیدم چند دقیقه دیگه یادت بندازم")
            return True

        if self._matches_any(command, config.LIST_REMINDERS_TRIGGERS):
            if self.active_reminders:
                items = "، ".join(r["message"] for r in self.active_reminders)
                self.speak(f"این یادآوری‌ها فعاله: {items}")
            else:
                self.speak("هیچ یادآوری فعالی نداری")
            return True

        if self._matches_any(command, config.TIMER_TRIGGERS):
            minutes = system_actions.parse_minutes(command)
            if minutes:
                system_actions.schedule_reminder(minutes, config.TIMER_DONE_TEXT, self._reminder_fired)
                self.active_reminders.append({"message": config.TIMER_DONE_TEXT, "minutes": minutes})
                self.speak(f"باشه، {minutes} دقیقه دیگه بهت میگم")
            else:
                self.speak("نفهمیدم چند دقیقه تایمر بذارم")
            return True

        if self._matches_any(command, config.STOPWATCH_START_TRIGGERS):
            self.stopwatch_start = datetime.datetime.now()
            self.speak("کرنومتر رو شروع کردم")
            return True

        if self._matches_any(command, config.STOPWATCH_STOP_TRIGGERS):
            if self.stopwatch_start:
                elapsed = datetime.datetime.now() - self.stopwatch_start
                total_seconds = int(elapsed.total_seconds())
                minutes, seconds = divmod(total_seconds, 60)
                self.stopwatch_start = None
                self.speak(f"{minutes} دقیقه و {seconds} ثانیه گذشت")
            else:
                self.speak("کرنومتر روشن نیست")
            return True

        if self._matches_any(command, config.MATH_TRIGGERS):
            result = self._do_math(command)
            if result:
                self.speak(result)
            else:
                self.speak("متوجه حساب نشدم")
            return True

        if self._matches_any(command, config.SYSTEM_STATUS_TRIGGERS):
            self.speak(system_actions.system_status())
            return True

        if self._matches_any(command, config.CLIPBOARD_READ_TRIGGERS):
            content = system_actions.read_clipboard()
            if content:
                self.speak(content)
            else:
                self.speak("چیزی توی کلیپ‌بورد نیست")
            return True

        if self._matches_any(command, config.DICTATE_TRIGGERS):
            text_to_type = self._extract_after_triggers(command, config.DICTATE_TRIGGERS)
            if text_to_type:
                system_actions.type_text(text_to_type)
                self.speak("نوشتم")
            else:
                self.speak("چی رو بنویسم؟")
            return True

        if self._matches_any(command, config.TRANSLATE_TO_EN_TRIGGERS):
            text_to_translate = self._extract_after_triggers(command, config.TRANSLATE_TO_EN_TRIGGERS)
            if text_to_translate:
                translated = system_actions.translate_text(text_to_translate, "en")
                self.speak(translated if translated else "نتونستم ترجمه کنم")
            else:
                self.speak("چی رو ترجمه کنم؟")
            return True

        if self._matches_any(command, config.TRANSLATE_TO_FA_TRIGGERS):
            text_to_translate = self._extract_after_triggers(command, config.TRANSLATE_TO_FA_TRIGGERS)
            if text_to_translate:
                translated = system_actions.translate_text(text_to_translate, "fa")
                self.speak(translated if translated else "نتونستم ترجمه کنم")
            else:
                self.speak("چی رو ترجمه کنم؟")
            return True

        if self._matches_any(command, config.WIFI_ON_TRIGGERS):
            ok = system_actions.wifi_set(True)
            self.speak("وایفای رو روشن کردم" if ok else "نتونستم وایفای رو روشن کنم")
            return True

        if self._matches_any(command, config.WIFI_OFF_TRIGGERS):
            ok = system_actions.wifi_set(False)
            self.speak("وایفای رو خاموش کردم" if ok else "نتونستم وایفای رو خاموش کنم")
            return True

        if self._matches_any(command, config.LOCK_TRIGGERS):
            system_actions.lock_screen()
            self.speak("قفلش کردم")
            return True

        if self._matches_any(command, config.BRIGHTNESS_UP_TRIGGERS):
            ok = system_actions.brightness_up()
            self.speak("روشنایی رو زیاد کردم" if ok else "نتونستم روشنایی رو تغییر بدم")
            return True

        if self._matches_any(command, config.BRIGHTNESS_DOWN_TRIGGERS):
            ok = system_actions.brightness_down()
            self.speak("روشنایی رو کم کردم" if ok else "نتونستم روشنایی رو تغییر بدم")
            return True

        if self._matches_any(command, config.MIC_MUTE_TRIGGERS):
            ok = system_actions.mic_mute(True)
            self.speak("میکروفون رو قطع کردم" if ok else "نتونستم میکروفون رو قطع کنم")
            return True

        if self._matches_any(command, config.MIC_UNMUTE_TRIGGERS):
            ok = system_actions.mic_mute(False)
            self.speak("میکروفون رو وصل کردم" if ok else "نتونستم میکروفون رو وصل کنم")
            return True

        if self._matches_any(command, config.FILE_OPEN_TRIGGERS):
            filename_query = self._extract_after_triggers(command, config.FILE_OPEN_TRIGGERS)
            if filename_query:
                matches = system_actions.search_files(filename_query)
                if matches:
                    system_actions.open_file(matches[0])
                    self.speak("پیدا کردم و باز کردم")
                else:
                    self.speak("همچین فایلی پیدا نکردم")
            else:
                self.speak("اسم فایل رو بگو")
            return True

        return False

    def _is_help_request(self, text):
        normalized = normalize_fa(text)
        return any(trigger in normalized for trigger in config.HELP_TRIGGERS)

    def _is_close_request(self, text):
        normalized = normalize_fa(text)
        return any(trigger in normalized for trigger in config.CLOSE_TRIGGERS)

    def _resolve_process_name(self, path, name):
        mapped = config.PROCESS_NAMES.get(name)
        if mapped:
            return mapped
        if path and (path.lower().endswith(".exe") or "/" in path or "\\" in path):
            return os.path.basename(path)
        return None

    def _close_app(self, process_name):
        if not process_name:
            return False
        process_name = process_name.lower()
        found = False
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() == process_name:
                    proc.terminate()
                    found = True
            except Exception:
                continue
        return found

    def run_forever(self):
        self._running = True
        activated = False

        while self._running:
            if not activated:
                self._set_state(self.STATE_IDLE)
                heard = self._listen_for_text(self.wake_model, timeout=None)

                if not heard:
                    continue

                print(f"[شنیده شد]: {heard}", flush=True)

                heard_norm = normalize_fa(heard)
                heard_no_space = heard_norm.replace(" ", "")
                wake_detected = any(
                    normalize_fa(w).replace(" ", "") in heard_no_space for w in config.WAKE_WORDS
                )

                if wake_detected:
                    activated = True
                    self._set_state(self.STATE_LISTENING)
                    self.speak(random.choice(config.GREETING_RESPONSES))
                continue

            self._set_state(self.STATE_LISTENING)

            if self.chat_mode:
                command = self._listen_for_text(self.command_model, timeout=None)
            else:
                command = self._listen_for_text(self.wake_model, timeout=None)

            if not command:
                continue

            print(f"[دستور شنیده شد]: {command}", flush=True)
            if self.on_text_change:
                self.on_text_change(heard=command)

            if self.pending_confirmation:
                if self._matches_any(command, config.CONFIRM_YES):
                    if self.pending_confirmation == "shutdown":
                        system_actions.shutdown_system()
                        self.speak("باشه، دارم خاموش می‌کنم")
                    elif self.pending_confirmation == "restart":
                        system_actions.restart_system()
                        self.speak("باشه، دارم ری‌استارت می‌کنم")
                    self.pending_confirmation = None
                elif self._matches_any(command, config.CONFIRM_NO):
                    self.pending_confirmation = None
                    self.speak(config.CANCELLED_TEXT)
                else:
                    self.speak("بگو بله یا نه")
                continue

            if self.chat_mode:
                if self._is_chat_exit_request(command):
                    self.chat_mode = False
                    self.chat_history = []
                    self.speak(config.CHAT_EXIT_TEXT)
                else:
                    reply = self._ask_local_model(command)
                    self.speak(reply)
                continue

            if self._is_chat_enter_request(command):
                self.chat_mode = True
                self.chat_history = []
                self.speak(config.CHAT_ENTER_TEXT)
                continue

            if self._matches_any(command, config.SLEEP_TRIGGERS):
                activated = False
                self.speak(config.SLEEP_TEXT)
                continue

            if self._is_help_request(command):
                self.speak(config.HELP_TEXT)
                continue

            if self._handle_system_command(command):
                continue

            close_requested = self._is_close_request(command)
            path, name = app_discovery.match_app(command, self.apps_cache)

            if close_requested:
                if path:
                    process_name = self._resolve_process_name(path, name)
                    ok = self._close_app(process_name)
                    if ok:
                        self.speak(f"{name} رو بستم")
                    else:
                        self.speak(f"{name} باز نیست")
                else:
                    self.speak("متوجه نشدم چی رو ببندم")
                continue

            if path:
                ok = self._open_app(path)
                if ok:
                    self.speak(f"{name} رو باز می‌کنم")
                else:
                    self.speak(f"نتونستم {name} رو باز کنم")
            else:
                self.speak("همچین دستوری رو هنوز بلد نیستم")

    def stop(self):
        self._running = False

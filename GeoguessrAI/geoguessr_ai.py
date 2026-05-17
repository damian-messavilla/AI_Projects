"""
GeoGuessr AI - Desktop-Anwendung
================================
Nimmt per Hotkey (Alt+X) einen Screenshot auf, sendet ihn an Google Gemini
und zeigt die Analyse mit gerenderten Markdown in einer modernen GUI an.

Benötigte Pakete (pip install):
    pip install google-genai PyQt6 Pillow keyboard

Autor: GeoGuessr AI Tool
"""

import sys
import io
import threading
import base64
import traceback
import os
import json
import re

def load_api_key(project_name):
    key_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api_keys.json")
    try:
        with open(key_file, "r", encoding="utf-8") as f:
            return json.load(f).get(project_name, "")
    except Exception:
        return ""

# --- Konfiguration -----------------------------------------------------------
API_KEY = load_api_key("GeoguessrAI")
MISTRAL_API_KEY = load_api_key("MistralAI")
MODEL_NAME = "gemini-3.1-flash-lite-preview"  # Modellname
MISTRAL_MODEL_NAME = "mistral-large-2512"
HOTKEY = "alt+x"  # Globaler Hotkey
# ------------------------------------------------------------------------------

# ── Drittanbieter-Imports ─────────────────────────────────────────────────────
try:
    from google import genai
    from google.genai import types
except ImportError:
    print("FEHLER: 'google-genai' ist nicht installiert.")
    print("Bitte installiere es mit:  pip install google-genai")
    sys.exit(1)

try:
    from mistralai.client import Mistral
except ImportError:
    print("FEHLER: 'mistralai' ist nicht installiert.")
    print("Bitte installiere es mit:  pip install mistralai")
    sys.exit(1)

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTextBrowser, QLabel, QFrame, QSplitter, QSystemTrayIcon, QMenu,
        QSizePolicy, QProgressBar, QTabWidget, QPushButton
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QObject, QSize, QTimer
    from PyQt6.QtGui import QPixmap, QImage, QIcon, QFont, QAction, QColor, QPalette
except ImportError:
    print("FEHLER: 'PyQt6' ist nicht installiert.")
    print("Bitte installiere es mit:  pip install PyQt6")
    sys.exit(1)

try:
    from PIL import ImageGrab, Image
except ImportError:
    print("FEHLER: 'Pillow' ist nicht installiert.")
    print("Bitte installiere es mit:  pip install Pillow")
    sys.exit(1)

try:
    import keyboard
except ImportError:
    print("FEHLER: 'keyboard' ist nicht installiert.")
    print("Bitte installiere es mit:  pip install keyboard")
    sys.exit(1)


# ── GeoGuessr-Analyse-Prompt ─────────────────────────────────────────────────
GEOGUESSR_PROMPT = """You are a world-class GeoGuessr expert and geolocation analyst.
Analyze this screenshot from a GeoGuessr round and determine the most likely location.

Examine the following clues systematically and report your findings for each visible category:

### Architecture & Infrastructure
- Building styles, materials, roof types, construction patterns
- Road surface quality, lane markings, road width

### Vegetation & Landscape
- Types of trees, plants, crops visible
- Terrain (flat, hilly, mountainous, coastal, desert)
- Soil color and type

### Road Signs & Text
- Any visible text, language, script/alphabet
- Road sign shapes, colors, and styles (European round, US rectangular, etc.)
- Speed limit formats, distance markers, highway numbering systems

### Utility Poles & Infrastructure
- Pole material (wood, concrete, metal), style, and shape
- Power line configurations
- Street light designs

### Bollards & Road Furniture
- Bollard styles (these are highly country-specific!)
- Guardrail types and colors
- Road barrier designs

### Vehicles & License Plates
- License plate colors, shapes, and formats
- Car brands and models common in specific regions
- Driving side (left or right)

### Weather & Sun Position
- Cloud types, sky color, lighting angle
- Sun position (helps determine hemisphere and latitude)
- Season indicators

### Google Coverage Meta-Clues
- Camera quality and generation (Gen 2, 3, 4)
- Car visible in bottom of screen (Google car type/color)
- Coverage patterns and rift lines
- Any compass or directional indicators

### Final Verdict
Write your full analysis as usual to maintain your reasoning process. However, you MUST wrap your final conclusion inside exactly these tags: <FINAL_VERDICT> and </FINAL_VERDICT>.
Inside these tags, provide ONLY the following points formatted EXACTLY like this:
**1. Country:** [Country Name] ([Confidence]%)

**2. Region/State:** [Region Name] ([Confidence]%)

**3. Specific City/Area:** [City Name]

**4. Key Deciding Factors:**
- [Factor 1]
- [Factor 2]
- [Factor 3]

You MUST ignore all GeoGuessr game UI elements (e.g., text like "Raten", "Hinweis", "Punkte", compass, minimap). This UI is in German simply because the user plays the game in German. It has NOTHING to do with the actual location of the image! Focus strictly on the street view environment.

Be specific and decisive. Use ALL visible clues to narrow down the location as precisely as possible.
Respond in English with well-structured Markdown formatting."""


# ── Signal-Bridge (Thread → GUI) ─────────────────────────────────────────────
class SignalBridge(QObject):
    """Brücke zwischen Worker-Threads und dem Qt-GUI-Thread."""
    result_ready = pyqtSignal(str, str)          # AI-Name, Markdown-Ergebnis
    error_occurred = pyqtSignal(str, str)        # AI-Name, Fehlermeldung
    screenshot_taken = pyqtSignal(object)   # PIL-Image des Screenshots
    loading_started = pyqtSignal()          # Ladeanimation starten


# ── Stylesheet ────────────────────────────────────────────────────────────────
STYLESHEET = """
QMainWindow {
    background-color: #0d1117;
}

QWidget#centralWidget {
    background-color: #0d1117;
}

QLabel#titleLabel {
    color: #58a6ff;
    font-size: 18px;
    font-weight: bold;
    padding: 8px 12px;
}

QLabel#statusLabel {
    color: #8b949e;
    font-size: 13px;
    padding: 4px 12px;
}

QLabel#hotkeyLabel {
    color: #f0883e;
    font-size: 12px;
    font-weight: bold;
    background-color: #1c2128;
    border: 1px solid #f0883e;
    border-radius: 6px;
    padding: 4px 10px;
}

QLabel#screenshotLabel {
    background-color: #161b22;
    border: 2px solid #21262d;
    border-radius: 10px;
    padding: 4px;
}

QTextBrowser#resultBrowser {
    background-color: #161b22;
    color: #c9d1d9;
    border: 2px solid #21262d;
    border-radius: 10px;
    padding: 16px;
    font-size: 14px;
    selection-background-color: #264f78;
}

QFrame#headerFrame {
    background-color: #161b22;
    border-bottom: 1px solid #21262d;
    padding: 8px;
}

QFrame#footerFrame {
    background-color: #161b22;
    border-top: 1px solid #21262d;
    padding: 4px;
}

QProgressBar {
    background-color: #21262d;
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #58a6ff, stop:0.5 #bc8cff, stop:1 #58a6ff);
    border-radius: 4px;
}

QSplitter::handle {
    background-color: #21262d;
    width: 2px;
}

QTabWidget::pane {
    border: 1px solid #21262d;
    border-radius: 8px;
    background: #161b22;
}

QTabBar::tab {
    background: #0d1117;
    color: #8b949e;
    padding: 8px 24px;
    border: 1px solid #21262d;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-weight: bold;
}

QTabBar::tab:selected {
    background: #161b22;
    color: #58a6ff;
    border-top: 2px solid #58a6ff;
}
"""

# Markdown-CSS für den QTextBrowser
MARKDOWN_CSS = """
<style>
    body {
        font-family: 'Segoe UI', -apple-system, sans-serif;
        color: #c9d1d9;
        line-height: 1.7;
        font-size: 14px;
    }
    h1 { color: #58a6ff; font-size: 22px; margin-top: 16px; margin-bottom: 8px;
         border-bottom: 1px solid #21262d; padding-bottom: 6px; }
    h2 { color: #58a6ff; font-size: 19px; margin-top: 14px; margin-bottom: 6px;
         border-bottom: 1px solid #21262d; padding-bottom: 4px; }
    h3 { color: #d2a8ff; font-size: 16px; margin-top: 12px; margin-bottom: 4px; }
    h4 { color: #f0883e; font-size: 15px; margin-top: 10px; margin-bottom: 4px; }
    strong, b { color: #f0f6fc; }
    em, i { color: #8b949e; }
    code {
        background-color: #1c2128;
        color: #f0883e;
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'Cascadia Code', 'Consolas', monospace;
        font-size: 13px;
    }
    pre {
        background-color: #1c2128;
        border: 1px solid #21262d;
        border-radius: 6px;
        padding: 12px;
        font-family: 'Cascadia Code', 'Consolas', monospace;
        font-size: 13px;
        color: #c9d1d9;
    }
    ul, ol { margin-left: 8px; padding-left: 16px; }
    li { margin-bottom: 4px; color: #c9d1d9; }
    blockquote {
        border-left: 3px solid #58a6ff;
        margin-left: 0;
        padding-left: 12px;
        color: #8b949e;
    }
    hr {
        border: none;
        border-top: 1px solid #21262d;
        margin: 12px 0;
    }
    a { color: #58a6ff; text-decoration: none; }
    table { border-collapse: collapse; width: 100%; margin: 8px 0; }
    th { background-color: #1c2128; color: #58a6ff; padding: 8px; text-align: left;
         border: 1px solid #21262d; }
    td { padding: 6px 8px; border: 1px solid #21262d; color: #c9d1d9; }
</style>
"""


# ── Haupt-Fenster ─────────────────────────────────────────────────────────────
class GeoGuessrWindow(QMainWindow):
    """Hauptfenster der GeoGuessr-AI-Anwendung."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🌍 GeoGuessr AI")
        self.setMinimumSize(950, 650)
        self.resize(1100, 750)
        self.setStyleSheet(STYLESHEET)
        
        self.full_responses = {"Gemini": "", "Mistral": ""}
        self.verdicts = {"Gemini": "", "Mistral": ""}

        # Signal-Bridge
        self.bridge = SignalBridge()
        self.bridge.result_ready.connect(self._on_result)
        self.bridge.error_occurred.connect(self._on_error)
        self.bridge.screenshot_taken.connect(self._on_screenshot)
        self.bridge.loading_started.connect(self._on_loading)

        # Gemini-Client
        try:
            self.client = genai.Client(api_key=API_KEY)
        except Exception as e:
            self.client = None
            print(f"WARNUNG: Gemini-Client konnte nicht erstellt werden: {e}")

        # Mistral-Client
        try:
            if not MISTRAL_API_KEY:
                raise ValueError("Mistral API-Key fehlt.")
            self.mistral_client = Mistral(api_key=MISTRAL_API_KEY)
        except Exception as e:
            self.mistral_client = None
            print(f"WARNUNG: Mistral-Client konnte nicht erstellt werden: {e}")

        # Status tracking
        self.ai_status = {"Gemini": "idle", "Mistral": "idle"}
        
        # UI aufbauen
        self._build_ui()

        # Globalen Hotkey registrieren
        self._register_hotkey()

        # Pulsierender Ladebalken-Timer
        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._pulse_progress)
        self._pulse_value = 0
        self._pulse_direction = 1

    # ── UI-Aufbau ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Header ───────────────────────────────────────────────────────────
        header = QFrame()
        header.setObjectName("headerFrame")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)

        title = QLabel("🌍  GeoGuessr AI  Analyzer")
        title.setObjectName("titleLabel")
        header_layout.addWidget(title)

        header_layout.addStretch()

        hotkey_label = QLabel(f"⌨  Hotkey:  {HOTKEY.upper()}")
        hotkey_label.setObjectName("hotkeyLabel")
        header_layout.addWidget(hotkey_label)

        main_layout.addWidget(header)

        # ── Ladebalken ───────────────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # ── Content-Bereich (Splitter) ───────────────────────────────────────
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.setSpacing(12)

        # Linke Seite: Screenshot-Vorschau
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        screenshot_title = QLabel("📸  Screenshot")
        screenshot_title.setStyleSheet("color: #8b949e; font-size: 12px; font-weight: bold;")
        left_layout.addWidget(screenshot_title)

        self.screenshot_label = QLabel("Drücke ALT+X um\neinen Screenshot\naufzunehmen")
        self.screenshot_label.setObjectName("screenshotLabel")
        self.screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.screenshot_label.setMinimumSize(320, 200)
        self.screenshot_label.setMaximumWidth(400)
        self.screenshot_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        self.screenshot_label.setStyleSheet(
            self.screenshot_label.styleSheet() + "color: #484f58; font-size: 13px;"
        )
        left_layout.addWidget(self.screenshot_label)

        # Statusanzeige unter dem Screenshot
        self.status_label = QLabel("⏳  Bereit – warte auf Hotkey...")
        self.status_label.setObjectName("statusLabel")
        left_layout.addWidget(self.status_label)

        content_layout.addWidget(left_panel)

        # Rechte Seite: Markdown-Ergebnis
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        right_header = QHBoxLayout()
        result_title = QLabel("🤖  AI-Analyse")
        result_title.setStyleSheet("color: #8b949e; font-size: 12px; font-weight: bold;")
        right_header.addWidget(result_title)
        
        right_header.addStretch()
        
        self.toggle_details_btn = QPushButton("Details")
        self.toggle_details_btn.setObjectName("toggleDetailsBtn")
        self.toggle_details_btn.setCheckable(True)
        self.toggle_details_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #30363d;
                border: 1px solid #8b949e;
            }
            QPushButton:checked {
                background-color: #1f6feb;
                color: #ffffff;
                border: 1px solid #1f6feb;
            }
        """)
        self.toggle_details_btn.clicked.connect(self._toggle_details)
        right_header.addWidget(self.toggle_details_btn)
        
        right_layout.addLayout(right_header)

        self.result_tabs = QTabWidget()
        self.result_tabs.setObjectName("resultTabs")
        
        self.gemini_browser = QTextBrowser()
        self.gemini_browser.setOpenExternalLinks(True)
        self.gemini_browser.setPlaceholderText("Die Analyse wird hier angezeigt...")
        
        self.mistral_browser = QTextBrowser()
        self.mistral_browser.setOpenExternalLinks(True)
        self.mistral_browser.setPlaceholderText("Die Analyse wird hier angezeigt...")

        self.result_tabs.addTab(self.gemini_browser, "Gemini 3.1")
        self.result_tabs.addTab(self.mistral_browser, "Mistral Large")
        
        right_layout.addWidget(self.result_tabs)

        content_layout.addWidget(right_panel, stretch=2)
        main_layout.addWidget(content_widget, stretch=1)

        # ── Footer ───────────────────────────────────────────────────────────
        footer = QFrame()
        footer.setObjectName("footerFrame")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 6, 16, 6)

        model_label = QLabel(f"Modell: {MODEL_NAME}")
        model_label.setStyleSheet("color: #484f58; font-size: 11px;")
        footer_layout.addWidget(model_label)

        footer_layout.addStretch()

        credits_label = QLabel("GeoGuessr AI Analyzer v1.0")
        credits_label.setStyleSheet("color: #484f58; font-size: 11px;")
        footer_layout.addWidget(credits_label)

        main_layout.addWidget(footer)

    # ── Hotkey-Registrierung ──────────────────────────────────────────────────
    def _register_hotkey(self):
        """Registriert den globalen Hotkey in einem separaten Thread."""
        try:
            keyboard.add_hotkey(HOTKEY, self._on_hotkey_pressed)
            print(f"[INFO] Globaler Hotkey '{HOTKEY.upper()}' registriert.")
        except Exception as e:
            print(f"[FEHLER] Hotkey konnte nicht registriert werden: {e}")
            self.status_label.setText(f"⚠️  Hotkey-Fehler: {e}")

    # ── Hotkey-Callback ───────────────────────────────────────────────────────
    def _on_hotkey_pressed(self):
        """Wird aufgerufen, wenn der Hotkey gedrückt wird (läuft im keyboard-Thread)."""
        # Signale aus dem Thread heraus senden → GUI-Thread
        self.bridge.loading_started.emit()
        threading.Thread(target=self._capture_and_analyze, daemon=True).start()

    # ── Screenshot + API-Aufruf ───────────────────────────────────────────────
    def _capture_and_analyze(self):
        """Nimmt einen Screenshot auf und sendet ihn parallel an die APIs."""
        try:
            screenshot: Image.Image = ImageGrab.grab()
            self.bridge.screenshot_taken.emit(screenshot)

            # Bild für die API vorbereiten
            img_buffer = io.BytesIO()
            screenshot.save(img_buffer, format="JPEG", quality=85)
            img_bytes = img_buffer.getvalue()
            base64_img = base64.b64encode(img_bytes).decode("utf-8")

            if self.client:
                threading.Thread(target=self._analyze_gemini, args=(img_bytes,), daemon=True).start()
            else:
                self.bridge.error_occurred.emit("Gemini", "❌ Gemini-Client nicht initialisiert.")
                
            if self.mistral_client:
                threading.Thread(target=self._analyze_mistral, args=(base64_img,), daemon=True).start()
            else:
                self.bridge.error_occurred.emit("Mistral", "❌ Mistral-Client nicht initialisiert.")

        except Exception as e:
            error_msg = f"❌ **Fehler bei der Aufnahme:**\n\n`{type(e).__name__}`: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
            self.bridge.error_occurred.emit("System", error_msg)

    def _analyze_gemini(self, img_bytes):
        try:
            image_part = {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode("utf-8")}}
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=[image_part, GEOGUESSR_PROMPT],
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
                    temperature=1
                )
            )
            if response and response.text:
                self.bridge.result_ready.emit("Gemini", response.text)
            else:
                self.bridge.error_occurred.emit("Gemini", "⚠️ Leere Antwort zurückgegeben.")
        except Exception as e:
            self.bridge.error_occurred.emit("Gemini", f"❌ Fehler:\n\n`{type(e).__name__}`: {str(e)}\n\n```\n{traceback.format_exc()}\n```")

    def _analyze_mistral(self, base64_image):
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": GEOGUESSR_PROMPT},
                        {"type": "image_url", "image_url": f"data:image/jpeg;base64,{base64_image}"}
                    ]
                }
            ]
            response = self.mistral_client.chat.complete(
                model=MISTRAL_MODEL_NAME,
                messages=messages
            )
            if response and response.choices and response.choices[0].message.content:
                self.bridge.result_ready.emit("Mistral", response.choices[0].message.content)
            else:
                self.bridge.error_occurred.emit("Mistral", "⚠️ Leere Antwort zurückgegeben.")
        except Exception as e:
            self.bridge.error_occurred.emit("Mistral", f"❌ Fehler:\n\n`{type(e).__name__}`: {str(e)}\n\n```\n{traceback.format_exc()}\n```")

    def _check_all_done(self):
        if self.ai_status["Gemini"] in ("done", "error") and self.ai_status["Mistral"] in ("done", "error"):
            self._pulse_timer.stop()
            self.progress_bar.setVisible(False)
            if self.ai_status["Gemini"] == "error" and self.ai_status["Mistral"] == "error":
                self.status_label.setText("❌  Fehler aufgetreten!")
                self.status_label.setStyleSheet("color: #f85149; font-size: 13px; padding: 4px 12px;")
            else:
                self.status_label.setText("✅  Analyse abgeschlossen!")
                self.status_label.setStyleSheet("color: #3fb950; font-size: 13px; padding: 4px 12px;")

    # ── GUI-Slot: Laden gestartet ─────────────────────────────────────────────
    def _on_loading(self):
        """Wird im GUI-Thread aufgerufen, wenn die Analyse startet."""
        self.showNormal()
        self.activateWindow()
        self.raise_()

        self.status_label.setText("🔄  Screenshot aufgenommen – Analyse läuft...")
        self.status_label.setStyleSheet("color: #58a6ff; font-size: 13px; padding: 4px 12px;")

        self.ai_status = {"Gemini": "loading", "Mistral": "loading"}
        self.result_tabs.setTabText(0, "Gemini (Lädt... ⏳)")
        self.result_tabs.setTabText(1, "Mistral (Lädt... ⏳)")

        # Ladebalken anzeigen
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._pulse_value = 0
        self._pulse_direction = 1
        self._pulse_timer.start(30)

        # Lade-Text in den Browser setzen
        loading_html = f"""
        {MARKDOWN_CSS}
        <div style="text-align: center; padding: 60px 20px;">
            <h2 style="color: #58a6ff;">🔍 Analysiere Screenshot...</h2>
            <p style="color: #8b949e; font-size: 15px;">
                Das Bild wird an die KIs gesendet.<br>
                Bitte warte einen Moment...
            </p>
        </div>
        """
        self.gemini_browser.setHtml(loading_html)
        self.mistral_browser.setHtml(loading_html)

    # ── GUI-Slot: Screenshot empfangen ────────────────────────────────────────
    def _on_screenshot(self, pil_image: Image.Image):
        """Zeigt den Screenshot als Vorschau in der GUI an."""
        try:
            # PIL → QPixmap
            img_buffer = io.BytesIO()
            pil_image.save(img_buffer, format="PNG")
            img_data = img_buffer.getvalue()

            qimage = QImage()
            qimage.loadFromData(img_data)
            pixmap = QPixmap.fromImage(qimage)

            # Skalieren auf die Label-Größe
            scaled = pixmap.scaled(
                self.screenshot_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.screenshot_label.setPixmap(scaled)
        except Exception as e:
            print(f"[WARNUNG] Screenshot-Vorschau fehlgeschlagen: {e}")

    def _extract_final_verdict(self, text: str) -> str:
        """Extrahiert den Text innerhalb von <FINAL_VERDICT>...</FINAL_VERDICT>.
        Greift auf alles nach 'Final Verdict' zurück oder den gesamten Text, falls die Tags fehlen."""
        match = re.search(r"<FINAL_VERDICT>(.*?)</FINAL_VERDICT>", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
            
        # Fallback 1: Suche nach Überschrift "Final Verdict"
        match_fallback = re.search(r"(#*\s*Final Verdict.*?)(?:\Z)", text, re.DOTALL | re.IGNORECASE)
        if match_fallback:
            return match_fallback.group(1).strip()
            
        # Fallback 2: Gib den gesamten Text zurück
        return text

    # ── GUI-Slot: Ergebnis empfangen ──────────────────────────────────────────
    def _on_result(self, ai_name: str, markdown_text: str):
        """Rendert das Markdown-Ergebnis in der GUI."""
        self.ai_status[ai_name] = "done"

        # Extrahiere nur den Final Verdict und speichere beide Versionen
        final_verdict_text = self._extract_final_verdict(markdown_text)
        
        if ai_name in ["Gemini", "Mistral"]:
            self.full_responses[ai_name] = markdown_text
            self.verdicts[ai_name] = final_verdict_text
            
        self._update_browser_content(ai_name)
        
        if ai_name == "Gemini":
            self.result_tabs.setTabText(0, "Gemini 3.1 ✅")
        elif ai_name == "Mistral":
            self.result_tabs.setTabText(1, "Mistral Large ✅")
        
        self._check_all_done()

    def _update_browser_content(self, ai_name: str):
        """Aktualisiert den Text-Browser basierend auf dem Toggle-Status."""
        if ai_name not in ["Gemini", "Mistral"]:
            return
            
        show_full = self.toggle_details_btn.isChecked()
        content = self.full_responses[ai_name] if show_full else self.verdicts[ai_name]
        
        # HTML erst generieren, wenn wir etwas anzuzeigen haben
        if content:
            html_content = f"{MARKDOWN_CSS}<body>{self._markdown_to_html(content)}</body>"
            if ai_name == "Gemini":
                self.gemini_browser.setHtml(html_content)
            elif ai_name == "Mistral":
                self.mistral_browser.setHtml(html_content)

    def _toggle_details(self):
        """Wechselt zwischen Final Verdict und kompletter Analyse für beide Browser."""
        self._update_browser_content("Gemini")
        self._update_browser_content("Mistral")


    # ── GUI-Slot: Fehler empfangen ────────────────────────────────────────────
    def _on_error(self, ai_name: str, error_text: str):
        """Zeigt eine Fehlermeldung in der GUI an."""
        self.ai_status[ai_name] = "error"

        error_html = f"""
        {MARKDOWN_CSS}
        <div style="padding: 20px;">
            <div style="background-color: #3d1f1f; border: 1px solid #f85149;
                        border-radius: 8px; padding: 16px; margin: 8px 0;">
                {self._markdown_to_html(error_text)}
            </div>
        </div>
        """
        
        if ai_name == "Gemini":
            self.gemini_browser.setHtml(error_html)
            self.result_tabs.setTabText(0, "Gemini 3.1 ❌")
        elif ai_name == "Mistral":
            self.mistral_browser.setHtml(error_html)
            self.result_tabs.setTabText(1, "Mistral Large ❌")
        else: # System-Fehler an beide übergeben
            self.gemini_browser.setHtml(error_html)
            self.mistral_browser.setHtml(error_html)
            self.ai_status["Gemini"] = "error"
            self.ai_status["Mistral"] = "error"

        self._check_all_done()

    # ── Markdown → HTML Konvertierung ─────────────────────────────────────────
    def _markdown_to_html(self, md: str) -> str:
        """Konvertiert Markdown in HTML. Nutzt QTextBrowser.setMarkdown() intern
        oder eine einfache manuelle Konvertierung als Fallback."""
        try:
            # Verwende einen temporären QTextBrowser für die Konvertierung
            temp = QTextBrowser()
            temp.setMarkdown(md)
            return temp.toHtml()
        except Exception:
            # Fallback: einfaches Escaping
            return f"<pre>{md}</pre>"

    # ── Pulsierender Ladebalken ───────────────────────────────────────────────
    def _pulse_progress(self):
        """Animiert den Ladebalken hin und her."""
        self._pulse_value += self._pulse_direction * 2
        if self._pulse_value >= 100:
            self._pulse_direction = -1
        elif self._pulse_value <= 0:
            self._pulse_direction = 1
        self.progress_bar.setValue(self._pulse_value)

    # ── Fenster-Schließen ─────────────────────────────────────────────────────
    def closeEvent(self, event):
        """Räumt auf beim Schließen."""
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        event.accept()


# ── Hauptprogramm ─────────────────────────────────────────────────────────────
def main():
    import os
    # Qt-Monitor-Warnung unter Windows unterdrücken (harmlos)
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.screen=false"

    # High-DPI-Unterstützung
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dunkle Palette setzen (Fusion + Dark)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0d1117"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#c9d1d9"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#161b22"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1c2128"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#c9d1d9"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#21262d"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#c9d1d9"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#58a6ff"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    window = GeoGuessrWindow()
    window.show()

    print("=" * 60)
    print("    GeoGuessr AI Analyzer gestartet!")
    print(f"     Drücke {HOTKEY.upper()} für Screenshot + Analyse")
    print(f"    Modell: {MODEL_NAME}")
    print("=" * 60)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

# ==============================================================================
# ExerciseAI - KI-Lernbegleiter
# ==============================================================================
# Ein hochmodernes Python-Tool, das im Hintergrund läuft und bei Schulaufgaben
# als KI-Lernbegleiter unterstützt.
#
# Benötigte Pakete (pip install):
#     pip install PyQt6 PyQt6-WebEngine google-genai keyboard Pillow markdown2
# ==============================================================================

import sys
import os
import io
import base64
import threading
import traceback
import json

def load_api_key(project_name):
    # Sucht die api_keys.json im übergeordneten AI_Projects Ordner
    key_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api_keys.json")
    try:
        with open(key_file, "r", encoding="utf-8") as f:
            return json.load(f).get(project_name, "")
    except Exception:
        return ""

# Verhindere Absturz durch print() Aufrufe, wenn das Skript per pythonw.exe (ohne Konsole) gestartet wird
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# --- Konfiguration -----------------------------------------------------------
API_KEY = load_api_key("ExerciseAI")
MODEL_NAME = "gemini-3.1-flash-lite-preview"
HOTKEY_FULLSCREEN = "alt+x"
HOTKEY_SNIP = "alt+c"
# ------------------------------------------------------------------------------

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("FEHLER: 'google-genai' ist nicht installiert.")
    print("Bitte installiere es mit:  pip install google-genai")
    sys.exit(1)

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QFrame, QSplitter, QSystemTrayIcon, QMenu,
        QSizePolicy, QProgressBar, QCheckBox, QPushButton, QTextEdit,
        QScrollArea, QLineEdit, QApplication, QComboBox
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QObject, QRect, QPoint, QTimer, QUrl
    from PyQt6.QtGui import QPixmap, QImage, QIcon, QFont, QAction, QColor, QPalette, QPainter, QPen, QBrush
except ImportError:
    print("FEHLER: 'PyQt6' ist nicht installiert.")
    print("Bitte installiere es mit:  pip install PyQt6")
    sys.exit(1)

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    print("FEHLER: 'PyQt6-WebEngine' ist nicht installiert.")
    print("Bitte installiere es mit:  pip install PyQt6-WebEngine")
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

try:
    import markdown2
except ImportError:
    print("FEHLER: 'markdown2' ist nicht installiert.")
    print("Bitte installiere es mit:  pip install markdown2")
    sys.exit(1)


# ── Stylesheet ────────────────────────────────────────────────────────────────
STYLESHEET = """
QMainWindow, QWidget#centralWidget {
    background-color: #0d1117;
    color: #c9d1d9;
}
QLabel {
    color: #c9d1d9;
}
QCheckBox {
    color: #c9d1d9;
    font-size: 14px;
    padding: 4px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #30363d;
    background-color: #161b22;
}
QCheckBox::indicator:checked {
    background-color: #238636;
    border: 1px solid #2ea043;
}
QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #30363d;
    border: 1px solid #8b949e;
}
QPushButton#sendButton {
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
}
QPushButton#sendButton:hover {
    background-color: #2ea043;
}
QLineEdit, QTextEdit {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px;
    font-size: 14px;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #58a6ff;
}
QComboBox {
    background-color: #0d1117;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px;
    font-size: 14px;
}
QComboBox::drop-down {
    border: none;
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
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
        onload="renderMathInElement(document.body, {{
            delimiters: [
                {{left: '$$', right: '$$', display: true}},
                {{left: '$', right: '$', display: false}},
                {{left: '\\\\(', right: '\\\\)', display: false}},
                {{left: '\\\\[', right: '\\\\]', display: true}}
            ]
        }});"></script>
    <style>
        body {{
            font-family: 'Segoe UI', -apple-system, sans-serif;
            color: #c9d1d9;
            background-color: #161b22;
            line-height: 1.6;
            font-size: 15px;
            margin: 0;
            padding: 20px;
        }}
        h1, h2, h3 {{ color: #58a6ff; }}
        code {{
            background-color: #1c2128;
            color: #f0883e;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Cascadia Code', monospace;
        }}
        pre {{
            background-color: #1c2128;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 12px;
            overflow-x: auto;
        }}
        pre code {{
            background-color: transparent;
            color: #c9d1d9;
            padding: 0;
        }}
        blockquote {{
            border-left: 3px solid #58a6ff;
            margin-left: 0;
            padding-left: 12px;
            color: #8b949e;
        }}
        ul, ol {{ padding-left: 20px; }}
        .message-user {{
            background-color: #0d1117;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 16px;
        }}
        .message-ai {{
            background-color: #161b22;
            padding: 12px;
            margin-bottom: 24px;
        }}
        hr {{ border: none; border-top: 1px solid #30363d; margin: 20px 0; }}
    </style>
</head>
<body>
    {content}
</body>
</html>
"""


# ── Signal-Bridge (Thread → GUI) ─────────────────────────────────────────────
class SignalBridge(QObject):
    show_main_window = pyqtSignal(object)  # PIL Image
    show_snipping_tool = pyqtSignal()
    update_chat = pyqtSignal(str)          # HTML Content
    loading_state = pyqtSignal(bool)


# ── Snipping Tool Overlay ─────────────────────────────────────────────────────
class SnippingTool(QWidget):
    """Transparentes Vollbild-Overlay zum Ausschneiden eines Bildschirmbereichs."""
    screenshot_taken = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        
        self.begin = QPoint()
        self.end = QPoint()
        self.is_drawing = False
        self.screen_pixmap = None

    def start_snipping(self):
        screen = QApplication.primaryScreen()
        self.screen_pixmap = screen.grabWindow(0)
        self.setGeometry(screen.geometry())
        self.begin = QPoint()
        self.end = QPoint()
        self.show()
        self.activateWindow()

    def paintEvent(self, event):
        if not self.screen_pixmap:
            return
            
        painter = QPainter(self)
        # 1. Bild des Desktops malen
        painter.drawPixmap(self.rect(), self.screen_pixmap)
        
        # 2. Dunkles Overlay über alles
        overlay_color = QColor(0, 0, 0, 120)
        painter.fillRect(self.rect(), overlay_color)
        
        # 3. Wenn gezogen wird, das Rechteck "ausschneiden"
        if not self.begin.isNull() and not self.end.isNull():
            rect = QRect(self.begin, self.end).normalized()
            # Ausgeschnittenen Bereich in voller Helligkeit malen
            painter.drawPixmap(rect, self.screen_pixmap, rect)
            
            # Rahmen zeichnen
            pen = QPen(QColor(88, 166, 255), 2)
            painter.setPen(pen)
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin = event.pos()
            self.end = self.begin
            self.is_drawing = True
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.close()

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = False
            rect = QRect(self.begin, self.end).normalized()
            self.hide()
            
            if rect.width() > 10 and rect.height() > 10:
                # Screenshot des gewählten Bereichs
                bbox = (rect.x(), rect.y(), rect.right(), rect.bottom())
                try:
                    img = ImageGrab.grab(bbox=bbox)
                    self.screenshot_taken.emit(img)
                except Exception as e:
                    print(f"Fehler beim Snippen: {e}")
            else:
                print("Bereich zu klein.")


# ── Haupt-Fenster ─────────────────────────────────────────────────────────────
class ExerciseAIWindow(QMainWindow):
    def __init__(self, bridge: SignalBridge):
        super().__init__()
        self.bridge = bridge
        self.setWindowTitle("📚 ExerciseAI - KI-Lernbegleiter")
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(STYLESHEET)
        
        self.current_image = None
        self.chat_history = []  # Chat-Verlauf für die API
        self.display_history = "" # Chat-Verlauf als HTML

        # Gemini-Client
        try:
            self.client = genai.Client(api_key=API_KEY)
        except Exception as e:
            self.client = None
            print(f"WARNUNG: Gemini-Client konnte nicht erstellt werden: {e}")

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # ── Linke Seite (Bild & Optionen) ───────────────────────────────────
        left_panel = QWidget()
        left_panel.setFixedWidth(350)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        # Vorschau
        preview_label = QLabel("📸 Screenshot Vorschau")
        preview_label.setStyleSheet("color: #8b949e; font-size: 13px; font-weight: bold;")
        left_layout.addWidget(preview_label)

        self.image_label = QLabel("Kein Bild")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 8px;")
        self.image_label.setMinimumHeight(200)
        left_layout.addWidget(self.image_label)

        # Optionen
        options_label = QLabel("⚙️ Aktionen auswählen:")
        options_label.setStyleSheet("color: #8b949e; font-size: 13px; font-weight: bold; margin-top: 10px;")
        left_layout.addWidget(options_label)

        self.cb_summarize = QCheckBox("Zusammenfassen")
        self.cb_explain = QCheckBox("Erklären")
        self.cb_solve = QCheckBox("Aufgabe Schritt-für-Schritt lösen")
        self.cb_check_errors = QCheckBox("Code/Text auf Fehler prüfen")
        self.cb_translate = QCheckBox("Übersetzen (EN ↔ DE)")

        self.checkboxes = [
            self.cb_summarize, self.cb_explain, self.cb_solve, 
            self.cb_check_errors, self.cb_translate
        ]
        
        for cb in self.checkboxes:
            left_layout.addWidget(cb)

        # Thinking Level Dropdown
        thinking_label = QLabel("🧠 Thinking Level:")
        thinking_label.setStyleSheet("color: #8b949e; font-size: 13px; font-weight: bold; margin-top: 10px;")
        left_layout.addWidget(thinking_label)
        
        self.thinking_combo = QComboBox()
        self.thinking_combo.addItems(["MINIMAL", "LOW", "MEDIUM", "HIGH"])
        self.thinking_combo.setCurrentText("MEDIUM")  # Standardwert
        left_layout.addWidget(self.thinking_combo)

        # Eigene Anweisung (Initialer Prompt-Zusatz)
        self.custom_prompt_input = QLineEdit()
        self.custom_prompt_input.setPlaceholderText("Zusätzliche Anweisungen (optional)...")
        left_layout.addWidget(self.custom_prompt_input)

        # Senden Button
        self.send_btn = QPushButton("🚀 Senden")
        self.send_btn.setObjectName("sendButton")
        self.send_btn.setMinimumHeight(45)
        self.send_btn.clicked.connect(self._on_send_clicked)
        left_layout.addWidget(self.send_btn)
        
        left_layout.addStretch()

        # ── Rechte Seite (Chat & Browser) ───────────────────────────────────
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # WebEngineView für Markdown & KaTeX
        self.web_view = QWebEngineView()
        self.web_view.setHtml(HTML_TEMPLATE.format(
            content="<div style='text-align:center; margin-top: 100px; color:#8b949e;'><h2>Warte auf Screenshot...</h2><p>Drücke Alt+X (Vollbild) oder Alt+C (Ausschnitt)</p></div>"
        ))
        right_layout.addWidget(self.web_view, stretch=1)

        # Ladebalken
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # Indeterminate mode
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)

        # Chat-Input (für Rückfragen)
        chat_input_layout = QHBoxLayout()
        
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Rückfrage stellen (z.B. 'Erkläre Schritt 2 genauer')...")
        self.chat_input.returnPressed.connect(self._on_chat_send_clicked)
        self.chat_input.setEnabled(False) # Erst aktiv nach erstem Bild
        chat_input_layout.addWidget(self.chat_input, stretch=1)

        self.chat_send_btn = QPushButton("Senden")
        self.chat_send_btn.clicked.connect(self._on_chat_send_clicked)
        self.chat_send_btn.setEnabled(False)
        chat_input_layout.addWidget(self.chat_send_btn)

        self.copy_btn = QPushButton("📋 Kopieren")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        chat_input_layout.addWidget(self.copy_btn)

        right_layout.addLayout(chat_input_layout)

        # Zum Main Layout hinzufügen
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, stretch=1)

    def _connect_signals(self):
        self.bridge.show_main_window.connect(self.load_new_screenshot)
        self.bridge.update_chat.connect(self._render_html)
        self.bridge.loading_state.connect(self._set_loading)

    def load_new_screenshot(self, pil_image: Image.Image):
        """Wird aufgerufen, wenn ein neuer Screenshot gemacht wurde."""
        self.showNormal()
        self.activateWindow()
        self.raise_()
        
        self.current_image = pil_image
        self.chat_history.clear() # Reset chat
        self.display_history = ""
        
        self.chat_input.setEnabled(False)
        self.chat_send_btn.setEnabled(False)
        
        self._render_html("<div style='text-align:center; margin-top: 100px; color:#8b949e;'><h2>Screenshot geladen!</h2><p>Wähle links die Aktionen aus und klicke auf 'Senden'.</p></div>")

        # PIL -> QPixmap für Vorschau
        try:
            img_buffer = io.BytesIO()
            pil_image.save(img_buffer, format="PNG")
            qimage = QImage()
            qimage.loadFromData(img_buffer.getvalue())
            pixmap = QPixmap.fromImage(qimage)
            
            scaled = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
        except Exception as e:
            print(f"Bildvorschau Fehler: {e}")

    def _build_initial_prompt(self):
        actions = []
        if self.cb_summarize.isChecked(): actions.append("Zusammenfassen")
        if self.cb_explain.isChecked(): actions.append("Erklären")
        if self.cb_solve.isChecked(): actions.append("Aufgabe Schritt-für-Schritt lösen")
        if self.cb_check_errors.isChecked(): actions.append("Code/Text auf Fehler prüfen")
        if self.cb_translate.isChecked(): actions.append("Übersetzen (zu Deutsch)")
        
        if not actions:
            actions = ["Bitte analysiere das Bild."]

        prompt = "Du bist ein hilfreicher KI-Lernbegleiter. Bitte führe folgende Aktionen für das Bild aus:\n"
        for act in actions:
            prompt += f"- {act}\n"
            
        custom = self.custom_prompt_input.text().strip()
        if custom:
            prompt += f"\nZusätzliche Anweisung: {custom}\n"
            
        #prompt += "\nVerwende zwingend sauberes Markdown und LaTeX für mathematische Formeln. Formeln müssen in $$ (für Blöcke) oder $ (inline) stehen."
        return prompt

    def _on_send_clicked(self):
        """Initialer Aufruf mit Bild."""
        if not self.current_image:
            return
            
        prompt = self._build_initial_prompt()
        thinking_lvl = self.thinking_combo.currentText()
        self._append_to_display("user", "<i>[Bild gesendet]</i><br>" + prompt.replace("\n", "<br>"))
        
        self.bridge.loading_state.emit(True)
        threading.Thread(target=self._api_worker_initial, args=(prompt, thinking_lvl), daemon=True).start()

    def _on_chat_send_clicked(self):
        """Folge-Aufruf (Chat) ohne neues Bild, aber mit History."""
        text = self.chat_input.text().strip()
        if not text: return
        
        self.chat_input.clear()
        thinking_lvl = self.thinking_combo.currentText()
        self._append_to_display("user", text)
        
        self.bridge.loading_state.emit(True)
        threading.Thread(target=self._api_worker_chat, args=(text, thinking_lvl), daemon=True).start()

    def _api_worker_initial(self, prompt: str, thinking_level: str):
        try:
            if not self.client:
                raise Exception("API-Client nicht initialisiert. API-Key prüfen!")

            # Bild vorbereiten
            img_buffer = io.BytesIO()
            self.current_image.save(img_buffer, format="JPEG", quality=85)
            img_bytes = img_buffer.getvalue()
            
            # Die SDK erfordert ein PIL Image Objekt direkt oder Base64 (hier PIL Image)
            # Config erstellen
            config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level=thinking_level)
            )
            
            # Wir starten eine neue Chat-Session
            self.chat = self.client.chats.create(model=MODEL_NAME, config=config)
            
            # Erster Aufruf: Bild + Text
            response = self.chat.send_message([self.current_image, prompt])
            
            if response.text:
                self._append_to_display("ai", response.text)
            else:
                self._append_to_display("ai", "<i>Keine Antwort erhalten.</i>")
                
        except Exception as e:
            self._append_to_display("ai", f"<b>❌ Fehler:</b> {str(e)}\n\n```\n{traceback.format_exc()}\n```")
        finally:
            self.bridge.loading_state.emit(False)

    def _api_worker_chat(self, text: str, thinking_level: str):
        try:
            if not hasattr(self, 'chat') or not self.chat:
                raise Exception("Keine aktive Chat-Session.")
                
            config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level=thinking_level)
            )
            response = self.chat.send_message(text, config=config)
            
            if response.text:
                self._append_to_display("ai", response.text)
            else:
                self._append_to_display("ai", "<i>Keine Antwort erhalten.</i>")
        except Exception as e:
            self._append_to_display("ai", f"<b>❌ Fehler:</b> {str(e)}")
        finally:
            self.bridge.loading_state.emit(False)

    def _append_to_display(self, role: str, raw_text: str):
        if role == "user":
            html_chunk = f"<div class='message-user'><b>Du:</b><br>{raw_text}</div>"
        else:
            # Markdown -> HTML
            md_html = markdown2.markdown(raw_text, extras=["fenced-code-blocks", "tables", "break-on-newline"])
            html_chunk = f"<div class='message-ai'><b>KI-Lernbegleiter:</b><br>{md_html}</div><hr>"
            
            # Speichere letzten AI Text für Zwischenablage
            self._last_ai_text = raw_text 

        self.display_history += html_chunk
        self.bridge.update_chat.emit(self.display_history)

    def _render_html(self, html_content: str):
        full_html = HTML_TEMPLATE.format(content=html_content)
        self.web_view.setHtml(full_html)
        
        # Enable Chat if AI replied
        if "message-ai" in html_content:
            self.chat_input.setEnabled(True)
            self.chat_send_btn.setEnabled(True)
            self.chat_input.setFocus()

    def _set_loading(self, is_loading: bool):
        self.progress_bar.setVisible(is_loading)
        self.send_btn.setEnabled(not is_loading)
        self.chat_send_btn.setEnabled(not is_loading)
        if is_loading:
            self.send_btn.setText("⏳ Lädt...")
        else:
            self.send_btn.setText("🚀 Senden")

    def _copy_to_clipboard(self):
        if hasattr(self, '_last_ai_text'):
            QApplication.clipboard().setText(self._last_ai_text)
            self.copy_btn.setText("✅ Kopiert!")
            QTimer.singleShot(2000, lambda: self.copy_btn.setText("📋 Kopieren"))

    def closeEvent(self, event):
        """Verstecken statt schließen, da Background-App."""
        event.ignore()
        self.hide()


# ── System Tray & App Controller ─────────────────────────────────────────────
class ExerciseAIApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False) # WICHTIG: App läuft im Hintergrund weiter
        
        self.bridge = SignalBridge()
        
        # Hauptfenster
        self.window = ExerciseAIWindow(self.bridge)
        
        # Snipping Tool
        self.snipper = SnippingTool()
        self.snipper.screenshot_taken.connect(self._on_snip_taken)

        # Tray Icon Setup
        self.tray_icon = QSystemTrayIcon()
        # Erzeuge ein simples Icon programmgesteuert (blaues Quadrat mit Text)
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setBrush(QColor(88, 166, 255))
        painter.drawRoundedRect(0, 0, 64, 64, 12, 12)
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "AI")
        painter.end()
        self.tray_icon.setIcon(QIcon(pixmap))
        
        # Tray Menu
        self.tray_menu = QMenu()
        
        self.action_show = QAction("Anzeigen")
        self.action_show.triggered.connect(self._force_show)
        self.tray_menu.addAction(self.action_show)
        
        self.action_pause = QAction("Pausieren (Hotkeys aus)")
        self.action_pause.setCheckable(True)
        self.action_pause.toggled.connect(self._toggle_pause)
        self.tray_menu.addAction(self.action_pause)
        
        self.tray_menu.addSeparator()
        
        self.action_quit = QAction("Beenden")
        self.action_quit.triggered.connect(self.quit_app)
        self.tray_menu.addAction(self.action_quit)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()
        
        # Hotkeys registrieren
        self._register_hotkeys()
        
        self.is_paused = False

    def _register_hotkeys(self):
        try:
            keyboard.add_hotkey(HOTKEY_FULLSCREEN, self._trigger_fullscreen_shot)
            keyboard.add_hotkey(HOTKEY_SNIP, self._trigger_snipping_tool)
            print(f"[INFO] Hotkeys registriert: Vollbild ({HOTKEY_FULLSCREEN}), Snipping ({HOTKEY_SNIP})")
        except Exception as e:
            print(f"[FEHLER] Hotkeys konnten nicht registriert werden: {e}")

    def _toggle_pause(self, checked):
        self.is_paused = checked
        if checked:
            keyboard.unhook_all()
            self.tray_icon.showMessage("ExerciseAI", "Pausiert. Hotkeys sind deaktiviert.", QSystemTrayIcon.MessageIcon.Warning, 2000)
        else:
            self._register_hotkeys()
            self.tray_icon.showMessage("ExerciseAI", "Aktiv. Hotkeys sind bereit.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def _force_show(self):
        self.window.showNormal()
        self.window.activateWindow()
        self.window.raise_()

    def _trigger_fullscreen_shot(self):
        if self.is_paused: return
        print("Vollbild-Screenshot ausgelöst.")
        # Muss im MainThread via Signal ausgeführt werden, falls wir UI-Elemente anfassen
        img = ImageGrab.grab()
        self.bridge.show_main_window.emit(img)

    def _trigger_snipping_tool(self):
        if self.is_paused: return
        print("Snipping Tool ausgelöst.")
        # PyQt Widgets dürfen nur im MainThread erzeugt/angezeigt werden
        self.bridge.show_snipping_tool.emit()

    def _on_snip_taken(self, img):
        self.bridge.show_main_window.emit(img)

    def quit_app(self):
        try:
            keyboard.unhook_all()
        except:
            pass
        self.tray_icon.hide()
        self.app.quit()

    def run(self):
        # Verbinde die Bridge für Thread-Sicherheit
        self.bridge.show_snipping_tool.connect(self.snipper.start_snipping)
        
        print("=" * 60)
        print("    ExerciseAI - KI-Lernbegleiter gestartet!")
        print("    Läuft im Hintergrund (siehe System Tray).")
        print(f"    - {HOTKEY_FULLSCREEN}: Vollbild aufnehmen")
        print(f"    - {HOTKEY_SNIP}: Bereich ausschneiden")
        print("=" * 60)
        
        self.tray_icon.showMessage("ExerciseAI Gestartet", f"Hotkeys bereit:\n{HOTKEY_FULLSCREEN} für Vollbild\n{HOTKEY_SNIP} für Ausschnitt", QSystemTrayIcon.MessageIcon.Information, 3000)
        
        return self.app.exec()


if __name__ == "__main__":
    import os
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.screen=false"
    # Unterdrückt die harmlosen Chromium/GPU-Fehlermeldungen im Hintergrund
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-logging --log-level=3"
    
    try:
        app_controller = ExerciseAIApp()
        sys.exit(app_controller.run())
    except Exception as e:
        # Crash-Log schreiben, damit man Fehler auch ohne Konsole debuggen kann
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        sys.exit(1)

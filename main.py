import sys
import re
from typing import List
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QVBoxLayout, QPushButton, QLabel, QMessageBox
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import speech_recognition as sr

BTN_IDLE_STYLE = "color: gray; background-color: #f0f0f0; border-radius: 5px;"
BTN_PLAYED_BG = "#e6e6e6"
COLOR_X = "#0078d7"
COLOR_O = "#d70000"

# wątek, który nasłuchuje mikrofon
class VoiceListener(QThread):
    command = pyqtSignal(str)  # rozpoznanie tekstu
    status = pyqtSignal(str)   # status do pokazania w labelu

    def __init__(self, language: str = "pl-PL", parent=None):
        super().__init__(parent)
        self.language = language
        self._running = True
        self.recognizer = sr.Recognizer()

    # zakończenie wątku nasłuchu
    def stop(self):
        self._running = False

    # głowna funkcja: kalibracja -> i fru do Googla
    def run(self):
        try:
            with sr.Microphone() as source:
                self.status.emit("Kalibracja mikrofonu...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.6)
                self.status.emit("Powiedz cyfre")

                while self._running:
                    try:
                        audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=3)
                    except sr.WaitTimeoutError:
                        continue

                    try:
                        text = self.recognizer.recognize_google(audio, language=self.language)
                        self.command.emit(text.strip().lower())
                    except sr.UnknownValueError:
                        self.status.emit("Nie zrozumiałem. Spróbuj jeszcze raz.")

        except Exception as e:
            # pojawiał sie gdy mieliśmy python 3.13
            # na 3.12 nie ma takich problemów
            self.status.emit(f"Błąd mikrofonu: {e}")


class TicTacToe(QMainWindow):
    # budowanie interfejsu
    def __init__(self):
        super().__init__()
        self.label = None
        self.setWindowTitle("Tic-Tac-Toe")
        self.current: str = "X"
        self.board: List[str] = [""] * 9
        self.buttons: List[QPushButton] = []
        self.init_ui()
        # wątek nasłuchu głosu
        self.voice_thread = None
        self.start_voice()

    def init_ui(self):
        # główny widget
        w = QWidget()
        self.setCentralWidget(w)
        layout = QVBoxLayout()
        w.setLayout(layout)

        # tura i statusy
        self.label = QLabel(f"Tura gracza: {self.current}")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(QFont("Arial", 16))
        layout.addWidget(self.label)

        grid = QGridLayout()
        layout.addLayout(grid)

        # buttony
        for i in range(9):
            b = QPushButton(str(i + 1))
            b.setFont(QFont("Arial", 24))
            b.setMinimumSize(100, 100)
            b.setStyleSheet(BTN_IDLE_STYLE)
            b.clicked.connect(lambda _, x=i: self.make_move(x))
            grid.addWidget(b, i // 3, i % 3)
            self.buttons.append(b)

        # przycisk resetu gry
        r = QPushButton("Nowa gra")
        r.setFont(QFont("Arial", 14))
        r.clicked.connect(self.reset_game)
        layout.addWidget(r)

        self.update_turn_label()

    # start wątku nasłuchu i podpięcie sygnałów
    def start_voice(self):
        self.voice_thread = VoiceListener(language="pl-PL", parent=self)
        self.voice_thread.status.connect(self.on_voice_status)
        self.voice_thread.command.connect(self.on_voice_command)
        self.voice_thread.start()

    # label z aktualna turą
    def update_turn_label(self):
        self.label.setText(f"Tura gracza: {self.current}\n")

    # label z aktualna tura + tekst pomocniczy
    def set_status(self, text: str):
        self.label.setText(f"Tura gracza: {self.current}\n{text}")

    # przywrócenie stylu pola "błędzie" - zajęte pole
    def reset_button_style(self, i: int, symbol: str):
        color = COLOR_X if symbol == "X" else COLOR_O
        self.buttons[i].setStyleSheet(f"color: {color}; background-color: {BTN_PLAYED_BG};")

    def parse_move(self, text: str):
        t = (text or "").strip().lower()

        # szuka cyfre
        m = re.search(r"\b([1-9])\b", t)
        if m:
            return int(m.group(1)) - 1  # 1..9 -> 0..8

        # a dopiero słowa
        words = {"jeden": 1, "dwa": 2, "trzy": 3,
                 "cztery": 4, "pięć": 5, "piec": 5, "sześć": 6, "szesc": 6,
                 "siedem": 7, "osiem": 8, "dziewięć": 9, "dziewiec": 9,}

        for w, n in words.items():
            if re.search(rf"\b{re.escape(w)}\b", t):
                return n - 1

        # pozycje opisowe
        if "środek" in t or "srodek" in t or "centrum" in t:
            return 4

        left = ("lewy" in t) or ("lewa" in t) or ("lewo" in t)
        right = ("prawy" in t) or ("prawa" in t) or ("prawo" in t)
        top = ("gór" in t) or ("gor" in t) or ("góra" in t) or ("gora" in t)
        bottom = ("dół" in t) or ("dol" in t) or ("dolny" in t)

        # narożniki - 1, 3, 7, 9
        if left and top:
            return 0
        if right and top:
            return 2
        if left and bottom:
            return 6
        if right and bottom:
            return 8

        # krawędzie - 2, 4, 6, 8
        if top and not left and not right:
            return 1
        if bottom and not left and not right:
            return 7
        if left and not top and not bottom:
            return 3
        if right and not top and not bottom:
            return 5

        return None

    # odbiór statusu z VoiceListener - błędy
    def on_voice_status(self, text: str):
        self.set_status(text)

    # odbiór rozpoznanej komendy z VoiceListener i wykonanie ruchu
    def on_voice_command(self, text: str):
        idx = self.parse_move(text)
        if idx is None:
            self.set_status(f"Nie rozpoznano: '{text}'")
            return

        self.make_move(idx)

    def make_move(self, i: int):
        # wskaznik zajetego pola
        if self.board[i] != "":
            self.set_status(f"Pole {i + 1} zajęte")
            self.buttons[i].setStyleSheet("color: white; background-color: #d70000; font-weight: bold;")
            symbol = self.board[i]  # poprawiony bug z kolorem
            QTimer.singleShot(2000, lambda idx=i, s=symbol: self.reset_button_style(idx, s))
            return

        # ustawiamy znak na planszy
        self.board[i] = self.current
        self.buttons[i].setText(self.current)
        self.buttons[i].setFont(QFont("Arial", 36, QFont.Weight.Bold))

        color = COLOR_X if self.current == "X" else COLOR_O
        self.buttons[i].setStyleSheet(f"color: {color}; background-color: {BTN_PLAYED_BG};")

        # sprawdzamy wygrana
        winning_line = self.check_win()
        if winning_line:
            self.highlight_win(winning_line)
            self.msg(f"Gracz {self.current} wygrywa!")
            self.reset_game()
        elif "" not in self.board:
            self.msg("Remis!")
            self.reset_game()
        else:
            self.current = "O" if self.current == "X" else "X"
            self.update_turn_label()

    # kombinacje wygranych
    def check_win(self):
        combinations = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],
            [0, 3, 6], [1, 4, 7], [2, 5, 8],
            [0, 4, 8], [2, 4, 6]
        ]
        for a, b, c in combinations:
            if self.board[a] == self.board[b] == self.board[c] and self.board[a] != "":
                return [a, b, c]
        return None

    # podświetlenie wygranej
    def highlight_win(self, indices: List[int]):
        for index in indices:
            self.buttons[index].setStyleSheet("color: white; background-color: #28a745; font-weight: bold;")

    # wiadomosc konczaca
    def msg(self, text: str):
        m = QMessageBox()
        m.setWindowTitle("Koniec gry")
        m.setIcon(QMessageBox.Icon.Information)
        m.setText(text)
        m.exec()

    # resetowanie stanu gry
    def reset_game(self):
        self.current = "X"
        self.board = [""] * 9
        for i, b in enumerate(self.buttons):
            b.setText(str(i + 1))
            b.setFont(QFont("Arial", 24))
            b.setStyleSheet(BTN_IDLE_STYLE)

        self.update_turn_label()

    # koniec nasłuchu
    def closeEvent(self, event):
        if self.voice_thread and self.voice_thread.isRunning():
            self.voice_thread.stop()
            self.voice_thread.wait(1500)
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    g = TicTacToe()
    g.show()
    sys.exit(app.exec())
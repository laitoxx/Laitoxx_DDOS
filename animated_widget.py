import random
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QFont, QPainter, QColor
from PyQt5.QtCore import QTimer

class DigitalRainWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 600)

        # Animation settings
        self.font_size = 12
        self.font = QFont("Monospace", self.font_size, QFont.Bold)
        self.katakana = [chr(i) for i in range(0x30a0, 0x30ff + 1)] # Katakana characters
        self.streams = []

        # Theming
        self.background_color = QColor(0, 0, 0)
        self.stream_color = QColor(0, 255, 0) # Default green
        self.head_char_color = QColor(200, 255, 200)

        # Timer for animation
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_streams)
        self.timer.start(50) # Update every 50ms

    def resizeEvent(self, event):
        """Initialize streams when the widget is first shown or resized."""
        super().resizeEvent(event)
        font_metrics = self.fontMetrics()
        num_cols = self.width() // font_metrics.averageCharWidth()
        
        self.streams = []
        for i in range(num_cols):
            self.streams.append(self._create_stream(i * font_metrics.averageCharWidth()))

    def _create_stream(self, x_pos):
        """Helper to create a single stream of characters."""
        stream_length = random.randint(10, 30)
        speed = random.randint(5, 15)
        return {
            "chars": [random.choice(self.katakana) for _ in range(stream_length)],
            "y_pos": -random.randint(0, self.height()), # Start off-screen
            "x_pos": x_pos,
            "speed": speed,
            "length": stream_length
        }

    def paintEvent(self, event):
        """Draws the animation frame."""
        painter = QPainter(self)
        painter.setFont(self.font)
        painter.fillRect(self.rect(), self.background_color)

        for stream in self.streams:
            y = stream["y_pos"]
            for i, char in enumerate(stream["chars"]):
                # Set color based on position in the stream
                if i == stream["length"] - 1: # Head character
                    painter.setPen(self.head_char_color)
                else:
                    # Fade the tail
                    alpha = (i / stream["length"]) * 255
                    fade_color = QColor(self.stream_color)
                    fade_color.setAlpha(int(alpha))
                    painter.setPen(fade_color)
                
                painter.drawText(stream["x_pos"], y, str(char))
                y -= self.font_size
    
    def update_streams(self):
        """Updates the position of each stream for the next frame."""
        for stream in self.streams:
            stream["y_pos"] += stream["speed"]
            # Reset stream if it's off-screen
            if stream["y_pos"] - (stream["length"] * self.font_size) > self.height():
                stream["y_pos"] = -random.randint(0, 100)
                stream["chars"] = [random.choice(self.katakana) for _ in range(stream["length"])]

        self.update() # Triggers a repaint

    def set_animation_theme(self, theme_name):
        """Sets the color theme for the animation."""
        if theme_name == "Matrix":
            self.background_color = QColor(0, 0, 0)
            self.stream_color = QColor(0, 255, 0)
            self.head_char_color = QColor(200, 255, 200)
        elif theme_name == "Blue":
            self.background_color = QColor(0, 0, 15)
            self.stream_color = QColor(0, 80, 255)
            self.head_char_color = QColor(180, 200, 255)
        elif theme_name == "Red Alert":
            self.background_color = QColor(15, 0, 0)
            self.stream_color = QColor(255, 0, 0)
            self.head_char_color = QColor(255, 180, 180)
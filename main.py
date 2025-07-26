import sys
import os
import asyncio
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QComboBox, QLineEdit, QPushButton, QLabel, QTextEdit, QFrame,
                             QFileDialog, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer

# --- Import Backend and New Animation Widget ---
from backend import (get_available_attacks, create_attack, stop_attack, force_stop_attack,
                     setup_logger, CustomLogHandler, logger, debug_logger, stop_event)
import logging
from animated_widget import DigitalRainWidget

class Worker(QObject):
    finished = pyqtSignal()
    log = pyqtSignal(str)
    debug_log = pyqtSignal(str)

    def __init__(self, attack_params):
        super().__init__()
        self.attack_params = attack_params
        self.attack_instance = None
        self.is_async = False
        self.async_loop = None

    def run(self):
        """This method starts the attack orchestration."""
        info_handler = CustomLogHandler(self.log.emit)
        setup_logger(info_handler, logger, logging.INFO)
        
        debug_handler = CustomLogHandler(self.debug_log.emit)
        setup_logger(debug_handler, debug_logger, logging.DEBUG)

        self.attack_instance, self.is_async = create_attack(self.attack_params)

        if not self.attack_instance:
            self.log.emit("Failed to create attack. Check parameters.")
            self.finished.emit()
            return

        self.log.emit(f"Starting attack on {self.attack_params['target']}...")

        try:
            if self.is_async:
                self.run_async_attack()
            else:
                # This now correctly calls the blocking method in backend
                self.attack_instance.run_sync_attack()
        except Exception as e:
            self.log.emit(f"An error occurred during attack: {e}")
        finally:
            self.log.emit("Worker has finished its job.")
            self.finished.emit()

    def run_async_attack(self):
        """Starts L7 attacks in a new event loop."""
        self.async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_loop)
        try:
            self.log.emit("Async attack loop started.")
            # The task is created and the loop runs until stop() is called
            self.async_loop.create_task(self.attack_instance.start_async())
            self.async_loop.run_forever()
        finally:
            self.debug_log.emit("Async loop stopping...")
            tasks = asyncio.all_tasks(loop=self.async_loop)
            for task in tasks:
                task.cancel()
            group = asyncio.gather(*tasks, return_exceptions=True)
            self.async_loop.run_until_complete(group)
            self.async_loop.close()
            self.log.emit("Async attack loop finished.")

    def stop(self):
        """Stops the attack gracefully."""
        if not stop_event.is_set():
            self.log.emit("Stopping attack...")
            stop_attack() # This sets the global stop_event

        if self.is_async:
            if self.attack_instance:
                self.attack_instance.stop_async()
            if self.async_loop and self.async_loop.is_running():
                # This will stop 'run_forever' and allow the 'run' method to finish
                self.async_loop.call_soon_threadsafe(self.async_loop.stop)
        # For sync attacks, setting the stop_event is enough to unblock wait()
        
        # The 'finished' signal is now emitted in the 'run' method's finally block

class LaitoxxDDoSGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Laitoxx DDoS Tool")
        self.setGeometry(100, 100, 850, 750)
        self.setMinimumSize(850, 750)

        self.attack_in_progress = False
        self.worker_thread = None
        self.worker = None
        self.attack_timer = None
        self.proxy_list = []

        self.animation_widget = DigitalRainWidget(self)
        self.setCentralWidget(self.animation_widget)

        self.overlay_widget = QWidget(self)
        self.overlay_widget.setStyleSheet("background-color: rgba(0, 0, 0, 0.75);")
        self.main_layout = QVBoxLayout(self.overlay_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        self.title_label = QLabel("Laitoxx")
        self.title_label.setObjectName("title_label")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.title_label)

        self.controls_frame = QFrame()
        self.main_layout.addWidget(self.controls_frame)
        self.controls_layout = QVBoxLayout(self.controls_frame)

        # ... (existing controls) ...
        self.selection_layout = QHBoxLayout()
        self.layer_label = QLabel("Attack Layer:")
        self.layer_combo = QComboBox()
        self.layer_combo.addItems(["Layer 4", "Layer 7"]) # L3 proxying is not practical
        self.method_label = QLabel("Attack Method:")
        self.method_combo = QComboBox()
        self.selection_layout.addWidget(self.layer_label)
        self.selection_layout.addWidget(self.layer_combo)
        self.selection_layout.addSpacing(20)
        self.selection_layout.addWidget(self.method_label)
        self.selection_layout.addWidget(self.method_combo)
        self.controls_layout.addLayout(self.selection_layout)
        
        self.target_layout = QHBoxLayout()
        self.target_label = QLabel("Target (IP/URL):")
        self.target_input = QLineEdit()
        self.target_layout.addWidget(self.target_label)
        self.target_layout.addWidget(self.target_input)
        self.controls_layout.addLayout(self.target_layout)

        self.params_layout = QHBoxLayout()
        self.port_label = QLabel("Port:")
        self.port_input = QLineEdit("80")
        self.port_input.setFixedWidth(80)
        self.threads_label = QLabel("Threads:")
        self.threads_input = QLineEdit("100")
        self.threads_input.setFixedWidth(80)
        self.duration_label = QLabel("Duration (s):")
        self.duration_input = QLineEdit("60")
        self.duration_input.setFixedWidth(80)
        self.params_layout.addWidget(self.port_label)
        self.params_layout.addWidget(self.port_input)
        self.params_layout.addStretch()
        self.params_layout.addWidget(self.threads_label)
        self.params_layout.addWidget(self.threads_input)
        self.params_layout.addStretch()
        self.params_layout.addWidget(self.duration_label)
        self.params_layout.addWidget(self.duration_input)
        self.controls_layout.addLayout(self.params_layout)

        # --- Proxy Controls ---
        self.proxy_layout = QHBoxLayout()
        self.use_proxy_checkbox = QCheckBox("Use Proxy")
        self.proxy_type_label = QLabel("Proxy Type:")
        self.proxy_type_combo = QComboBox()
        self.proxy_type_combo.addItems(["SOCKS4", "SOCKS5"])
        self.load_proxy_button = QPushButton("Load Proxies")
        self.proxy_count_label = QLabel("Loaded: 0")
        
        self.proxy_layout.addWidget(self.use_proxy_checkbox)
        self.proxy_layout.addSpacing(10)
        self.proxy_layout.addWidget(self.proxy_type_label)
        self.proxy_layout.addWidget(self.proxy_type_combo)
        self.proxy_layout.addSpacing(10)
        self.proxy_layout.addWidget(self.load_proxy_button)
        self.proxy_layout.addSpacing(10)
        self.proxy_layout.addWidget(self.proxy_count_label)
        self.proxy_layout.addStretch()
        self.controls_layout.addLayout(self.proxy_layout)

        # --- Action Buttons ---
        self.buttons_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Attack")
        self.stop_button = QPushButton("Stop Attack")
        self.force_stop_button = QPushButton("Stop & Queit")
        self.toggle_debug_button = QPushButton("Console Logs")
        self.stop_button.setEnabled(False)
        self.force_stop_button.setEnabled(False)
        self.buttons_layout.addWidget(self.start_button)
        self.buttons_layout.addWidget(self.stop_button)
        self.buttons_layout.addWidget(self.force_stop_button)
        self.buttons_layout.addWidget(self.toggle_debug_button)
        self.controls_layout.addLayout(self.buttons_layout)

        # ... (rest of the UI) ...
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.main_layout.addWidget(self.log_output)
        self.debug_log_output = QTextEdit()
        self.debug_log_output.setReadOnly(True)
        self.debug_log_output.setVisible(False)
        self.main_layout.addWidget(self.debug_log_output)
        self.theme_layout = QHBoxLayout()
        self.theme_label = QLabel("Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark (Default)", "Light", "Matrix"])
        self.anim_theme_label = QLabel("Animation Theme:")
        self.anim_theme_combo = QComboBox()
        self.anim_theme_combo.addItems(["Matrix", "Blue", "Red Alert"])
        self.theme_layout.addWidget(self.theme_label)
        self.theme_layout.addWidget(self.theme_combo)
        self.theme_layout.addSpacing(20)
        self.theme_layout.addWidget(self.anim_theme_label)
        self.theme_layout.addWidget(self.anim_theme_combo)
        self.main_layout.addLayout(self.theme_layout)

        # --- Connect Signals ---
        self.layer_combo.currentTextChanged.connect(self.update_methods)
        self.start_button.clicked.connect(self.start_attack)
        self.stop_button.clicked.connect(self.stop_attack_thread)
        self.force_stop_button.clicked.connect(self.force_stop_attack_thread)
        self.toggle_debug_button.clicked.connect(self.toggle_debug_console)
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        self.anim_theme_combo.currentTextChanged.connect(self.animation_widget.set_animation_theme)
        self.load_proxy_button.clicked.connect(self.load_proxies)
        
        self.update_methods(self.layer_combo.currentText())
        self.apply_theme("Dark (Default)")
        self.animation_widget.set_animation_theme("Matrix")

    def load_proxies(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Proxy File", "", "Text Files (*.txt);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    self.proxy_list = [line.strip() for line in f if line.strip()]
                self.proxy_count_label.setText(f"Loaded: {len(self.proxy_list)}")
                self.update_log(f"Successfully loaded {len(self.proxy_list)} proxies.")
            except Exception as e:
                self.update_log(f"Error loading proxy file: {e}")

    def start_attack(self):
        if self.attack_in_progress:
            self.update_log("An attack is already in progress.")
            return

        attack_params = {
            "method": self.method_combo.currentText(),
            "target": self.target_input.text(),
            "port": int(self.port_input.text()) if self.port_input.text().isdigit() else 80,
            "threads": int(self.threads_input.text()) if self.threads_input.text().isdigit() else 100,
            "duration": int(self.duration_input.text()) if self.duration_input.text().isdigit() else 60,
            "use_proxy": self.use_proxy_checkbox.isChecked(),
            "proxy_type": self.proxy_type_combo.currentText().lower(),
            "proxy_list": self.proxy_list
        }

        if attack_params["use_proxy"] and not self.proxy_list:
            self.update_log("Proxy is enabled, but no proxies are loaded.")
            return

        self.log_output.clear()
        self.debug_log_output.clear()
        self.update_log("Initializing attack...")

        self.worker_thread = QThread()
        self.worker = Worker(attack_params)
        self.worker.moveToThread(self.worker_thread)
        
        # --- Robust Thread Management ---
        self.worker.log.connect(self.update_log)
        self.worker.debug_log.connect(self.update_debug_log)
        self.worker.finished.connect(self.on_attack_finished_ui) # Update UI when worker is done
        self.worker.finished.connect(self.worker_thread.quit) # Tell thread's event loop to quit
        self.worker_thread.finished.connect(self.worker.deleteLater) # Schedule worker for deletion
        self.worker_thread.finished.connect(self.worker_thread.deleteLater) # Schedule thread for deletion

        self.worker_thread.started.connect(self.worker.run)
        
        self.attack_timer = QTimer(self)
        self.attack_timer.setSingleShot(True)
        self.attack_timer.timeout.connect(self.stop_attack_thread)
        self.attack_timer.start(attack_params['duration'] * 1000)

        self.worker_thread.start()
        
        self.attack_in_progress = True
        self.set_controls_enabled(False)

    def set_controls_enabled(self, enabled):
        self.start_button.setEnabled(enabled)
        self.stop_button.setEnabled(not enabled)
        self.force_stop_button.setEnabled(not enabled)
        self.layer_combo.setEnabled(enabled)
        self.method_combo.setEnabled(enabled)
        self.target_input.setEnabled(enabled)
        self.port_input.setEnabled(enabled)
        self.threads_input.setEnabled(enabled)
        self.duration_input.setEnabled(enabled)
        self.use_proxy_checkbox.setEnabled(enabled)
        self.proxy_type_combo.setEnabled(enabled)
        self.load_proxy_button.setEnabled(enabled)

    def stop_attack_thread(self):
        if self.attack_timer and self.attack_timer.isActive():
            self.attack_timer.stop()
        if self.worker:
            # This will trigger the whole stop sequence
            self.worker.stop()
        self.stop_button.setEnabled(False)
        self.force_stop_button.setEnabled(False)

    def on_attack_finished_ui(self):
        """This method only handles GUI updates after the attack is finished."""
        self.update_log("Attack has terminated.")
        if self.attack_timer and self.attack_timer.isActive():
            self.attack_timer.stop()
        
        self.attack_in_progress = False
        self.set_controls_enabled(True)

    def update_log(self, message):
        self.log_output.append(message)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def update_debug_log(self, message):
        self.debug_log_output.append(message)
        self.debug_log_output.verticalScrollBar().setValue(self.debug_log_output.verticalScrollBar().maximum())

    def toggle_debug_console(self):
        self.debug_log_output.setVisible(not self.debug_log_output.isVisible())

    def update_methods(self, layer):
        self.method_combo.clear()
        methods = get_available_attacks(layer)
        self.method_combo.addItems(methods)
        is_l7 = (layer == "Layer 7")
        self.port_label.setVisible(not is_l7)
        self.port_input.setVisible(not is_l7)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay_widget.setGeometry(self.rect())

    def apply_theme(self, theme_name):
        script_dir = os.path.dirname(os.path.realpath(__file__))
        qss_file = ""
        if theme_name == "Light":
            qss_file = os.path.join(script_dir, "themes", "light.qss")
            self.overlay_widget.setStyleSheet("background-color: rgba(240, 240, 240, 0.85);")
        elif theme_name == "Matrix":
            qss_file = os.path.join(script_dir, "themes", "matrix.qss")
            self.overlay_widget.setStyleSheet("background-color: rgba(0, 0, 0, 0.8);")
        else: # Dark
            qss_file = os.path.join(script_dir, "themes", "dark.qss")
            self.overlay_widget.setStyleSheet("background-color: rgba(0, 0, 0, 0.75);")
            
        if os.path.exists(qss_file):
            with open(qss_file, "r") as f:
                self.setStyleSheet(f.read())

    def force_stop_attack_thread(self):
        if self.attack_in_progress:
            self.update_log("Force stopping... Application will terminate.")
            force_stop_attack()
            QTimer.singleShot(500, lambda: os._exit(1))

    def closeEvent(self, event):
        if self.attack_in_progress and self.worker:
            self.worker.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = LaitoxxDDoSGUI()
    main_window.show()
    sys.exit(app.exec_())

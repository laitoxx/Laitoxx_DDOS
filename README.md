# Laitoxx DDoS Tool

A graphical interface for network stress testing and DDoS attacks, built with PyQt5.

---

### 🇷🇺 Русский

Laitoxx DDoS Tool — это приложение с графическим интерфейсом для проведения стресс-тестирования сетей и моделирования DDoS-атак. Инструмент создан с использованием PyQt5 и предоставляет удобный интерфейс для настройки и запуска различных типов атак.

### 🇬🇧 English

Laitoxx DDoS Tool is a GUI application for network stress testing and simulating DDoS attacks. The tool is built with PyQt5 and provides a user-friendly interface for configuring and launching various types of attacks.

---

## ✨ Features

- **Multiple Attack Layers:** Supports Layer 4 and Layer 7 attacks.
- **Variety of Methods:** Includes a wide range of attack methods like UDP, TCP-SYN, HTTP-FLOOD, and more.
- **Proxy Support:** Ability to use SOCKS4/SOCKS5 proxies for L4 (socket-based) and L7 attacks.
- **Multi-threading:** Runs attacks in multiple threads for higher performance.
- **Customizable Interface:**
    - Multiple visual themes (Dark, Light, Matrix, Cyberpunk, Obsidian).
    - Animated "Digital Rain" background with customizable colors.
- **Real-time Logs:** Two log panels for general information and debug messages.
- **User-Friendly Controls:** Easy-to-use controls for setting target, port, threads, and duration.


## 📋 Requirements

- Python 3.x
- PyQt5
- scapy
- aiohttp
- faker
- fake-useragent
- PySocks
- aiohttp_socks
- selenium (optional, for browser-based attacks)
- playwright (optional, for browser-based attacks)

## ⚙️ Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-folder>/Laitoxx GUI/ui
    ```

2.  **Install the required libraries:**
    ```bash
    pip install PyQt5 scapy aiohttp faker fake-useragent PySocks aiohttp_socks
    ```

3.  **Install optional browser automation tools if needed:**
    ```bash
    pip install selenium playwright
    playwright install
    ```

## 🚀 Usage

To run the application, execute the `main.py` script:

```bash
python main.py
```

1.  Select the attack layer (Layer 4 or Layer 7).
2.  Choose a specific attack method from the dropdown menu.
3.  Enter the target IP address or URL.
4.  Set the port, number of threads, and attack duration.
5.  (Optional) Enable proxies, select the proxy type, and load a proxy list file (`.txt`, one `ip:port` per line).
6.  Click "Start Attack".
7.  Use the "Stop Attack" button to gracefully end the attack or "Stop & Quit" to force terminate.

## ⚠️ Disclaimer

This tool is intended for educational and testing purposes **only**. The developer is not responsible for any illegal use of this software. Using this tool against networks or services without explicit permission is illegal and can lead to serious consequences. **You are solely responsible for your actions.**

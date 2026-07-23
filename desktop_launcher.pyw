from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


def runtime_root() -> Path:
    """Writable application root.

    In source mode this is the project folder. In a PyInstaller one-folder build
    this is the folder containing CareerOS.exe.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = runtime_root()
os.chdir(ROOT)
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = DATA_DIR / "desktop.log"
STATE_FILE = DATA_DIR / "desktop_state.json"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)

holder: dict[str, object] = {}


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def health_ok(base_url: str, timeout: float = 1.2) -> bool:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/health", timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def load_running_instance() -> str | None:
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        port = int(payload.get("port", 0))
        if 1 <= port <= 65535:
            base = f"http://127.0.0.1:{port}"
            if health_ok(base):
                return base
    except Exception:
        pass
    return None


def write_state(port: int) -> None:
    payload = {"port": port, "pid": os.getpid(), "started_at": time.time()}
    STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_state(port: int) -> None:
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
        if int(payload.get("port", -1)) == port:
            STATE_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def find_browser() -> tuple[str, str] | None:
    """Return (browser_name, executable) for app-mode capable Chromium browsers."""
    candidates: list[tuple[str, Path]] = []
    for env_name in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        root = os.environ.get(env_name)
        if not root:
            continue
        base = Path(root)
        candidates.extend(
            [
                ("Edge", base / "Microsoft/Edge/Application/msedge.exe"),
                ("Chrome", base / "Google/Chrome/Application/chrome.exe"),
                ("Chrome", base / "Google/Chrome Beta/Application/chrome.exe"),
            ]
        )
    seen: set[str] = set()
    for name, path in candidates:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if path.exists():
            return name, str(path)
    return None


def run_server(port: int) -> None:
    import uvicorn

    config = uvicorn.Config(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    holder["server"] = server
    server.run()


def wait_ready(base_url: str, timeout: float = 35.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if health_ok(base_url):
            return True
        time.sleep(0.3)
    return False


def show_message(message: str, *, error: bool = False) -> None:
    logging.error(message) if error else logging.info(message)
    try:
        import ctypes

        flags = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(0, message, "CareerOS", flags)
    except Exception:
        pass


def open_app_window(base_url: str) -> subprocess.Popen | None:
    browser = find_browser()
    if browser:
        browser_name, executable = browser
        profile = Path(os.environ.get("LOCALAPPDATA", str(ROOT))) / "CareerOS" / f"{browser_name}Profile"
        profile.mkdir(parents=True, exist_ok=True)
        logging.info("Opening CareerOS with %s app mode", browser_name)
        return subprocess.Popen(
            [
                executable,
                f"--app={base_url}/",
                f"--user-data-dir={profile}",
                "--no-first-run",
                "--start-maximized",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # Last-resort browser fallback. Keep the local server alive rather than
    # immediately shutting it down after a message box is closed.
    logging.warning("No Edge/Chrome detected; using default browser")
    webbrowser.open(base_url + "/")
    show_message(
        "未检测到 Microsoft Edge 或 Google Chrome。\n"
        "CareerOS 已在默认浏览器中打开。\n\n"
        "本地服务将在后台保持运行；需要停止时，可在任务管理器结束 pythonw.exe。"
    )
    return None


def main() -> None:
    # Reuse an already-running CareerOS instance if the user double-clicks twice.
    existing = load_running_instance()
    if existing:
        logging.info("Reusing existing CareerOS instance at %s", existing)
        open_app_window(existing)
        return

    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    logging.info("Starting CareerOS at %s", base_url)

    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()

    if not wait_ready(base_url):
        show_message(
            "CareerOS 本地服务启动失败。\n\n"
            f"请查看日志：{LOG_FILE}",
            error=True,
        )
        return

    write_state(port)
    browser_process: subprocess.Popen | None = None
    try:
        browser_process = open_app_window(base_url)
        if browser_process is not None:
            # Dedicated user-data-dir normally keeps this process associated
            # with the app window. If Chromium hands off and exits immediately,
            # keep the server alive for a short grace period rather than killing it.
            started = time.time()
            code = browser_process.wait()
            elapsed = time.time() - started
            logging.info("Browser app process exited code=%s elapsed=%.2fs", code, elapsed)
            if elapsed < 3:
                # Browser process hand-off: keep CareerOS alive in background.
                while True:
                    time.sleep(30)
                    if not health_ok(base_url):
                        break
        else:
            # Default-browser fallback: keep service running until process is ended.
            while True:
                time.sleep(30)
                if not health_ok(base_url):
                    break
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        show_message(f"CareerOS 桌面窗口启动失败：{exc}", error=True)
    finally:
        server = holder.get("server")
        if server is not None:
            try:
                server.should_exit = True
            except Exception:
                pass
        server_thread.join(timeout=5)
        clear_state(port)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        show_message(
            "CareerOS 启动失败。\n\n"
            f"错误：{exc}\n\n"
            f"日志：{LOG_FILE}",
            error=True,
        )

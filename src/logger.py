from datetime import datetime
from rich.console import Console
from rich.text import Text

from src.config import BASE_DIR

LOGS_DIR = BASE_DIR / "logs"

_LEVEL_STYLES = {
    "DEBUG": "dim",
    "INFO": "cyan",
    "SUCCESS": "bold green",
    "WARNING": "yellow",
    "ERROR": "bold red",
}


class CustomLogger:
    """
    Console logger that displays rich colored terminal output while
    simultaneously recording clean timestamped plaintext logs to files.

    Log files are created lazily on first use (not at import time), so
    importing this module has no filesystem side effects.
    """

    def __init__(self):
        self.console = Console()
        self._files_ready = False
        self.run_log_file = None
        self.latest_log_file = None

    def _ensure_log_files(self):
        if self._files_ready:
            return
        LOGS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_log_file = LOGS_DIR / f"run_{timestamp}.log"
        self.latest_log_file = LOGS_DIR / "latest.log"

        header = f"=== FP Markets Copy Trading Log - Session Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n"
        with open(self.run_log_file, "a", encoding="utf-8") as f:
            f.write(header)
        with open(self.latest_log_file, "w", encoding="utf-8") as f:
            f.write(header)
        self._files_ready = True

    def _write_to_files(self, line: str):
        self._ensure_log_files()
        with open(self.run_log_file, "a", encoding="utf-8") as f:
            f.write(line)
        with open(self.latest_log_file, "a", encoding="utf-8") as f:
            f.write(line)

    def _log(self, level: str, message: str):
        style = _LEVEL_STYLES.get(level, "")
        self.console.print(f"[{style}]{message}[/{style}]" if style else message)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self._write_to_files(f"[{timestamp}] {level}: {message}\n")
        except Exception:
            pass

    def debug(self, message: str):
        self._log("DEBUG", message)

    def info(self, message: str):
        self._log("INFO", message)

    def success(self, message: str):
        self._log("SUCCESS", message)

    def warning(self, message: str):
        self._log("WARNING", message)

    def error(self, message: str):
        self._log("ERROR", message)

    def print(self, *args, **kwargs):
        """Raw passthrough for rich renderables (e.g. Panel) that don't map to a log level."""
        self.console.print(*args, **kwargs)

        try:
            plain_parts = []
            for arg in args:
                if isinstance(arg, str):
                    plain_parts.append(Text.from_markup(arg).plain)
                else:
                    plain_parts.append(str(arg))

            plain_message = " ".join(plain_parts).strip()
            if plain_message:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._write_to_files(f"[{timestamp}] {plain_message}\n")
        except Exception:
            pass


log = CustomLogger()

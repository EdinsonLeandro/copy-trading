import sys
from datetime import datetime
from rich.console import Console
from rich.text import Text

from src.common.config import BASE_DIR

LOGS_DIR = BASE_DIR / "logs"

_LEVEL_STYLES = {
    "DEBUG": "dim",
    "INFO": "cyan",
    "SUCCESS": "bold green",
    "WARNING": "yellow",
    "ERROR": "bold red",
}


class _StderrTee:
    """Duplicates everything written to stderr into the run's log files.

    Uncaught exception tracebacks and third-party warnings (Playwright,
    etc.) write straight to stderr, bypassing log.debug/info/error/print
    entirely - without this, a crash's traceback shows up in the terminal
    but never in the log file. stdout is deliberately left alone: the rich
    Console used by log.*/log.print already writes there, and its output
    is separately captured (as clean plaintext) by _write_to_files, so
    teeing stdout too would just duplicate every log line.
    """

    def __init__(self, original, log_paths):
        self._original = original
        self._log_paths = log_paths

    def write(self, data):
        self._original.write(data)
        if not data:
            return
        for path in self._log_paths:
            try:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(data)
            except Exception:
                pass

    def flush(self):
        self._original.flush()

    def isatty(self):
        return getattr(self._original, "isatty", lambda: False)()


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
        self._label = None
        self.run_log_file = None
        self.latest_log_file = None
        self._run_fh = None
        self._latest_fh = None

    def set_label(self, label: str) -> None:
        """Tags subsequent log filenames with `label` (e.g. the active broker
        name) if called before the first log write. A no-op after that point,
        since the run's log file has already been created."""
        if not self._files_ready:
            self._label = label

    def _ensure_log_files(self):
        if self._files_ready:
            return
        LOGS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{self._label}" if self._label else ""
        self.run_log_file = LOGS_DIR / f"run{suffix}_{timestamp}.log"
        self.latest_log_file = LOGS_DIR / f"latest{suffix}.log"

        header = f"=== Copy Trading Scraper Log - Session Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n"
        self._run_fh = open(self.run_log_file, "a", encoding="utf-8")
        self._latest_fh = open(self.latest_log_file, "w", encoding="utf-8")
        self._run_fh.write(header)
        self._run_fh.flush()
        self._latest_fh.write(header)
        self._latest_fh.flush()

        if not isinstance(sys.stderr, _StderrTee):
            sys.stderr = _StderrTee(sys.stderr, [self.run_log_file, self.latest_log_file])

        self._files_ready = True

    def _write_to_files(self, line: str):
        self._ensure_log_files()
        self._run_fh.write(line)
        self._run_fh.flush()
        self._latest_fh.write(line)
        self._latest_fh.flush()

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

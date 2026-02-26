
# from os import path
from datetime import datetime
from pytz import timezone
import logging.config
import logging
import os
from logging import Logger


debug_mode = os.getenv("LOG_LEVEL", "info").lower() == "debug"
loglevel = logging.INFO if not debug_mode else logging.DEBUG

# Supported ANSI color names for the color= parameter
_ANSI_RESET = "\033[0m"
_COLOR_MAP: dict[str, str] = {
    "cyan":    "\033[36m",
    "green":   "\033[32m",
    "yellow":  "\033[33m",
    "red":     "\033[31m",
    "magenta": "\033[35m",
    "blue":    "\033[34m",
    "white":   "\033[37m",
}


class FontToolsFilter(logging.Filter):
    """Filter out broken fontTools warnings that cause TypeError."""

    def filter(self, record):
        # Suppress fontTools warnings with malformed format strings
        if record.name.startswith('fontTools'):
            # Check if this is the problematic warning
            if 'timestamp seems very low' in str(record.msg):
                return False  # Suppress this log
        return True  # Allow all other logs


class CustomFormatter(logging.Formatter):
    def __init__(self, tz_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tz = timezone(tz_name)

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, self.tz)
        return dt.strftime(datefmt) if datefmt else dt.isoformat()

    def format(self, record):
        # Based on the log level, add an emoji prefix to the message
        try:
            # Try to get fully formatted message
            original_msg = record.getMessage()
        except (TypeError, ValueError) as e:
            # Fallback for broken log messages (e.g. from fontTools)
            original_msg = str(record.msg)
            # Don't modify record, just suppress
            return ""  # Return empty string to suppress broken logs

        # Add prefix based on level
        if record.levelno == logging.ERROR:
            record.msg = "⛔ " + original_msg
        elif record.levelno == logging.WARNING:
            record.msg = "⚠️ " + original_msg
        else:
            record.msg = original_msg

        # Important: Clear args AFTER getting the message
        record.args = ()

        # Now call parent formatter
        return super().format(record)


class ColoredFormatter(CustomFormatter):
    """Console formatter with optional per-message ANSI color support.

    Colors are applied only when the log record carries a ``color`` attribute,
    which is set by passing ``color=<name>`` to :class:`ColorLogger` methods.
    Supported color names: cyan, green, yellow, red, magenta, blue, white.
    """

    def format(self, record) -> str:
        line = super().format(record)
        if not line:
            return line
        color_name = getattr(record, "color", None)
        ansi = _COLOR_MAP.get(color_name, "") if color_name else ""
        return f"{ansi}{line}{_ANSI_RESET}" if ansi else line


class ColorLogger:
    """Thin wrapper around :class:`logging.Logger` that adds an optional
    ``color=`` keyword argument to all log methods.

    Usage::

        logger.info("plain message")
        logger.info("highlighted", color="cyan")
        logger.warning("something off", color="yellow")

    Colors are only applied in the console handler; the file handler always
    writes plain text.
    Available colors: cyan, green, yellow, red, magenta, blue, white.
    """

    def __init__(self, logger: Logger):
        self._logger = logger

    def _with_color(self, kwargs: dict, color: str | None) -> dict:
        """Inject color name into the extra dict if provided."""
        if color is not None:
            extra = dict(kwargs.get("extra") or {})
            extra["color"] = color
            return {**kwargs, "extra": extra}
        return kwargs

    def debug(self, msg, *args, color: str | None = None, **kwargs):
        self._logger.debug(msg, *args, **self._with_color(kwargs, color))

    def info(self, msg, *args, color: str | None = None, **kwargs):
        self._logger.info(msg, *args, **self._with_color(kwargs, color))

    def warning(self, msg, *args, color: str | None = None, **kwargs):
        self._logger.warning(msg, *args, **self._with_color(kwargs, color))

    def error(self, msg, *args, color: str | None = None, **kwargs):
        self._logger.error(msg, *args, **self._with_color(kwargs, color))

    def critical(self, msg, *args, color: str | None = None, **kwargs):
        self._logger.critical(msg, *args, **self._with_color(kwargs, color))

    def exception(self, msg, *args, color: str | None = None, **kwargs):
        self._logger.exception(msg, *args, **self._with_color(kwargs, color))

    def log(self, level: int, msg, *args, color: str | None = None, **kwargs):
        self._logger.log(level, msg, *args, **self._with_color(kwargs, color))

    def __getattr__(self, name):
        """Delegate all other Logger attributes (e.g. setLevel, handlers) transparently."""
        return getattr(self._logger, name)


def setup_logging() -> ColorLogger:
    log_dir = os.path.join(os.environ['ROOT_DIR'], "logs")
    tz_name = os.getenv("TIMEZONE", "Europe/Berlin")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "()": CustomFormatter,
                "format": "%(asctime)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "tz_name": tz_name,
            },
            "colored": {
                "()": ColoredFormatter,
                "format": "%(asctime)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "tz_name": tz_name,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "colored",
                "level": loglevel,
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.FileHandler",
                "formatter": "standard",
                "level": loglevel,
                "filename": os.path.join(log_dir, "app.log"),
                "encoding": "utf-8",
            },
        },
        "root": {
            "handlers": ["console", "file"],
            "level": loglevel,
        },
    }

    logging.config.dictConfig(logging_config)

    # Suppress httpx request logs unless in debug mode
    logging.getLogger("httpx").setLevel(logging.DEBUG if debug_mode else logging.WARNING)

    # Add FontToolsFilter to all handlers
    root_logger = logging.getLogger()
    fonttools_filter = FontToolsFilter()
    for handler in root_logger.handlers:
        handler.addFilter(fonttools_filter)

    # Also set fontTools logger to ERROR level to suppress warnings
    logging.getLogger('fontTools').setLevel(logging.ERROR)

    return ColorLogger(logging.getLogger(__name__))

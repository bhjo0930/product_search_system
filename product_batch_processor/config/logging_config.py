import logging
import logging.handlers
import json
import sys
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

from .settings import config


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, 'batch_id'):
            log_data['batch_id'] = record.batch_id
        if hasattr(record, 'product_id'):
            log_data['product_id'] = record.product_id
        if hasattr(record, 'module'):
            log_data['module'] = record.module
        if hasattr(record, 'function'):
            log_data['function'] = record.function
        if hasattr(record, 'step'):
            log_data['step'] = record.step
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms
        if hasattr(record, 'data'):
            log_data['data'] = record.data
        if hasattr(record, 'error'):
            log_data['error'] = record.error
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class StructuredLogger:
    """Structured logger with context support."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context = {}
    
    def set_context(self, **kwargs):
        """Set context variables for logging."""
        self.context.update(kwargs)
    
    def clear_context(self):
        """Clear context variables."""
        self.context.clear()
    
    def _log(self, level: int, message: str, **kwargs):
        """Internal logging method with context."""
        # Filter out reserved LogRecord attributes
        reserved_attrs = {'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                         'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                         'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                         'thread', 'threadName', 'processName', 'process', 'message'}
        
        extra = {}
        for key, value in {**self.context, **kwargs}.items():
            if key not in reserved_attrs:
                extra[key] = value
        
        self.logger.log(level, message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._log(logging.CRITICAL, message, **kwargs)
    
    def step_start(self, step: str, **kwargs):
        """Log step start."""
        self.info(f"Starting {step}", step=step, **kwargs)
    
    def step_complete(self, step: str, duration_ms: int = None, **kwargs):
        """Log step completion."""
        extra = {"step": step}
        if duration_ms is not None:
            extra["duration_ms"] = duration_ms
        extra.update(kwargs)
        self.info(f"Completed {step}", **extra)
    
    def step_error(self, step: str, error: str, **kwargs):
        """Log step error."""
        self.error(f"Failed {step}: {error}", step=step, error=error, **kwargs)


def setup_logging() -> None:
    """Setup logging configuration."""
    
    # Create logs directory
    Path(config.LOGS_DIR).mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    if config.LOG_FORMAT == "json":
        console_formatter = JSONFormatter()
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    log_file = Path(config.LOGS_DIR) / "batch_processor.log"
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_file,
        when=config.LOG_ROTATION,
        backupCount=config.LOG_RETENTION,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
    
    if config.LOG_FORMAT == "json":
        file_formatter = JSONFormatter()
    else:
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler
    error_file = Path(config.LOGS_DIR) / "batch_processor_errors.log"
    error_handler = logging.handlers.TimedRotatingFileHandler(
        filename=error_file,
        when=config.LOG_ROTATION,
        backupCount=config.LOG_RETENTION,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)


def get_logger(name: str) -> StructuredLogger:
    """Get structured logger instance."""
    return StructuredLogger(name)
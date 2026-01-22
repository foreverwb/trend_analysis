"""
Enhanced Logging Module
Provides structured logging for API calls, errors, and debugging
"""
import logging
import sys
import os
import functools
import traceback
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Optional
from logging.handlers import RotatingFileHandler

# ANSI color codes for console output
class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    GRAY = '\033[90m'


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""
    
    LEVEL_COLORS = {
        logging.DEBUG: Colors.GRAY,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.MAGENTA,
    }
    
    def format(self, record):
        # Add color to level name
        color = self.LEVEL_COLORS.get(record.levelno, Colors.RESET)
        record.levelname = f"{color}{record.levelname}{Colors.RESET}"
        
        # Add color to specific components
        if hasattr(record, 'api_source'):
            record.api_source = f"{Colors.CYAN}{record.api_source}{Colors.RESET}"
        
        return super().format(record)


class APICallLogger:
    """Logger for API calls with timing and error tracking"""
    
    def __init__(self, logger: logging.Logger, source: str):
        self.logger = logger
        self.source = source
    
    def log_request(self, method: str, endpoint: str, params: Optional[dict] = None):
        """Log an outgoing API request"""
        extra = {'api_source': self.source}
        msg = f"[{self.source}] → REQUEST: {method} {endpoint}"
        if params:
            # Sanitize sensitive data
            safe_params = self._sanitize_params(params)
            msg += f" | Params: {json.dumps(safe_params, default=str)}"
        self.logger.info(msg, extra=extra)
    
    def log_response(self, method: str, endpoint: str, status: str, duration_ms: float, 
                     data: Any = None, log_data: bool = False):
        """Log an API response"""
        extra = {'api_source': self.source}
        msg = f"[{self.source}] ← RESPONSE: {method} {endpoint} | Status: {status} | Time: {duration_ms:.2f}ms"
        
        if log_data and data:
            # Truncate large responses
            data_str = json.dumps(data, default=str)
            if len(data_str) > 500:
                data_str = data_str[:500] + "... (truncated)"
            msg += f" | Data: {data_str}"
        
        if status == "success":
            self.logger.info(msg, extra=extra)
        else:
            self.logger.warning(msg, extra=extra)
    
    def log_error(self, method: str, endpoint: str, error: Exception, duration_ms: float = 0):
        """Log an API error"""
        extra = {'api_source': self.source}
        error_type = type(error).__name__
        error_msg = str(error)
        
        msg = f"[{self.source}] ✗ ERROR: {method} {endpoint} | {error_type}: {error_msg}"
        if duration_ms > 0:
            msg += f" | Time: {duration_ms:.2f}ms"
        
        self.logger.error(msg, extra=extra)
        
        # Log full traceback at debug level
        self.logger.debug(f"[{self.source}] Traceback:\n{traceback.format_exc()}", extra=extra)
    
    def log_connection(self, action: str, success: bool, message: str = ""):
        """Log connection events"""
        extra = {'api_source': self.source}
        status = "✓" if success else "✗"
        level = logging.INFO if success else logging.WARNING
        msg = f"[{self.source}] {status} CONNECTION {action.upper()}"
        if message:
            msg += f": {message}"
        self.logger.log(level, msg, extra=extra)
    
    @staticmethod
    def _sanitize_params(params: dict) -> dict:
        """Remove sensitive data from params for logging"""
        sensitive_keys = {'password', 'secret', 'api_key', 'api_secret', 'token', 'auth'}
        sanitized = {}
        for key, value in params.items():
            if any(s in key.lower() for s in sensitive_keys):
                sanitized[key] = '***REDACTED***'
            else:
                sanitized[key] = value
        return sanitized


def setup_logging(
    level: str = "INFO",
    log_format: str = None,
    log_file: str = None,
    max_file_size: int = 10,
    backup_count: int = 5
) -> logging.Logger:
    """
    Setup application logging with console and optional file output.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Custom log format string
        log_file: Path to log file (optional)
        max_file_size: Maximum log file size in MB
        backup_count: Number of backup files to keep
    
    Returns:
        Root logger instance
    """
    # Default format
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    
    # Get numeric level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_formatter = ColoredFormatter(log_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        # Create log directory if needed
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_file_size * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_formatter = logging.Formatter(log_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Set specific logger levels
    logging.getLogger('uvicorn').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    
    return root_logger


def get_api_logger(source: str) -> APICallLogger:
    """Get an API call logger for a specific source"""
    logger = logging.getLogger(f"api.{source}")
    return APICallLogger(logger, source)


def log_function_call(logger: logging.Logger = None, log_args: bool = True, log_result: bool = False):
    """
    Decorator to log function calls with timing.
    
    Args:
        logger: Logger instance (uses function's module logger if not provided)
        log_args: Whether to log function arguments
        log_result: Whether to log function result
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)
            
            func_name = f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            
            # Log function entry
            if log_args:
                # Filter out 'self' from args display
                display_args = args[1:] if args and hasattr(args[0], '__class__') else args
                logger.debug(f"→ CALL: {func_name}(args={display_args}, kwargs={kwargs})")
            else:
                logger.debug(f"→ CALL: {func_name}()")
            
            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000
                
                if log_result:
                    logger.debug(f"← RETURN: {func_name} | Time: {duration:.2f}ms | Result: {result}")
                else:
                    logger.debug(f"← RETURN: {func_name} | Time: {duration:.2f}ms")
                
                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.error(f"✗ ERROR: {func_name} | Time: {duration:.2f}ms | {type(e).__name__}: {e}")
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = logging.getLogger(func.__module__)
            
            func_name = f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            
            if log_args:
                display_args = args[1:] if args and hasattr(args[0], '__class__') else args
                logger.debug(f"→ CALL: {func_name}(args={display_args}, kwargs={kwargs})")
            else:
                logger.debug(f"→ CALL: {func_name}()")
            
            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000
                
                if log_result:
                    logger.debug(f"← RETURN: {func_name} | Time: {duration:.2f}ms | Result: {result}")
                else:
                    logger.debug(f"← RETURN: {func_name} | Time: {duration:.2f}ms")
                
                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.error(f"✗ ERROR: {func_name} | Time: {duration:.2f}ms | {type(e).__name__}: {e}")
                raise
        
        # Return appropriate wrapper based on function type
        if asyncio_iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def asyncio_iscoroutinefunction(func):
    """Check if function is a coroutine function"""
    import asyncio
    return asyncio.iscoroutinefunction(func)


class LogContext:
    """Context manager for logging with additional context"""
    
    def __init__(self, logger: logging.Logger, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        context_str = " | ".join(f"{k}={v}" for k, v in self.context.items())
        self.logger.info(f"▶ START: {self.operation} | {context_str}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (time.time() - self.start_time) * 1000
        context_str = " | ".join(f"{k}={v}" for k, v in self.context.items())
        
        if exc_type is None:
            self.logger.info(f"■ END: {self.operation} | {context_str} | Time: {duration:.2f}ms")
        else:
            self.logger.error(
                f"✗ FAILED: {self.operation} | {context_str} | "
                f"Time: {duration:.2f}ms | Error: {exc_type.__name__}: {exc_val}"
            )
        
        return False  # Don't suppress exceptions

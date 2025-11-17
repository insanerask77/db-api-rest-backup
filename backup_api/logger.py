import logging
import logging.handlers
import os
import sys

LOG_FILE_PATH = "data/backup_api.log"

def setup_logging():
    """Configure the logging for the application."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)

    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Prevent propagation to the default handler
    logger.propagate = False

    # Remove existing handlers to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating File Handler
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE_PATH, maxBytes=10 * 1024 * 1024, backupCount=5  # 10 MB
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.error(f"Failed to create log file handler: {e}")

    # Set the logger for the application
    app_logger = logging.getLogger("backup_api")
    app_logger.setLevel(log_level)

    logging.info(f"Logging configured with level {log_level}")

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)

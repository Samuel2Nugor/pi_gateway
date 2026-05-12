import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "gateway.log"
MAX_BYTES = 2 * 1024 * 1024  # 2MB per file
BACKUP_COUNT = 5             # Keep 5 rotated files


def _build_formatter() -> logging.Formatter:
    return logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d  %H:%M:%S",
    )
        
def _setup_root_logger() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    
    formatter = _build_formatter()
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    
    # Console handler   
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(formatter)
    
    # Rotating file handler
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
        
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
        
    root.addHandler(console)
    root.addHandler(file_handler)
        
    
# Setup once on import
    
_setup_root_logger()
    
def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Use module name as a convention, e.g get_logger('ble_client')"""
    return logging.getLogger(name)
    

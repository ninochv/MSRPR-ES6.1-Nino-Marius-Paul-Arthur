"""
Module de logging horodaté pour NTL-SysToolbox.
Gère les logs console et fichier avec rotation.
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional


# Couleurs ANSI pour la sortie console
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"


class ColoredFormatter(logging.Formatter):
    """Formatter avec couleurs pour la console."""
    
    LEVEL_COLORS = {
        logging.DEBUG: Colors.CYAN,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.RED + Colors.BOLD,
    }
    
    def __init__(self, fmt: str, datefmt: str = None, use_colors: bool = True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and sys.stdout.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        if self.use_colors:
            color = self.LEVEL_COLORS.get(record.levelno, Colors.WHITE)
            record.levelname = f"{color}{record.levelname}{Colors.RESET}"
            record.msg = f"{color}{record.msg}{Colors.RESET}"
        return super().format(record)


class NTLLogger:
    """Logger principal pour NTL-SysToolbox."""
    
    _instance: Optional['NTLLogger'] = None
    _logger: Optional[logging.Logger] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def setup(cls, 
              log_level: str = "INFO",
              log_dir: str = "./logs",
              log_to_file: bool = True,
              log_to_console: bool = True) -> logging.Logger:
        """
        Configure le logger principal.
        
        Args:
            log_level: Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_dir: Répertoire des fichiers de log
            log_to_file: Activer les logs fichier
            log_to_console: Activer les logs console
            
        Returns:
            Logger configuré
        """
        instance = cls()
        
        # Créer le logger
        logger = logging.getLogger("ntl_systoolbox")
        logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        
        # Éviter les handlers dupliqués
        logger.handlers.clear()
        
        # Format avec horodatage
        file_format = "%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d | %(message)s"
        console_format = "%(asctime)s | %(levelname)-8s | %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        
        # Handler console
        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(ColoredFormatter(console_format, date_format))
            logger.addHandler(console_handler)
        
        # Handler fichier avec rotation
        if log_to_file:
            os.makedirs(log_dir, exist_ok=True)
            log_filename = datetime.now().strftime("ntl_systoolbox_%Y%m%d.log")
            log_path = os.path.join(log_dir, log_filename)
            
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setFormatter(logging.Formatter(file_format, date_format))
            logger.addHandler(file_handler)
        
        cls._logger = logger
        return logger
    
    @classmethod
    def get(cls) -> logging.Logger:
        """Retourne le logger configuré ou en crée un par défaut."""
        if cls._logger is None:
            return cls.setup()
        return cls._logger


def setup_logger(log_level: str = "INFO", 
                 log_dir: str = "./logs",
                 log_to_file: bool = True,
                 log_to_console: bool = True) -> logging.Logger:
    """
    Fonction helper pour configurer le logger.
    
    Args:
        log_level: Niveau de log
        log_dir: Répertoire des logs
        log_to_file: Activer logs fichier
        log_to_console: Activer logs console
        
    Returns:
        Logger configuré
    """
    return NTLLogger.setup(log_level, log_dir, log_to_file, log_to_console)


def get_logger() -> logging.Logger:
    """Retourne le logger principal."""
    return NTLLogger.get()

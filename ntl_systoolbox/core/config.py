"""
Module de configuration pour NTL-SysToolbox.
Gère le chargement depuis config.yaml, .env et variables d'environnement.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml


class Config:
    """
    Gestionnaire de configuration.
    Priorité: Variables d'environnement > .env > config.yaml
    """
    
    _instance: Optional['Config'] = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._config:
            self.load()
    
    def load(self, config_path: str = None, env_path: str = None) -> None:
        """
        Charge la configuration depuis les fichiers et l'environnement.
        
        Args:
            config_path: Chemin vers config.yaml
            env_path: Chemin vers le fichier .env
        """
        # Trouver le répertoire racine du projet
        root_dir = self._find_root_dir()
        
        # Charger config.yaml
        if config_path is None:
            config_path = root_dir / "config.yaml"
        
        if Path(config_path).exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        
        # Charger .env
        if env_path is None:
            env_path = root_dir / ".env"
        
        self._load_env_file(env_path)
        
        # Surcharger avec les variables d'environnement
        self._load_env_overrides()
    
    def _find_root_dir(self) -> Path:
        """Trouve le répertoire racine du projet."""
        # Chercher config.yaml en remontant l'arborescence
        current = Path(__file__).resolve().parent
        
        for _ in range(5):  # Maximum 5 niveaux
            if (current / "config.yaml").exists():
                return current
            current = current.parent
        
        # Par défaut, répertoire courant
        return Path.cwd()
    
    def _load_env_file(self, env_path: Path) -> None:
        """Charge les variables depuis un fichier .env."""
        if not Path(env_path).exists():
            return
        
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Ignorer commentaires et lignes vides
                if not line or line.startswith('#'):
                    continue
                
                # Parser KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    
                    # Mettre dans l'environnement si pas déjà défini
                    if key not in os.environ:
                        os.environ[key] = value
    
    def _load_env_overrides(self) -> None:
        """Surcharge la config avec les variables d'environnement NTL_*."""
        env_mapping = {
            'NTL_LOG_LEVEL': ('general', 'log_level'),
            'NTL_LOG_DIR': ('general', 'log_dir'),
            'NTL_BACKUP_DIR': ('general', 'backup_dir'),
            'NTL_REPORT_DIR': ('general', 'report_dir'),
            'NTL_OUTPUT_FORMAT': ('general', 'output_format'),
            'NTL_DB_HOST': ('wms_database', 'host'),
            'NTL_DB_PORT': ('wms_database', 'port'),
            'NTL_DB_NAME': ('wms_database', 'database'),
            'NTL_DB_USER': ('wms_database', 'user'),
            'NTL_DB_PASSWORD': ('wms_database', 'password'),
        }
        
        for env_var, (section, key) in env_mapping.items():
            value = os.environ.get(env_var)
            if value is not None:
                if section not in self._config:
                    self._config[section] = {}
                
                # Conversion de type pour les ports
                if 'port' in key.lower():
                    try:
                        value = int(value)
                    except ValueError:
                        pass
                
                self._config[section][key] = value
    
    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Récupère une valeur de configuration.
        
        Args:
            *keys: Chemin vers la valeur (ex: 'general', 'log_level')
            default: Valeur par défaut si non trouvée
            
        Returns:
            La valeur de configuration ou la valeur par défaut
        """
        value = self._config
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            
            if value is None:
                return default
        
        return value
    
    def get_env(self, key: str, default: str = None) -> Optional[str]:
        """Récupère une variable d'environnement."""
        return os.environ.get(key, default)
    
    def get_db_config(self) -> Dict[str, Any]:
        """Retourne la configuration complète de la base de données."""
        db_config = self.get('wms_database', default={}).copy()
        
        # Ajouter les credentials depuis l'environnement
        db_config['user'] = self.get_env('NTL_DB_USER', db_config.get('user', ''))
        db_config['password'] = self.get_env('NTL_DB_PASSWORD', db_config.get('password', ''))
        
        return db_config
    
    def get_ad_config(self) -> Dict[str, str]:
        """Retourne la configuration Active Directory."""
        return {
            'user': self.get_env('NTL_AD_USER', ''),
            'password': self.get_env('NTL_AD_PASSWORD', ''),
        }
    
    def get_domain_controllers(self) -> list:
        """Retourne la liste des contrôleurs de domaine."""
        return self.get('domain_controllers', default=[])
    
    def get_eol_database(self) -> list:
        """Retourne la base de données EOL."""
        return self.get('eol_database', default=[])
    
    def get_thresholds(self) -> Dict[str, int]:
        """Retourne les seuils d'alerte."""
        return self.get('thresholds', default={
            'cpu_warning': 80,
            'cpu_critical': 95,
            'memory_warning': 80,
            'memory_critical': 95,
            'disk_warning': 80,
            'disk_critical': 95,
            'eol_warning_days': 180,
            'eol_critical_days': 30,
        })
    
    @property
    def all(self) -> Dict[str, Any]:
        """Retourne toute la configuration."""
        return self._config.copy()
    
    def reload(self) -> None:
        """Recharge la configuration."""
        self._config = {}
        self.load()

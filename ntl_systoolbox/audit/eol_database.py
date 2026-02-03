"""
Base de données End-of-Life (EOL) pour les systèmes d'exploitation.
Permet de vérifier la date de fin de support des OS.
"""

from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple
import re

from ..core.config import Config
from ..core.logger import get_logger


class EOLDatabase:
    """
    Base de données des dates de fin de vie des systèmes d'exploitation.
    """
    
    # Patterns pour normaliser les noms d'OS
    OS_PATTERNS = {
        # Windows Server
        r'windows\s*server\s*2022': 'Windows Server 2022',
        r'windows\s*server\s*2019': 'Windows Server 2019',
        r'windows\s*server\s*2016': 'Windows Server 2016',
        r'windows\s*server\s*2012\s*r2': 'Windows Server 2012 R2',
        r'windows\s*server\s*2012(?!\s*r2)': 'Windows Server 2012',
        r'windows\s*server\s*2008\s*r2': 'Windows Server 2008 R2',
        r'windows\s*server\s*2008(?!\s*r2)': 'Windows Server 2008',
        
        # Windows Desktop
        r'windows\s*11': 'Windows 11',
        r'windows\s*10': 'Windows 10',
        r'windows\s*8\.1': 'Windows 8.1',
        r'windows\s*8(?!\.1)': 'Windows 8',
        r'windows\s*7': 'Windows 7',
        
        # Ubuntu
        r'ubuntu\s*24\.04': 'Ubuntu 24.04',
        r'ubuntu\s*22\.04': 'Ubuntu 22.04',
        r'ubuntu\s*20\.04': 'Ubuntu 20.04',
        r'ubuntu\s*18\.04': 'Ubuntu 18.04',
        r'ubuntu\s*16\.04': 'Ubuntu 16.04',
        
        # Debian
        r'debian\s*12': 'Debian 12',
        r'debian\s*11': 'Debian 11',
        r'debian\s*10': 'Debian 10',
        r'debian\s*9': 'Debian 9',
        
        # CentOS / RHEL
        r'centos\s*stream\s*9': 'CentOS Stream 9',
        r'centos\s*stream\s*8': 'CentOS Stream 8',
        r'centos\s*9': 'CentOS Stream 9',
        r'centos\s*8': 'CentOS 8',
        r'centos\s*7': 'CentOS 7',
        r'rhel\s*9|red\s*hat.*9': 'RHEL 9',
        r'rhel\s*8|red\s*hat.*8': 'RHEL 8',
        r'rhel\s*7|red\s*hat.*7': 'RHEL 7',
        
        # VMware ESXi
        r'esxi\s*8': 'VMware ESXi 8.0',
        r'esxi\s*7': 'VMware ESXi 7.0',
        r'esxi\s*6\.7': 'VMware ESXi 6.7',
        r'esxi\s*6\.5': 'VMware ESXi 6.5',
        r'vmware.*8\.0': 'VMware ESXi 8.0',
        r'vmware.*7\.0': 'VMware ESXi 7.0',
        r'vmware.*6\.7': 'VMware ESXi 6.7',
        r'vmware.*6\.5': 'VMware ESXi 6.5',
    }
    
    # Base de données EOL intégrée (fallback si config absente)
    DEFAULT_EOL_DATA = [
        # Windows Server
        {'os': 'Windows Server 2022', 'eol_date': '2031-10-14', 'extended_support': '2031-10-14'},
        {'os': 'Windows Server 2019', 'eol_date': '2029-01-09', 'extended_support': '2029-01-09'},
        {'os': 'Windows Server 2016', 'eol_date': '2027-01-12', 'extended_support': '2027-01-12'},
        {'os': 'Windows Server 2012 R2', 'eol_date': '2023-10-10', 'extended_support': '2026-10-13'},
        {'os': 'Windows Server 2012', 'eol_date': '2023-10-10', 'extended_support': '2026-10-13'},
        {'os': 'Windows Server 2008 R2', 'eol_date': '2020-01-14', 'extended_support': '2023-01-10'},
        
        # Ubuntu
        {'os': 'Ubuntu 24.04', 'eol_date': '2029-04-01', 'extended_support': '2034-04-01'},
        {'os': 'Ubuntu 22.04', 'eol_date': '2027-04-01', 'extended_support': '2032-04-01'},
        {'os': 'Ubuntu 20.04', 'eol_date': '2025-04-02', 'extended_support': '2030-04-02'},
        {'os': 'Ubuntu 18.04', 'eol_date': '2023-05-31', 'extended_support': '2028-04-01'},
        {'os': 'Ubuntu 16.04', 'eol_date': '2021-04-30', 'extended_support': '2026-04-01'},
        
        # Debian
        {'os': 'Debian 12', 'eol_date': '2028-06-01', 'extended_support': '2030-06-01'},
        {'os': 'Debian 11', 'eol_date': '2026-06-01', 'extended_support': '2028-06-01'},
        {'os': 'Debian 10', 'eol_date': '2024-06-30', 'extended_support': '2026-06-30'},
        {'os': 'Debian 9', 'eol_date': '2022-06-30', 'extended_support': '2024-06-30'},
        
        # CentOS / RHEL
        {'os': 'CentOS 7', 'eol_date': '2024-06-30', 'extended_support': '2024-06-30'},
        {'os': 'CentOS 8', 'eol_date': '2021-12-31', 'extended_support': '2021-12-31'},
        {'os': 'RHEL 9', 'eol_date': '2032-05-31', 'extended_support': '2034-05-31'},
        {'os': 'RHEL 8', 'eol_date': '2029-05-31', 'extended_support': '2031-05-31'},
        {'os': 'RHEL 7', 'eol_date': '2024-06-30', 'extended_support': '2026-06-30'},
        
        # VMware ESXi - CRITIQUE pour le sujet
        {'os': 'VMware ESXi 8.0', 'eol_date': '2029-04-01', 'extended_support': '2031-04-01'},
        {'os': 'VMware ESXi 7.0', 'eol_date': '2025-04-02', 'extended_support': '2027-04-02'},
        {'os': 'VMware ESXi 6.7', 'eol_date': '2022-10-15', 'extended_support': '2023-11-15'},
        {'os': 'VMware ESXi 6.5', 'eol_date': '2022-10-15', 'extended_support': '2022-10-15'},
    ]
    
    def __init__(self, config: Config = None):
        """
        Initialise la base de données EOL.
        
        Args:
            config: Instance de configuration
        """
        self.config = config or Config()
        self.logger = get_logger()
        
        # Charger les données EOL
        self.eol_data = self._load_eol_data()
        
        # Seuils d'alerte
        thresholds = self.config.get_thresholds()
        self.warning_days = thresholds.get('eol_warning_days', 180)
        self.critical_days = thresholds.get('eol_critical_days', 30)
    
    def _load_eol_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Charge les données EOL depuis la configuration ou utilise les valeurs par défaut.
        
        Returns:
            Dictionnaire des données EOL par OS
        """
        config_data = self.config.get_eol_database()
        data_list = config_data if config_data else self.DEFAULT_EOL_DATA
        
        eol_dict = {}
        for entry in data_list:
            os_name = entry.get('os')
            if os_name:
                eol_dict[os_name.lower()] = {
                    'name': os_name,
                    'eol_date': self._parse_date(entry.get('eol_date')),
                    'extended_support': self._parse_date(entry.get('extended_support')),
                }
        
        return eol_dict
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """
        Parse une date depuis une chaîne.
        
        Args:
            date_str: Date au format YYYY-MM-DD
            
        Returns:
            Objet date ou None
        """
        if not date_str:
            return None
        
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            self.logger.warning(f"Format de date invalide: {date_str}")
            return None
    
    def normalize_os_name(self, os_string: str) -> Optional[str]:
        """
        Normalise un nom d'OS pour le faire correspondre à la base EOL.
        
        Args:
            os_string: Chaîne décrivant l'OS
            
        Returns:
            Nom d'OS normalisé ou None
        """
        if not os_string:
            return None
        
        os_lower = os_string.lower()
        
        for pattern, normalized in self.OS_PATTERNS.items():
            if re.search(pattern, os_lower):
                return normalized
        
        return None
    
    def get_eol_info(self, os_name: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations EOL pour un OS.
        
        Args:
            os_name: Nom de l'OS
            
        Returns:
            Informations EOL ou None
        """
        # Normaliser le nom
        normalized = self.normalize_os_name(os_name)
        
        if normalized:
            key = normalized.lower()
            if key in self.eol_data:
                return self.eol_data[key].copy()
        
        # Essai direct
        key = os_name.lower()
        if key in self.eol_data:
            return self.eol_data[key].copy()
        
        return None
    
    def check_eol_status(self, os_name: str, reference_date: date = None) -> Dict[str, Any]:
        """
        Vérifie le statut EOL d'un OS.
        
        Args:
            os_name: Nom de l'OS
            reference_date: Date de référence (défaut: aujourd'hui)
            
        Returns:
            Statut EOL avec criticité
        """
        if reference_date is None:
            reference_date = date.today()
        
        result = {
            'os_original': os_name,
            'os_normalized': None,
            'status': 'unknown',
            'criticality': 'unknown',
            'eol_date': None,
            'extended_support': None,
            'days_until_eol': None,
            'days_since_eol': None,
            'message': None,
        }
        
        eol_info = self.get_eol_info(os_name)
        
        if not eol_info:
            result['message'] = f"OS non trouvé dans la base EOL: {os_name}"
            return result
        
        result['os_normalized'] = eol_info['name']
        result['eol_date'] = eol_info['eol_date'].isoformat() if eol_info['eol_date'] else None
        result['extended_support'] = eol_info['extended_support'].isoformat() if eol_info['extended_support'] else None
        
        eol_date = eol_info['eol_date']
        extended_date = eol_info['extended_support']
        
        if not eol_date:
            result['status'] = 'unknown'
            result['message'] = "Date EOL non disponible"
            return result
        
        # Calculer les jours
        delta = (eol_date - reference_date).days
        
        if delta < 0:
            # Déjà EOL
            result['days_since_eol'] = abs(delta)
            
            # Vérifier le support étendu
            if extended_date and reference_date < extended_date:
                result['status'] = 'extended_support'
                result['criticality'] = 'warning'
                ext_delta = (extended_date - reference_date).days
                result['message'] = f"EOL standard dépassé, support étendu jusqu'au {extended_date} ({ext_delta} jours)"
            else:
                result['status'] = 'end_of_life'
                result['criticality'] = 'critical'
                result['message'] = f"FIN DE VIE depuis {abs(delta)} jours - REMPLACEMENT URGENT"
        else:
            result['days_until_eol'] = delta
            
            if delta <= self.critical_days:
                result['status'] = 'critical_soon'
                result['criticality'] = 'critical'
                result['message'] = f"EOL dans {delta} jours - PLANIFIER MIGRATION"
            elif delta <= self.warning_days:
                result['status'] = 'warning_soon'
                result['criticality'] = 'warning'
                result['message'] = f"EOL dans {delta} jours - Migration à prévoir"
            else:
                result['status'] = 'supported'
                result['criticality'] = 'ok'
                result['message'] = f"Supporté jusqu'au {eol_date} ({delta} jours)"
        
        return result
    
    def get_all_os(self) -> List[str]:
        """
        Retourne la liste de tous les OS dans la base.
        
        Returns:
            Liste des noms d'OS
        """
        return [info['name'] for info in self.eol_data.values()]
    
    def find_similar_os(self, os_string: str) -> List[Dict[str, Any]]:
        """
        Trouve les OS similaires dans la base.
        
        Args:
            os_string: Chaîne de recherche
            
        Returns:
            Liste des OS correspondants avec leurs infos EOL
        """
        results = []
        search_lower = os_string.lower()
        
        for key, info in self.eol_data.items():
            if search_lower in key or search_lower in info['name'].lower():
                status = self.check_eol_status(info['name'])
                results.append({
                    **info,
                    'status': status,
                })
        
        return results

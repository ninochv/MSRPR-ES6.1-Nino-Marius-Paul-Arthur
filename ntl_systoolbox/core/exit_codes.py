"""
Codes de retour pour l'intégration avec les outils de supervision (Zabbix, Nagios, etc.)

Conventions:
- 0: OK - Opération réussie
- 1: WARNING - Avertissement, résultat partiel
- 2: CRITICAL - Erreur critique
- 3: UNKNOWN - État inconnu ou erreur d'exécution
"""

from enum import IntEnum


class ExitCode(IntEnum):
    """
    Codes de retour standards pour l'intégration supervision.
    Compatible avec les conventions Nagios/Zabbix.
    """
    # Succès
    OK = 0
    
    # Avertissements (opération réussie avec alertes)
    WARNING = 1
    
    # Erreurs critiques
    CRITICAL = 2
    
    # État inconnu ou erreur d'exécution
    UNKNOWN = 3
    
    # Codes spécifiques NTL-SysToolbox (10-99)
    # Configuration
    CONFIG_ERROR = 10
    CONFIG_MISSING = 11
    
    # Connectivité
    CONNECTION_FAILED = 20
    TIMEOUT = 21
    AUTH_FAILED = 22
    
    # Base de données
    DB_CONNECTION_ERROR = 30
    DB_QUERY_ERROR = 31
    DB_BACKUP_FAILED = 32
    
    # Services
    SERVICE_DOWN = 40
    SERVICE_DEGRADED = 41
    
    # Système
    RESOURCE_CRITICAL = 50
    DISK_FULL = 51
    
    # Audit
    EOL_DETECTED = 60
    SECURITY_RISK = 61
    
    # Sauvegarde
    BACKUP_FAILED = 70
    INTEGRITY_ERROR = 71
    
    @classmethod
    def get_description(cls, code: int) -> str:
        """Retourne la description d'un code de retour."""
        descriptions = {
            cls.OK: "Opération réussie",
            cls.WARNING: "Avertissement - Vérification recommandée",
            cls.CRITICAL: "Erreur critique - Action requise",
            cls.UNKNOWN: "État inconnu - Vérifier les logs",
            cls.CONFIG_ERROR: "Erreur de configuration",
            cls.CONFIG_MISSING: "Fichier de configuration manquant",
            cls.CONNECTION_FAILED: "Échec de connexion",
            cls.TIMEOUT: "Délai d'attente dépassé",
            cls.AUTH_FAILED: "Échec d'authentification",
            cls.DB_CONNECTION_ERROR: "Erreur de connexion base de données",
            cls.DB_QUERY_ERROR: "Erreur de requête base de données",
            cls.DB_BACKUP_FAILED: "Échec de sauvegarde base de données",
            cls.SERVICE_DOWN: "Service arrêté",
            cls.SERVICE_DEGRADED: "Service dégradé",
            cls.RESOURCE_CRITICAL: "Ressources système critiques",
            cls.DISK_FULL: "Disque plein",
            cls.EOL_DETECTED: "Composant obsolète détecté",
            cls.SECURITY_RISK: "Risque de sécurité identifié",
            cls.BACKUP_FAILED: "Échec de sauvegarde",
            cls.INTEGRITY_ERROR: "Erreur d'intégrité",
        }
        return descriptions.get(code, f"Code inconnu: {code}")
    
    @classmethod
    def is_error(cls, code: int) -> bool:
        """Vérifie si le code indique une erreur."""
        return code >= cls.CRITICAL
    
    @classmethod
    def is_warning(cls, code: int) -> bool:
        """Vérifie si le code indique un avertissement."""
        return code == cls.WARNING
    
    @classmethod
    def is_ok(cls, code: int) -> bool:
        """Vérifie si le code indique un succès."""
        return code == cls.OK

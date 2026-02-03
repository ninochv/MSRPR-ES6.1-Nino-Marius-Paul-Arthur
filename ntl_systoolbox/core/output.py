"""
Module de formatage de sortie pour NTL-SysToolbox.
Gère les sorties humaines et JSON avec horodatage.
"""

import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from .exit_codes import ExitCode


class OutputFormat(Enum):
    """Formats de sortie supportés."""
    HUMAN = "human"
    JSON = "json"
    BOTH = "both"


class Severity(Enum):
    """Niveaux de sévérité pour les résultats."""
    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class OutputFormatter:
    """
    Formateur de sortie pour les résultats des modules.
    Supporte les sorties humaines lisibles et JSON structuré.
    """

    # Symboles pour l'affichage (ASCII compatible Windows)
    SYMBOLS = {
        Severity.OK: "[OK]",
        Severity.INFO: "[i]",
        Severity.WARNING: "[!]",
        Severity.CRITICAL: "[X]",
        Severity.UNKNOWN: "[?]",
    }
    
    # Couleurs ANSI
    COLORS = {
        Severity.OK: "\033[92m",      # Vert
        Severity.INFO: "\033[94m",    # Bleu
        Severity.WARNING: "\033[93m", # Jaune
        Severity.CRITICAL: "\033[91m", # Rouge
        Severity.UNKNOWN: "\033[90m", # Gris
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    def __init__(self, format_type: str = "both", use_colors: bool = True):
        """
        Initialise le formateur.
        
        Args:
            format_type: Type de format (human, json, both)
            use_colors: Utiliser les couleurs ANSI
        """
        self.format_type = OutputFormat(format_type.lower())
        self.use_colors = use_colors and sys.stdout.isatty()
        self.results: List[Dict[str, Any]] = []
        self.start_time = datetime.now()
        self.module_name = ""
    
    def set_module(self, name: str) -> None:
        """Définit le nom du module courant."""
        self.module_name = name
        self.results = []
        self.start_time = datetime.now()
    
    def add_result(self,
                   check_name: str,
                   status: Union[Severity, str],
                   message: str,
                   details: Dict[str, Any] = None,
                   target: str = None) -> None:
        """
        Ajoute un résultat de vérification.
        
        Args:
            check_name: Nom de la vérification
            status: Statut/Sévérité du résultat
            message: Message descriptif
            details: Détails supplémentaires (dict)
            target: Cible de la vérification (IP, hostname, etc.)
        """
        if isinstance(status, str):
            status = Severity(status.lower())
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "check": check_name,
            "status": status.value,
            "message": message,
            "target": target,
            "details": details or {},
        }
        
        self.results.append(result)
        
        # Affichage immédiat en mode human ou both
        if self.format_type in (OutputFormat.HUMAN, OutputFormat.BOTH):
            self._print_human_result(result, status)
    
    def _print_human_result(self, result: Dict[str, Any], status: Severity) -> None:
        """Affiche un résultat en format humain."""
        symbol = self.SYMBOLS.get(status, "•")
        
        if self.use_colors:
            color = self.COLORS.get(status, "")
            reset = self.RESET
        else:
            color = ""
            reset = ""
        
        # Construire la ligne
        target_str = f" [{result['target']}]" if result['target'] else ""
        line = f"{color}{symbol}{reset} {result['check']}{target_str}: {result['message']}"
        
        print(line)
        
        # Afficher les détails importants
        if result['details']:
            for key, value in result['details'].items():
                if key.startswith('_'):  # Ignorer les clés privées
                    continue
                print(f"    {key}: {value}")
    
    def print_header(self, title: str) -> None:
        """Affiche un en-tête de section."""
        if self.format_type in (OutputFormat.HUMAN, OutputFormat.BOTH):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            width = 60
            print()
            print("=" * width)
            print(f"{self.BOLD if self.use_colors else ''}{title}{self.RESET if self.use_colors else ''}")
            print(f"Horodatage: {timestamp}")
            print("=" * width)
    
    def print_separator(self, title: str = "") -> None:
        """Affiche un séparateur."""
        if self.format_type in (OutputFormat.HUMAN, OutputFormat.BOTH):
            if title:
                print(f"\n--- {title} ---")
            else:
                print("-" * 40)
    
    def get_summary(self) -> Dict[str, Any]:
        """Génère un résumé des résultats."""
        # Comptage par statut
        status_counts = {s.value: 0 for s in Severity}
        for result in self.results:
            status_counts[result['status']] += 1
        
        # Déterminer le code de sortie global
        if status_counts[Severity.CRITICAL.value] > 0:
            exit_code = ExitCode.CRITICAL
        elif status_counts[Severity.WARNING.value] > 0:
            exit_code = ExitCode.WARNING
        elif status_counts[Severity.UNKNOWN.value] > 0:
            exit_code = ExitCode.UNKNOWN
        else:
            exit_code = ExitCode.OK
        
        return {
            "module": self.module_name,
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
            "exit_code": int(exit_code),
            "exit_message": ExitCode.get_description(exit_code),
            "summary": {
                "total": len(self.results),
                "ok": status_counts[Severity.OK.value],
                "info": status_counts[Severity.INFO.value],
                "warning": status_counts[Severity.WARNING.value],
                "critical": status_counts[Severity.CRITICAL.value],
                "unknown": status_counts[Severity.UNKNOWN.value],
            },
            "results": self.results,
        }
    
    def print_summary(self) -> int:
        """
        Affiche le résumé final et retourne le code de sortie.
        
        Returns:
            Code de sortie pour la supervision
        """
        summary = self.get_summary()
        
        if self.format_type in (OutputFormat.HUMAN, OutputFormat.BOTH):
            print()
            print("=" * 60)
            print(f"RÉSUMÉ - {summary['module']}")
            print("=" * 60)
            print(f"Durée: {summary['duration_seconds']:.2f} secondes")
            print(f"Total: {summary['summary']['total']} vérifications")
            
            s = summary['summary']
            status_line = []
            if s['ok']: status_line.append(f"{self.COLORS[Severity.OK] if self.use_colors else ''}OK: {s['ok']}{self.RESET if self.use_colors else ''}")
            if s['warning']: status_line.append(f"{self.COLORS[Severity.WARNING] if self.use_colors else ''}WARNING: {s['warning']}{self.RESET if self.use_colors else ''}")
            if s['critical']: status_line.append(f"{self.COLORS[Severity.CRITICAL] if self.use_colors else ''}CRITICAL: {s['critical']}{self.RESET if self.use_colors else ''}")
            if s['unknown']: status_line.append(f"{self.COLORS[Severity.UNKNOWN] if self.use_colors else ''}UNKNOWN: {s['unknown']}{self.RESET if self.use_colors else ''}")
            
            print(" | ".join(status_line))
            print(f"\nCode de sortie: {summary['exit_code']} ({summary['exit_message']})")
            print("=" * 60)
        
        if self.format_type in (OutputFormat.JSON, OutputFormat.BOTH):
            if self.format_type == OutputFormat.BOTH:
                print("\n--- JSON OUTPUT ---")
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        
        return summary['exit_code']
    
    def to_json(self) -> str:
        """Retourne les résultats en JSON."""
        return json.dumps(self.get_summary(), indent=2, ensure_ascii=False)
    
    def save_json(self, filepath: str) -> None:
        """Sauvegarde les résultats dans un fichier JSON."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.get_summary(), f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def format_bytes(size) -> str:
        """Formate une taille en bytes en format lisible."""
        size = float(size)  # Convertir Decimal en float si nécessaire
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    @staticmethod
    def format_uptime(seconds: float) -> str:
        """Formate un uptime en format lisible."""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}j")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        
        return " ".join(parts) if parts else "< 1m"

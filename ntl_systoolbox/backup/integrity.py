"""
Module de vérification d'intégrité des sauvegardes.
"""

import os
import hashlib
import json
import gzip
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..core.config import Config
from ..core.output import OutputFormatter, Severity
from ..core.logger import get_logger


class IntegrityChecker:
    """
    Vérifie l'intégrité des fichiers de sauvegarde.
    """
    
    def __init__(self, config: Config = None, output: OutputFormatter = None):
        """
        Initialise le vérificateur d'intégrité.
        
        Args:
            config: Instance de configuration
            output: Formateur de sortie
        """
        self.config = config or Config()
        self.output = output or OutputFormatter()
        self.logger = get_logger()
        self.backup_dir = Path(self.config.get('general', 'backup_dir', default='./backups'))
    
    def verify_backup(self, backup_path: str) -> Dict[str, Any]:
        """
        Vérifie l'intégrité d'un fichier de sauvegarde spécifique.
        
        Args:
            backup_path: Chemin du fichier de sauvegarde
            
        Returns:
            Résultat de la vérification
        """
        self.output.print_header(f"Vérification Intégrité: {os.path.basename(backup_path)}")
        
        backup_path = Path(backup_path)
        
        if not backup_path.exists():
            self.output.add_result(
                "Fichier",
                Severity.CRITICAL,
                "Fichier non trouvé",
                target=str(backup_path)
            )
            return {'valid': False, 'error': 'Fichier non trouvé'}
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'file': str(backup_path),
            'file_name': backup_path.name,
            'checks': {},
        }
        
        # 1. Vérifier l'existence et la taille
        file_stat = backup_path.stat()
        result['size'] = file_stat.st_size
        result['size_formatted'] = OutputFormatter.format_bytes(file_stat.st_size)
        result['modified'] = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
        
        self.output.add_result(
            "Fichier",
            Severity.OK,
            f"Taille: {result['size_formatted']}",
            details={'modifié': result['modified']}
        )
        
        # 2. Calculer le hash SHA256
        self.output.print_separator("Hash SHA256")
        sha256 = self._calculate_sha256(backup_path)
        result['sha256'] = sha256
        result['checks']['sha256'] = {'calculated': sha256}
        
        self.output.add_result(
            "Hash SHA256",
            Severity.OK,
            f"{sha256[:32]}...",
            details={'hash_complet': sha256}
        )
        
        # 3. Chercher le fichier de traçabilité
        trace_path = Path(str(backup_path) + '.trace.json')
        
        if trace_path.exists():
            self.output.print_separator("Fichier de Traçabilité")
            
            try:
                with open(trace_path, 'r', encoding='utf-8') as f:
                    trace_data = json.load(f)
                
                result['trace'] = trace_data
                result['checks']['trace'] = {'found': True}
                
                # Comparer les hashs
                expected_sha256 = trace_data.get('integrity', {}).get('sha256')
                
                if expected_sha256:
                    if expected_sha256 == sha256:
                        result['checks']['trace']['hash_match'] = True
                        self.output.add_result(
                            "Cohérence Hash",
                            Severity.OK,
                            "Le hash correspond au fichier de traçabilité"
                        )
                    else:
                        result['checks']['trace']['hash_match'] = False
                        self.output.add_result(
                            "Cohérence Hash",
                            Severity.CRITICAL,
                            "Le hash ne correspond PAS au fichier de traçabilité",
                            details={
                                'attendu': expected_sha256[:32] + '...',
                                'calculé': sha256[:32] + '...'
                            }
                        )
                        result['valid'] = False
                        return result
                
                # Afficher les métadonnées
                self.output.add_result(
                    "Métadonnées",
                    Severity.INFO,
                    f"Créé: {trace_data.get('created_at', 'N/A')}",
                    details={
                        'type': trace_data.get('type'),
                        'database': trace_data.get('database'),
                        'lignes': trace_data.get('row_count'),
                    }
                )
                
            except json.JSONDecodeError as e:
                result['checks']['trace'] = {'found': True, 'valid': False, 'error': str(e)}
                self.output.add_result(
                    "Fichier de Traçabilité",
                    Severity.WARNING,
                    "Fichier corrompu ou invalide"
                )
        else:
            result['checks']['trace'] = {'found': False}
            self.output.add_result(
                "Fichier de Traçabilité",
                Severity.WARNING,
                "Pas de fichier de traçabilité trouvé"
            )
        
        # 4. Vérifier le contenu (si compressé)
        if backup_path.suffix == '.gz':
            self.output.print_separator("Vérification Compression")
            gz_valid = self._verify_gzip(backup_path)
            result['checks']['gzip'] = {'valid': gz_valid}
            
            if gz_valid:
                self.output.add_result(
                    "Archive GZIP",
                    Severity.OK,
                    "Archive compressée valide"
                )
            else:
                self.output.add_result(
                    "Archive GZIP",
                    Severity.CRITICAL,
                    "Archive corrompue"
                )
                result['valid'] = False
                return result
        
        # 5. Vérification basique du contenu SQL
        if '.sql' in backup_path.name:
            self.output.print_separator("Vérification Contenu SQL")
            sql_check = self._verify_sql_content(backup_path)
            result['checks']['sql'] = sql_check
            
            if sql_check.get('valid'):
                self.output.add_result(
                    "Structure SQL",
                    Severity.OK,
                    f"Tables détectées: {sql_check.get('table_count', 0)}",
                    details={
                        'create_tables': sql_check.get('create_count'),
                        'inserts': sql_check.get('insert_count'),
                    }
                )
            else:
                self.output.add_result(
                    "Structure SQL",
                    Severity.WARNING,
                    "Structure SQL non standard ou vide"
                )
        
        result['valid'] = True
        return result
    
    def verify_all_backups(self) -> Dict[str, Any]:
        """
        Vérifie tous les fichiers de sauvegarde du répertoire.
        
        Returns:
            Résultats de toutes les vérifications
        """
        self.output.print_header("Vérification de Toutes les Sauvegardes")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'backup_dir': str(self.backup_dir),
            'backups': [],
            'valid_count': 0,
            'invalid_count': 0,
        }
        
        # Lister les fichiers de sauvegarde (exclure les .trace.json)
        backup_files = [
            f for f in self.backup_dir.glob('*')
            if f.is_file() and not f.name.endswith('.trace.json')
        ]
        
        for backup_file in sorted(backup_files):
            self.output.print_separator(backup_file.name)
            
            check_result = {
                'file': backup_file.name,
                'size': backup_file.stat().st_size,
                'sha256': self._calculate_sha256(backup_file),
            }
            
            # Vérifier si valide
            trace_path = Path(str(backup_file) + '.trace.json')
            if trace_path.exists():
                try:
                    with open(trace_path, 'r') as f:
                        trace = json.load(f)
                    
                    expected_hash = trace.get('integrity', {}).get('sha256')
                    if expected_hash and expected_hash == check_result['sha256']:
                        check_result['valid'] = True
                        results['valid_count'] += 1
                        
                        self.output.add_result(
                            backup_file.name,
                            Severity.OK,
                            f"Valide ({OutputFormatter.format_bytes(check_result['size'])})"
                        )
                    else:
                        check_result['valid'] = False
                        results['invalid_count'] += 1
                        
                        self.output.add_result(
                            backup_file.name,
                            Severity.CRITICAL,
                            "Hash non concordant"
                        )
                except Exception as e:
                    check_result['valid'] = None
                    check_result['error'] = str(e)
                    
                    self.output.add_result(
                        backup_file.name,
                        Severity.WARNING,
                        "Impossible de vérifier"
                    )
            else:
                check_result['valid'] = None
                check_result['no_trace'] = True
                
                self.output.add_result(
                    backup_file.name,
                    Severity.INFO,
                    f"Pas de traçabilité ({OutputFormatter.format_bytes(check_result['size'])})"
                )
            
            results['backups'].append(check_result)
        
        # Résumé
        total = len(backup_files)
        self.output.print_separator("Résumé")
        self.output.add_result(
            "Vérification Globale",
            Severity.OK if results['invalid_count'] == 0 else Severity.WARNING,
            f"{results['valid_count']}/{total} sauvegardes vérifiées valides"
        )
        
        return results
    
    def _calculate_sha256(self, file_path: Path) -> str:
        """
        Calcule le hash SHA256 d'un fichier.
        
        Args:
            file_path: Chemin du fichier
            
        Returns:
            Hash SHA256 en hexadécimal
        """
        sha256_hash = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    def _verify_gzip(self, file_path: Path) -> bool:
        """
        Vérifie qu'un fichier GZIP est valide.
        
        Args:
            file_path: Chemin du fichier
            
        Returns:
            True si valide
        """
        try:
            with gzip.open(file_path, 'rb') as f:
                # Lire par blocs pour vérifier
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
            return True
        except Exception as e:
            self.logger.error(f"Erreur vérification GZIP: {e}")
            return False
    
    def _verify_sql_content(self, file_path: Path) -> Dict[str, Any]:
        """
        Vérifie basiquement le contenu d'un fichier SQL.
        
        Args:
            file_path: Chemin du fichier
            
        Returns:
            Résultats de la vérification
        """
        result = {
            'valid': False,
            'create_count': 0,
            'insert_count': 0,
            'table_count': 0,
        }
        
        try:
            # Ouvrir selon compression
            if file_path.suffix == '.gz':
                f = gzip.open(file_path, 'rt', encoding='utf-8', errors='replace')
            else:
                f = open(file_path, 'r', encoding='utf-8', errors='replace')
            
            tables_seen = set()
            
            with f:
                for line in f:
                    line_upper = line.upper().strip()
                    
                    if line_upper.startswith('CREATE TABLE'):
                        result['create_count'] += 1
                        # Extraire le nom de la table
                        parts = line.split()
                        if len(parts) >= 3:
                            table_name = parts[2].strip('`').strip('(')
                            tables_seen.add(table_name)
                    
                    elif line_upper.startswith('INSERT INTO'):
                        result['insert_count'] += 1
            
            result['table_count'] = len(tables_seen)
            result['valid'] = result['create_count'] > 0 or result['insert_count'] > 0
            
        except Exception as e:
            self.logger.error(f"Erreur vérification SQL: {e}")
            result['error'] = str(e)
        
        return result

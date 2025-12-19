"""
Module de sauvegarde de la base de données WMS.
Export SQL complet et CSV par table avec traçabilité et intégrité.
"""

import os
import gzip
import hashlib
import subprocess
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import json

from ..core.config import Config
from ..core.output import OutputFormatter, Severity
from ..core.logger import get_logger
from ..core.exit_codes import ExitCode


class WMSBackupManager:
    """
    Gestionnaire de sauvegarde pour la base de données WMS.
    Supporte l'export SQL complet et CSV par table.
    """
    
    def __init__(self, config: Config = None, output: OutputFormatter = None):
        """
        Initialise le gestionnaire de sauvegarde.
        
        Args:
            config: Instance de configuration
            output: Formateur de sortie
        """
        self.config = config or Config()
        self.output = output or OutputFormatter()
        self.logger = get_logger()
        self.db_config = self.config.get_db_config()
        
        # Répertoire de sauvegarde
        self.backup_dir = Path(self.config.get('general', 'backup_dir', default='./backups'))
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Options de sauvegarde
        backup_config = self.config.get('backup', default={})
        self.compress = backup_config.get('compress', True)
        self.verify_integrity = backup_config.get('verify_integrity', True)
        self.retention_days = backup_config.get('retention_days', 30)
        
        self._connection = None
    
    def backup_full_database(self, output_path: str = None) -> Dict[str, Any]:
        """
        Exporte la base de données complète au format SQL.
        
        Args:
            output_path: Chemin de sortie (optionnel)
            
        Returns:
            Résultat de la sauvegarde
        """
        self.output.print_header("Sauvegarde Complète Base de Données WMS")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        database = self.db_config.get('database', 'wms_production')
        
        if output_path is None:
            filename = f"{database}_{timestamp}.sql"
            if self.compress:
                filename += ".gz"
            output_path = self.backup_dir / filename
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'type': 'full_backup',
            'database': database,
            'output_path': str(output_path),
            'status': 'pending',
        }
        
        self.output.print_separator("Export mysqldump")
        
        # Exécuter mysqldump
        dump_result = self._run_mysqldump(output_path)
        
        if dump_result['success']:
            result['status'] = 'success'
            result['size'] = dump_result.get('size', 0)
            result['size_formatted'] = OutputFormatter.format_bytes(result['size'])
            result['duration_seconds'] = dump_result.get('duration', 0)
            
            self.output.add_result(
                "Export SQL",
                Severity.OK,
                f"Sauvegarde créée: {result['size_formatted']}",
                details={
                    'fichier': os.path.basename(str(output_path)),
                    'durée': f"{result['duration_seconds']:.1f}s"
                }
            )
            
            # Vérification d'intégrité
            if self.verify_integrity:
                self.output.print_separator("Vérification Intégrité")
                integrity = self._verify_backup_integrity(output_path)
                result['integrity'] = integrity
                
                if integrity.get('valid'):
                    self.output.add_result(
                        "Intégrité SHA256",
                        Severity.OK,
                        f"Hash: {integrity.get('sha256', 'N/A')[:16]}...",
                        details={'hash_complet': integrity.get('sha256')}
                    )
                else:
                    self.output.add_result(
                        "Intégrité",
                        Severity.WARNING,
                        "Impossible de calculer le hash"
                    )
            
            # Créer le fichier de traçabilité
            self._create_trace_file(result, output_path)
            
        else:
            result['status'] = 'failed'
            result['error'] = dump_result.get('error', 'Erreur inconnue')
            
            self.output.add_result(
                "Export SQL",
                Severity.CRITICAL,
                f"Échec: {result['error']}"
            )
        
        return result
    
    def export_table_to_csv(self, table_name: str, output_path: str = None,
                            where_clause: str = None) -> Dict[str, Any]:
        """
        Exporte une table spécifique au format CSV.
        
        Args:
            table_name: Nom de la table à exporter
            output_path: Chemin de sortie (optionnel)
            where_clause: Clause WHERE optionnelle
            
        Returns:
            Résultat de l'export
        """
        self.output.print_header(f"Export CSV - Table {table_name}")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        database = self.db_config.get('database', 'wms_production')
        
        if output_path is None:
            filename = f"{database}_{table_name}_{timestamp}.csv"
            if self.compress:
                filename += ".gz"
            output_path = self.backup_dir / filename
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'type': 'csv_export',
            'database': database,
            'table': table_name,
            'output_path': str(output_path),
            'status': 'pending',
            'row_count': 0,
        }
        
        try:
            # Essayer avec mysql-connector
            import mysql.connector
            
            start_time = datetime.now()
            
            connection = mysql.connector.connect(
                host=self.db_config.get('host'),
                port=self.db_config.get('port', 3306),
                database=database,
                user=self.db_config.get('user'),
                password=self.db_config.get('password'),
                charset=self.db_config.get('charset', 'utf8mb4'),
            )
            
            cursor = connection.cursor()
            
            # Construire la requête
            query = f"SELECT * FROM `{table_name}`"
            if where_clause:
                query += f" WHERE {where_clause}"
            
            cursor.execute(query)
            
            # Récupérer les colonnes
            columns = [desc[0] for desc in cursor.description]
            
            # Écrire le CSV
            row_count = 0
            
            if self.compress:
                file_handler = gzip.open(output_path, 'wt', encoding='utf-8', newline='')
            else:
                file_handler = open(output_path, 'w', encoding='utf-8', newline='')
            
            with file_handler as f:
                writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                writer.writerow(columns)  # Header
                
                # Écrire par lots pour éviter les problèmes de mémoire
                while True:
                    rows = cursor.fetchmany(1000)
                    if not rows:
                        break
                    
                    for row in rows:
                        # Convertir les types non-string
                        row_data = []
                        for value in row:
                            if value is None:
                                row_data.append('')
                            elif isinstance(value, (datetime, )):
                                row_data.append(value.isoformat())
                            elif isinstance(value, bytes):
                                row_data.append(value.decode('utf-8', errors='replace'))
                            else:
                                row_data.append(str(value))
                        writer.writerow(row_data)
                        row_count += 1
            
            cursor.close()
            connection.close()
            
            duration = (datetime.now() - start_time).total_seconds()
            file_size = os.path.getsize(output_path)
            
            result['status'] = 'success'
            result['row_count'] = row_count
            result['columns'] = columns
            result['size'] = file_size
            result['size_formatted'] = OutputFormatter.format_bytes(file_size)
            result['duration_seconds'] = duration
            
            self.output.add_result(
                f"Export CSV {table_name}",
                Severity.OK,
                f"{row_count} lignes exportées ({result['size_formatted']})",
                details={
                    'colonnes': len(columns),
                    'durée': f"{duration:.1f}s"
                }
            )
            
            # Vérification d'intégrité
            if self.verify_integrity:
                integrity = self._verify_backup_integrity(output_path)
                result['integrity'] = integrity
                
                if integrity.get('valid'):
                    self.output.add_result(
                        "Intégrité SHA256",
                        Severity.OK,
                        f"Hash: {integrity.get('sha256', 'N/A')[:16]}..."
                    )
            
            # Créer le fichier de traçabilité
            self._create_trace_file(result, output_path)
            
        except ImportError:
            # Fallback: utiliser mysql CLI
            result = self._export_csv_cli(table_name, output_path, where_clause)
            
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
            
            self.output.add_result(
                f"Export CSV {table_name}",
                Severity.CRITICAL,
                f"Échec: {str(e)}"
            )
        
        return result
    
    def backup_critical_tables(self) -> Dict[str, Any]:
        """
        Sauvegarde toutes les tables critiques définies dans la config.
        
        Returns:
            Résultats des sauvegardes
        """
        self.output.print_header("Sauvegarde Tables Critiques WMS")
        
        critical_tables = self.config.get('backup', 'critical_tables', default=[
            'orders', 'inventory', 'shipments', 'customers', 'products'
        ])
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'type': 'critical_tables_backup',
            'tables': {},
            'success_count': 0,
            'failed_count': 0,
        }
        
        for table in critical_tables:
            self.output.print_separator(f"Table: {table}")
            table_result = self.export_table_to_csv(table)
            results['tables'][table] = table_result
            
            if table_result.get('status') == 'success':
                results['success_count'] += 1
            else:
                results['failed_count'] += 1
        
        # Résumé
        total = len(critical_tables)
        if results['failed_count'] == 0:
            results['status'] = 'success'
        elif results['success_count'] > 0:
            results['status'] = 'partial'
        else:
            results['status'] = 'failed'
        
        self.output.print_separator("Résumé")
        self.output.add_result(
            "Sauvegarde Tables Critiques",
            Severity.OK if results['status'] == 'success' else Severity.WARNING,
            f"{results['success_count']}/{total} tables sauvegardées"
        )
        
        return results
    
    def _run_mysqldump(self, output_path: Path) -> Dict[str, Any]:
        """
        Exécute mysqldump pour créer le backup SQL.
        
        Args:
            output_path: Chemin de sortie
            
        Returns:
            Résultat de l'opération
        """
        host = self.db_config.get('host')
        port = self.db_config.get('port', 3306)
        database = self.db_config.get('database')
        user = self.db_config.get('user')
        password = self.db_config.get('password')
        
        # Construire la commande mysqldump
        cmd = [
            'mysqldump',
            f'--host={host}',
            f'--port={port}',
            f'--user={user}',
            f'--password={password}',
            '--single-transaction',  # Cohérence pour InnoDB
            '--routines',            # Inclure procédures stockées
            '--triggers',            # Inclure triggers
            '--events',              # Inclure events
            '--add-drop-table',      # DROP TABLE avant CREATE
            '--complete-insert',     # INSERT avec noms de colonnes
            database
        ]
        
        start_time = datetime.now()
        
        try:
            if self.compress:
                # Pipe vers gzip
                output_path = Path(str(output_path))
                
                dump_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                with gzip.open(output_path, 'wb') as f:
                    while True:
                        chunk = dump_process.stdout.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                
                dump_process.wait()
                returncode = dump_process.returncode
                stderr = dump_process.stderr.read().decode('utf-8', errors='replace')
                
            else:
                with open(output_path, 'w', encoding='utf-8') as f:
                    result = subprocess.run(
                        cmd,
                        stdout=f,
                        stderr=subprocess.PIPE,
                        timeout=3600  # 1 heure max
                    )
                    returncode = result.returncode
                    stderr = result.stderr.decode('utf-8', errors='replace')
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if returncode == 0:
                file_size = os.path.getsize(output_path)
                return {
                    'success': True,
                    'size': file_size,
                    'duration': duration,
                }
            else:
                return {
                    'success': False,
                    'error': stderr or f'mysqldump a retourné le code {returncode}',
                }
                
        except FileNotFoundError:
            return {
                'success': False,
                'error': 'mysqldump non trouvé dans le PATH'
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Timeout dépassé (1 heure)'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _export_csv_cli(self, table_name: str, output_path: Path, 
                        where_clause: str = None) -> Dict[str, Any]:
        """
        Export CSV via mysql CLI (fallback).
        
        Args:
            table_name: Nom de la table
            output_path: Chemin de sortie
            where_clause: Clause WHERE optionnelle
            
        Returns:
            Résultat de l'export
        """
        host = self.db_config.get('host')
        port = self.db_config.get('port', 3306)
        database = self.db_config.get('database')
        user = self.db_config.get('user')
        password = self.db_config.get('password')
        
        query = f"SELECT * FROM `{table_name}`"
        if where_clause:
            query += f" WHERE {where_clause}"
        
        cmd = [
            'mysql',
            f'--host={host}',
            f'--port={port}',
            f'--user={user}',
            f'--password={password}',
            '--batch',           # Mode batch (TSV)
            '--skip-column-names',
            '-e', query,
            database
        ]
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'type': 'csv_export',
            'table': table_name,
            'output_path': str(output_path),
            'status': 'pending',
        }
        
        start_time = datetime.now()
        
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                timeout=3600
            )
            
            if process.returncode == 0:
                # Convertir TSV en CSV
                lines = process.stdout.decode('utf-8').split('\n')
                
                if self.compress:
                    file_handler = gzip.open(output_path, 'wt', encoding='utf-8', newline='')
                else:
                    file_handler = open(output_path, 'w', encoding='utf-8', newline='')
                
                row_count = 0
                with file_handler as f:
                    writer = csv.writer(f)
                    for line in lines:
                        if line.strip():
                            writer.writerow(line.split('\t'))
                            row_count += 1
                
                duration = (datetime.now() - start_time).total_seconds()
                file_size = os.path.getsize(output_path)
                
                result['status'] = 'success'
                result['row_count'] = row_count
                result['size'] = file_size
                result['size_formatted'] = OutputFormatter.format_bytes(file_size)
                result['duration_seconds'] = duration
                
                self.output.add_result(
                    f"Export CSV {table_name}",
                    Severity.OK,
                    f"{row_count} lignes exportées"
                )
            else:
                result['status'] = 'failed'
                result['error'] = process.stderr.decode('utf-8', errors='replace')
                
                self.output.add_result(
                    f"Export CSV {table_name}",
                    Severity.CRITICAL,
                    f"Échec: {result['error']}"
                )
                
        except FileNotFoundError:
            result['status'] = 'failed'
            result['error'] = 'mysql CLI non trouvé dans le PATH'
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
        
        return result
    
    def _verify_backup_integrity(self, file_path: Path) -> Dict[str, Any]:
        """
        Vérifie l'intégrité d'un fichier de sauvegarde.
        
        Args:
            file_path: Chemin du fichier
            
        Returns:
            Résultat de la vérification
        """
        try:
            sha256_hash = hashlib.sha256()
            
            # Lire le fichier par blocs
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    sha256_hash.update(chunk)
            
            return {
                'valid': True,
                'sha256': sha256_hash.hexdigest(),
                'file_size': os.path.getsize(file_path),
            }
            
        except Exception as e:
            self.logger.error(f"Erreur vérification intégrité: {e}")
            return {
                'valid': False,
                'error': str(e),
            }
    
    def _create_trace_file(self, result: Dict[str, Any], backup_path: Path) -> None:
        """
        Crée un fichier de traçabilité pour la sauvegarde.
        
        Args:
            result: Résultat de la sauvegarde
            backup_path: Chemin du fichier de sauvegarde
        """
        trace_path = Path(str(backup_path) + '.trace.json')
        
        trace_data = {
            'backup_file': os.path.basename(str(backup_path)),
            'backup_path': str(backup_path),
            'created_at': result.get('timestamp'),
            'type': result.get('type'),
            'database': result.get('database'),
            'table': result.get('table'),
            'status': result.get('status'),
            'size': result.get('size'),
            'row_count': result.get('row_count'),
            'integrity': result.get('integrity', {}),
            'duration_seconds': result.get('duration_seconds'),
        }
        
        try:
            with open(trace_path, 'w', encoding='utf-8') as f:
                json.dump(trace_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Fichier de traçabilité créé: {trace_path}")
            
        except Exception as e:
            self.logger.error(f"Erreur création fichier traçabilité: {e}")
    
    def cleanup_old_backups(self) -> Dict[str, Any]:
        """
        Supprime les sauvegardes plus anciennes que la période de rétention.
        
        Returns:
            Résultat du nettoyage
        """
        self.output.print_header("Nettoyage Anciennes Sauvegardes")
        
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        
        deleted_files = []
        errors = []
        
        # Parcourir les fichiers de sauvegarde
        for file_path in self.backup_dir.glob('*'):
            if file_path.is_file():
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    if mtime < cutoff_date:
                        # Fichier trop ancien, le supprimer
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        deleted_files.append({
                            'path': str(file_path),
                            'size': file_size,
                            'modified': mtime.isoformat(),
                        })
                        
                        self.logger.info(f"Supprimé: {file_path}")
                        
                except Exception as e:
                    errors.append({
                        'path': str(file_path),
                        'error': str(e),
                    })
                    self.logger.error(f"Erreur suppression {file_path}: {e}")
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'retention_days': self.retention_days,
            'cutoff_date': cutoff_date.isoformat(),
            'deleted_count': len(deleted_files),
            'deleted_files': deleted_files,
            'errors': errors,
        }
        
        total_freed = sum(f['size'] for f in deleted_files)
        
        self.output.add_result(
            "Nettoyage Sauvegardes",
            Severity.OK if not errors else Severity.WARNING,
            f"{len(deleted_files)} fichiers supprimés ({OutputFormatter.format_bytes(total_freed)} libérés)",
            details={'erreurs': len(errors)} if errors else None
        )
        
        return result

"""
Module de vérification de la connexion à la base de données MySQL.
"""

import subprocess
import socket
import platform
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from ..core.config import Config
from ..core.output import OutputFormatter, Severity
from ..core.logger import get_logger
from ..core.exit_codes import ExitCode


class DatabaseChecker:
    """
    Vérifie la connexion et l'état de la base de données MySQL/MariaDB.
    """
    
    def __init__(self, config: Config = None, output: OutputFormatter = None):
        """
        Initialise le vérificateur de base de données.
        
        Args:
            config: Instance de configuration
            output: Formateur de sortie
        """
        self.config = config or Config()
        self.output = output or OutputFormatter()
        self.logger = get_logger()
        self.db_config = self.config.get_db_config()
        self._connection = None
    
    def check_database(self) -> Dict[str, Any]:
        """
        Effectue une vérification complète de la base de données.
        
        Returns:
            Résultats de la vérification
        """
        self.output.print_header("Vérification Base de Données WMS")
        
        host = self.db_config.get('host', '192.168.10.21')
        port = self.db_config.get('port', 3306)
        database = self.db_config.get('database', 'wms_production')
        
        results = {
            'host': host,
            'port': port,
            'database': database,
            'timestamp': datetime.now().isoformat(),
            'checks': {},
        }
        
        # 1. Test de connectivité réseau (port)
        self.output.print_separator("Connectivité Réseau")
        port_ok, response_time = self._check_port(host, port)
        results['checks']['port_connectivity'] = {
            'status': 'ok' if port_ok else 'failed',
            'response_time_ms': response_time,
        }
        
        if port_ok:
            self.output.add_result(
                "Port MySQL",
                Severity.OK,
                f"Port {port} accessible ({response_time:.1f}ms)",
                target=f"{host}:{port}"
            )
        else:
            self.output.add_result(
                "Port MySQL",
                Severity.CRITICAL,
                f"Port {port} inaccessible",
                target=f"{host}:{port}"
            )
            results['exit_code'] = ExitCode.DB_CONNECTION_ERROR
            return results
        
        # 2. Test de connexion MySQL
        self.output.print_separator("Connexion MySQL")
        
        try:
            # Tenter d'importer mysql.connector
            import mysql.connector
            mysql_available = True
        except ImportError:
            mysql_available = False
            self.logger.warning("mysql-connector-python non installé, utilisation de mysqladmin")
        
        if mysql_available:
            conn_result = self._check_mysql_connection_native()
        else:
            conn_result = self._check_mysql_connection_cli()
        
        results['checks']['mysql_connection'] = conn_result
        
        if conn_result.get('status') == 'ok':
            self.output.add_result(
                "Connexion MySQL",
                Severity.OK,
                f"Connexion établie à {database}",
                details=conn_result.get('details', {}),
                target=host
            )
        else:
            self.output.add_result(
                "Connexion MySQL",
                Severity.CRITICAL,
                conn_result.get('error', 'Échec de connexion'),
                target=host
            )
            results['exit_code'] = ExitCode.DB_CONNECTION_ERROR
            return results
        
        # 3. Statistiques de la base (si connexion réussie)
        if mysql_available and conn_result.get('status') == 'ok':
            self.output.print_separator("Statistiques Base de Données")
            stats = self._get_database_stats()
            results['checks']['database_stats'] = stats
            
            if stats:
                self.output.add_result(
                    "Statistiques BD",
                    Severity.INFO,
                    f"Tables: {stats.get('table_count', 'N/A')}",
                    details=stats,
                    target=database
                )
        
        # 4. Vérification des processus MySQL
        self.output.print_separator("État du Serveur")
        server_status = self._check_server_status()
        results['checks']['server_status'] = server_status
        
        if server_status.get('uptime'):
            uptime_str = OutputFormatter.format_uptime(server_status['uptime'])
            self.output.add_result(
                "Uptime MySQL",
                Severity.OK,
                f"Serveur actif depuis {uptime_str}",
                target=host
            )
        
        results['exit_code'] = ExitCode.OK
        return results
    
    def _check_port(self, host: str, port: int, timeout: float = 5.0) -> Tuple[bool, float]:
        """
        Vérifie si le port MySQL est accessible.
        
        Args:
            host: Adresse du serveur
            port: Numéro de port
            timeout: Timeout en secondes
            
        Returns:
            Tuple (accessible, temps_ms)
        """
        import time
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            start_time = time.time()
            result = sock.connect_ex((host, port))
            elapsed = (time.time() - start_time) * 1000
            
            sock.close()
            
            return result == 0, elapsed
            
        except socket.timeout:
            return False, 0.0
        except Exception as e:
            self.logger.error(f"Erreur check port MySQL: {e}")
            return False, 0.0
    
    def _check_mysql_connection_native(self) -> Dict[str, Any]:
        """
        Teste la connexion MySQL avec mysql-connector-python.
        
        Returns:
            Résultat de la vérification
        """
        try:
            import mysql.connector
            from mysql.connector import Error
            
            connection = mysql.connector.connect(
                host=self.db_config.get('host'),
                port=self.db_config.get('port', 3306),
                database=self.db_config.get('database'),
                user=self.db_config.get('user'),
                password=self.db_config.get('password'),
                charset=self.db_config.get('charset', 'utf8mb4'),
                connect_timeout=self.db_config.get('connect_timeout', 10),
            )
            
            if connection.is_connected():
                db_info = connection.get_server_info()
                cursor = connection.cursor()
                cursor.execute("SELECT DATABASE();")
                db_name = cursor.fetchone()[0]
                
                self._connection = connection
                
                return {
                    'status': 'ok',
                    'details': {
                        'server_version': db_info,
                        'database': db_name,
                        'charset': connection.charset,
                    }
                }
            
            return {'status': 'failed', 'error': 'Connexion non établie'}
            
        except ImportError:
            return {'status': 'failed', 'error': 'mysql-connector-python non installé'}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    def _check_mysql_connection_cli(self) -> Dict[str, Any]:
        """
        Teste la connexion MySQL avec les outils CLI.
        
        Returns:
            Résultat de la vérification
        """
        host = self.db_config.get('host')
        port = self.db_config.get('port', 3306)
        user = self.db_config.get('user')
        password = self.db_config.get('password')
        database = self.db_config.get('database')
        
        try:
            # Tester avec mysqladmin
            cmd = [
                'mysqladmin',
                f'-h{host}',
                f'-P{port}',
                f'-u{user}',
                f'-p{password}',
                'ping'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if 'alive' in result.stdout.lower() or result.returncode == 0:
                return {
                    'status': 'ok',
                    'details': {'method': 'mysqladmin ping'}
                }
            else:
                return {
                    'status': 'failed',
                    'error': result.stderr or 'Échec mysqladmin ping'
                }
                
        except FileNotFoundError:
            return {
                'status': 'failed',
                'error': 'mysqladmin non trouvé dans le PATH'
            }
        except subprocess.TimeoutExpired:
            return {
                'status': 'failed',
                'error': 'Timeout connexion MySQL'
            }
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _get_database_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques de la base de données.
        
        Returns:
            Statistiques de la base
        """
        if not self._connection:
            return {}
        
        try:
            cursor = self._connection.cursor(dictionary=True)
            stats = {}
            
            # Nombre de tables
            cursor.execute("""
                SELECT COUNT(*) as table_count 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE()
            """)
            result = cursor.fetchone()
            stats['table_count'] = result['table_count'] if result else 0
            
            # Taille de la base
            cursor.execute("""
                SELECT 
                    SUM(data_length + index_length) as total_size,
                    SUM(data_length) as data_size,
                    SUM(index_length) as index_size
                FROM information_schema.tables 
                WHERE table_schema = DATABASE()
            """)
            result = cursor.fetchone()
            if result:
                stats['total_size'] = OutputFormatter.format_bytes(result['total_size'] or 0)
                stats['data_size'] = OutputFormatter.format_bytes(result['data_size'] or 0)
                stats['index_size'] = OutputFormatter.format_bytes(result['index_size'] or 0)
            
            cursor.close()
            return stats
            
        except Exception as e:
            self.logger.error(f"Erreur récupération stats DB: {e}")
            return {}
    
    def _check_server_status(self) -> Dict[str, Any]:
        """
        Vérifie le statut du serveur MySQL.
        
        Returns:
            Statut du serveur
        """
        if not self._connection:
            return {}
        
        try:
            cursor = self._connection.cursor(dictionary=True)
            
            # Variables du serveur
            cursor.execute("SHOW GLOBAL STATUS LIKE 'Uptime'")
            result = cursor.fetchone()
            uptime = int(result['Value']) if result else None
            
            # Connexions
            cursor.execute("SHOW GLOBAL STATUS LIKE 'Threads_connected'")
            result = cursor.fetchone()
            connections = int(result['Value']) if result else None
            
            # Requêtes
            cursor.execute("SHOW GLOBAL STATUS LIKE 'Queries'")
            result = cursor.fetchone()
            queries = int(result['Value']) if result else None
            
            cursor.close()
            
            return {
                'uptime': uptime,
                'connections': connections,
                'total_queries': queries,
            }
            
        except Exception as e:
            self.logger.error(f"Erreur récupération status serveur: {e}")
            return {}
    
    def close(self):
        """Ferme la connexion à la base de données."""
        if self._connection:
            try:
                self._connection.close()
            except:
                pass
            self._connection = None
    
    def __del__(self):
        """Destructeur - ferme la connexion."""
        self.close()

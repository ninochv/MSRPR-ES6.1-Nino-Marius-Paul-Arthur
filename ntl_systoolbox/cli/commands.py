"""
Gestionnaire de commandes CLI pour NTL-SysToolbox.
Exécute les commandes non-interactives.
"""

import sys
from typing import Any
from argparse import Namespace

from ..core import Config, OutputFormatter, ExitCode, get_logger
from ..diagnostic import ServiceChecker, DatabaseChecker, SystemInfoCollector
from ..backup import WMSBackupManager, IntegrityChecker
from ..audit import NetworkScanner, EOLDatabase, ObsolescenceReport


class CommandHandler:
    """
    Gère l'exécution des commandes CLI.
    """
    
    def __init__(self, config: Config = None, output: OutputFormatter = None):
        """
        Initialise le gestionnaire de commandes.
        
        Args:
            config: Instance de configuration
            output: Formateur de sortie
        """
        self.config = config or Config()
        self.output = output or OutputFormatter()
        self.logger = get_logger()
    
    def execute(self, args: Namespace) -> int:
        """
        Exécute une commande basée sur les arguments.
        
        Args:
            args: Arguments parsés
            
        Returns:
            Code de sortie
        """
        command = args.command
        
        if command in ('diagnostic', 'diag'):
            return self._handle_diagnostic(args)
        elif command in ('backup', 'bkp'):
            return self._handle_backup(args)
        elif command == 'audit':
            return self._handle_audit(args)
        else:
            print(f"Commande inconnue: {command}")
            print("Utilisez --help pour voir les commandes disponibles.")
            return ExitCode.UNKNOWN
    
    def _handle_diagnostic(self, args: Namespace) -> int:
        """Gère les commandes du module diagnostic."""
        sub_command = args.diag_command
        
        if sub_command == 'services':
            self.output.set_module("Vérification Services AD/DNS")
            checker = ServiceChecker(config=self.config, output=self.output)
            
            if args.dc:
                checker.check_domain_controller(args.dc)
            else:
                checker.check_all_domain_controllers()
            
            return self.output.print_summary()
        
        elif sub_command in ('database', 'db'):
            self.output.set_module("Vérification Base de Données")
            
            # Override config si spécifié
            if args.host:
                self.config._config.setdefault('wms_database', {})['host'] = args.host
            if args.port:
                self.config._config.setdefault('wms_database', {})['port'] = args.port
            
            checker = DatabaseChecker(config=self.config, output=self.output)
            checker.check_database()
            
            return self.output.print_summary()
        
        elif sub_command in ('system', 'sys'):
            self.output.set_module("Informations Système")
            collector = SystemInfoCollector(config=self.config, output=self.output)
            collector.collect_local_info()
            
            return self.output.print_summary()
        
        elif sub_command == 'all':
            self.output.set_module("Diagnostic Complet")
            
            # Services
            checker = ServiceChecker(config=self.config, output=self.output)
            checker.check_all_domain_controllers()
            
            # Database
            db_checker = DatabaseChecker(config=self.config, output=self.output)
            db_checker.check_database()
            
            # System
            collector = SystemInfoCollector(config=self.config, output=self.output)
            collector.collect_local_info()
            
            return self.output.print_summary()
        
        else:
            print("Sous-commande diagnostic requise. Utilisez --help.")
            return ExitCode.UNKNOWN
    
    def _handle_backup(self, args: Namespace) -> int:
        """Gère les commandes du module backup."""
        sub_command = args.backup_command
        
        if sub_command == 'full':
            self.output.set_module("Sauvegarde Complète")
            manager = WMSBackupManager(config=self.config, output=self.output)
            
            output_path = getattr(args, 'output', None)
            manager.backup_full_database(output_path)
            
            return self.output.print_summary()
        
        elif sub_command == 'table':
            self.output.set_module("Export Table CSV")
            manager = WMSBackupManager(config=self.config, output=self.output)
            
            manager.export_table_to_csv(
                args.table_name,
                output_path=getattr(args, 'output', None),
                where_clause=getattr(args, 'where', None)
            )
            
            return self.output.print_summary()
        
        elif sub_command == 'critical':
            self.output.set_module("Sauvegarde Tables Critiques")
            manager = WMSBackupManager(config=self.config, output=self.output)
            manager.backup_critical_tables()
            
            return self.output.print_summary()
        
        elif sub_command == 'verify':
            self.output.set_module("Vérification Intégrité")
            checker = IntegrityChecker(config=self.config, output=self.output)
            
            if getattr(args, 'all', False):
                checker.verify_all_backups()
            elif args.backup_file:
                checker.verify_backup(args.backup_file)
            else:
                checker.verify_all_backups()
            
            return self.output.print_summary()
        
        elif sub_command == 'cleanup':
            self.output.set_module("Nettoyage Sauvegardes")
            manager = WMSBackupManager(config=self.config, output=self.output)
            manager.cleanup_old_backups()
            
            return self.output.print_summary()
        
        else:
            print("Sous-commande backup requise. Utilisez --help.")
            return ExitCode.UNKNOWN
    
    def _handle_audit(self, args: Namespace) -> int:
        """Gère les commandes du module audit."""
        sub_command = args.audit_command
        
        if sub_command == 'scan':
            self.output.set_module("Scan Réseau")
            scanner = NetworkScanner(config=self.config, output=self.output)
            
            if getattr(args, 'host', None):
                scanner.scan_host_detailed(args.host)
            else:
                network_range = getattr(args, 'range', None)
                scanner.scan_network(network_range)
            
            return self.output.print_summary()
        
        elif sub_command == 'report':
            self.output.set_module("Rapport d'Obsolescence")
            report = ObsolescenceReport(config=self.config, output=self.output)
            
            network_range = getattr(args, 'range', None)
            save = not getattr(args, 'no_save', False)
            
            report.generate_full_report(network_range=network_range, save_report=save)
            
            return self.output.print_summary()
        
        elif sub_command == 'check':
            self.output.set_module("Vérification EOL")
            report = ObsolescenceReport(config=self.config, output=self.output)
            report.check_single_os(args.os_name)
            
            return self.output.print_summary()
        
        elif sub_command == 'list-eol':
            self.output.set_module("Base EOL")
            eol_db = EOLDatabase(config=self.config)
            
            print("\n" + "=" * 60)
            print("BASE DE DONNÉES END-OF-LIFE (EOL)")
            print("=" * 60)
            
            for os_name in sorted(eol_db.get_all_os()):
                status = eol_db.check_eol_status(os_name)
                criticality = status.get('criticality', 'unknown')
                
                if criticality == 'critical':
                    symbol = "[CRITIQUE]"
                elif criticality == 'warning':
                    symbol = "[ATTENTION]"
                elif criticality == 'ok':
                    symbol = "[OK]"
                else:
                    symbol = "[?]"
                
                eol_date = status.get('eol_date', 'N/A')
                print(f"{symbol:12} {os_name:30} EOL: {eol_date}")
            
            return ExitCode.OK
        
        else:
            print("Sous-commande audit requise. Utilisez --help.")
            return ExitCode.UNKNOWN

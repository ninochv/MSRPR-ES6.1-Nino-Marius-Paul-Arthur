"""
Menu interactif pour NTL-SysToolbox.
"""

import sys
import os
from typing import Optional, Callable, Dict, Any

from ..core import Config, OutputFormatter, ExitCode, get_logger
from ..diagnostic import ServiceChecker, DatabaseChecker, SystemInfoCollector
from ..backup import WMSBackupManager, IntegrityChecker
from ..audit import NetworkScanner, EOLDatabase, ObsolescenceReport


class InteractiveMenu:
    """
    Menu interactif CLI pour NTL-SysToolbox.
    """
    
    BANNER = r"""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   ███╗   ██╗████████╗██╗      ███████╗██╗   ██╗███████╗   ║
║   ████╗  ██║╚══██╔══╝██║      ██╔════╝╚██╗ ██╔╝██╔════╝   ║
║   ██╔██╗ ██║   ██║   ██║█████╗███████╗ ╚████╔╝ ███████╗   ║
║   ██║╚██╗██║   ██║   ██║╚════╝╚════██║  ╚██╔╝  ╚════██║   ║
║   ██║ ╚████║   ██║   ███████╗ ███████║   ██║   ███████║   ║
║   ╚═╝  ╚═══╝   ╚═╝   ╚══════╝ ╚══════╝   ╚═╝   ╚══════╝   ║
║                                                           ║
║          Nord Transit Logistics - SysToolbox              ║
║                     Version 1.0.2                         ║
╚═══════════════════════════════════════════════════════════╝

    """
    
    def __init__(self, config: Config = None, output: OutputFormatter = None):
        """
        Initialise le menu interactif.
        
        Args:
            config: Instance de configuration
            output: Formateur de sortie
        """
        self.config = config or Config()
        self.output = output or OutputFormatter()
        self.logger = get_logger()
        self.running = True
        self.last_exit_code = ExitCode.OK
    
    def run(self) -> int:
        """
        Lance le menu interactif principal.
        
        Returns:
            Code de sortie
        """
        self._clear_screen()
        print(self.BANNER)
        
        while self.running:
            try:
                self._show_main_menu()
                choice = self._get_input("\n➤ Votre choix: ")
                self._handle_main_choice(choice)
                
            except KeyboardInterrupt:
                print("\n\nInterruption détectée. Utilisez 'q' pour quitter proprement.")
            except Exception as e:
                self.logger.error(f"Erreur: {e}")
                print(f"\n[ERREUR] {e}")
        
        print("\nAu revoir!\n")
        return self.last_exit_code
    
    def _clear_screen(self):
        """Efface l'écran."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def _show_main_menu(self):
        """Affiche le menu principal."""
        print("\n" + "=" * 50)
        print("              MENU PRINCIPAL")
        print("=" * 50)
        print()
        print("  [1] Module Diagnostic")
        print("      -> Services AD/DNS, MySQL, Etat systeme")
        print()
        print("  [2] Module Sauvegarde WMS")
        print("      -> Export SQL/CSV, Integrite")
        print()
        print("  [3] Module Audit d'Obsolescence")
        print("      -> Scan reseau, Rapport EOL")
        print()
        print("  [4] Configuration")
        print("      -> Afficher/Modifier la configuration")
        print()
        print("  [q] Quitter")
        print()
        print("-" * 50)
    
    def _handle_main_choice(self, choice: str):
        """Gère le choix du menu principal."""
        choice = choice.strip().lower()
        
        if choice == '1':
            self._diagnostic_menu()
        elif choice == '2':
            self._backup_menu()
        elif choice == '3':
            self._audit_menu()
        elif choice == '4':
            self._config_menu()
        elif choice in ('q', 'quit', 'exit'):
            self.running = False
        else:
            print("\n[!] Choix invalide. Veuillez reessayer.")
    
    def _diagnostic_menu(self):
        """Menu du module Diagnostic."""
        while True:
            self._clear_screen()
            print("\n" + "=" * 50)
            print("         MODULE DIAGNOSTIC")
            print("=" * 50)
            print()
            print("  [1] Verifier les Controleurs de Domaine")
            print("      -> Services AD/DNS sur 192.168.10.10/11")
            print()
            print("  [2] Tester la connexion MySQL")
            print("      -> Base WMS sur 192.168.10.21")
            print()
            print("  [3] Informations Systeme Local")
            print("      -> Uptime, CPU, RAM, Disques")
            print()
            print("  [4] Executer TOUS les diagnostics")
            print()
            print("  [b] Retour au menu principal")
            print()
            print("-" * 50)
            
            choice = self._get_input("\n➤ Votre choix: ").strip().lower()
            
            if choice == '1':
                self._run_service_check()
            elif choice == '2':
                self._run_database_check()
            elif choice == '3':
                self._run_system_check()
            elif choice == '4':
                self._run_all_diagnostics()
            elif choice in ('b', 'back', 'retour'):
                break
            
            if choice in ('1', '2', '3', '4'):
                self._pause()
    
    def _run_service_check(self):
        """Exécute la vérification des services."""
        print("\n" + "=" * 60)
        self.output.set_module("Vérification Services AD/DNS")
        
        # Demander si on veut un DC spécifique
        dc_ip = self._get_input("IP du DC (laisser vide pour tous): ").strip()
        
        checker = ServiceChecker(config=self.config, output=self.output)
        
        if dc_ip:
            result = checker.check_domain_controller(dc_ip)
        else:
            result = checker.check_all_domain_controllers()
        
        self.last_exit_code = self.output.print_summary()
    
    def _run_database_check(self):
        """Exécute la vérification de la base de données."""
        print("\n" + "=" * 60)
        self.output.set_module("Vérification Base de Données")
        
        checker = DatabaseChecker(config=self.config, output=self.output)
        result = checker.check_database()
        
        self.last_exit_code = self.output.print_summary()
    
    def _run_system_check(self):
        """Exécute la collecte d'informations système."""
        print("\n" + "=" * 60)
        self.output.set_module("Informations Système")
        
        collector = SystemInfoCollector(config=self.config, output=self.output)
        result = collector.collect_local_info()
        
        self.last_exit_code = self.output.print_summary()
    
    def _run_all_diagnostics(self):
        """Exécute tous les diagnostics."""
        print("\n" + "=" * 60)
        print("Exécution de tous les diagnostics...")
        print("=" * 60)
        
        self._run_service_check()
        self._run_database_check()
        self._run_system_check()
    
    def _backup_menu(self):
        """Menu du module Sauvegarde."""
        while True:
            self._clear_screen()
            print("\n" + "=" * 50)
            print("         MODULE SAUVEGARDE WMS")
            print("=" * 50)
            print()
            print("  [1] Sauvegarde COMPLETE (SQL)")
            print("      -> Export mysqldump de toute la base")
            print()
            print("  [2] Exporter une TABLE en CSV")
            print("      -> Export d'une table specifique")
            print()
            print("  [3] Sauvegarder les TABLES CRITIQUES")
            print("      -> orders, inventory, shipments, etc.")
            print()
            print("  [4] Verifier l'integrite d'une sauvegarde")
            print()
            print("  [5] Nettoyer les anciennes sauvegardes")
            print()
            print("  [b] Retour au menu principal")
            print()
            print("-" * 50)
            
            choice = self._get_input("\n➤ Votre choix: ").strip().lower()
            
            if choice == '1':
                self._run_full_backup()
            elif choice == '2':
                self._run_table_export()
            elif choice == '3':
                self._run_critical_backup()
            elif choice == '4':
                self._run_integrity_check()
            elif choice == '5':
                self._run_backup_cleanup()
            elif choice in ('b', 'back', 'retour'):
                break
            
            if choice in ('1', '2', '3', '4', '5'):
                self._pause()
    
    def _run_full_backup(self):
        """Exécute une sauvegarde complète."""
        print("\n" + "=" * 60)
        self.output.set_module("Sauvegarde Complète")
        
        output_path = self._get_input("Chemin de sortie (laisser vide pour auto): ").strip()
        
        manager = WMSBackupManager(config=self.config, output=self.output)
        result = manager.backup_full_database(output_path if output_path else None)
        
        self.last_exit_code = self.output.print_summary()
    
    def _run_table_export(self):
        """Exécute l'export d'une table."""
        print("\n" + "=" * 60)
        self.output.set_module("Export Table CSV")
        
        table_name = self._get_input("Nom de la table: ").strip()
        if not table_name:
            print("[ERREUR] Nom de table requis")
            return
        
        where_clause = self._get_input("Clause WHERE (optionnel): ").strip()
        
        manager = WMSBackupManager(config=self.config, output=self.output)
        result = manager.export_table_to_csv(
            table_name,
            where_clause=where_clause if where_clause else None
        )
        
        self.last_exit_code = self.output.print_summary()
    
    def _run_critical_backup(self):
        """Sauvegarde les tables critiques."""
        print("\n" + "=" * 60)
        self.output.set_module("Sauvegarde Tables Critiques")
        
        manager = WMSBackupManager(config=self.config, output=self.output)
        result = manager.backup_critical_tables()
        
        self.last_exit_code = self.output.print_summary()
    
    def _run_integrity_check(self):
        """Vérifie l'intégrité des sauvegardes."""
        print("\n" + "=" * 60)
        self.output.set_module("Vérification Intégrité")
        
        checker = IntegrityChecker(config=self.config, output=self.output)
        
        file_path = self._get_input("Fichier à vérifier (laisser vide pour tous): ").strip()
        
        if file_path:
            result = checker.verify_backup(file_path)
        else:
            result = checker.verify_all_backups()
        
        self.last_exit_code = self.output.print_summary()
    
    def _run_backup_cleanup(self):
        """Nettoie les anciennes sauvegardes."""
        print("\n" + "=" * 60)
        self.output.set_module("Nettoyage Sauvegardes")
        
        confirm = self._get_input("Confirmer la suppression des anciennes sauvegardes? [o/N]: ")
        
        if confirm.lower() in ('o', 'oui', 'y', 'yes'):
            manager = WMSBackupManager(config=self.config, output=self.output)
            result = manager.cleanup_old_backups()
            self.last_exit_code = self.output.print_summary()
        else:
            print("Annulé.")
    
    def _audit_menu(self):
        """Menu du module Audit."""
        while True:
            self._clear_screen()
            print("\n" + "=" * 50)
            print("      MODULE AUDIT D'OBSOLESCENCE")
            print("=" * 50)
            print()
            print("  [1] Scanner le reseau")
            print("      -> Decouvrir les hotes et identifier les OS")
            print()
            print("  [2] Generer un rapport d'obsolescence")
            print("      -> Scan + Analyse EOL complete")
            print()
            print("  [3] Verifier un OS specifique")
            print("      -> Statut EOL d'un systeme")
            print()
            print("  [4] Lister la base EOL")
            print("      -> Tous les OS et leurs dates de fin de vie")
            print()
            print("  [b] Retour au menu principal")
            print()
            print("-" * 50)
            
            choice = self._get_input("\n➤ Votre choix: ").strip().lower()
            
            if choice == '1':
                self._run_network_scan()
            elif choice == '2':
                self._run_obsolescence_report()
            elif choice == '3':
                self._run_eol_check()
            elif choice == '4':
                self._run_list_eol()
            elif choice in ('b', 'back', 'retour'):
                break
            
            if choice in ('1', '2', '3', '4'):
                self._pause()
    
    def _run_network_scan(self):
        """Exécute un scan réseau."""
        print("\n" + "=" * 60)
        self.output.set_module("Scan Réseau")
        
        network_range = self._get_input("Plage réseau (défaut: 192.168.10.0/24): ").strip()
        
        scanner = NetworkScanner(config=self.config, output=self.output)
        
        host = self._get_input("Scanner un hôte spécifique? (laisser vide pour plage): ").strip()
        
        if host:
            result = scanner.scan_host_detailed(host)
        else:
            result = scanner.scan_network(network_range if network_range else None)
        
        self.last_exit_code = self.output.print_summary()
    
    def _run_obsolescence_report(self):
        """Génère un rapport d'obsolescence."""
        print("\n" + "=" * 60)
        self.output.set_module("Rapport d'Obsolescence")
        
        network_range = self._get_input("Plage réseau (défaut: 192.168.10.0/24): ").strip()
        
        report = ObsolescenceReport(config=self.config, output=self.output)
        result = report.generate_full_report(
            network_range=network_range if network_range else None
        )
        
        self.last_exit_code = self.output.print_summary()
    
    def _run_eol_check(self):
        """Vérifie le statut EOL d'un OS."""
        print("\n" + "=" * 60)
        self.output.set_module("Vérification EOL")
        
        os_name = self._get_input("Nom de l'OS à vérifier: ").strip()
        
        if not os_name:
            print("[ERREUR] Nom d'OS requis")
            return
        
        report = ObsolescenceReport(config=self.config, output=self.output)
        result = report.check_single_os(os_name)
        
        self.last_exit_code = self.output.print_summary()
    
    def _run_list_eol(self):
        """Liste tous les OS de la base EOL."""
        print("\n" + "=" * 60)
        print("BASE DE DONNÉES END-OF-LIFE (EOL)")
        print("=" * 60)
        
        eol_db = EOLDatabase(config=self.config)
        
        # Grouper par type d'OS
        from collections import defaultdict
        grouped = defaultdict(list)
        
        for os_name in eol_db.get_all_os():
            status = eol_db.check_eol_status(os_name)
            
            # Déterminer la catégorie
            os_lower = os_name.lower()
            if 'windows' in os_lower:
                category = 'Windows'
            elif 'ubuntu' in os_lower:
                category = 'Ubuntu'
            elif 'debian' in os_lower:
                category = 'Debian'
            elif 'centos' in os_lower or 'rhel' in os_lower or 'red hat' in os_lower:
                category = 'RHEL/CentOS'
            elif 'esxi' in os_lower or 'vmware' in os_lower:
                category = 'VMware ESXi'
            else:
                category = 'Autres'
            
            grouped[category].append((os_name, status))
        
        # Afficher
        for category in ['Windows', 'Ubuntu', 'Debian', 'RHEL/CentOS', 'VMware ESXi', 'Autres']:
            if category in grouped:
                print(f"\n--- {category} ---")
                for os_name, status in grouped[category]:
                    criticality = status.get('criticality', 'unknown')
                    
                    if criticality == 'critical':
                        icon = "[X]"
                    elif criticality == 'warning':
                        icon = "[!]"
                    elif criticality == 'ok':
                        icon = "[OK]"
                    else:
                        icon = "[?]"
                    
                    eol_date = status.get('eol_date', 'N/A')
                    print(f"  {icon} {os_name}: EOL {eol_date}")
        
        print()
    
    def _config_menu(self):
        """Menu de configuration."""
        self._clear_screen()
        print("\n" + "=" * 50)
        print("         CONFIGURATION")
        print("=" * 50)
        print()
        print("Configuration actuelle:")
        print("-" * 40)
        
        # Afficher la config principale
        print(f"  Log Level: {self.config.get('general', 'log_level', default='INFO')}")
        print(f"  Log Dir: {self.config.get('general', 'log_dir', default='./logs')}")
        print(f"  Backup Dir: {self.config.get('general', 'backup_dir', default='./backups')}")
        print(f"  Report Dir: {self.config.get('general', 'report_dir', default='./reports')}")
        print(f"  Output Format: {self.config.get('general', 'output_format', default='both')}")
        
        print()
        print("Contrôleurs de Domaine:")
        for dc in self.config.get_domain_controllers():
            print(f"  - {dc.get('name')}: {dc.get('ip')}")
        
        print()
        print("Base de données WMS:")
        db_config = self.config.get_db_config()
        print(f"  Host: {db_config.get('host')}:{db_config.get('port', 3306)}")
        print(f"  Database: {db_config.get('database')}")
        print(f"  User: {db_config.get('user', '***')}")
        
        print()
        print("Seuils d'alerte:")
        thresholds = self.config.get_thresholds()
        print(f"  CPU Warning/Critical: {thresholds.get('cpu_warning')}%/{thresholds.get('cpu_critical')}%")
        print(f"  RAM Warning/Critical: {thresholds.get('memory_warning')}%/{thresholds.get('memory_critical')}%")
        print(f"  Disk Warning/Critical: {thresholds.get('disk_warning')}%/{thresholds.get('disk_critical')}%")
        print(f"  EOL Warning/Critical: {thresholds.get('eol_warning_days')}j/{thresholds.get('eol_critical_days')}j")
        
        print()
        print("-" * 40)
        print("Fichier de configuration: config.yaml")
        print("Variables d'environnement: .env")
        
        self._pause()
    
    def _get_input(self, prompt: str) -> str:
        """Affiche un prompt et récupère l'entrée utilisateur."""
        try:
            return input(prompt)
        except EOFError:
            return ''
    
    def _pause(self):
        """Pause en attendant une touche."""
        print()
        self._get_input("Appuyez sur Entrée pour continuer...")

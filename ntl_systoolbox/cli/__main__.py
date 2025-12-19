#!/usr/bin/env python3
"""
NTL-SysToolbox - Interface CLI interactive
Outil d'exploitation système pour Nord Transit Logistics
"""

import sys
import os
import argparse
from typing import Optional

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ntl_systoolbox import __version__
from ntl_systoolbox.core import setup_logger, get_logger, Config, OutputFormatter, ExitCode
from ntl_systoolbox.cli.menu import InteractiveMenu
from ntl_systoolbox.cli.commands import CommandHandler


def parse_arguments():
    """Parse les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(
        prog='ntl-systoolbox',
        description='NTL-SysToolbox - Outil CLI pour Nord Transit Logistics',
        epilog='Utilisez --interactive pour le menu interactif ou spécifiez une commande.'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version=f'NTL-SysToolbox v{__version__}'
    )
    
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Lancer le menu interactif'
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        default=None,
        help='Chemin vers le fichier de configuration'
    )
    
    parser.add_argument(
        '--output', '-o',
        choices=['human', 'json', 'both'],
        default='both',
        help='Format de sortie (défaut: both)'
    )
    
    parser.add_argument(
        '--log-level', '-l',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Niveau de log (défaut: INFO)'
    )
    
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Désactiver les couleurs dans la sortie'
    )
    
    # Sous-commandes
    subparsers = parser.add_subparsers(dest='command', help='Commandes disponibles')
    
    # === Module Diagnostic ===
    diag_parser = subparsers.add_parser('diagnostic', aliases=['diag'], 
                                         help='Module de diagnostic système')
    diag_sub = diag_parser.add_subparsers(dest='diag_command')
    
    # diagnostic services
    services_parser = diag_sub.add_parser('services', help='Vérifier les services AD/DNS')
    services_parser.add_argument('--dc', type=str, help='IP du contrôleur de domaine spécifique')
    
    # diagnostic database
    db_parser = diag_sub.add_parser('database', aliases=['db'], help='Vérifier la connexion MySQL')
    db_parser.add_argument('--host', type=str, help='Hôte MySQL')
    db_parser.add_argument('--port', type=int, help='Port MySQL')
    
    # diagnostic system
    sys_parser = diag_sub.add_parser('system', aliases=['sys'], help='Informations système local')
    
    # diagnostic all
    all_parser = diag_sub.add_parser('all', help='Exécuter tous les diagnostics')
    
    # === Module Sauvegarde ===
    backup_parser = subparsers.add_parser('backup', aliases=['bkp'],
                                          help='Module de sauvegarde WMS')
    backup_sub = backup_parser.add_subparsers(dest='backup_command')
    
    # backup full
    full_parser = backup_sub.add_parser('full', help='Sauvegarde complète de la base')
    full_parser.add_argument('--output', '-o', type=str, help='Chemin du fichier de sortie')
    
    # backup table
    table_parser = backup_sub.add_parser('table', help='Exporter une table en CSV')
    table_parser.add_argument('table_name', type=str, help='Nom de la table à exporter')
    table_parser.add_argument('--output', '-o', type=str, help='Chemin du fichier de sortie')
    table_parser.add_argument('--where', type=str, help='Clause WHERE pour filtrer')
    
    # backup critical
    critical_parser = backup_sub.add_parser('critical', help='Sauvegarder les tables critiques')
    
    # backup verify
    verify_parser = backup_sub.add_parser('verify', help='Vérifier l\'intégrité d\'une sauvegarde')
    verify_parser.add_argument('backup_file', type=str, nargs='?', help='Fichier à vérifier')
    verify_parser.add_argument('--all', action='store_true', help='Vérifier toutes les sauvegardes')
    
    # backup cleanup
    cleanup_parser = backup_sub.add_parser('cleanup', help='Nettoyer les anciennes sauvegardes')
    
    # === Module Audit ===
    audit_parser = subparsers.add_parser('audit', help='Module d\'audit d\'obsolescence')
    audit_sub = audit_parser.add_subparsers(dest='audit_command')
    
    # audit scan
    scan_parser = audit_sub.add_parser('scan', help='Scanner le réseau')
    scan_parser.add_argument('--range', '-r', type=str, help='Plage réseau (ex: 192.168.10.0/24)')
    scan_parser.add_argument('--host', type=str, help='Scanner un hôte spécifique')
    
    # audit report
    report_parser = audit_sub.add_parser('report', help='Générer un rapport d\'obsolescence')
    report_parser.add_argument('--range', '-r', type=str, help='Plage réseau')
    report_parser.add_argument('--no-save', action='store_true', help='Ne pas sauvegarder le rapport')
    
    # audit check
    check_parser = audit_sub.add_parser('check', help='Vérifier le statut EOL d\'un OS')
    check_parser.add_argument('os_name', type=str, help='Nom de l\'OS à vérifier')
    
    # audit list-eol
    list_parser = audit_sub.add_parser('list-eol', help='Lister tous les OS dans la base EOL')
    
    return parser.parse_args()


def main():
    """Point d'entrée principal."""
    args = parse_arguments()
    
    # Initialiser la configuration
    config = Config()
    if args.config:
        config.load(config_path=args.config)
    
    # Initialiser le logger
    log_level = args.log_level or config.get('general', 'log_level', default='INFO')
    log_dir = config.get('general', 'log_dir', default='./logs')
    logger = setup_logger(log_level=log_level, log_dir=log_dir)
    
    # Initialiser le formateur de sortie
    output_format = args.output or config.get('general', 'output_format', default='both')
    use_colors = not args.no_color
    output = OutputFormatter(format_type=output_format, use_colors=use_colors)
    
    # Mode interactif ou commande directe
    if args.interactive or args.command is None:
        # Lancer le menu interactif
        menu = InteractiveMenu(config=config, output=output)
        exit_code = menu.run()
    else:
        # Exécuter la commande
        handler = CommandHandler(config=config, output=output)
        exit_code = handler.execute(args)
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()

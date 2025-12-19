"""
Module de génération de rapports d'obsolescence.
Combine les résultats du scan réseau avec la base EOL.
"""

import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict

from ..core.config import Config
from ..core.output import OutputFormatter, Severity
from ..core.logger import get_logger
from .scanner import NetworkScanner
from .eol_database import EOLDatabase


class ObsolescenceReport:
    """
    Génère des rapports d'obsolescence basés sur le scan réseau et la base EOL.
    """
    
    def __init__(self, config: Config = None, output: OutputFormatter = None):
        """
        Initialise le générateur de rapports.
        
        Args:
            config: Instance de configuration
            output: Formateur de sortie
        """
        self.config = config or Config()
        self.output = output or OutputFormatter()
        self.logger = get_logger()
        
        self.scanner = NetworkScanner(config=self.config, output=self.output)
        self.eol_db = EOLDatabase(config=self.config)
        
        self.report_dir = Path(self.config.get('general', 'report_dir', default='./reports'))
        self.report_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_full_report(self, network_range: str = None, 
                             save_report: bool = True) -> Dict[str, Any]:
        """
        Génère un rapport complet d'obsolescence.
        
        Args:
            network_range: Plage réseau à scanner
            save_report: Sauvegarder le rapport en fichier
            
        Returns:
            Rapport complet
        """
        self.output.set_module("Audit d'Obsolescence")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'generated_by': 'NTL-SysToolbox',
            'network_range': network_range,
            'summary': {
                'total_hosts': 0,
                'analyzed': 0,
                'supported': 0,
                'warning': 0,
                'critical': 0,
                'unknown': 0,
            },
            'hosts': [],
            'by_criticality': {
                'critical': [],
                'warning': [],
                'ok': [],
                'unknown': [],
            },
            'recommendations': [],
        }
        
        # 1. Scanner le réseau
        scan_results = self.scanner.scan_network(network_range)
        report['network_range'] = scan_results.get('network')
        report['summary']['total_hosts'] = scan_results.get('hosts_up', 0)
        
        # 2. Analyser chaque hôte
        self.output.print_header("Analyse EOL des Hôtes Découverts")
        
        for host in scan_results.get('hosts', []):
            host_analysis = self._analyze_host(host)
            report['hosts'].append(host_analysis)
            
            # Comptabiliser
            criticality = host_analysis.get('eol_status', {}).get('criticality', 'unknown')
            
            if criticality == 'critical':
                report['summary']['critical'] += 1
                report['by_criticality']['critical'].append(host_analysis)
            elif criticality == 'warning':
                report['summary']['warning'] += 1
                report['by_criticality']['warning'].append(host_analysis)
            elif criticality == 'ok':
                report['summary']['supported'] += 1
                report['by_criticality']['ok'].append(host_analysis)
            else:
                report['summary']['unknown'] += 1
                report['by_criticality']['unknown'].append(host_analysis)
            
            report['summary']['analyzed'] += 1
        
        # 3. Générer les recommandations
        report['recommendations'] = self._generate_recommendations(report)
        
        # 4. Afficher le résumé
        self._print_summary(report)
        
        # 5. Sauvegarder le rapport
        if save_report:
            report_path = self._save_report(report)
            report['report_file'] = str(report_path)
        
        return report
    
    def _analyze_host(self, host: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyse un hôte pour déterminer son statut EOL.
        
        Args:
            host: Informations sur l'hôte
            
        Returns:
            Analyse de l'hôte
        """
        ip = host.get('ip')
        os_guess = host.get('os_guess', 'Inconnu')
        
        analysis = {
            'ip': ip,
            'hostname': host.get('hostname'),
            'os_detected': os_guess,
            'os_confidence': host.get('os_details', {}).get('confidence', 'low'),
            'open_ports': list(host.get('open_ports', {}).keys()),
            'eol_status': {},
            'scan_time': host.get('scan_time'),
        }
        
        # Vérifier le statut EOL
        if os_guess and os_guess != 'Inconnu':
            eol_status = self.eol_db.check_eol_status(os_guess)
            analysis['eol_status'] = eol_status
            
            # Afficher le résultat
            criticality = eol_status.get('criticality', 'unknown')
            
            if criticality == 'critical':
                severity = Severity.CRITICAL
            elif criticality == 'warning':
                severity = Severity.WARNING
            elif criticality == 'ok':
                severity = Severity.OK
            else:
                severity = Severity.UNKNOWN
            
            self.output.add_result(
                f"{ip}",
                severity,
                f"{eol_status.get('os_normalized', os_guess)} - {eol_status.get('message', 'Statut inconnu')}",
                details={
                    'hostname': host.get('hostname'),
                    'eol_date': eol_status.get('eol_date'),
                },
                target=ip
            )
        else:
            analysis['eol_status'] = {
                'status': 'unknown',
                'criticality': 'unknown',
                'message': 'OS non identifié',
            }
            
            self.output.add_result(
                f"{ip}",
                Severity.UNKNOWN,
                "OS non identifié - Vérification manuelle requise",
                details={'hostname': host.get('hostname')},
                target=ip
            )
        
        return analysis
    
    def _generate_recommendations(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Génère des recommandations basées sur le rapport.
        
        Args:
            report: Rapport d'analyse
            
        Returns:
            Liste des recommandations
        """
        recommendations = []
        
        # Recommandations critiques
        critical_hosts = report['by_criticality']['critical']
        if critical_hosts:
            for host in critical_hosts:
                os_name = host.get('eol_status', {}).get('os_normalized', host.get('os_detected'))
                recommendations.append({
                    'priority': 'CRITIQUE',
                    'type': 'migration_urgente',
                    'target': host['ip'],
                    'hostname': host.get('hostname'),
                    'current_os': os_name,
                    'action': f"Migration/remplacement URGENT de {os_name}",
                    'reason': host.get('eol_status', {}).get('message', 'Système obsolète'),
                    'suggested_alternatives': self._suggest_alternatives(os_name),
                })
        
        # Recommandations warning
        warning_hosts = report['by_criticality']['warning']
        if warning_hosts:
            for host in warning_hosts:
                os_name = host.get('eol_status', {}).get('os_normalized', host.get('os_detected'))
                days = host.get('eol_status', {}).get('days_until_eol')
                recommendations.append({
                    'priority': 'ATTENTION',
                    'type': 'planifier_migration',
                    'target': host['ip'],
                    'hostname': host.get('hostname'),
                    'current_os': os_name,
                    'action': f"Planifier la migration de {os_name}",
                    'reason': f"EOL dans {days} jours" if days else "Proche de la fin de vie",
                    'suggested_alternatives': self._suggest_alternatives(os_name),
                })
        
        # Vérification spéciale ESXi 6.5 (mentionné dans le sujet)
        for host in report['hosts']:
            os_detected = host.get('os_detected', '').lower()
            if 'esxi' in os_detected and '6.5' in os_detected:
                if not any(r['target'] == host['ip'] for r in recommendations):
                    recommendations.insert(0, {
                        'priority': 'CRITIQUE',
                        'type': 'esxi_obsolete',
                        'target': host['ip'],
                        'hostname': host.get('hostname'),
                        'current_os': 'VMware ESXi 6.5',
                        'action': "MISE À JOUR CRITIQUE - ESXi 6.5 est en fin de vie",
                        'reason': "VMware ESXi 6.5 n'est plus supporté depuis octobre 2022",
                        'suggested_alternatives': ['VMware ESXi 7.0', 'VMware ESXi 8.0'],
                    })
        
        # Hôtes inconnus
        unknown_hosts = report['by_criticality']['unknown']
        if unknown_hosts:
            recommendations.append({
                'priority': 'INFO',
                'type': 'verification_manuelle',
                'targets': [h['ip'] for h in unknown_hosts],
                'action': f"Vérifier manuellement {len(unknown_hosts)} hôtes non identifiés",
                'reason': "OS non détecté automatiquement",
            })
        
        return recommendations
    
    def _suggest_alternatives(self, os_name: str) -> List[str]:
        """
        Suggère des alternatives pour un OS obsolète.
        
        Args:
            os_name: Nom de l'OS
            
        Returns:
            Liste des alternatives suggérées
        """
        if not os_name:
            return []
        
        os_lower = os_name.lower()
        
        # Windows Server
        if 'windows server' in os_lower:
            if '2012' in os_lower or '2008' in os_lower:
                return ['Windows Server 2019', 'Windows Server 2022']
            elif '2016' in os_lower:
                return ['Windows Server 2022']
        
        # Ubuntu
        if 'ubuntu' in os_lower:
            if '16.04' in os_lower or '18.04' in os_lower:
                return ['Ubuntu 22.04 LTS', 'Ubuntu 24.04 LTS']
            elif '20.04' in os_lower:
                return ['Ubuntu 22.04 LTS', 'Ubuntu 24.04 LTS']
        
        # Debian
        if 'debian' in os_lower:
            if '9' in os_lower or '10' in os_lower:
                return ['Debian 11', 'Debian 12']
        
        # CentOS / RHEL
        if 'centos' in os_lower:
            return ['Rocky Linux 9', 'AlmaLinux 9', 'RHEL 9']
        
        if 'rhel' in os_lower or 'red hat' in os_lower:
            if '7' in os_lower:
                return ['RHEL 8', 'RHEL 9']
        
        # VMware ESXi
        if 'esxi' in os_lower or 'vmware' in os_lower:
            if '6.5' in os_lower or '6.7' in os_lower:
                return ['VMware ESXi 7.0', 'VMware ESXi 8.0']
            elif '7.0' in os_lower:
                return ['VMware ESXi 8.0']
        
        return []
    
    def _print_summary(self, report: Dict[str, Any]) -> None:
        """
        Affiche le résumé du rapport.
        
        Args:
            report: Rapport à afficher
        """
        self.output.print_header("RÉSUMÉ DU RAPPORT D'OBSOLESCENCE")
        
        summary = report['summary']
        
        self.output.add_result(
            "Total hôtes analysés",
            Severity.INFO,
            f"{summary['analyzed']} / {summary['total_hosts']}"
        )
        
        if summary['critical'] > 0:
            self.output.add_result(
                "CRITIQUES (Action urgente)",
                Severity.CRITICAL,
                f"{summary['critical']} système(s) en fin de vie"
            )
        
        if summary['warning'] > 0:
            self.output.add_result(
                "ATTENTION (Planifier)",
                Severity.WARNING,
                f"{summary['warning']} système(s) proche(s) de l'obsolescence"
            )
        
        if summary['supported'] > 0:
            self.output.add_result(
                "SUPPORTÉS",
                Severity.OK,
                f"{summary['supported']} système(s) à jour"
            )
        
        if summary['unknown'] > 0:
            self.output.add_result(
                "INCONNUS",
                Severity.UNKNOWN,
                f"{summary['unknown']} système(s) non identifié(s)"
            )
        
        # Afficher les recommandations prioritaires
        if report['recommendations']:
            self.output.print_separator("RECOMMANDATIONS PRIORITAIRES")
            
            for i, rec in enumerate(report['recommendations'][:5], 1):
                priority = rec.get('priority', 'INFO')
                
                if priority == 'CRITIQUE':
                    severity = Severity.CRITICAL
                elif priority == 'ATTENTION':
                    severity = Severity.WARNING
                else:
                    severity = Severity.INFO
                
                target = rec.get('target') or ', '.join(rec.get('targets', [])[:3])
                
                self.output.add_result(
                    f"[{priority}] {target}",
                    severity,
                    rec.get('action', 'Action requise'),
                    details={
                        'os_actuel': rec.get('current_os'),
                        'alternatives': rec.get('suggested_alternatives'),
                    }
                )
    
    def _save_report(self, report: Dict[str, Any]) -> Path:
        """
        Sauvegarde le rapport en fichier JSON.
        
        Args:
            report: Rapport à sauvegarder
            
        Returns:
            Chemin du fichier créé
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"obsolescence_report_{timestamp}.json"
        filepath = self.report_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"Rapport sauvegardé: {filepath}")
        
        self.output.add_result(
            "Rapport sauvegardé",
            Severity.OK,
            str(filepath)
        )
        
        # Générer aussi un rapport texte lisible
        text_filepath = self.report_dir / f"obsolescence_report_{timestamp}.txt"
        self._save_text_report(report, text_filepath)
        
        return filepath
    
    def _save_text_report(self, report: Dict[str, Any], filepath: Path) -> None:
        """
        Sauvegarde une version texte du rapport.
        
        Args:
            report: Rapport à sauvegarder
            filepath: Chemin du fichier
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("RAPPORT D'OBSOLESCENCE - NTL-SysToolbox\n")
            f.write("Nord Transit Logistics\n")
            f.write("=" * 70 + "\n\n")
            
            f.write(f"Date: {report['timestamp']}\n")
            f.write(f"Réseau scanné: {report['network_range']}\n\n")
            
            # Résumé
            f.write("-" * 40 + "\n")
            f.write("RÉSUMÉ\n")
            f.write("-" * 40 + "\n")
            summary = report['summary']
            f.write(f"Total hôtes: {summary['total_hosts']}\n")
            f.write(f"Analysés: {summary['analyzed']}\n")
            f.write(f"Critiques: {summary['critical']}\n")
            f.write(f"Attention: {summary['warning']}\n")
            f.write(f"Supportés: {summary['supported']}\n")
            f.write(f"Inconnus: {summary['unknown']}\n\n")
            
            # Systèmes critiques
            if report['by_criticality']['critical']:
                f.write("-" * 40 + "\n")
                f.write("SYSTEMES CRITIQUES (FIN DE VIE)\n")
                f.write("-" * 40 + "\n")
                for host in report['by_criticality']['critical']:
                    f.write(f"\n{host['ip']}")
                    if host.get('hostname'):
                        f.write(f" ({host['hostname']})")
                    f.write("\n")
                    f.write(f"  OS: {host.get('eol_status', {}).get('os_normalized', host['os_detected'])}\n")
                    f.write(f"  Status: {host.get('eol_status', {}).get('message', 'N/A')}\n")
                f.write("\n")
            
            # Recommandations
            if report['recommendations']:
                f.write("-" * 40 + "\n")
                f.write("RECOMMANDATIONS\n")
                f.write("-" * 40 + "\n")
                for rec in report['recommendations']:
                    f.write(f"\n[{rec.get('priority', 'INFO')}] ")
                    target = rec.get('target') or ', '.join(rec.get('targets', []))
                    f.write(f"{target}\n")
                    f.write(f"  Action: {rec.get('action', 'N/A')}\n")
                    if rec.get('suggested_alternatives'):
                        f.write(f"  Alternatives: {', '.join(rec['suggested_alternatives'])}\n")
            
            f.write("\n" + "=" * 70 + "\n")
            f.write("Fin du rapport\n")
    
    def check_single_os(self, os_name: str) -> Dict[str, Any]:
        """
        Vérifie le statut EOL d'un OS spécifique.
        
        Args:
            os_name: Nom de l'OS à vérifier
            
        Returns:
            Statut EOL
        """
        self.output.print_header(f"Vérification EOL: {os_name}")
        
        status = self.eol_db.check_eol_status(os_name)
        
        criticality = status.get('criticality', 'unknown')
        
        if criticality == 'critical':
            severity = Severity.CRITICAL
        elif criticality == 'warning':
            severity = Severity.WARNING
        elif criticality == 'ok':
            severity = Severity.OK
        else:
            severity = Severity.UNKNOWN
        
        self.output.add_result(
            "Statut EOL",
            severity,
            status.get('message', 'Statut inconnu'),
            details={
                'os_normalisé': status.get('os_normalized'),
                'date_eol': status.get('eol_date'),
                'support_étendu': status.get('extended_support'),
                'jours_restants': status.get('days_until_eol'),
            }
        )
        
        # Suggérer des alternatives si obsolète
        if criticality in ('critical', 'warning'):
            alternatives = self._suggest_alternatives(status.get('os_normalized', os_name))
            if alternatives:
                self.output.add_result(
                    "Alternatives suggérées",
                    Severity.INFO,
                    ', '.join(alternatives)
                )
        
        return status

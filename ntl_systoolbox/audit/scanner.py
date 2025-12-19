"""
Module de scan réseau pour l'audit d'obsolescence.
Détecte les hôtes actifs et tente d'identifier leur OS.
"""

import socket
import subprocess
import platform
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import re

from ..core.config import Config
from ..core.output import OutputFormatter, Severity
from ..core.logger import get_logger


class NetworkScanner:
    """
    Scanner réseau pour découvrir les hôtes et identifier les systèmes d'exploitation.
    """
    
    # Signatures OS basées sur les réponses
    OS_SIGNATURES = {
        # Basé sur les ports ouverts
        'port_patterns': {
            (22,): ['Linux', 'Unix', 'ESXi'],
            (3389,): ['Windows'],
            (445, 135): ['Windows'],
            (445,): ['Windows', 'Samba'],
            (80, 443, 902): ['ESXi'],  # VMware ESXi
            (3306,): ['MySQL Server'],
            (5432,): ['PostgreSQL Server'],
        },
        # Basé sur les bannières
        'banner_patterns': {
            r'ubuntu': 'Ubuntu',
            r'debian': 'Debian',
            r'centos': 'CentOS',
            r'red\s*hat': 'RHEL',
            r'windows': 'Windows',
            r'esxi': 'VMware ESXi',
            r'vmware': 'VMware',
            r'openssh': 'Linux/Unix',
            r'microsoft': 'Windows',
            r'iis': 'Windows Server',
        }
    }
    
    def __init__(self, config: Config = None, output: OutputFormatter = None):
        """
        Initialise le scanner réseau.
        
        Args:
            config: Instance de configuration
            output: Formateur de sortie
        """
        self.config = config or Config()
        self.output = output or OutputFormatter()
        self.logger = get_logger()
        self.is_windows = platform.system().lower() == 'windows'
        
        # Configuration du scan
        audit_config = self.config.get('network_audit', default={})
        self.scan_timeout = audit_config.get('scan_timeout', 2)
        self.scan_ports = audit_config.get('scan_ports', [22, 80, 135, 139, 443, 445, 3306, 3389])
        self.max_threads = audit_config.get('max_threads', 50)
    
    def scan_network(self, network_range: str = None) -> Dict[str, Any]:
        """
        Scanne une plage réseau pour découvrir les hôtes.
        
        Args:
            network_range: Plage réseau en notation CIDR (ex: 192.168.10.0/24)
            
        Returns:
            Résultats du scan
        """
        if network_range is None:
            # Utiliser la première plage configurée
            ranges = self.config.get('network_audit', 'scan_ranges', default=['192.168.10.0/24'])
            network_range = ranges[0] if ranges else '192.168.10.0/24'
        
        self.output.print_header(f"Scan Réseau: {network_range}")
        
        start_time = datetime.now()
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'network': network_range,
            'hosts': [],
            'total_scanned': 0,
            'hosts_up': 0,
        }
        
        try:
            network = ipaddress.ip_network(network_range, strict=False)
            hosts_to_scan = list(network.hosts())
            results['total_scanned'] = len(hosts_to_scan)
            
            self.output.add_result(
                "Plage réseau",
                Severity.INFO,
                f"{len(hosts_to_scan)} adresses à scanner",
                target=network_range
            )
            
            # Scanner les hôtes en parallèle
            self.output.print_separator("Découverte des hôtes")
            
            with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
                futures = {
                    executor.submit(self._scan_host, str(ip)): str(ip)
                    for ip in hosts_to_scan
                }
                
                for future in as_completed(futures):
                    ip = futures[future]
                    try:
                        host_result = future.result()
                        if host_result and host_result.get('is_up'):
                            results['hosts'].append(host_result)
                            results['hosts_up'] += 1
                            
                            # Afficher la découverte
                            os_guess = host_result.get('os_guess', 'Inconnu')
                            self.output.add_result(
                                f"Hôte découvert",
                                Severity.INFO,
                                f"{ip} - OS probable: {os_guess}",
                                details={
                                    'hostname': host_result.get('hostname'),
                                    'ports_ouverts': list(host_result.get('open_ports', {}).keys()),
                                }
                            )
                    except Exception as e:
                        self.logger.debug(f"Erreur scan {ip}: {e}")
            
        except ValueError as e:
            self.output.add_result(
                "Erreur",
                Severity.CRITICAL,
                f"Plage réseau invalide: {e}"
            )
            return results
        
        duration = (datetime.now() - start_time).total_seconds()
        results['duration_seconds'] = duration
        
        # Résumé
        self.output.print_separator("Résumé")
        self.output.add_result(
            "Scan terminé",
            Severity.OK,
            f"{results['hosts_up']} hôtes actifs sur {results['total_scanned']} scannés",
            details={'durée': f"{duration:.1f}s"}
        )
        
        return results
    
    def _scan_host(self, ip: str) -> Optional[Dict[str, Any]]:
        """
        Scanne un hôte individuel.
        
        Args:
            ip: Adresse IP à scanner
            
        Returns:
            Informations sur l'hôte ou None si inactif
        """
        # Test rapide de connectivité
        if not self._is_host_up(ip):
            return None
        
        result = {
            'ip': ip,
            'is_up': True,
            'hostname': None,
            'open_ports': {},
            'os_guess': None,
            'os_details': {},
            'scan_time': datetime.now().isoformat(),
        }
        
        # Résolution DNS inverse
        result['hostname'] = self._resolve_hostname(ip)
        
        # Scan des ports
        for port in self.scan_ports:
            port_info = self._scan_port(ip, port)
            if port_info['open']:
                result['open_ports'][port] = port_info
        
        # Deviner l'OS
        result['os_guess'], result['os_details'] = self._guess_os(result)
        
        return result
    
    def _is_host_up(self, ip: str) -> bool:
        """
        Vérifie rapidement si un hôte est actif.
        
        Args:
            ip: Adresse IP
            
        Returns:
            True si l'hôte répond
        """
        # Ping rapide
        try:
            if self.is_windows:
                cmd = ['ping', '-n', '1', '-w', str(self.scan_timeout * 1000), ip]
            else:
                cmd = ['ping', '-c', '1', '-W', str(self.scan_timeout), ip]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.scan_timeout + 1
            )
            
            return result.returncode == 0
            
        except (subprocess.TimeoutExpired, Exception):
            # Si ping échoue, essayer un port commun
            return self._check_port_quick(ip, 445) or self._check_port_quick(ip, 22)
    
    def _check_port_quick(self, ip: str, port: int) -> bool:
        """
        Vérification rapide d'un port.
        
        Args:
            ip: Adresse IP
            port: Numéro de port
            
        Returns:
            True si le port répond
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.scan_timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def _scan_port(self, ip: str, port: int) -> Dict[str, Any]:
        """
        Scanne un port et tente de récupérer une bannière.
        
        Args:
            ip: Adresse IP
            port: Numéro de port
            
        Returns:
            Informations sur le port
        """
        result = {
            'port': port,
            'open': False,
            'service': self._get_service_name(port),
            'banner': None,
        }
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.scan_timeout)
            
            if sock.connect_ex((ip, port)) == 0:
                result['open'] = True
                
                # Tenter de récupérer une bannière
                try:
                    # Envoyer une requête simple pour certains services
                    if port in [21, 22, 25, 110, 143]:
                        sock.settimeout(1)
                        banner = sock.recv(1024).decode('utf-8', errors='replace').strip()
                        if banner:
                            result['banner'] = banner[:200]
                    elif port == 80:
                        sock.send(b'HEAD / HTTP/1.0\r\n\r\n')
                        sock.settimeout(1)
                        response = sock.recv(1024).decode('utf-8', errors='replace')
                        result['banner'] = response[:200]
                except:
                    pass
            
            sock.close()
            
        except Exception as e:
            self.logger.debug(f"Erreur scan port {ip}:{port}: {e}")
        
        return result
    
    def _get_service_name(self, port: int) -> str:
        """
        Retourne le nom du service associé à un port.
        
        Args:
            port: Numéro de port
            
        Returns:
            Nom du service
        """
        services = {
            21: 'FTP',
            22: 'SSH',
            23: 'Telnet',
            25: 'SMTP',
            53: 'DNS',
            80: 'HTTP',
            110: 'POP3',
            135: 'RPC',
            139: 'NetBIOS',
            143: 'IMAP',
            443: 'HTTPS',
            445: 'SMB',
            902: 'VMware',
            3306: 'MySQL',
            3389: 'RDP',
            5432: 'PostgreSQL',
            8080: 'HTTP-Alt',
        }
        return services.get(port, f'Port-{port}')
    
    def _resolve_hostname(self, ip: str) -> Optional[str]:
        """
        Résout le nom d'hôte à partir de l'IP.
        
        Args:
            ip: Adresse IP
            
        Returns:
            Nom d'hôte ou None
        """
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except:
            return None
    
    def _guess_os(self, host_info: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        Devine le système d'exploitation basé sur les informations collectées.
        
        Args:
            host_info: Informations sur l'hôte
            
        Returns:
            Tuple (OS deviné, détails)
        """
        details = {
            'confidence': 'low',
            'method': [],
            'indicators': [],
        }
        
        open_ports = set(host_info.get('open_ports', {}).keys())
        banners = [p.get('banner', '') or '' for p in host_info.get('open_ports', {}).values()]
        all_banners = ' '.join(banners).lower()
        
        os_scores = {}
        
        # Analyse des ports
        if 3389 in open_ports:
            os_scores['Windows'] = os_scores.get('Windows', 0) + 3
            details['indicators'].append('Port RDP (3389)')
        
        if 135 in open_ports or (445 in open_ports and 139 in open_ports):
            os_scores['Windows'] = os_scores.get('Windows', 0) + 2
            details['indicators'].append('Ports Windows (135/139/445)')
        
        if 22 in open_ports and 3389 not in open_ports:
            os_scores['Linux'] = os_scores.get('Linux', 0) + 2
            details['indicators'].append('Port SSH sans RDP')
        
        if 902 in open_ports or 443 in open_ports:
            if 22 in open_ports and 3389 not in open_ports:
                os_scores['VMware ESXi'] = os_scores.get('VMware ESXi', 0) + 3
                details['indicators'].append('Ports VMware (902/443) + SSH')
        
        # Analyse des bannières
        for pattern, os_name in self.OS_SIGNATURES['banner_patterns'].items():
            if re.search(pattern, all_banners, re.IGNORECASE):
                os_scores[os_name] = os_scores.get(os_name, 0) + 4
                details['indicators'].append(f'Bannière contient "{pattern}"')
                details['method'].append('banner_analysis')
        
        # Déterminer le meilleur candidat
        if os_scores:
            best_os = max(os_scores, key=os_scores.get)
            best_score = os_scores[best_os]
            
            if best_score >= 5:
                details['confidence'] = 'high'
            elif best_score >= 3:
                details['confidence'] = 'medium'
            else:
                details['confidence'] = 'low'
            
            details['scores'] = os_scores
            return best_os, details
        
        return 'Inconnu', details
    
    def scan_host_detailed(self, ip: str) -> Dict[str, Any]:
        """
        Effectue un scan détaillé d'un hôte spécifique.
        
        Args:
            ip: Adresse IP de l'hôte
            
        Returns:
            Informations détaillées
        """
        self.output.print_header(f"Scan Détaillé: {ip}")
        
        result = self._scan_host(ip)
        
        if result is None:
            self.output.add_result(
                "Connectivité",
                Severity.CRITICAL,
                "Hôte inaccessible",
                target=ip
            )
            return {'ip': ip, 'is_up': False}
        
        self.output.add_result(
            "Connectivité",
            Severity.OK,
            "Hôte actif",
            target=ip
        )
        
        if result.get('hostname'):
            self.output.add_result(
                "Hostname",
                Severity.INFO,
                result['hostname']
            )
        
        # Ports ouverts
        self.output.print_separator("Ports Ouverts")
        for port, info in result.get('open_ports', {}).items():
            self.output.add_result(
                f"Port {port}",
                Severity.INFO,
                info.get('service', 'Unknown'),
                details={'bannière': info.get('banner', 'N/A')[:50] if info.get('banner') else None}
            )
        
        # OS détecté
        self.output.print_separator("Système d'Exploitation")
        self.output.add_result(
            "OS Détecté",
            Severity.INFO,
            result.get('os_guess', 'Inconnu'),
            details={
                'confiance': result.get('os_details', {}).get('confidence', 'low'),
                'indicateurs': result.get('os_details', {}).get('indicators', []),
            }
        )
        
        return result

"""
Module de vérification des services AD et DNS sur les contrôleurs de domaine.
Compatible Windows et Linux.
"""

import socket
import subprocess
import platform
from typing import Dict, List, Any, Optional, Tuple

from ..core.config import Config
from ..core.output import OutputFormatter, Severity
from ..core.logger import get_logger


class ServiceChecker:
    """
    Vérifie l'état des services Active Directory et DNS
    sur les contrôleurs de domaine.
    """
    
    # Ports standards pour les services
    SERVICE_PORTS = {
        'LDAP': 389,
        'LDAPS': 636,
        'Kerberos': 88,
        'DNS': 53,
        'Global Catalog': 3268,
        'Global Catalog SSL': 3269,
        'SMB': 445,
        'RPC': 135,
        'NetBIOS': 139,
    }
    
    def __init__(self, config: Config = None, output: OutputFormatter = None):
        """
        Initialise le vérificateur de services.
        
        Args:
            config: Instance de configuration
            output: Formateur de sortie
        """
        self.config = config or Config()
        self.output = output or OutputFormatter()
        self.logger = get_logger()
        self.is_windows = platform.system().lower() == 'windows'
    
    def check_all_domain_controllers(self) -> Dict[str, Any]:
        """
        Vérifie tous les contrôleurs de domaine configurés.
        
        Returns:
            Dictionnaire des résultats par DC
        """
        dcs = self.config.get_domain_controllers()
        results = {}
        
        self.output.print_header("Vérification des Contrôleurs de Domaine")
        
        for dc in dcs:
            name = dc.get('name', 'Unknown')
            ip = dc.get('ip')
            
            if not ip:
                self.logger.warning(f"Pas d'IP configurée pour {name}")
                continue
            
            self.output.print_separator(f"DC: {name} ({ip})")
            results[name] = self.check_domain_controller(ip, name)
        
        return results
    
    def check_domain_controller(self, ip: str, name: str = None) -> Dict[str, Any]:
        """
        Vérifie un contrôleur de domaine spécifique.
        
        Args:
            ip: Adresse IP du DC
            name: Nom du DC (optionnel)
            
        Returns:
            Résultats de la vérification
        """
        target = name or ip
        results = {
            'ip': ip,
            'name': name,
            'reachable': False,
            'services': {},
            'dns_resolution': None,
        }
        
        # Test de connectivité basique (ping)
        ping_ok, ping_time = self._ping_host(ip)
        results['reachable'] = ping_ok
        results['ping_time_ms'] = ping_time
        
        if ping_ok:
            self.output.add_result(
                "Connectivité ICMP",
                Severity.OK,
                f"Réponse en {ping_time:.1f}ms",
                target=target
            )
        else:
            self.output.add_result(
                "Connectivité ICMP",
                Severity.CRITICAL,
                "Pas de réponse au ping",
                target=target
            )
            return results
        
        # Vérification des ports/services
        for service_name, port in self.SERVICE_PORTS.items():
            # DNS utilise UDP, pas TCP
            use_udp = (service_name == 'DNS')
            is_open, response_time = self._check_port(ip, port, use_udp=use_udp)
            results['services'][service_name] = {
                'port': port,
                'protocol': 'UDP' if use_udp else 'TCP',
                'status': 'open' if is_open else 'closed',
                'response_time_ms': response_time,
            }

            if is_open:
                proto = "UDP" if use_udp else "TCP"
                self.output.add_result(
                    f"Service {service_name}",
                    Severity.OK,
                    f"Port {proto}/{port} ouvert ({response_time:.1f}ms)",
                    target=target
                )
            else:
                # DNS, LDAP et Kerberos sont critiques
                severity = Severity.CRITICAL if service_name in ['LDAP', 'DNS', 'Kerberos'] else Severity.WARNING
                proto = "UDP" if use_udp else "TCP"
                self.output.add_result(
                    f"Service {service_name}",
                    severity,
                    f"Port {proto}/{port} ferme ou inaccessible",
                    target=target
                )
        
        # Test de résolution DNS
        dns_ok, dns_result = self._test_dns_resolution(ip)
        results['dns_resolution'] = dns_result
        
        if dns_ok:
            self.output.add_result(
                "Résolution DNS",
                Severity.OK,
                f"Résolution fonctionnelle",
                details=dns_result,
                target=target
            )
        else:
            self.output.add_result(
                "Résolution DNS",
                Severity.WARNING,
                "Échec de la résolution DNS de test",
                target=target
            )
        
        return results
    
    def _ping_host(self, ip: str, timeout: int = 2) -> Tuple[bool, float]:
        """
        Ping un hôte et retourne le temps de réponse.
        
        Args:
            ip: Adresse IP à pinger
            timeout: Timeout en secondes
            
        Returns:
            Tuple (succès, temps_ms)
        """
        try:
            if self.is_windows:
                cmd = ['ping', '-n', '1', '-w', str(timeout * 1000), ip]
            else:
                cmd = ['ping', '-c', '1', '-W', str(timeout), ip]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 2
            )
            
            if result.returncode == 0:
                # Extraire le temps de réponse
                output = result.stdout
                if self.is_windows:
                    # Format Windows: "temps=XXms" ou "time=XXms"
                    import re
                    match = re.search(r'(?:temps|time)[=<](\d+)', output, re.IGNORECASE)
                    if match:
                        return True, float(match.group(1))
                else:
                    # Format Linux: "time=XX.X ms"
                    import re
                    match = re.search(r'time[=]?([\d.]+)', output)
                    if match:
                        return True, float(match.group(1))
                return True, 0.0
            
            return False, 0.0
            
        except subprocess.TimeoutExpired:
            self.logger.debug(f"Ping timeout pour {ip}")
            return False, 0.0
        except Exception as e:
            self.logger.error(f"Erreur ping {ip}: {e}")
            return False, 0.0
    
    def _check_port(self, ip: str, port: int, timeout: float = 2.0, use_udp: bool = False) -> Tuple[bool, float]:
        """
        Vérifie si un port TCP ou UDP est ouvert.

        Args:
            ip: Adresse IP
            port: Numéro de port
            timeout: Timeout en secondes
            use_udp: Utiliser UDP au lieu de TCP

        Returns:
            Tuple (ouvert, temps_ms)
        """
        import time

        try:
            if use_udp:
                # Pour UDP, on envoie un paquet et on attend une réponse
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(timeout)

                start_time = time.time()
                # Envoyer une requête DNS simple (query pour ".")
                dns_query = b'\x00\x01\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x01'
                sock.sendto(dns_query, (ip, port))

                try:
                    data, addr = sock.recvfrom(512)
                    elapsed = (time.time() - start_time) * 1000
                    sock.close()
                    return True, elapsed
                except socket.timeout:
                    sock.close()
                    return False, 0.0
            else:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)

                start_time = time.time()
                result = sock.connect_ex((ip, port))
                elapsed = (time.time() - start_time) * 1000

                sock.close()

                if result == 0:
                    return True, elapsed
                else:
                    return False, 0.0

        except socket.timeout:
            return False, 0.0
        except Exception as e:
            self.logger.debug(f"Erreur check port {ip}:{port}: {e}")
            return False, 0.0
    
    def _test_dns_resolution(self, dns_server: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Teste la résolution DNS en interrogeant le serveur spécifié.
        
        Args:
            dns_server: Adresse IP du serveur DNS
            
        Returns:
            Tuple (succès, résultats)
        """
        test_domains = ['localhost', 'google.com']
        results = {}
        
        for domain in test_domains:
            try:
                # Utiliser nslookup pour interroger le serveur spécifique
                if self.is_windows:
                    cmd = ['nslookup', domain, dns_server]
                else:
                    cmd = ['nslookup', domain, dns_server]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                results[domain] = {
                    'resolved': result.returncode == 0,
                    'output': result.stdout[:200] if result.stdout else None,
                }
                
            except subprocess.TimeoutExpired:
                results[domain] = {'resolved': False, 'error': 'timeout'}
            except Exception as e:
                results[domain] = {'resolved': False, 'error': str(e)}
        
        # Succès si au moins un domaine est résolu
        success = any(r.get('resolved', False) for r in results.values())
        
        return success, results
    
    def check_windows_services(self, target_ip: str = None) -> Dict[str, Any]:
        """
        Vérifie les services Windows AD/DNS (local ou distant via WMI).
        
        Args:
            target_ip: IP cible (None = local)
            
        Returns:
            État des services
        """
        if not self.is_windows:
            self.logger.info("Vérification services Windows non disponible sur Linux")
            return {}
        
        services = self.config.get('ad_services', 'windows', default=[
            'NTDS', 'DNS', 'Netlogon', 'DFSR', 'W32Time'
        ])
        
        results = {}
        
        for service_name in services:
            try:
                # Utiliser sc query
                if target_ip:
                    cmd = ['sc', f'\\\\{target_ip}', 'query', service_name]
                else:
                    cmd = ['sc', 'query', service_name]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                output = result.stdout
                
                # Parser l'état du service
                if 'RUNNING' in output:
                    status = 'running'
                    severity = Severity.OK
                elif 'STOPPED' in output:
                    status = 'stopped'
                    severity = Severity.CRITICAL
                elif 'PAUSED' in output:
                    status = 'paused'
                    severity = Severity.WARNING
                else:
                    status = 'unknown'
                    severity = Severity.UNKNOWN
                
                results[service_name] = {
                    'status': status,
                    'exists': result.returncode == 0,
                }
                
                self.output.add_result(
                    f"Service Windows {service_name}",
                    severity,
                    f"État: {status}",
                    target=target_ip or "local"
                )
                
            except subprocess.TimeoutExpired:
                results[service_name] = {'status': 'timeout', 'exists': False}
                self.output.add_result(
                    f"Service Windows {service_name}",
                    Severity.UNKNOWN,
                    "Timeout lors de la vérification",
                    target=target_ip or "local"
                )
            except Exception as e:
                results[service_name] = {'status': 'error', 'error': str(e)}
                self.logger.error(f"Erreur vérification service {service_name}: {e}")
        
        return results
    
    def check_linux_services(self, services: List[str] = None) -> Dict[str, Any]:
        """
        Vérifie les services Linux (systemd).
        
        Args:
            services: Liste des services à vérifier
            
        Returns:
            État des services
        """
        if self.is_windows:
            self.logger.info("Vérification services Linux non disponible sur Windows")
            return {}
        
        if services is None:
            services = self.config.get('ad_services', 'linux', default=[
                'samba-ad-dc', 'bind9', 'sshd'
            ])
        
        results = {}
        
        for service_name in services:
            try:
                # Utiliser systemctl
                cmd = ['systemctl', 'is-active', service_name]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                status = result.stdout.strip()
                
                if status == 'active':
                    severity = Severity.OK
                elif status == 'inactive':
                    severity = Severity.CRITICAL
                elif status == 'failed':
                    severity = Severity.CRITICAL
                else:
                    severity = Severity.WARNING
                
                results[service_name] = {
                    'status': status,
                    'exists': result.returncode != 4,  # 4 = service not found
                }
                
                self.output.add_result(
                    f"Service Linux {service_name}",
                    severity,
                    f"État: {status}",
                    target="local"
                )
                
            except subprocess.TimeoutExpired:
                results[service_name] = {'status': 'timeout'}
            except Exception as e:
                results[service_name] = {'status': 'error', 'error': str(e)}
                self.logger.error(f"Erreur vérification service {service_name}: {e}")
        
        return results

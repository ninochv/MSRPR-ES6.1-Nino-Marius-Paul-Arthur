"""
Module de collecte d'informations système.
Récupère uptime, version OS, usage CPU/RAM/Disque.
Compatible Windows et Linux.
"""

import os
import platform
import subprocess
import re
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from ..core.config import Config
from ..core.output import OutputFormatter, Severity
from ..core.logger import get_logger


class SystemInfoCollector:
    """
    Collecte les informations système (local ou distant).
    Supporte Windows et Linux.
    """
    
    def __init__(self, config: Config = None, output: OutputFormatter = None):
        """
        Initialise le collecteur d'informations système.
        
        Args:
            config: Instance de configuration
            output: Formateur de sortie
        """
        self.config = config or Config()
        self.output = output or OutputFormatter()
        self.logger = get_logger()
        self.is_windows = platform.system().lower() == 'windows'
        self.thresholds = self.config.get_thresholds()
    
    def collect_local_info(self) -> Dict[str, Any]:
        """
        Collecte les informations du système local.
        
        Returns:
            Dictionnaire des informations système
        """
        self.output.print_header("Informations Système Local")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'hostname': platform.node(),
            'platform': platform.system(),
            'platform_version': platform.version(),
            'platform_release': platform.release(),
            'architecture': platform.machine(),
        }
        
        # Informations OS
        self.output.print_separator("Système d'Exploitation")
        os_info = self._get_os_info()
        results['os'] = os_info
        
        self.output.add_result(
            "Système d'Exploitation",
            Severity.INFO,
            f"{os_info.get('name', 'Unknown')} {os_info.get('version', '')}",
            details={'architecture': results['architecture']}
        )
        
        # Uptime
        self.output.print_separator("Disponibilité")
        uptime_info = self._get_uptime()
        results['uptime'] = uptime_info
        
        if uptime_info.get('seconds'):
            uptime_str = OutputFormatter.format_uptime(uptime_info['seconds'])
            self.output.add_result(
                "Uptime",
                Severity.OK,
                f"Système actif depuis {uptime_str}",
                details={'boot_time': uptime_info.get('boot_time')}
            )
        
        # CPU
        self.output.print_separator("Processeur")
        cpu_info = self._get_cpu_info()
        results['cpu'] = cpu_info
        
        cpu_usage = cpu_info.get('usage_percent', 0)
        cpu_severity = self._get_severity_for_usage(cpu_usage, 'cpu')
        
        self.output.add_result(
            "Utilisation CPU",
            cpu_severity,
            f"{cpu_usage:.1f}%",
            details={
                'cores': cpu_info.get('cores'),
                'model': cpu_info.get('model', 'N/A')
            }
        )
        
        # Mémoire
        self.output.print_separator("Mémoire")
        memory_info = self._get_memory_info()
        results['memory'] = memory_info
        
        mem_usage = memory_info.get('percent', 0)
        mem_severity = self._get_severity_for_usage(mem_usage, 'memory')
        
        self.output.add_result(
            "Utilisation Mémoire",
            mem_severity,
            f"{mem_usage:.1f}% ({memory_info.get('used_formatted', 'N/A')} / {memory_info.get('total_formatted', 'N/A')})",
            details={
                'available': memory_info.get('available_formatted'),
            }
        )
        
        # Disques
        self.output.print_separator("Stockage")
        disk_info = self._get_disk_info()
        results['disks'] = disk_info
        
        for disk in disk_info:
            usage = disk.get('percent', 0)
            disk_severity = self._get_severity_for_usage(usage, 'disk')
            
            self.output.add_result(
                f"Disque {disk.get('mountpoint', disk.get('device', 'N/A'))}",
                disk_severity,
                f"{usage:.1f}% ({disk.get('used_formatted', 'N/A')} / {disk.get('total_formatted', 'N/A')})",
                details={'filesystem': disk.get('fstype')}
            )
        
        return results
    
    def _get_severity_for_usage(self, usage: float, resource_type: str) -> Severity:
        """
        Détermine la sévérité en fonction de l'utilisation.
        
        Args:
            usage: Pourcentage d'utilisation
            resource_type: Type de ressource (cpu, memory, disk)
            
        Returns:
            Sévérité appropriée
        """
        warning_key = f"{resource_type}_warning"
        critical_key = f"{resource_type}_critical"
        
        warning_threshold = self.thresholds.get(warning_key, 80)
        critical_threshold = self.thresholds.get(critical_key, 95)
        
        if usage >= critical_threshold:
            return Severity.CRITICAL
        elif usage >= warning_threshold:
            return Severity.WARNING
        else:
            return Severity.OK
    
    def _get_os_info(self) -> Dict[str, Any]:
        """
        Récupère les informations sur le système d'exploitation.
        
        Returns:
            Informations OS
        """
        info = {
            'name': platform.system(),
            'version': platform.version(),
            'release': platform.release(),
        }
        
        if self.is_windows:
            try:
                # Windows: utiliser wmic pour plus de détails
                result = subprocess.run(
                    ['wmic', 'os', 'get', 'Caption,Version', '/format:list'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                for line in result.stdout.strip().split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        if key.strip() == 'Caption':
                            info['name'] = value.strip()
                        elif key.strip() == 'Version':
                            info['version'] = value.strip()
                            
            except Exception as e:
                self.logger.debug(f"Erreur récupération info OS Windows: {e}")
        else:
            try:
                # Linux: lire /etc/os-release
                if os.path.exists('/etc/os-release'):
                    with open('/etc/os-release', 'r') as f:
                        for line in f:
                            if line.startswith('PRETTY_NAME='):
                                info['name'] = line.split('=', 1)[1].strip().strip('"')
                            elif line.startswith('VERSION_ID='):
                                info['version'] = line.split('=', 1)[1].strip().strip('"')
                                
            except Exception as e:
                self.logger.debug(f"Erreur récupération info OS Linux: {e}")
        
        return info
    
    def _get_uptime(self) -> Dict[str, Any]:
        """
        Récupère l'uptime du système.
        
        Returns:
            Informations d'uptime
        """
        info = {'seconds': None, 'boot_time': None}
        
        try:
            # Essayer psutil d'abord
            import psutil
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime_seconds = (datetime.now() - boot_time).total_seconds()
            
            info['seconds'] = uptime_seconds
            info['boot_time'] = boot_time.isoformat()
            return info
            
        except ImportError:
            pass
        
        if self.is_windows:
            try:
                # Windows: wmic
                result = subprocess.run(
                    ['wmic', 'os', 'get', 'LastBootUpTime', '/format:list'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                for line in result.stdout.strip().split('\n'):
                    if line.startswith('LastBootUpTime='):
                        # Format: YYYYMMDDHHMMSS.MMMMMM+ZZZ
                        boot_str = line.split('=', 1)[1].strip()[:14]
                        boot_time = datetime.strptime(boot_str, '%Y%m%d%H%M%S')
                        uptime_seconds = (datetime.now() - boot_time).total_seconds()
                        
                        info['seconds'] = uptime_seconds
                        info['boot_time'] = boot_time.isoformat()
                        
            except Exception as e:
                self.logger.debug(f"Erreur récupération uptime Windows: {e}")
        else:
            try:
                # Linux: /proc/uptime
                with open('/proc/uptime', 'r') as f:
                    uptime_seconds = float(f.read().split()[0])
                    info['seconds'] = uptime_seconds
                    info['boot_time'] = (datetime.now() - timedelta(seconds=uptime_seconds)).isoformat()
                    
            except Exception as e:
                self.logger.debug(f"Erreur récupération uptime Linux: {e}")
        
        return info
    
    def _get_cpu_info(self) -> Dict[str, Any]:
        """
        Récupère les informations CPU.
        
        Returns:
            Informations CPU
        """
        info = {
            'cores': os.cpu_count(),
            'model': None,
            'usage_percent': 0.0,
        }
        
        try:
            # Essayer psutil
            import psutil
            info['usage_percent'] = psutil.cpu_percent(interval=1)
            info['cores_logical'] = psutil.cpu_count(logical=True)
            info['cores_physical'] = psutil.cpu_count(logical=False)
            
        except ImportError:
            # Fallback
            if self.is_windows:
                try:
                    # Windows: wmic
                    result = subprocess.run(
                        ['wmic', 'cpu', 'get', 'LoadPercentage', '/format:list'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    for line in result.stdout.strip().split('\n'):
                        if line.startswith('LoadPercentage='):
                            info['usage_percent'] = float(line.split('=', 1)[1].strip())
                            
                except Exception as e:
                    self.logger.debug(f"Erreur récupération CPU Windows: {e}")
            else:
                try:
                    # Linux: /proc/stat
                    with open('/proc/stat', 'r') as f:
                        line = f.readline()
                        cpu_times = list(map(int, line.split()[1:]))
                        idle = cpu_times[3]
                        total = sum(cpu_times)
                        info['usage_percent'] = (1 - idle / total) * 100
                        
                except Exception as e:
                    self.logger.debug(f"Erreur récupération CPU Linux: {e}")
        
        # Modèle CPU
        if self.is_windows:
            try:
                result = subprocess.run(
                    ['wmic', 'cpu', 'get', 'Name', '/format:list'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                for line in result.stdout.strip().split('\n'):
                    if line.startswith('Name='):
                        info['model'] = line.split('=', 1)[1].strip()
                        
            except Exception:
                pass
        else:
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if line.startswith('model name'):
                            info['model'] = line.split(':', 1)[1].strip()
                            break
                            
            except Exception:
                pass
        
        return info
    
    def _get_memory_info(self) -> Dict[str, Any]:
        """
        Récupère les informations mémoire.
        
        Returns:
            Informations mémoire
        """
        info = {
            'total': 0,
            'used': 0,
            'available': 0,
            'percent': 0.0,
        }
        
        try:
            # Essayer psutil
            import psutil
            mem = psutil.virtual_memory()
            
            info['total'] = mem.total
            info['used'] = mem.used
            info['available'] = mem.available
            info['percent'] = mem.percent
            
        except ImportError:
            if self.is_windows:
                try:
                    result = subprocess.run(
                        ['wmic', 'OS', 'get', 'TotalVisibleMemorySize,FreePhysicalMemory', '/format:list'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    total_kb = 0
                    free_kb = 0
                    
                    for line in result.stdout.strip().split('\n'):
                        if line.startswith('TotalVisibleMemorySize='):
                            total_kb = int(line.split('=', 1)[1].strip())
                        elif line.startswith('FreePhysicalMemory='):
                            free_kb = int(line.split('=', 1)[1].strip())
                    
                    info['total'] = total_kb * 1024
                    info['available'] = free_kb * 1024
                    info['used'] = info['total'] - info['available']
                    info['percent'] = (info['used'] / info['total']) * 100 if info['total'] > 0 else 0
                    
                except Exception as e:
                    self.logger.debug(f"Erreur récupération mémoire Windows: {e}")
            else:
                try:
                    with open('/proc/meminfo', 'r') as f:
                        meminfo = {}
                        for line in f:
                            parts = line.split()
                            if len(parts) >= 2:
                                key = parts[0].rstrip(':')
                                value = int(parts[1]) * 1024  # kB to bytes
                                meminfo[key] = value
                    
                    info['total'] = meminfo.get('MemTotal', 0)
                    info['available'] = meminfo.get('MemAvailable', meminfo.get('MemFree', 0))
                    info['used'] = info['total'] - info['available']
                    info['percent'] = (info['used'] / info['total']) * 100 if info['total'] > 0 else 0
                    
                except Exception as e:
                    self.logger.debug(f"Erreur récupération mémoire Linux: {e}")
        
        # Formater les valeurs
        info['total_formatted'] = OutputFormatter.format_bytes(info['total'])
        info['used_formatted'] = OutputFormatter.format_bytes(info['used'])
        info['available_formatted'] = OutputFormatter.format_bytes(info['available'])
        
        return info
    
    def _get_disk_info(self) -> list:
        """
        Récupère les informations des disques.
        
        Returns:
            Liste des informations disques
        """
        disks = []
        
        try:
            # Essayer psutil
            import psutil
            
            for partition in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disks.append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype,
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free,
                        'percent': usage.percent,
                        'total_formatted': OutputFormatter.format_bytes(usage.total),
                        'used_formatted': OutputFormatter.format_bytes(usage.used),
                        'free_formatted': OutputFormatter.format_bytes(usage.free),
                    })
                except (PermissionError, OSError):
                    continue
                    
        except ImportError:
            if self.is_windows:
                try:
                    result = subprocess.run(
                        ['wmic', 'logicaldisk', 'get', 'DeviceID,Size,FreeSpace,FileSystem', '/format:csv'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
                    if len(lines) > 1:
                        for line in lines[1:]:
                            parts = line.split(',')
                            if len(parts) >= 4:
                                try:
                                    device = parts[1]
                                    free = int(parts[2]) if parts[2] else 0
                                    total = int(parts[3]) if parts[3] else 0
                                    fstype = parts[4] if len(parts) > 4 else 'Unknown'
                                    
                                    used = total - free
                                    percent = (used / total * 100) if total > 0 else 0
                                    
                                    disks.append({
                                        'device': device,
                                        'mountpoint': device,
                                        'fstype': fstype,
                                        'total': total,
                                        'used': used,
                                        'free': free,
                                        'percent': percent,
                                        'total_formatted': OutputFormatter.format_bytes(total),
                                        'used_formatted': OutputFormatter.format_bytes(used),
                                        'free_formatted': OutputFormatter.format_bytes(free),
                                    })
                                except (ValueError, IndexError):
                                    continue
                                    
                except Exception as e:
                    self.logger.debug(f"Erreur récupération disques Windows: {e}")
            else:
                try:
                    result = subprocess.run(
                        ['df', '-B1', '--output=source,fstype,size,used,avail,target'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    lines = result.stdout.strip().split('\n')[1:]  # Skip header
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 6 and not parts[0].startswith('tmpfs'):
                            try:
                                device = parts[0]
                                fstype = parts[1]
                                total = int(parts[2])
                                used = int(parts[3])
                                free = int(parts[4])
                                mountpoint = parts[5]
                                
                                percent = (used / total * 100) if total > 0 else 0
                                
                                disks.append({
                                    'device': device,
                                    'mountpoint': mountpoint,
                                    'fstype': fstype,
                                    'total': total,
                                    'used': used,
                                    'free': free,
                                    'percent': percent,
                                    'total_formatted': OutputFormatter.format_bytes(total),
                                    'used_formatted': OutputFormatter.format_bytes(used),
                                    'free_formatted': OutputFormatter.format_bytes(free),
                                })
                            except (ValueError, IndexError):
                                continue
                                
                except Exception as e:
                    self.logger.debug(f"Erreur récupération disques Linux: {e}")
        
        return disks

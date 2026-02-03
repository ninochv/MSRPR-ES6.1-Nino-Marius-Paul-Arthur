# NTL-SysToolbox

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey.svg)

**Outil CLI d'exploitation système pour Nord Transit Logistics**

NTL-SysToolbox est un outil en ligne de commande conçu pour automatiser l'exploitation, sécuriser les sauvegardes et auditer l'obsolescence de l'infrastructure informatique de Nord Transit Logistics.

---

## Table des matières

- [Fonctionnalités](#fonctionnalités)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
  - [Mode Interactif](#mode-interactif)
  - [Mode Commande](#mode-commande)
- [Modules](#modules)
  - [Module Diagnostic](#module-diagnostic)
  - [Module Sauvegarde WMS](#module-sauvegarde-wms)
  - [Module Audit d'Obsolescence](#module-audit-dobsolescence)
- [Codes de Retour](#codes-de-retour)
- [Intégration Zabbix](#intégration-zabbix)
- [Structure du Projet](#structure-du-projet)
- [Développement](#développement)
- [Licence](#licence)

---

## Fonctionnalités

### Module Diagnostic
- Vérification des services AD/DNS sur les contrôleurs de domaine
- Test de connexion à la base MySQL WMS
- Collecte d'informations système (uptime, CPU, RAM, disques)

### Module Sauvegarde WMS
- Export complet de la base de données (SQL avec mysqldump)
- Export de tables spécifiques en CSV
- Traçabilité et vérification d'intégrité (SHA256)
- Nettoyage automatique des anciennes sauvegardes

### Module Audit d'Obsolescence
- Scan réseau pour découvrir les hôtes
- Détection automatique des systèmes d'exploitation
- Base de données End-of-Life (EOL) intégrée
- Rapport de criticité avec recommandations

---

## Prérequis

### Système
- **Python 3.8+** (3.10+ recommandé)
- **Windows Server 2016+** ou **Ubuntu 20.04+**

### Dépendances Python
```
pyyaml>=6.0
mysql-connector-python>=8.0
psutil>=5.9 (optionnel, recommandé)
```

### Outils externes (optionnels)
- `mysqldump` / `mysql` CLI pour les sauvegardes de base de données
- Accès réseau aux serveurs à diagnostiquer

---

## Installation

### Installation rapide

```bash
# Cloner ou copier le projet
cd /chemin/vers/NTL-SYSTOOLBOX

# Créer un environnement virtuel (recommandé)
python -m venv venv

# Activer l'environnement
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux/Mac:
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Copier le fichier de configuration des secrets
copy .env.example .env
# Puis éditer .env avec vos credentials
```

### Installation en mode développement

```bash
pip install -e ".[all]"
```

---

## Configuration

### Fichier `config.yaml`

Le fichier `config.yaml` contient la configuration principale :

```yaml
# Configuration générale
general:
  log_level: INFO
  log_dir: ./logs
  backup_dir: ./backups
  report_dir: ./reports
  output_format: both  # human, json, both

# Contrôleurs de domaine
domain_controllers:
  - name: DC-PRIMARY
    ip: 192.168.10.10
  - name: DC-SECONDARY
    ip: 192.168.10.11

# Base de données WMS
wms_database:
  host: 192.168.10.21
  port: 3306
  database: wms_production

# Seuils d'alerte
thresholds:
  cpu_warning: 80
  cpu_critical: 95
  memory_warning: 80
  memory_critical: 95
  disk_warning: 80
  disk_critical: 95
  eol_warning_days: 180
  eol_critical_days: 30
```

### Fichier `.env` (Secrets)

```bash
# Credentials Base de données WMS
NTL_DB_USER=wms_admin
NTL_DB_PASSWORD=votre_mot_de_passe_securise

# Credentials Active Directory
NTL_AD_USER=administrator@nordtransit.local
NTL_AD_PASSWORD=votre_mot_de_passe_ad
```

### Variables d'environnement

Les variables d'environnement surchargent la configuration :

| Variable | Description |
|----------|-------------|
| `NTL_LOG_LEVEL` | Niveau de log (DEBUG, INFO, WARNING, ERROR) |
| `NTL_DB_HOST` | Hôte MySQL |
| `NTL_DB_PORT` | Port MySQL |
| `NTL_DB_USER` | Utilisateur MySQL |
| `NTL_DB_PASSWORD` | Mot de passe MySQL |

---

## Utilisation

### Mode Interactif

Lancez le menu interactif :

```bash
# Méthode 1: Script direct
python ntl-systoolbox.py

# Méthode 2: Module Python
python -m ntl_systoolbox

# Méthode 3: Option interactive
python ntl-systoolbox.py --interactive
```

Le menu interactif propose :

```
╔═══════════════════════════════════════════════════════════════╗
║           Nord Transit Logistics - SysToolbox                 ║
╚═══════════════════════════════════════════════════════════════╝

  [1] Module Diagnostic
  [2] Module Sauvegarde WMS
  [3] Module Audit d'Obsolescence
  [4] Configuration
  [q] Quitter
```

### Mode Commande

Exécutez des commandes directement :

```bash
# Afficher l'aide
python ntl-systoolbox.py --help

# Diagnostic des services
python ntl-systoolbox.py diagnostic services

# Diagnostic complet
python ntl-systoolbox.py diagnostic all

# Sauvegarde complète
python ntl-systoolbox.py backup full

# Export d'une table
python ntl-systoolbox.py backup table orders

# Rapport d'obsolescence
python ntl-systoolbox.py audit report

# Vérifier un OS
python ntl-systoolbox.py audit check "VMware ESXi 6.5"
```

### Options globales

```bash
python ntl-systoolbox.py [OPTIONS] COMMANDE

Options:
  --version, -v          Afficher la version
  --interactive, -i      Lancer le menu interactif
  --config, -c PATH      Chemin vers config.yaml
  --output, -o FORMAT    Format de sortie (human/json/both)
  --log-level, -l LEVEL  Niveau de log
  --no-color             Désactiver les couleurs
```

---

## Modules

### Module Diagnostic

```bash
# Vérifier tous les contrôleurs de domaine
python ntl-systoolbox.py diagnostic services

# Vérifier un DC spécifique
python ntl-systoolbox.py diagnostic services --dc 192.168.10.10

# Tester la connexion MySQL
python ntl-systoolbox.py diagnostic database

# Informations système local
python ntl-systoolbox.py diagnostic system

# Exécuter tous les diagnostics
python ntl-systoolbox.py diagnostic all
```

**Exemple de sortie :**

```
============================================================
Vérification des Contrôleurs de Domaine
Horodatage: 2024-12-19 14:30:00
============================================================

--- DC: DC-PRIMARY (192.168.10.10) ---
✓ Connectivité ICMP [192.168.10.10]: Réponse en 1.2ms
✓ Service LDAP [192.168.10.10]: Port 389 ouvert (5.3ms)
✓ Service DNS [192.168.10.10]: Port 53 ouvert (2.1ms)
✓ Service Kerberos [192.168.10.10]: Port 88 ouvert (3.5ms)
```

### Module Sauvegarde WMS

```bash
# Sauvegarde complète
python ntl-systoolbox.py backup full

# Sauvegarde avec chemin personnalisé
python ntl-systoolbox.py backup full --output /backup/wms_$(date +%Y%m%d).sql.gz

# Exporter une table en CSV
python ntl-systoolbox.py backup table orders

# Exporter avec filtre
python ntl-systoolbox.py backup table orders --where "created_at > '2024-01-01'"

# Sauvegarder les tables critiques
python ntl-systoolbox.py backup critical

# Vérifier l'intégrité d'une sauvegarde
python ntl-systoolbox.py backup verify /backup/wms_20241219.sql.gz

# Vérifier toutes les sauvegardes
python ntl-systoolbox.py backup verify --all

# Nettoyer les anciennes sauvegardes
python ntl-systoolbox.py backup cleanup
```

**Exemple de sortie :**

```
============================================================
Sauvegarde Complète Base de Données WMS
Horodatage: 2024-12-19 14:30:00
============================================================

--- Export mysqldump ---
✓ Export SQL: Sauvegarde créée: 125.4 MB
    fichier: wms_production_20241219_143000.sql.gz
    durée: 45.2s

--- Vérification Intégrité ---
✓ Intégrité SHA256: Hash: a1b2c3d4e5f6...
```

### Module Audit d'Obsolescence

```bash
# Scanner le réseau
python ntl-systoolbox.py audit scan

# Scanner une plage spécifique
python ntl-systoolbox.py audit scan --range 192.168.10.0/24

# Scanner un hôte spécifique
python ntl-systoolbox.py audit scan --host 192.168.10.50

# Générer un rapport d'obsolescence complet
python ntl-systoolbox.py audit report

# Vérifier le statut EOL d'un OS
python ntl-systoolbox.py audit check "Ubuntu 20.04"
python ntl-systoolbox.py audit check "VMware ESXi 6.5"

# Lister la base EOL
python ntl-systoolbox.py audit list-eol
```

**Exemple de sortie :**

```
============================================================
RÉSUMÉ DU RAPPORT D'OBSOLESCENCE
============================================================
ℹ Total hôtes analysés: 15 / 15
✗ CRITIQUES (Action urgente): 2 système(s) en fin de vie
⚠ ATTENTION (Planifier): 1 système(s) proche(s) de l'obsolescence
✓ SUPPORTÉS: 10 système(s) à jour
? INCONNUS: 2 système(s) non identifié(s)

--- RECOMMANDATIONS PRIORITAIRES ---
[CRITIQUE] 192.168.10.50
  VMware ESXi 6.5 - FIN DE VIE depuis 793 jours
  Alternatives: VMware ESXi 7.0, VMware ESXi 8.0
```

---

## Codes de Retour

L'outil retourne des codes de sortie standards pour l'intégration avec les outils de supervision :

| Code | Signification | Description |
|------|---------------|-------------|
| 0 | OK | Opération réussie |
| 1 | WARNING | Avertissement, vérification recommandée |
| 2 | CRITICAL | Erreur critique, action requise |
| 3 | UNKNOWN | État inconnu, vérifier les logs |
| 10-19 | CONFIG | Erreurs de configuration |
| 20-29 | NETWORK | Erreurs de connexion réseau |
| 30-39 | DATABASE | Erreurs base de données |
| 40-49 | SERVICES | Erreurs de services |
| 50-59 | SYSTEM | Erreurs système |
| 60-69 | AUDIT | Alertes d'obsolescence |
| 70-79 | BACKUP | Erreurs de sauvegarde |

---

## Intégration Zabbix

### Script UserParameter

Ajoutez dans `/etc/zabbix/zabbix_agentd.conf.d/ntl-systoolbox.conf` :

```ini
# Diagnostic services
UserParameter=ntl.diag.services,python3 /opt/ntl-systoolbox/ntl-systoolbox.py diagnostic services --output json 2>/dev/null; echo $?

# Diagnostic database
UserParameter=ntl.diag.database,python3 /opt/ntl-systoolbox/ntl-systoolbox.py diagnostic database --output json 2>/dev/null; echo $?

# Backup verification
UserParameter=ntl.backup.verify,python3 /opt/ntl-systoolbox/ntl-systoolbox.py backup verify --all --output json 2>/dev/null; echo $?

# Audit EOL
UserParameter=ntl.audit.report,python3 /opt/ntl-systoolbox/ntl-systoolbox.py audit report --output json --no-save 2>/dev/null; echo $?
```

### Template Zabbix

```yaml
# Items
- name: NTL - Services AD/DNS Status
  key: ntl.diag.services
  type: ZABBIX_ACTIVE
  value_type: UNSIGNED
  triggers:
    - expression: "last()>=2"
      severity: HIGH
      name: "Services AD/DNS critiques"
    - expression: "last()=1"
      severity: WARNING
      name: "Services AD/DNS en warning"

- name: NTL - EOL Audit Status
  key: ntl.audit.report
  type: ZABBIX_ACTIVE
  value_type: UNSIGNED
  triggers:
    - expression: "last()>=60"
      severity: HIGH
      name: "Systèmes obsolètes détectés"
```

---

## Structure du Projet

```
NTL-SYSTOOLBOX/
├── ntl-systoolbox.py          # Point d'entrée principal
├── config.yaml                # Configuration principale
├── .env.example               # Template pour les secrets
├── requirements.txt           # Dépendances Python
├── pyproject.toml             # Configuration projet Python
├── README.md                  # Documentation
├── .gitignore                 # Fichiers à ignorer
│
├── ntl_systoolbox/            # Package principal
│   ├── __init__.py
│   ├── __main__.py            # Point d'entrée module
│   │
│   ├── core/                  # Module core (utilitaires)
│   │   ├── __init__.py
│   │   ├── config.py          # Gestion configuration
│   │   ├── logger.py          # Logging horodaté
│   │   ├── output.py          # Formatage sortie
│   │   └── exit_codes.py      # Codes de retour
│   │
│   ├── diagnostic/            # Module diagnostic
│   │   ├── __init__.py
│   │   ├── services.py        # Vérification AD/DNS
│   │   ├── database.py        # Vérification MySQL
│   │   └── system_info.py     # Infos système
│   │
│   ├── backup/                # Module sauvegarde
│   │   ├── __init__.py
│   │   ├── wms_backup.py      # Sauvegarde WMS
│   │   └── integrity.py       # Vérification intégrité
│   │
│   ├── audit/                 # Module audit
│   │   ├── __init__.py
│   │   ├── scanner.py         # Scan réseau
│   │   ├── eol_database.py    # Base EOL
│   │   └── report.py          # Génération rapports
│   │
│   └── cli/                   # Interface CLI
│       ├── __init__.py
│       ├── __main__.py        # Point d'entrée CLI
│       ├── menu.py            # Menu interactif
│       └── commands.py        # Gestionnaire commandes
│
├── logs/                      # Logs (auto-créé)
├── backups/                   # Sauvegardes (auto-créé)
└── reports/                   # Rapports (auto-créé)
```

---

## Développement

### Tests

```bash
# Installer les dépendances de développement
pip install -e ".[dev]"

# Lancer les tests
pytest

# Avec couverture
pytest --cov=ntl_systoolbox
```

### Formatage du code

```bash
# Formater avec Black
black ntl_systoolbox/

# Vérifier avec Flake8
flake8 ntl_systoolbox/
```

### Ajouter un nouvel OS à la base EOL

Éditez `config.yaml` ou ajoutez dans `eol_database.py` :

```yaml
eol_database:
  - os: "Nouveau OS 1.0"
    eol_date: "2030-01-01"
    extended_support: "2032-01-01"
```

---

## Licence

MIT License - Nord Transit Logistics © 2024

---

## Support

Pour toute question ou problème :
- Email: it@nordtransit.local
- Issues: Créez un ticket sur le dépôt Git interne

---

**Développé pour Nord Transit Logistics - MSPR 2024**

# DOSSIER TECHNIQUE – MODULE DIAGNOSTIC

## 1. Présentation
Le module Diagnostic a pour objectif de fournir aux administrateurs système un état rapide, synthétique et exploitable des briques critiques du SI : contrôleurs de domaine, base de données métier, et santé système (CPU, RAM, disques).

## 2. Architecture du Module

L’architecture suit une logique modulaire :  
- **ServiceChecker** : Vérifie la disponibilité et l’état des services AD/DNS (LDAP, DNS, Kerberos, SMB, etc.) via scans port et ping.
- **DatabaseChecker** : Teste la connexion MySQL (port 3306), interroge la base et remonte ses statistiques essentielles, avec Fallback CLI.
- **SystemInfoCollector** : Analyse l’OS environnant, l’uptime, les ressources CPU/RAM/disque, avec un système de seuil d’alerte.

L’ensemble fonctionne via une **CLI** ergonomique offrant un menu interactif et une journalisation structurée, respectant les standards Nagios/Zabbix (codes de sortie, sortie JSON).

## 3. Description des Classes

- **ServiceChecker** (`services.py`)  
  Ping + scan des ports critiques.  
  Résolution DNS testée.  
  Vérifications des services via sc query (Windows) ou systemctl (Linux).

- **DatabaseChecker** (`database.py`)  
  Vérification connectivité réseau + login MySQL.  
  Choix natif Python ou command-line fallback.  
  Extractions statistiques : nombre de tables, taille BDD, uptime serveur.

- **SystemInfoCollector** (`system_info.py`)  
  Collecte OS, uptime, CPU, RAM, disques, en gérant fallback si psutil absent.  
  Application de seuils warning/critical (configurables).

## 4. Configuration et Gestion des Secrets

La configuration s’appuie sur un fichier `config.yaml` structuré :

```yaml
domain_controllers:
  - name: DC01
    ip: 192.168.10.10
ad_services:
  windows:
    - NTDS
    - DNS
  linux:
    - samba-ad-dc
wms_database:
  host: 192.168.10.21
  port: 3306
  database: wms_production
thresholds:
  cpu_warning: 80
  cpu_critical: 95
```

Les secrets (identifiants, mots de passe) sont gestionnés via le `.env` ou variables d’environnement (ex : NTL_DB_USER, NTL_DB_PASSWORD). Les mots de passe ne sont jamais loggés et ne doivent pas apparaître dans les fichiers sources (voir `.gitignore`).

## 5. Ergonomie du Menu Interactif

Le menu CLI (`menu.py`) propose :
1. Vérification des contrôleurs de domaine (services AD/DNS)
2. Vérification de la base de données MySQL
3. Informations système (uptime, CPU, RAM, disques)
4. Diagnostic complet

Chaque choix lance le module correspondant et affiche un résumé coloré (symboles ASCII pour compatibilité Windows/Linux), avec message explicite et aide intégrée.

## 6. Mode de Configuration

- Fichier `config.yaml` configurable selon infrastructure.
- `.env` et variables d’environnement prioritaires pour les secrets.
- Personnalisation possible des seuils d’alerte, des services surveillés, des contrôleurs ou BDD.

## 7. Démarche pour l’audit d’obsolescence

Le diagnostic intègre la collecte de version OS et la supervision de la santé système.  
La gestion des dates de fin de support (EOL) s’appuie sur une base de données statique (config.yaml) associée à chaque OS reconnu, basée sur les sources officielles :  
- Microsoft, Canonical, VMware, RedHat.
- La mise à jour de la base est manuelle (compromis d’intégration, sécurité).

## 8. Compromis et Limitations
- Fallback vers commandes systèmes si librairies absentes (psutil, mysql-connector-python)
- Vérification services Windows locale uniquement (pas de WMI distant, trop complexe)
- Détection OS basée sur heuristique, pas scan intrusif
- Timeout fixes pour diagnostics rapides ; faux positifs possibles sur réseaux instables
- Base EOL statique à mettre à jour à la main (évite dépendances externes)

## 9. Déploiement et intégration
- Installation par clonage du dépôt, pip install, configuration initiale adaptée.
- Planification recommandée via cron (`*/15 * * * * ...`) pour supervision récurrente.
- Format JSON compatible Zabbix/Nagios (UserParameter prêt à intégrer).
- Logs rotation automatique, formaté (DEBUG, INFO, WARNING, ERROR).
- Exploitation possible via exit codes standard.

## 10. Exemple de sortie (console)
```
============================================================
Vérification des Contrôleurs de Domaine
-- DC: DC01 (192.168.10.10) --
✓ Connectivité ICMP : Réponse en 1.2ms
✓ Service LDAP : Port 389 ouvert (OK)
✓ Service DNS : Port 53 ouvert (OK)
✓ Service Kerberos : Port 88 ouvert (OK)
�� Résolution DNS : Fonctionnelle
============================================================
RÉSUMÉ : 5 checks, 5 OK, code de sortie : 0 (OK)
```

---

**Pour toute reprise, reportez-vous à la structure du code et à cette documentation concise et claire. N'hésitez pas à adapter les seuils, les services et les configurations à votre SI !**

Fin du dossier technique.
#!/usr/bin/env python3
"""
Script de lancement NTL-SysToolbox
"""

import sys
import os

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ntl_systoolbox.cli.__main__ import main

if __name__ == '__main__':
    main()

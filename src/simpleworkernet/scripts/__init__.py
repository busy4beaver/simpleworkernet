# simpleworkernet/scripts/__init__.py
"""
Скрипты для управления SimpleWorkerNet
"""

from .uninstall import cleanup_with_confirmation, main as uninstall_main

__all__ = ['cleanup_with_confirmation', 'uninstall_main']
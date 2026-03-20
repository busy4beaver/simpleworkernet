# simpleworkernet/utils/app_name.py
"""
Утилиты для определения имени приложения
"""
import os
import sys
import hashlib
from pathlib import Path
from typing import Optional


def get_app_name(with_hash: bool = False) -> str:
    """
    Определяет имя приложения на основе пути к исполняемому скрипту.
    
    Args:
        with_hash: Если True, добавляет хеш пути для уникальности
        
    Returns:
        Имя приложения
    """
    try:
        # Получаем путь к исполняемому скрипту
        if getattr(sys, 'frozen', False):
            # Запуск из скомпилированного exe
            script_path = Path(sys.executable)
        else:
            # Запуск из скрипта Python
            script_path = Path(sys.argv[0])
        
        # Получаем имя скрипта без расширения
        script_name = script_path.stem
        
        if with_hash:
            # Получаем абсолютный путь к директории скрипта
            script_dir = script_path.parent.absolute()
            # Создаем хеш от полного пути для уникальности
            path_hash = hashlib.md5(str(script_dir).encode()).hexdigest()[:8]
            # Формируем имя приложения с хешем
            app_name = f"{script_name}_{path_hash}"
        else:
            # Используем только имя скрипта
            app_name = script_name
        
        return app_name
        
    except Exception:
        # В случае ошибки возвращаем имя по умолчанию
        return "default"


def get_caller_info() -> str:
    """
    Определяет информацию о caller'е (файл, строка, функция).
    
    Returns:
        Строка с информацией о месте вызова
    """
    import inspect
    try:
        stack = inspect.stack()
        
        for frame_info in stack[2:]:
            frame = frame_info.frame
            module = inspect.getmodule(frame)
            
            if module is None:
                continue
            
            module_name = module.__name__
            
            # Пропускаем внутренние модули
            if module_name.startswith('logging') or module_name == __name__:
                continue
            
            filename = os.path.basename(frame_info.filename)
            return f"{filename}:{frame_info.lineno} - {frame_info.function}()"
        
        return "unknown"
    except Exception:
        return "unknown"
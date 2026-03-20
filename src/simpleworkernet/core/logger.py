# simpleworkernet/core/logger.py
"""
Модуль логирования для SimpleWorkerNet
"""
import logging
import sys
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Union, List

from .constants import DEBUG, INFO, WARNING, ERROR, CRITICAL, LOGGER_NAME
from ..utils.app_name import get_app_name


def get_session_timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def cleanup_old_logs(log_dir: Path, max_files: int, pattern: str = "*.log") -> List[Path]:
    """Очищает старые лог-файлы"""
    if not log_dir.exists():
        return []
    
    log_files = list(log_dir.glob(pattern))
    log_files.sort(key=lambda p: p.stat().st_ctime)
    
    removed = []
    if len(log_files) > max_files:
        for file_path in log_files[:-max_files]:
            try:
                file_path.unlink()
                removed.append(file_path)
            except Exception:
                pass
    
    return removed


class WorkerNetLogger:
    """
    Логгер для WorkerNet.
    Синглтон для текущего процесса, использует имя текущего приложения.
    Поддерживает разные уровни для консоли и файла.
    """
    
    _instance: Optional['WorkerNetLogger'] = None
    
    def __new__(cls) -> 'WorkerNetLogger':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Определяем имя приложения
        self.app_name = get_app_name(with_hash=True)
        self.display_name = get_app_name(with_hash=False)
        
        # Создаем логгер
        logger_name = f"{LOGGER_NAME}.{self.app_name}"
        self._logger = logging.getLogger(logger_name)
        self._logger.setLevel(DEBUG)  # Самый низкий уровень, фильтровать будем в обработчиках
        self._logger.propagate = False
        
        # Состояние
        self._console_handler: Optional[logging.Handler] = None
        self._file_handler: Optional[logging.Handler] = None
        self._suppress_output = False
        self._session_id = get_session_timestamp()
        self._log_dir: Optional[Path] = None
        
        # Текущие настройки
        self._console_level = INFO
        self._file_level = DEBUG
        self._console_output = False
        self._log_to_file = False
        
        self._initialized = True
    
    def configure(self, **kwargs):
        """
        Настраивает логирование с раздельными уровнями.
        
        Args:
            console_level: Уровень для консоли (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            file_level: Уровень для файла
            log_to_file: Включить запись в файл
            console_output: Включить вывод в консоль
            max_log_files: Максимальное количество файлов логов
            log_dir: Директория для логов
        """
        console_level = kwargs.get('console_level', 'INFO')
        file_level = kwargs.get('file_level', 'DEBUG')
        log_to_file = kwargs.get('log_to_file', False)
        console_output = kwargs.get('console_output', False)
        max_log_files = kwargs.get('max_log_files', 50)
        log_dir = kwargs.get('log_dir')
        
        # Сохраняем настройки
        self._console_output = console_output
        self._log_to_file = log_to_file
        self._console_level = self._str_to_level(console_level)
        self._file_level = self._str_to_level(file_level)
        
        # Полностью очищаем все обработчики
        self._clear_handlers()
        
        # Создаем консольный обработчик, если нужно
        if console_output and not self._suppress_output:
            self._setup_console_handler()
        
        # Создаем файловый обработчик, если нужно
        if log_to_file and log_dir:
            self._log_dir = Path(log_dir)
            self._setup_file_handler(max_log_files)
    
    def _str_to_level(self, level: Union[str, int]) -> int:
        """Преобразует строковое представление уровня в число"""
        if isinstance(level, int):
            return level
        level_map = {
            'DEBUG': DEBUG,
            'INFO': INFO,
            'WARNING': WARNING,
            'ERROR': ERROR,
            'CRITICAL': CRITICAL
        }
        return level_map.get(level.upper(), INFO)
    
    def _clear_handlers(self):
        """Полностью очищает все обработчики логгера"""
        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)
        
        self._console_handler = None
        self._file_handler = None
    
    def _setup_console_handler(self):
        """Создает консольный обработчик с его уровнем"""
        formatter = logging.Formatter(
            f'%(asctime)s.%(msecs)03d - [{self.display_name}] - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self._console_level)  # Свой уровень для консоли
        handler.setFormatter(formatter)
        
        self._logger.addHandler(handler)
        self._console_handler = handler
        
        # Пробное сообщение для проверки
        self._logger.log(self._console_level, f"Консольный вывод активирован (уровень: {logging.getLevelName(self._console_level)})")
    
    def _setup_file_handler(self, max_log_files: int):
        """Создает файловый обработчик с его уровнем"""
        if not self._log_dir:
            return
        
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log_file = self._log_dir / f"{self.display_name}_{self._session_id}.log"
        
        formatter = logging.Formatter(
            f'%(asctime)s.%(msecs)03d - [{self.app_name}] - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        try:
            handler = logging.FileHandler(log_file, encoding='utf-8')
            handler.setLevel(self._file_level)  # Свой уровень для файла
            handler.setFormatter(formatter)
            
            self._logger.addHandler(handler)
            self._file_handler = handler
            
            self._logger.log(self._file_level, f"Лог-файл создан: {log_file} (уровень: {logging.getLevelName(self._file_level)})")
            
            pattern = f"{self.display_name}_*.log"
            cleanup_old_logs(self._log_dir, max_log_files, pattern)
            
        except Exception as e:
            print(f"Предупреждение: не удалось создать файловый обработчик: {e}")
    
    def set_console_output(self, enabled: bool):
        """Быстро включает/отключает консольный вывод"""
        if enabled == (self._console_handler is not None):
            return
        
        if enabled:
            if not self._suppress_output:
                self._setup_console_handler()
                self._console_output = True
        else:
            if self._console_handler:
                self._logger.removeHandler(self._console_handler)
                self._console_handler = None
                self._console_output = False
    
    def set_console_level(self, level: Union[str, int]):
        """Изменяет уровень логирования для консоли"""
        new_level = self._str_to_level(level)
        if new_level == self._console_level:
            return
        
        self._console_level = new_level
        if self._console_handler:
            self._console_handler.setLevel(new_level)
            self._logger.log(new_level, f"Уровень консоли изменён на {logging.getLevelName(new_level)}")
    
    def set_file_level(self, level: Union[str, int]):
        """Изменяет уровень логирования для файла"""
        new_level = self._str_to_level(level)
        if new_level == self._file_level:
            return
        
        self._file_level = new_level
        if self._file_handler:
            self._file_handler.setLevel(new_level)
            self._logger.log(new_level, f"Уровень файла изменён на {logging.getLevelName(new_level)}")
    
    def suppress_output(self, suppress: bool = True):
        """
        Подавляет или восстанавливает вывод в консоль.
        При подавлении - удаляет консольный обработчик.
        При восстановлении - создает заново, если console_output=True.
        """
        if self._suppress_output == suppress:
            return
        
        self._suppress_output = suppress
        
        if suppress:
            # Подавляем вывод - удаляем консольный обработчик
            if self._console_handler:
                self._logger.removeHandler(self._console_handler)
                self._console_handler = None
        else:
            # Восстанавливаем вывод - создаем консольный обработчик, если нужно
            if self._console_output:
                self._setup_console_handler()
    
    def get_session_id(self) -> str:
        return self._session_id
    
    def get_log_file(self) -> Optional[Path]:
        if self._file_handler:
            for handler in self._logger.handlers:
                if hasattr(handler, 'baseFilename'):
                    return Path(handler.baseFilename)
        return None
    
    # ==================== Специализированные методы логирования ====================
    
    def log_api_call(self, category: str, action: str, params: dict = None):
        """Логирует вызов API"""
        if self._logger.isEnabledFor(DEBUG):
            params_str = f"Параметры: {params}" if params else ""
            self.debug(f"API вызов: {category}.{action}; {params_str}")
    
    def log_api_response(self, category: str, action: str, status_code: int, size: int = None):
        """Логирует ответ API"""
        if self._logger.isEnabledFor(DEBUG):
            size_str = f"({size} байт)" if size else ""
            self.debug(f"API ответ: HTTP {status_code}; данных принято {size_str}")
    
    def log_cache_operation(self, operation: str, details: dict = None):
        """Логирует операцию с кэшем"""
        if details:
            details_str = " ".join(f"{k}={v}" for k, v in details.items())
            self.info(f"Кэш {operation}: {details_str}")
        else:
            self.info(f"Кэш {operation}")
    
    def log_smartdata_operation(self, operation: str, details: dict = None):
        """Логирует операцию SmartData"""
        if details:
            details_str = " ".join(f"{k}={v}" for k, v in details.items())
            self.debug(f"SmartData.{operation}: {details_str}")
        else:
            self.debug(f"SmartData.{operation}")
    
    def log_cache_stats(self, stats: Dict[str, Any]):
        """Логирует статистику кэша"""
        self.info(f"Статистика кэша: попаданий={stats.get('hits', 0)}")
    
    # ==================== Основные методы логирования ====================
    
    def debug(self, message: str, *args, **kwargs):
        """Отправляет DEBUG сообщение"""
        self._logger.debug(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Отправляет INFO сообщение"""
        self._logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Отправляет WARNING сообщение"""
        self._logger.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Отправляет ERROR сообщение"""
        self._logger.error(message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """Отправляет CRITICAL сообщение"""
        self._logger.critical(message, *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs):
        """Отправляет EXCEPTION сообщение"""
        self._logger.exception(message, *args, **kwargs)


# Глобальный экземпляр
log = WorkerNetLogger()
# simpleworkernet/core/cache.py
"""
Менеджер кэша для SmartData
"""
import time
import pickle
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from .exceptions import WorkerNetCacheError

# Ленивый импорт
_logger = None
_config_manager = None


def _get_logger():
    """Ленивый импорт логгера"""
    global _logger
    if _logger is None:
        from .logger import log
        _logger = log
    return _logger


def _get_config_manager():
    """Ленивый импорт ConfigManager (экземпляра)"""
    global _config_manager
    if _config_manager is None:
        from .config import config_manager
        _config_manager = config_manager
    return _config_manager


@dataclass
class CacheStats:
    """Статистика кэша"""
    hits: int = 0
    misses: int = 0
    numeric_hits: int = 0
    access_count: Dict[str, int] = field(default_factory=dict)
    total_operations: int = 0
    last_save_time: float = 0
    last_load_time: float = 0


class SmartDataCache:
    """
    Менеджер кэша для SmartData.
    Синглтон для текущего процесса, использует имя текущего приложения.
    """

    _instance: Optional['SmartDataCache'] = None

    def __new__(cls) -> 'SmartDataCache':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Получаем информацию из ConfigManager
        config_manager = _get_config_manager()
        self.app_name = config_manager.app_name

        self._field_name_cache: Dict[str, bool] = {}
        self._numeric_cache: Dict[str, bool] = {}
        self._stats = CacheStats()

        # Для LRU и FIFO
        self._access_order: List[str] = []    # порядок доступа (последний использованный в конце)
        self._insertion_order: List[str] = [] # порядок добавления

        self._cache_dir: Optional[Path] = None
        self._cache_file: Optional[Path] = None
        self._cache_version = 2
        self._dirty = False

        self._apply_config()
        self._initialized = True

    def _apply_config(self):
        """Применяет текущую конфигурацию из ConfigManager к локальным атрибутам."""
        config_manager = _get_config_manager()
        config = config_manager.get_cache_config()
        cache_cfg = config_manager.get().cache

        self._enabled = cache_cfg.enabled
        self._max_size = max(1000, cache_cfg.max_size)
        self._auto_save_enabled = cache_cfg.auto_save
        self._evict_threshold = max(0.1, min(1.0, cache_cfg.evict_threshold))
        self._evict_percent = max(0.01, min(1.0, cache_cfg.evict_percent))
        self._evict_strategy = cache_cfg.evict_strategy.lower()  # 'lru', 'lfu', 'fifo'

        cache_dir = config.get('cache_dir')
        if cache_dir:
            self._cache_dir = Path(cache_dir)
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._generate_cache_path()

    def _generate_cache_path(self):
        """Генерирует путь к файлу кэша"""
        if not self._cache_dir:
            return
        import inspect
        frame = inspect.currentframe()
        while frame:
            if frame.f_code.co_name == '<module>':
                module_path = Path(frame.f_code.co_filename).parent
                break
            frame = frame.f_back
        else:
            module_path = Path.cwd()
        hash_str = hashlib.md5(str(module_path).encode()).hexdigest()[:8]
        self._cache_file = self._cache_dir / f"cache_{hash_str}.pkl"

    def enable(self):
        """Включает кэширование (обновляет конфиг и себя)"""
        config_manager = _get_config_manager()
        config_manager.cache_enabled = True

    def disable(self):
        """Отключает кэширование (обновляет конфиг и себя)"""
        config_manager = _get_config_manager()
        config_manager.cache_enabled = False

    def is_enabled(self) -> bool:
        return self._enabled

    def get_cache_path(self) -> Optional[Path]:
        return self._cache_file

    def save(self, force: bool = False) -> bool:
        """Сохраняет кэш в файл, только если были изменения"""
        if not self._enabled:
            return False
        if not self._auto_save_enabled and not force:
            return False
        if not self._dirty and not force:
            _get_logger().debug("Кэш не изменялся, пропускаем сохранение")
            return False
        if not self._cache_file:
            return False

        self._cache_file.parent.mkdir(parents=True, exist_ok=True)

        cache_data = {
            'version': self._cache_version,
            'timestamp': time.time(),
            'field_name_cache': dict(self._field_name_cache),
            'numeric_cache': dict(self._numeric_cache),
            'access_count': dict(self._stats.access_count),
            'access_order': self._access_order,          # сохраняем порядок для LRU
            'insertion_order': self._insertion_order,    # для FIFO
            'hits': self._stats.hits,
            'misses': self._stats.misses,
            'numeric_hits': self._stats.numeric_hits,
        }

        try:
            with open(self._cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            self._stats.last_save_time = time.time()
            size_kb = self._cache_file.stat().st_size / 1024
            self._dirty = False
            _get_logger().info(
                f"Кэш сохранён: {len(self._field_name_cache)} полей, {size_kb:.1f} КБ"
            )
            return True
        except Exception as e:
            raise WorkerNetCacheError(f"Ошибка сохранения кэша: {e}")

    def load(self) -> bool:
        if not self._enabled or not self._cache_file or not self._cache_file.exists():
            return False

        try:
            with open(self._cache_file, 'rb') as f:
                cache_data = pickle.load(f)

            if cache_data.get('version') != self._cache_version:
                _get_logger().warning("Версия кэша не совпадает")
                return False

            self._field_name_cache = cache_data.get('field_name_cache', {})
            self._numeric_cache = cache_data.get('numeric_cache', {})
            self._stats.access_count = cache_data.get('access_count', {})
            self._stats.hits = cache_data.get('hits', 0)
            self._stats.misses = cache_data.get('misses', 0)
            self._stats.numeric_hits = cache_data.get('numeric_hits', 0)
            self._stats.last_load_time = time.time()

            # Восстанавливаем порядки
            self._access_order = cache_data.get('access_order', [])
            self._insertion_order = cache_data.get('insertion_order', [])

            self._dirty = False
            _get_logger().info(
                f"Кэш загружен: {len(self._field_name_cache)} полей"
            )
            return True
        except Exception as e:
            raise WorkerNetCacheError(f"Ошибка загрузки кэша: {e}")

    def ensure_saved(self) -> bool:
        """Гарантирует сохранение кэша, если были изменения."""
        if not self._enabled:
            return False
        if self._dirty and (self._field_name_cache or self._numeric_cache):
            return self.save(force=True)
        return False

    def clear(self):
        """Очищает кэш"""
        fields_before = len(self._field_name_cache)
        numbers_before = len(self._numeric_cache)

        self._field_name_cache.clear()
        self._numeric_cache.clear()
        self._stats.access_count.clear()
        self._stats.hits = 0
        self._stats.misses = 0
        self._stats.numeric_hits = 0
        self._access_order.clear()
        self._insertion_order.clear()
        self._dirty = True

        _get_logger().info(
            f"Кэш очищен: удалено {fields_before} полей, {numbers_before} чисел"
        )

    def is_valid_field_name(self, name: str) -> bool:
        """Проверяет валидность имени поля с кэшированием"""
        if not self._enabled:
            return name and isinstance(name, str) and name.isidentifier()

        if not name or not isinstance(name, str):
            return False

        self._stats.total_operations += 1

        if name.isdigit():
            if name not in self._numeric_cache:
                self._numeric_cache[name] = False
                self._stats.misses += 1
                self._dirty = True
                self._add_to_order(name)        # добавляем в порядки
                self._check_size()
            else:
                self._stats.numeric_hits += 1
                self._track_access(name)        # обновляем порядок доступа
            return False

        cached = self._field_name_cache.get(name)
        if cached is not None:
            self._stats.hits += 1
            self._track_access(name)
            return cached

        result = name.isidentifier()
        self._field_name_cache[name] = result
        self._stats.misses += 1
        self._track_access(name)
        self._add_to_order(name)                # новый ключ
        self._dirty = True
        self._check_size()

        return result

    def _add_to_order(self, name: str):
        """Добавляет ключ в порядки для LRU и FIFO"""
        if self._evict_strategy in ('lru', 'fifo'):
            self._insertion_order.append(name)
        if self._evict_strategy == 'lru':
            self._access_order.append(name)

    def _track_access(self, name: str):
        """Обновляет счётчик доступа и порядок для LRU"""
        if name not in self._stats.access_count:
            self._stats.access_count[name] = 0
        self._stats.access_count[name] += 1

        if self._evict_strategy == 'lru':
            # Перемещаем ключ в конец (последний использованный)
            if name in self._access_order:
                self._access_order.remove(name)
            self._access_order.append(name)

    def _check_size(self):
        """Проверяет размер кэша и при необходимости запускает очистку."""
        total_size = len(self._field_name_cache) + len(self._numeric_cache)
        if total_size >= self._max_size * self._evict_threshold:
            self._evict_least_used()

    def _evict_least_used(self):
        """Удаляет записи согласно выбранной стратегии"""
        total_size = len(self._field_name_cache) + len(self._numeric_cache)
        if total_size == 0:
            return

        to_remove_count = max(1, int(total_size * self._evict_percent))

        # Выбираем ключи для удаления в зависимости от стратегии
        if self._evict_strategy == 'lfu':
            # LFU – удаляем самые редко используемые
            sorted_items = sorted(self._stats.access_count.items(), key=lambda x: x[1])
            to_remove = {name for name, _ in sorted_items[:to_remove_count]}
        elif self._evict_strategy == 'lru':
            # LRU – удаляем самые давние (первые в access_order)
            to_remove = set(self._access_order[:to_remove_count])
        else:  # fifo (по умолчанию)
            # FIFO – удаляем самые старые (первые в insertion_order)
            to_remove = set(self._insertion_order[:to_remove_count])

        removed = 0
        for name in list(to_remove):
            if name in self._field_name_cache:
                del self._field_name_cache[name]
                removed += 1
            if name in self._numeric_cache:
                del self._numeric_cache[name]
                removed += 1
            if name in self._stats.access_count:
                del self._stats.access_count[name]
            # Удаляем из порядков
            if self._evict_strategy == 'lru' and name in self._access_order:
                self._access_order.remove(name)
            if self._evict_strategy == 'fifo' and name in self._insertion_order:
                self._insertion_order.remove(name)

        if removed > 0:
            self._dirty = True
            _get_logger().debug(
                f"Кэш очищен (стратегия {self._evict_strategy.upper()}): "
                f"удалено {removed} записей (размер до: {total_size}, после: {total_size - removed})"
            )

    def get_stats(self) -> Dict[str, Any]:
        total = self._stats.hits + self._stats.misses
        return {
            'enabled': self._enabled,
            'total_operations': self._stats.total_operations,
            'total': total,
            'hits': self._stats.hits,
            'misses': self._stats.misses,
            'numeric_hits': self._stats.numeric_hits,
            'field_cache_size': len(self._field_name_cache),
            'numeric_cache_size': len(self._numeric_cache),
            'max_size': self._max_size,
            'evict_strategy': self._evict_strategy,
            'hit_rate': (self._stats.hits / total * 100) if total > 0 else 0,
            'last_save': self._stats.last_save_time,
            'last_load': self._stats.last_load_time,
            'dirty': self._dirty,
        }

    def set_max_size(self, size: int):
        """Устанавливает максимальный размер кэша (обновляет конфиг и себя)"""
        config_manager = _get_config_manager()
        config_manager.cache_max_size = max(1000, min(size, 100000))


# Глобальный экземпляр (синглтон для текущего процесса)
cache = SmartDataCache()
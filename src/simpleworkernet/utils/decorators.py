# simpleworkernet/utils/decorators.py
"""
Декораторы для SimpleWorkerNet
"""
import functools
import time
import threading
import inspect
from typing import TypeVar, Generic, List, Dict, Any, Union, Literal, Type, Optional, Callable
from functools import wraps

# Используем ленивый импорт для логгера
_logger = None


def _get_logger():
    """Ленивый импорт логгера"""
    global _logger
    if _logger is None:
        from ..core.logger import log
        _logger = log
    return _logger


from ..core.exceptions import WorkerNetAPIError, WorkerNetError

T = TypeVar('T')

def logged_method(func):
    """
    Декоратор для автоматического логирования вызовов методов.
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        class_name = self.__class__.__name__
        method_name = func.__name__
        logger = _get_logger()
        
        # Не логируем слишком частые вызовы
        if method_name not in ['_deep_cast']:
            logger.debug(f"Вызов: {class_name}.{method_name}()")
        
        try:
            result = func(self, *args, **kwargs)
            return result
        except Exception as e:
            logger.error(f"Ошибка в {class_name}.{method_name}(): {e}")
            raise
    
    return wrapper

# simpleworkernet/utils/decorators.py

def api_method(model: Union[Type[T], Type[Any]] = Any, preprocessor: Optional[Callable] = None) -> Callable:
    """
    Декоратор для методов API категорий.
    
    Args:
        model: Модель для преобразования ответа
        preprocessor: Опциональная функция для предварительной обработки ответа
                      Должна принимать словарь и возвращать обработанный словарь
    
    Улучшенная логика обработки ответа:
    1. Если передан preprocessor, применяем его к ответу
    2. Список -> SmartData
    3. Не словарь -> как есть
    4. Словарь:
       a. Если есть ключ 'data' -> используем его значение
       b. Если модель BaseModel и в ответе есть ключи, совпадающие с полями модели -> передаём весь словарь
       c. Иначе ищем первый неслужебный ключ
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            logger = _get_logger()
            logger.debug(f"API метод: {self.__class__.__name__}.{func.__name__}()")
            
            # Получаем подготовленные параметры
            prepared_kwargs = func(self, *args, **kwargs)
            final_params = prepared_kwargs if isinstance(prepared_kwargs, dict) else kwargs
            
            try:
                # Получаем метод API
                api_action = getattr(getattr(self._client, self._category), func.__name__)
            except AttributeError as e:
                logger.error(f"Ошибка API: метод {self._category}.{func.__name__} не найден")
                raise WorkerNetAPIError(f"Метод API не найден: {self._category}.{func.__name__}")
            
            try:
                # Выполняем запрос
                response = api_action(**final_params)
                
                # Если нужно вернуть сырой ответ
                if model is Any or getattr(self, '_is_ret_origin', False):
                    logger.debug("Возврат сырого ответа")
                    return response
                    
            except WorkerNetError as e:
                # Пробрасываем ошибки WorkerNet
                if model is Any:
                    raise
                logger.warning(f"Ошибка API в {self._category}.{func.__name__}: {e}")
                return None
            except Exception as e:
                # Неожиданная ошибка
                logger.error(f"Неожиданная ошибка в {self._category}.{func.__name__}: {e}")
                raise WorkerNetAPIError(f"Ошибка API: {e}")
            
            # Применяем предобработчик если есть
            if preprocessor is not None:
                logger.debug(f"Применение предобработчика данных для {self.__class__.__name__}.{func.__name__}")
                try:
                    response = preprocessor(response)
                except Exception as e:
                    logger.error(f"Ошибка в предобработчике: {e}")
                    # В случае ошибки продолжаем с исходными данными
            
            # Обработка ответа
            return _process_api_response(response, model, self._category, func.__name__)
            
        return wrapper
    return decorator

def _process_api_response(
    response: Any, 
    model: Type, 
    category: str, 
    action: str
) -> Any:
    """
    Обрабатывает ответ API и преобразует в SmartData.

    1. Список -> SmartData
    2. Не словарь -> как есть
    3. Словарь:
       a. Если есть 'data' -> берём его
       b. Если модель BaseModel и в ответе есть ключи, совпадающие с полями модели -> передаём весь словарь
       c. Иначе ищем первый неслужебный ключ
    """
    logger = _get_logger()
    from ..smartdata.core import SmartData
    from ..models.base import BaseModel
    from ..models.primitives import vStr
    
    logger.debug(f"Обработка ответа {category}.{action}, тип: {type(response)}")
    
    # 1. Список -> SmartData
    if isinstance(response, list):
        result = SmartData(response, model)
        logger.debug(f"SmartData создан из списка: {len(result)} элементов")
        return result
    
    # 2. Не словарь -> возвращаем как есть
    if not isinstance(response, dict):
        logger.debug(f"Ответ не словарь: {type(response)}")
        return response
    
    # 3. Словарь
    logger.debug(f"Анализ словаря: ключи={list(response.keys())}")
    
    # Проверяем наличие результата операции
    result_value = response.get('result')
    error_value = response.get('error')
    
    # Если есть ошибка, логируем но не прерываем (может быть частичный успех)
    if error_value:
        logger.warning(f"API вернул ошибку: {error_value}")
    
    # 3a. Если есть явный ключ 'data' - используем его
    if 'data' in response:
        data = response['data']
        logger.debug(f"Найден ключ 'data', тип: {type(data)}")
        
        if data is None:
            logger.debug("data is None, возвращаем None")
            return None
            
        if isinstance(data, list):
            result = SmartData(data, model)
            logger.debug(f"SmartData создан из data: {len(result)} элементов")
            return result
        
        # Если data - словарь, и модель указана, передаём в SmartData
        if isinstance(data, dict):
            # Если модель BaseModel и data содержит все нужные поля
            if model is not Any and issubclass(model, BaseModel):
                logger.debug(f"Передаём data в SmartData с моделью {model.__name__}")
                return SmartData(data, model)
            
            # Иначе просто SmartData без модели
            logger.debug("Передаём data в SmartData без модели")
            return SmartData(data, Any)
        
        # data - примитив
        logger.debug(f"data - примитив: {type(data)}({data})")
        return SmartData(data, type(data))
    
    # 3b. Если модель BaseModel, проверяем, можно ли использовать весь словарь
    if model is not Any and issubclass(model, BaseModel):
        # Получаем ожидаемые поля модели
        model_fields = set()
        if hasattr(model, '__annotations__'):
            model_fields = set(model.__annotations__.keys())
        
        # Ключи ответа (исключая служебные)
        response_keys = {k for k in response.keys() if k not in ('result', 'error')}
        
        # Данные для модели (исключаем result и error)
        model_data = {k: v for k, v in response.items() if k not in ('result', 'error')}
        
        logger.debug(f"Поля модели: {model_fields}")
        logger.debug(f"Ключи ответа: {response_keys}")
        
        # Если все неслужебные ключи ответа есть в модели, или модель может принять лишние поля
        if response_keys.issubset(model_fields) or len(response_keys) > 0:
            logger.debug(f"Передаём данные в SmartData с моделью {model.__name__}: {list(model_data.keys())}")
            
            # Если модель ожидает один конкретный ключ, а у нас несколько, это нормально
            # BaseModel примет все переданные ключи
            return SmartData(model_data, model)
    
    # 3c. Ищем первый неслужебный ключ
    for key in response:
        if key not in ('result', 'error'):
            data = response[key]
            logger.debug(f"Используем ключ '{key}' для данных, тип: {type(data)}")
            
            if data is None:
                logger.debug(f"data[{key}] is None")
                continue
                
            if isinstance(data, list):
                result = SmartData(data, model)
                logger.debug(f"SmartData создан из {key}: {len(result)} элементов")
                return result
            
            if isinstance(data, dict):
                # Если модель BaseModel, передаём с моделью
                if model is not Any and issubclass(model, BaseModel):
                    logger.debug(f"Передаём {key} в SmartData с моделью {model.__name__}")
                    return SmartData(data, model)
                
            logger.debug(f"{key} - примитив: {data}")
            if type(data) is str: data = vStr(data)
            return SmartData(data, model)
    
    # Если ничего не нашли, возвращаем result или None
    logger.debug(f"result: {result_value if result_value is not None else None}")
    return result_value == 'OK' if result_value is not None else None

def log_method(level: str = 'debug', log_args: bool = True, log_result: bool = False):
    """
    Декоратор для логирования вызовов методов с параметрами.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = _get_logger()
            class_name = args[0].__class__.__name__ if args else ''
            method_name = func.__name__
            full_name = f"{class_name}.{method_name}" if class_name else method_name
            
            if log_args:
                args_str = ", ".join(str(a) for a in args[1:3])
                if len(args) > 3:
                    args_str += f"... (+{len(args)-3})"
                kwargs_str = ", ".join(f"{k}={v}" for k, v in list(kwargs.items())[:3])
                if len(kwargs) > 3:
                    kwargs_str += f"... (+{len(kwargs)-3})"
                
                params = []
                if args_str:
                    params.append(args_str)
                if kwargs_str:
                    params.append(kwargs_str)
                
                call_msg = f"{full_name}({', '.join(params)})"
            else:
                call_msg = full_name
            
            log_method = getattr(logger, level.lower())
            log_method(f"Вызов: {call_msg}")
            
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                elapsed = (time.time() - start_time) * 1000
                logger.debug(f"Выполнено за {elapsed:.2f}мс")
                
                if log_result:
                    result_str = str(result)[:100]
                    if len(str(result)) > 100:
                        result_str += "..."
                    logger.debug(f"Результат: {result_str}")
                
                return result
                
            except Exception as e:
                logger.error(f"Ошибка в {full_name}: {e}")
                raise
                
        return wrapper
    return decorator


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Декоратор для повторных попыток выполнения функции при ошибках.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = _get_logger()
            current_delay = delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(f"Все {max_attempts} попыток не удались для {func.__name__}: {e}")
                        raise
                    
                    logger.warning(f"Попытка {attempt}/{max_attempts} не удалась: {e}. Повтор через {current_delay:.1f}с")
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        return wrapper
    return decorator


def cache_result(ttl_seconds: Optional[int] = None, max_size: int = 100):
    """
    Декоратор для кэширования результатов функции.
    """
    cache = {}
    cache_times = {}
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = _get_logger()
            # Создаем ключ кэша из аргументов
            key = str(args) + str(sorted(kwargs.items()))
            
            # Проверяем наличие в кэше
            if key in cache:
                if ttl_seconds is not None:
                    age = time.time() - cache_times[key]
                    if age < ttl_seconds:
                        logger.debug(f"Кэш попадание для {func.__name__}")
                        return cache[key]
                    else:
                        logger.debug(f"Кэш устарел для {func.__name__}")
                        del cache[key]
                        del cache_times[key]
                else:
                    logger.debug(f"Кэш попадание для {func.__name__}")
                    return cache[key]
            
            # Выполняем функцию
            result = func(*args, **kwargs)
            
            # Ограничиваем размер кэша
            if len(cache) >= max_size:
                # Удаляем самую старую запись
                oldest_key = min(cache_times.keys(), key=lambda k: cache_times[k])
                del cache[oldest_key]
                del cache_times[oldest_key]
                logger.debug("Кэш очищен: удалена самая старая запись")
            
            # Сохраняем результат
            cache[key] = result
            cache_times[key] = time.time()
            logger.debug(f"Кэш промах для {func.__name__}, результат сохранён")
            
            return result
        return wrapper
    return decorator


def deprecated(reason: str = "", alternative: Optional[str] = None):
    """
    Декоратор для пометки устаревших функций.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = _get_logger()
            message = f"{func.__name__} устарел"
            if reason:
                message += f": {reason}"
            if alternative:
                message += f". Используйте {alternative}"
            
            logger.warning(message)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def synchronized(lock=None):
    """
    Декоратор для синхронизации доступа к методу (thread-safe).
    """
    import threading
    
    if lock is None:
        lock = threading.RLock()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                return func(*args, **kwargs)
        return wrapper
    return decorator


def singleton(cls):
    """
    Декоратор для создания класса-синглтона.
    """
    instances = {}
    
    @wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
            _get_logger().debug(f"Экземпляр синглтона создан: {cls.__name__}")
        return instances[cls]
    
    return get_instance


def async_method(func: Callable) -> Callable:
    """
    Декоратор для выполнения метода в отдельном потоке.
    """
    import threading
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        _get_logger().debug(f"Асинхронный поток запущен для {func.__name__}")
        return thread
    
    return wrapper


def validate_args(**validators):
    """
    Декоратор для валидации аргументов функции.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            
            for arg_name, validator in validators.items():
                if arg_name in bound.arguments:
                    value = bound.arguments[arg_name]
                    if not validator(value):
                        raise ValueError(f"Аргумент '{arg_name}' = {value} не прошёл валидацию")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def timer(log_level: str = 'debug'):
    """
    Декоратор для измерения времени выполнения функции.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            logger = _get_logger()
            start = time.perf_counter()
            result = func(self, *args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            
            log_method = getattr(logger, log_level)
            log_method(f"{self.__class__.__name__}.{func.__name__} выполнена за {elapsed:.2f}мс")
            
            return result
        return wrapper
    return decorator


def ensure_session(func: Callable) -> Callable:
    """
    Декоратор для методов API, требующих активной сессии.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        logger = _get_logger()
        if not hasattr(self, '_session') or self._session is None:
            logger.debug("Сессия не активна, создаем новую")
            self.session()
        return func(self, *args, **kwargs)
    return wrapper


def memoize(func: Callable) -> Callable:
    """
    Простой декоратор для мемоизации результатов функции.
    """
    cache = {}
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = _get_logger()
        key = str(args) + str(sorted(kwargs.items()))
        if key not in cache:
            cache[key] = func(*args, **kwargs)
            logger.debug(f"Мемоизация для {func.__name__}{args}")
        return cache[key]
    
    return wrapper


def abstract_method(func: Callable) -> Callable:
    """
    Декоратор для пометки абстрактного метода.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        raise NotImplementedError(f"Абстрактный метод {func.__name__} должен быть реализован")
    
    return wrapper


__all__ = [
    'logged_method',
    'api_method',
    'log_method',
    'retry',
    'cache_result',
    'deprecated',
    'synchronized',
    'singleton',
    'async_method',
    'validate_args',
    'timer',
    'ensure_session',
    'memoize',
    'abstract_method',
]
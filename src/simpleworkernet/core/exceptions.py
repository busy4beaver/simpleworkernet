# simpleworkernet/core/exceptions.py
"""
Классы исключений для SimpleWorkerNet
"""


class WorkerNetError(Exception):
    """Базовое исключение для всех ошибок WorkerNet"""
    pass


class WorkerNetConfigError(WorkerNetError):
    """Ошибка конфигурации"""
    pass


class WorkerNetConnectionError(WorkerNetError):
    """Ошибка соединения с сервером"""
    def __init__(self, message: str, url: str = None, timeout: int = None):
        self.url = url
        self.timeout = timeout
        details = []
        if url:
            details.append(f"url={url}")
        if timeout:
            details.append(f"timeout={timeout}")
        details_str = f" ({', '.join(details)})" if details else ""
        super().__init__(f"{message}{details_str}")


class WorkerNetAPIError(WorkerNetError):
    """Ошибка API WorkerNet"""
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        self.status_code = status_code
        self.response = response
        details = []
        if status_code:
            details.append(f"status={status_code}")
        if response and 'error' in response:
            details.append(f"error={response['error']}")
        details_str = f" ({', '.join(details)})" if details else ""
        super().__init__(f"{message}{details_str}")


class WorkerNetCacheError(WorkerNetError):
    """Ошибка кэширования"""
    pass


class WorkerNetValidationError(WorkerNetError):
    """Ошибка валидации данных"""
    pass


class WorkerNetSmartDataError(WorkerNetError):
    """Ошибка обработки SmartData"""
    pass


class WorkerNetRecursionError(WorkerNetSmartDataError):
    """Ошибка превышения глубины рекурсии в SmartData"""
    pass


class GraphicsError(WorkerNetError):
    """Ошибка при работе с графикой"""
    pass


class SVGValidationError(GraphicsError):
    """Ошибка валидации SVG"""
    pass
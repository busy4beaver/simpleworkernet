# simpleworkernet/core/client.py
"""
API клиент для WorkerNet
"""
import requests
from typing import Literal, Any, Optional, Dict, Union

from .logger import log
from .exceptions import (
    WorkerNetAPIError, 
    WorkerNetConnectionError,
    WorkerNetError
)
from .config import config_manager
from ..utils.decorators import timer

# Импортируем все категории
from ..models.categories.additional_data import Additional_data
from ..models.categories.address import Address
from ..models.categories.advertising import Advertising
from ..models.categories.attach import Attach
from ..models.categories.billing import Billing
from ..models.categories.cable_route import Cable_route
from ..models.categories.call import Call
from ..models.categories.commutation import Commutation
from ..models.categories.cross import Cross
from ..models.categories.customer import Customer
from ..models.categories.cwdm import Cwdm
from ..models.categories.device import Device
from ..models.categories.employee import Employee
from ..models.categories.fiber import Fiber
from ..models.categories.gps import Gps
from ..models.categories.inventory import Inventory
from ..models.categories.key import Key
from ..models.categories.map import Map
from ..models.categories.module import Module
from ..models.categories.node import Node
from ..models.categories.notepad import Notepad
from ..models.categories.owner import Owner
from ..models.categories.service import Service
from ..models.categories.setting import Setting
from ..models.categories.sms import Sms
from ..models.categories.splitter import Splitter
from ..models.categories.system import System
from ..models.categories.tariff import Tariff
from ..models.categories.task import Task


class WorkerNetClient:
    """
    API Клиент WorkerNet.
    
    Предоставляет доступ ко всем категориям API через dot-нотацию.
    
    Пример:
        >>> client = WorkerNetClient("api.example.com", "your-api-key")
        >>> customers = client.Customer.get_data(customer_id=1)
        >>> print(customers)
    """
    
    # Максимальная длина URL для GET запросов
    MAX_URL_LENGTH = 2048
    
    def __init__(
        self, 
        host: str, 
        apikey: str, 
        protocol: Literal['http', 'https'] = 'https', 
        port: int = 443, 
        apiscr: str = 'api.php', 
        session: Optional[requests.Session] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None
    ):
        """
        Инициализация клиента.
        
        Args:
            host: Хост API (например: "simple.workernet.ru")
            apikey: Ключ API
            protocol: Протокол ('http' или 'https')
            port: Порт
            apiscr: Имя скрипта API
            session: Существующая сессия requests (опционально)
            timeout: Таймаут запроса в секундах
            max_retries: Максимальное количество повторов при ошибке
        """
        self._url = f'{protocol}://{host}:{port}/{apiscr}'
        self._apikey = apikey
        self._session = session
        
        # Загружаем настройки из конфига
        if timeout is not None:
            config_manager.default_timeout = timeout
        if max_retries is not None:
            config_manager.max_retries = max_retries
        
        # Текущая категория для запроса
        self._current_category = None
        
        log.info(f"Инициализация WorkerNetClient: {self._url}")
        log.debug(f"Таймаут: {config_manager.default_timeout}с, повторы: {config_manager.max_retries}")
        
        self.Address = Address(self)
        self.Attach = Attach(self)
        self.Additional_data = Additional_data(self)
        self.Advertising = Advertising(self)
        self.Billing = Billing(self)
        self.Cable_route = Cable_route(self)
        self.Call = Call(self)
        self.Commutation = Commutation(self)
        self.Cross = Cross(self)
        self.Customer = Customer(self)
        self.Cwdm = Cwdm(self)
        self.Device = Device(self)
        self.Employee = Employee(self)
        self.Fiber = Fiber(self)
        self.Gps = Gps(self)
        self.Inventory = Inventory(self)
        self.Key = Key(self)
        self.Map = Map(self)
        self.Module = Module(self)
        self.Node = Node(self)
        self.Notepad = Notepad(self)
        self.Owner = Owner(self)
        self.Service = Service(self)
        self.Setting = Setting(self)
        self.Sms = Sms(self)
        self.Splitter = Splitter(self)
        self.System = System(self)
        self.Tariff = Tariff(self)
        self.Task = Task(self)
    
    def _encode_str(self, data: Any) -> Any:
        """
        Особая обработка слешей в строках.
        Заменяет / на &#047; и \\ на &#092;
        """
        if isinstance(data, dict):
            return {k: self._encode_str(v) for k, v in data.items()}
        elif isinstance(data, (list, tuple)):
            return [self._encode_str(v) for v in data]
        elif isinstance(data, str):
            return data.replace('/', '&#047;').replace('\\', '&#092;')
        return data
    
    def _prepare_params(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        Подготавливает параметры запроса.
        
        Args:
            action: Название действия
            **kwargs: Параметры запроса
            
        Returns:
            Словарь с параметрами
        """
        params = {
            'key': self._apikey,
            'cat': self._current_category,
            'action': action
        }
        
        # Для модуля special case
        if self._current_category == 'module':
            params["request"] = params.pop("action")
        
        # Кодируем параметры
        encoded_kwargs = self._encode_str(kwargs)
        params.update(encoded_kwargs)
        
        # Удаляем None значения
        params = {k: v for k, v in params.items() if v is not None}
        
        return params
    
    @timer()
    def _make_request(self, params: Dict[str, Any]) -> requests.Response:
        """
        Выполняет HTTP запрос с поддержкой повторных попыток.
        
        Args:
            params: Параметры запроса
            
        Returns:
            Response объект
            
        Raises:
            WorkerNetConnectionError: При ошибке соединения
        """
        # Создаем сессию если нужно
        close_after = self.session()
        
        try:
            # Подготавливаем GET запрос
            prepared = requests.Request(
                method='GET',
                url=self._url,
                params=params
            ).prepare()
            
            url_length = len(prepared.url)
            log.debug(f"Длина URL: {url_length} символов")
            
            # Выполняем запрос с повторами
            retry_count = 0
            last_error = None
            
            while retry_count <= config_manager.max_retries:
                try:
                    if url_length > self.MAX_URL_LENGTH:
                        # Слишком длинный URL - используем POST
                        log.debug(f"URL слишком длинный, используем POST")
                        response = self._session.post(
                            self._url, 
                            params=params,
                            timeout=config_manager.default_timeout
                        )
                    else:
                        response = self._session.send(
                            prepared,
                            timeout=config_manager.default_timeout
                        )
                    break
                    
                except requests.exceptions.Timeout as e:
                    last_error = e
                    retry_count += 1
                    if retry_count <= config_manager.max_retries:
                        log.warning(f"Таймаут запроса, повтор {retry_count}/{config_manager.max_retries}")
                    else:
                        raise WorkerNetConnectionError(
                            f"Таймаут после {retry_count} попыток",
                            url=self._url,
                            timeout=config_manager.Client.timeout
                        )
                        
                except requests.exceptions.ConnectionError as e:
                    raise WorkerNetConnectionError(
                        f"Ошибка соединения: {e}",
                        url=self._url
                    )
                    
        except Exception as e:
            if not isinstance(e, WorkerNetError):
                raise WorkerNetConnectionError(f"Ошибка запроса: {e}")
            raise
        
        finally:
            # Закрываем сессию если создавали
            if close_after:
                self.closeSession()
        
        return response
    
    def _parse_response(self, response: requests.Response) -> Union[dict, Any]:
        """
        Парсит ответ API.
        
        Args:
            response: Response объект
            
        Returns:
            Распарсенные данные
            
        Raises:
            WorkerNetAPIError: При ошибке API
        """
        log.log_api_response(
            self._current_category,
            self._url,
            response.status_code,
            len(response.content)
        )
        
        # Проверяем статус
        if response.status_code != 200:
            try:
                error_data = response.json()
                error_msg = error_data.get('error') or error_data.get('Error', 'Неизвестная ошибка')
            except:
                error_msg = response.text[:200]
            
            log.error(f"Ошибка API {response.status_code}: {error_msg}")
            raise WorkerNetAPIError(
                f"Ошибка API",
                status_code=response.status_code,
                response={'error': error_msg}
            )
        
        # Парсим JSON
        try:
            content = response.json()
            log.debug(f"Ответ распарсен, тип: {type(content)}")
            return content
        except ValueError:
            # Не JSON ответ
            log.debug(f"Ответ не в JSON формате, возвращаем сырой контент")
            return response.content
    
    def _exec(self, action: str, **kwargs) -> Union[dict, Any]:
        """
        Выполняет запрос к API.
        
        Args:
            action: Название действия
            **kwargs: Параметры запроса
            
        Returns:
            Ответ API
            
        Raises:
            WorkerNetAPIError: При ошибке API
            WorkerNetConnectionError: При ошибке соединения
        """
        # Логируем вызов
        log.log_api_call(self._current_category, action, kwargs)
        
        # Подготавливаем параметры
        params = self._prepare_params(action, **kwargs)
        
        try:
            # Выполняем запрос
            response = self._make_request(params)
            
            # Парсим ответ
            content = self._parse_response(response)
            
            return content
            
        except WorkerNetError:
            # Пробрасываем наши исключения
            raise
        except Exception as e:
            # Неожиданная ошибка
            log.exception(f"Неожиданная ошибка в запросе: {e}")
            raise WorkerNetError(f"Внутренняя ошибка клиента: {e}")
    
    def is_online(self, timeout: int = 5) -> bool:
        """
        Проверяет доступность сервера.
        
        Args:
            timeout: Таймаут проверки в секундах
            
        Returns:
            True если сервер доступен
        """
        log.debug(f"Проверка доступности сервера: {self._url}")
        try:
            response = requests.get(self._url, timeout=timeout)
            return response.status_code
        except requests.RequestException:
            return False
    
    def session(self) -> bool:
        """
        Создает сессию если её нет.
        
        Returns:
            True если сессия была создана
        """
        if not self._session:
            self._session = requests.Session()
            self._session.headers.update({
                'User-Agent': config_manager.user_agent,
                'Accept': 'application/json',
            })
            log.debug("Новая сессия создана")
            return True
        return False
    
    def closeSession(self):
        """Закрывает текущую сессию"""
        if self._session:
            self._session.close()
            self._session = None
            log.debug("Сессия закрыта")
    
    def set_timeout(self, timeout: int):
        """Устанавливает таймаут запросов"""
        config_manager.default_timeout = timeout
        log.debug(f"Таймаут изменён на {timeout}с")
    
    def set_max_retries(self, retries: int):
        """Устанавливает максимальное количество повторов"""
        config_manager.max_retries = retries
        log.debug(f"Максимальное количество повторов изменено на {retries}")
    
    # ==================== Динамические категории ====================
    
    def __getattr__(self, name: str):
        """
        Позволяет обращаться к категориям динамически.
        
        Пример:
            >>> client.some_category.some_action()
        """
        # Проверяем, не запрашивают ли существующий атрибут
        if name in self.__dict__:
            return self.__dict__[name]
        
        # Создаем динамическую категорию
        self._current_category = name.lower()
        log.debug(f"Динамическая категория: {name}")
        
        class DynamicCategory:
            def __init__(self, client: WorkerNetClient, category: str):
                self._client = client
                self._category = category
            
            def __getattr__(self, action: str):
                def _action(**kwargs):
                    self._client._current_category = self._category
                    return self._client._exec(action, **kwargs)
                return _action
        
        return DynamicCategory(self, self._current_category)
    
    # ==================== Контекстный менеджер ====================
    
    def __enter__(self):
        """Вход в контекстный менеджер"""
        self.session()
        log.debug("Вход в контекстный менеджер")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекстного менеджера"""
        self.closeSession()
        log.debug("Выход из контекстного менеджера")
        if exc_type:
            log.error(f"Исключение в контекстном менеджере: {exc_val}")
    
    def __del__(self):
        """Деструктор"""
        self.closeSession()
    
    def __repr__(self) -> str:
        return f"WorkerNetClient(URL={self._url}, timeout={config_manager.default_timeout}, retriers={config_manager.max_retries})"
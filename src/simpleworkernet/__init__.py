# simpleworkernet/__init__.py
"""
SimpleWorkerNet - Python клиент для API WorkerNet
"""

import sys
import os
import atexit

from .__version__ import __version__, __author__, __email__, __license__

# ------------------------------------------------------------------------
# Определение режима запуска
# ------------------------------------------------------------------------

_IN_CLEANUP = os.environ.get('SIMPLEWORKERNET_CLEANUP') == '1'

is_cli = any(arg.endswith(('cleanup-simpleworkernet', 'simpleworkernet-cli')) 
             for arg in sys.argv) or '--help' in sys.argv or '--version' in sys.argv

if is_cli:
    # Для CLI минимум импортов
    from .scripts.uninstall import cleanup_with_confirmation, list_applications
    from .core.logger import log
    from .core.config import config_manager
    
    # Подавляем логи для CLI
    log.suppress_output(True)
    
    # Принудительно применяем конфигурацию после подавления
    log.configure(**config_manager.get_log_config())

    __all__ = [
        '__version__', '__author__', '__email__', '__license__',
        'cleanup_with_confirmation', 'list_applications',
    ]
else:
    # ------------------------------------------------------------------------
    # Нормальная инициализация для основного использования
    # ------------------------------------------------------------------------
    
    # 1. Сначала импортируем константы (без зависимостей)
    from .core.constants import DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    # 2. Импортируем утилиты
    from .utils.app_name import get_app_name
    
    # 3. Инициализируем ConfigManager (определит имя приложения)
    from .core.config import config_manager
    
    # 4. Инициализируем логгер и применяем конфигурацию
    from .core.logger import log
    log.configure(**config_manager.get_log_config())
    
    # 5. Импортируем остальные модули
    from .core.client import WorkerNetClient
    from .core.cache import cache
    from .core.exceptions import (
        WorkerNetError, WorkerNetConfigError, WorkerNetConnectionError,
        WorkerNetAPIError, WorkerNetCacheError, WorkerNetValidationError,
        WorkerNetSmartDataError, GraphicsError, SVGValidationError
    )
    
    # 6. Импортируем модели и утилиты
    from .models.base import BaseModel, BaseCategory, smart_model, CollapsedField
    from .models.primitives import (
        vStr, vFlag, GeoPoint, vPhoneNumber, vINN, vKPP, vSNILS, vOGRN,
        vMoney, vPercent, vPeriod, additional_field, additional_data
    )
    from .models.operators import Operator, Where
    from .smartdata import SmartData
    from .smartdata.metadata import MetaData, PathSegment, SegmentType
    from .utils.decorators import api_method, logged_method, timer
    from .utils.graphics import save_svg, load_svg, svg_to_png
    from .scripts.uninstall import cleanup_with_confirmation, cleanup

    # ------------------------------------------------------------------------
    # Работа с кэшем – только если не в режиме очистки
    # ------------------------------------------------------------------------
    if not _IN_CLEANUP:
        # 7. Загружаем кэш если включено
        if config_manager.get().cache_enabled:
            if not cache.load():
                log.info("Создание нового кэша...")
                # Импортируем модели для предзагрузки
                from .models.categories.additional_data import Additional_data
                from .models.categories.address import Address
                from .models.categories.advertising import Advertising
                from .models.categories.attach import Attach
                from .models.categories.billing import Billing
                from .models.categories.cable_route import Cable_route
                from .models.categories.call import Call
                from .models.categories.commutation import Commutation
                from .models.categories.cross import Cross
                from .models.categories.customer import Customer
                from .models.categories.cwdm import Cwdm
                from .models.categories.device import Device
                from .models.categories.employee import Employee
                from .models.categories.fiber import Fiber
                from .models.categories.gps import Gps
                from .models.categories.inventory import Inventory
                from .models.categories.key import Key
                from .models.categories.map import Map
                from .models.categories.module import Module
                from .models.categories.node import Node
                from .models.categories.notepad import Notepad
                from .models.categories.owner import Owner
                from .models.categories.service import Service
                from .models.categories.setting import Setting
                from .models.categories.sms import Sms
                from .models.categories.splitter import Splitter
                from .models.categories.system import System
                from .models.categories.tariff import Tariff
                from .models.categories.task import Task
                
                models = [
                    Additional_data.Get_list,
                    Address.Get_locality_type,
                    Address.Get_alias,
                    Address.Get,
                    Address.Get_province,
                    Address.Get_district,
                    Address.Get_city,
                    Address.Get_area,
                    Address.Get_street,
                    Address.Get_building_structure,
                    Address.Get_house,
                    Address.Get_level,
                    Advertising.Get,
                    Cable_route.Get_route,
                    Cable_route.GetDuct,
                    Commutation.Get_data,
                    Cross.Get_list,
                    Customer.Abon_hist,
                    Customer.Get_customer_group,
                    Customer.Get_data,
                    Customer.Get_data.Agreement,
                    Customer.Get_data.Traffic,
                    Customer.Get_data.Phone,
                    Customer.Get_data.Address,
                    Customer.Get_data.Tariff,
                    Customer.Get_data.Service,
                    Customer.Get_data.Ip_mac,
                    Customer.Get_data.Billing,
                    Customer.Msg,
                    Cwdm.Get,
                    Device.Get_connected_ont_information,
                    Device.Get_data,
                    Device.Get_current_ont_data,
                    Device.Get_iface_info,
                    Device.Get_iface_mac,
                    Device.Get_mac_list,
                    Device.Get_ont_data,
                    Device.Get_pon_level_history,
                    Employee.Get_data,
                    Employee.Get_division,
                    Employee.Get_division_list,
                    Employee.Get_history,
                    Employee.Get_history_type,
                    Employee.Get_timesheet_data,
                    Fiber.Catalog_cables_get,
                    Fiber.Get_fiber,
                    Fiber.Get_list,
                    Fiber.Map_color_get,
                    Gps.Get_info,
                    Gps.Get_list,
                    Gps.Get_route,
                    Inventory.Get_inventory,
                    Inventory.Get_inventory_amount,
                    Inventory.Get_inventory_catalog,
                    Inventory.Get_inventory_section_catalog,
                    Inventory.Get_inventory_storage,
                    Inventory.Get_operation,
                    Key.Get_list,
                    Map.Check_entry_point_in_polygon,
                    Map.Get,
                    Map.Get_poly,
                    Module.Get_connect_list,
                    Module.Get_device_list,
                    Module.Get_house_list,
                    Module.Get_services_list,
                    Module.Get_street_list,
                    Module.Get_system_information,
                    Module.Get_tariff_list,
                    Module.Get_user_history,
                    Module.Get_user_list,
                    Module.Get_user_messages,
                    Module.Get_user_state_list
                ]
                if models:
                    SmartData.preload_from_models(*models, recursive=True)
        
        # 8. Регистрируем сохранение кэша при выходе
        def _save_cache():
            try:
                cache.ensure_saved()
            except Exception as e:
                log.error(f"Ошибка при сохранении кэша: {e}")
        
        atexit.register(_save_cache)
        
        # 9. Приветственное сообщение
        app_name = get_app_name(with_hash=False)
        log.info("=" * 60)
        log.info(f"SimpleWorkerNet v{__version__} - '{app_name}'")
        log.info("=" * 60)
    
    __all__ = [
        '__version__', '__author__', '__email__', '__license__',
        'WorkerNetClient',
        'WorkerNetError', 'WorkerNetConfigError', 'WorkerNetConnectionError',
        'WorkerNetAPIError', 'WorkerNetCacheError', 'WorkerNetValidationError',
        'WorkerNetSmartDataError', 'GraphicsError', 'SVGValidationError', 
        'config_manager', 'log', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL',
        'get_app_name', 'cleanup_with_confirmation', 'cleanup',
        'SmartData', 'cache',
        'MetaData', 'PathSegment', 'SegmentType',
        'BaseCategory', 'BaseModel', 'smart_model', 'CollapsedField',
        'vStr', 'vFlag', 'GeoPoint', 'vPhoneNumber', 'vINN', 'vKPP',
        'vSNILS', 'vOGRN', 'vMoney', 'vPercent', 'vPeriod',
        'Operator', 'Where',
        'api_method', 'logged_method', 'timer',
        'additional_field', 'additional_data',
        'save_svg', 'load_svg', 'svg_to_png'
    ]
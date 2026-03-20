from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method

class Gps(BaseCategory):
    """GPS трекеры"""

    @smart_model
    class Get_info(BaseModel):
        id: vStr
        object_type: vStr
        object_id: int
        last_alive: vStr
        lat: float
        lon: float
        speed: int

    @api_method(Get_info)
    def get_info(self, *, id: str) -> ApiRetSData[Get_info]:
        """Общая информация по трекеру

            Обязательные параметры:
                id - id/imei трекера
        """
        ...
    
    @smart_model
    class Get_list(BaseModel):
        id: vStr
        object_type: vStr
        object_id: int

    @api_method(Get_list)
    def get_list(self) -> ApiRetSData[Get_list]:
        """Список трекеров"""
        ...

    @smart_model
    class Get_route(BaseModel):
        date: vStr
        lat: float
        lon: float
        speed: int

    @api_method(Get_route)
    def get_route(self, *, id: str, date_start: str, date_finish: str) -> ApiRetSData[Get_route]:
        """Маршрут движения 

            Обязательные параметры:
                id - id/imei трекера
                date_start - дата начала
                date_finish - дата окончания
        """
        ...
    
    @api_method(bool)
    def set_position(self, *, id: str, lat: float, lng: float, time: int = None, speed: int = None) -> ApiRetBool:
        """Установить позицию для трекера

            Обязательные параметры:
                id - id/imei трекера
                lat - широта
                lng - долгота
            Необязательные параметры:
                time - дата и время (unixtime)
                speed - скорость (км/ч)
        """
        ...
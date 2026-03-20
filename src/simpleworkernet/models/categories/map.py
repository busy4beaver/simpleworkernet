from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method

class Map(BaseCategory):
    """Действие с картами покрытия"""

    @api_method(str)
    def add_label(self, *, lat: float, lon: float, text: str) -> ApiRetSData[str]:
        """Добавление надписи

            Обязательные параметры:
                lat - широта
                lon - долгота
                text - текст надписи
        """
        ...

    @api_method(str)
    def add_poly(self, *, coord: str, name: str, color: str = None) -> ApiRetSData[str]:
        """Добавление полигона

            Обязательные параметры:
                coord - координаты (через запятую)
                name - наименование
            Необязательные параметры:
                color - HTML-цвет полигона
        """
        ...
    
    @smart_model
    class Check_entry_point_in_polygon(BaseModel):
        id: int
        name: vStr
        color: vStr
        coordinates: List[GeoPoint]
        coordinates_center: GeoPoint

    @api_method(Check_entry_point_in_polygon)
    def check_entry_point_in_polygon(self, *, lat: float, lon: float) -> ApiRetSData[Check_entry_point_in_polygon]:
        """Список полигонов в которые входит точка

            Обязательные параметры:
                lat - широта точки
                lon - долгота точки
        """
        ...

    @api_method(bool)
    def edit_label(self, *, id: str, lat: float = None, lon: float = None, text: str = None) -> ApiRetBool:
        """Изменение надписи

            Обязательные параметры:
                id - id объекта
            Необязательные параметры:
                lat - широта
                lon - долгота
                text - текст надписи
        """
        ...

    @api_method(bool)
    def edit_poly(self, *, id: str, coord: str = None, name: str = None, color: str = None) -> ApiRetBool:
        """Изменение полигона

            Обязательные параметры:
                id - id объекта
            Необязательные параметры:
                coord - координаты (через запятую)
                name - наименование
                color - HTML-цвет полигона
        """
        ...
    
    @smart_model
    class Get(BaseModel):
        @smart_model
        class Center(BaseModel):
            lat: float
            lon: float
            zoom: int
        id: int
        name: vStr
        center: Center

    @api_method(Get)
    def get(self, *, id: int | str = None) -> ApiRetSData[Get]:
        """Список объектов

            Необязательные параметры:
                id - перечень ID объектов (через запятую)
        """
        ...

    @smart_model
    class Get_poly(BaseModel):
        id: int
        name: vStr
        color: vStr
        coordinates: List[GeoPoint]
        coordinates_center: GeoPoint

    @api_method(Get_poly)
    def get_poly(self, *, id: str = None) -> ApiRetSData[Get_poly]:
        """Список полигонов

            Необязательные параметры:
                id - перечень ID объектов (через запятую)
        """
        ...

    @api_method()
    def map_object_facilities_inside(self, *, id: str) -> dict[str, List[int]]:
        """Получение списка объектов, что находятся внутри объекта на карте (например внутри полигона)

            Обязательные параметры:
                id - id объекта
        """
        ...
    
    @api_method(bool)
    def map_object_mark_add(self, *, id: str, mark_id: int) -> ApiRetBool:
        """Добавление метки на объекте на карте

            Обязательные параметры:
                id - id объекта
                mark_id - id метки
        """
        ...
    
    @api_method(bool)
    def map_object_mark_delete(self, *, id: str, mark_id: int) -> ApiRetBool:
        """Удаление метки с объекта на карте

            Обязательные параметры:
                id - id объекта
                mark_id - id метки
        """
        ...

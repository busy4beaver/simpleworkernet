from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method, deprecated

class Node(BaseCategory):
    """Объекты инфраструктуры (узлы связи, муфты, опоры, колодцы)"""

    link_cat = 'node'

    class In_type_id(IntEnum):
        """ID типов объектов инфраструктуры"""
        splice_closure = 1
        """муфта"""
        pole = 2
        """опора"""
        manhole = 3
        """колодец"""
        node = 4
        """узел связи"""

    @api_method(int)
    def add(self, *, 
            type: int | In_type_id, 
            city_id: int = None, 
            custom_icon_id: int = None, 
            comment: str = None, 
            date_add: str = None, 
            entrance: int = None, 
            house_id: int = None, 
            inventory_number: str = None, 
            is_planned: vFlag = None, 
            level: str = None, 
            level_id: int = None, 
            location: str = None, 
            node_parent_id: int = None, 
            number: str = None, 
            owner_id: int = None, 
            coordinates: str = None) -> ApiRetSData[int]:
        """Описание: Добавление объекта

            Обязательные параметры:
                type - Тип объекта
            Дополнительные параметры:
                city_id - ID населенного пункта размещения объекта
                custom_icon_id - ID индивидуального значка на карте
                comment - заметки
                date_add - дата добавления
                entrance - номер подъезда
                house_id - ID дома размещения объекта
                inventory_number - инв.номер объекта
                is_planned - Флаг - объект только запланирован
                level - номер этажа
                level_id - ID этажа/уровня (из структуры здания)
                location - размещение объекта (текстовое)
                node_parent_id - ID родительского объекта
                number - номер объекта
                owner_id - ID собственника
                coordinates - координаты в текстовом виде через запятую (пример: 47.839628,35.140553)
        """
        ...

    @api_method(bool)
    def add_mark(self, *, node_id: int, mark_id: int) -> ApiRetBool:
        """Добавление метки

            Обязательные параметры:
                node_id - id объекта
                mark_id - id метки
        """
        ...

    @api_method(bool)
    def change_custom_icon(self, *, id: int, custom_icon_id: int) -> ApiRetBool:
        """Изменение собственного значка на карте

            Обязательные параметры:
                id - id объекта
                custom_icon_id - id значка
        """
        ...

    @api_method(bool)
    def delete(self, *, id: int) -> ApiRetBool:
        """Удаление сооружения связи

            Обязательные параметры:
                id - id объекта
        """
        ...

    @api_method(bool)
    def delete_mark(self, *, node_id: int, mark_id: int) -> ApiRetBool:
        """Снятие метки

            Обязательные параметры:
                node_id - id объекта
                mark_id - id метки
        """
        ...
    
    @api_method(bool)
    def edit(self, *, 
             id: int, 
             city_id: int = None, 
             custom_icon_id: int = None, 
             comment: str = None, 
             coordinates: str = None, 
             date_add: str = None, 
             entrance: int = None, 
             house_id: int = None, 
             inventory_number: str = None, 
             is_planned: vFlag = None, 
             level: str = None, 
             level_id: int = None, 
             location: str = None, 
             node_parent_id: int = None, 
             number: str = None, 
             owner_id: int = None) -> ApiRetBool:
        """Редактирование объекта

            Обязательные параметры:
                id - ID объекта
            Необязательные параметры:
                city_id - ID населенного пункта размещения объекта
                custom_icon_id - ID индивидуального значка на карте
                comment - заметки
                coordinates - координаты в текстовом виде через запятую (пример: 47.839628,35.140553)
                date_add - дата добавления
                entrance - номер подъезда
                house_id - ID дома размещения объекта
                inventory_number - инв.номер объекта
                is_planned - Флаг - объект только запланирован
                level - номер этажа
                level_id - ID этажа/уровня (из структуры здания)
                location - размещение объекта (текстовое)
                node_parent_id - ID родительского объекта
                number - номер объекта
                owner_id - ID собственника
        """
        ...

    @smart_model
    class Get(BaseModel):
        id: int
        address_id: int
        date_add: vStr
        entrance: int
        level: int
        level_id: int
        parent_id: int
        is_planned: int
        location: vStr
        comment: vStr | None
        type: int
        custom_icon_id: int
        number: vStr
        coordinates: GeoPoint

    @api_method(Get)
    def get(self, *, address_id: int = None, entrance_number: int = None, id: int | str = None, mark_id: int = None, object_type: int | In_type_id = None, parent_id: int = None) -> ApiRetSData[Get]:
        """Список объектов

            Обязательные параметры:
                нет
            Необязательные параметры:
                address_id - id адресной единицы (можно через запятую)
                entrance_number - номер подъезда
                id - id объектов (можно через запятую)
                mark_id - id метки
                object_type - тип объекта
                parent_id - id родительского объекта (можно через запятую)
        """
        ...
    
    @smart_model
    class Get_icon_list(BaseModel):
        id: int
        name: vStr

    @api_method(Get_icon_list)
    def get_icon_list(self, *, id: int | str = None) -> ApiRetSData[Get_icon_list]:
        """Список собственных значков для объектов

            Необязательные параметры:
                id - перечень ID объектов (через запятую)
        """
        ...
    
    @api_method(int)
    def get_id(self, *, data_type: Literal['comment', 'number'] | str, data_value: str, is_entry: vFlag = None, type_id: int | In_type_id = None) -> ApiRetSData[int]:
        """Получение ID объекта по входящим данным

            Обязательные параметры:
                data_type - тип данных, которые проверяем (возможные значения: comment, number, additional_dataX (вместо X - id дополнительного поля))
                data_value - значение
            Необязательные параметры:
                is_entry - флаг - проверять ли в т.ч. совпадение по части вхождения в строку
                type_id - тип объекта
        """
        ...
    
    @smart_model
    class Get_id_by_coord(BaseModel):
        id: int
        lat: float
        lon: float
        distance: int

    @api_method(Get_id_by_coord)
    def get_id_by_coord(self, *, lat: float, lon: float, type: int | In_type_id = None, range: int = None) -> ApiRetSData[Get_id_by_coord]:
        """Получение ID ближайшего объекта по указанным координатам

            Обязательные параметры:
                lat - широта
                lon - долгота
            Необязательные параметры:
                type - тип объекта
                range - радиус в метрах, в пределах которого отобразить объекты
        """
        ...

    @smart_model
    class Get_redevelopment_scheme(BaseModel):
        id: int
        name: vStr
        updated_at: int

    @api_method(Get_redevelopment_scheme)
    def get_redevelopment_scheme(self, *, id: int) -> ApiRetSData[Get_redevelopment_scheme]:
        """Список схем перепланировки для сооружения связи

            Обязательные параметры:
                id - id сооружения связи
        """
        ...

    @deprecated()
    def get_relation_customers(self, *, id: int):
        """Получение информации о зависимых абонентах

            Обязательные параметры:
                id - id сооружения связи
        """
        ...

    @api_method()
    def get_scheme(self, *, id: int):
        """Получение схемы коммутации

            Обязательные параметры:
                id - id сооружения связи
        """
        ...

    @smart_model
    class Get_type_list(BaseModel):
        id: int
        name: vStr
        order: int
        single_name: vStr
        is_layer_on_map: int
        is_can_parent: int
        is_commutation: int
        template: int
        z_position: int
        map_ico: vStr
        map_opation: int
        map_color: vStr
        map_stroke_color: vStr
        map_stroke_width: int
        map_ico_plan: vStr
        map_color_plan: vStr
        map_stroke_color_plan: vStr
        map_stroke_width_plan: int
        @smart_model
        class Employee_profile_rights(BaseModel):
            is_read: List[int]
            is_write: List[int]
        employee_profile_rights: Employee_profile_rights

        @staticmethod
        def preprocess_response(data: Any) -> Any:
            """
            Предобработчик с маппингом ключей.
            """
            KEY_MAPPING = {
                'z-position': 'z_position',
            }
            def transform_key(key: str) -> str:
                # Заменяем только те ключи, которые есть в маппинге
                return KEY_MAPPING.get(key, key)
            
            if isinstance(data, dict):
                return {
                    transform_key(key): Node.Get_type_list.preprocess_response(value)
                    for key, value in data.items()
                }
            elif isinstance(data, list):
                return [Node.Get_type_list.preprocess_response(item) for item in data]
            else:
                return data
    
    @api_method(Get_type_list, preprocessor=Get_type_list.preprocess_response)
    def get_type_list(self) -> ApiRetSData[Get_type_list]:
        """Получение список типов сооружения связи"""
        ...
from typing import List, Any, Literal
from enum import IntEnum
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method 

class Additional_data(BaseCategory):
    """Действие с дополнительными полями/данными"""

    class In_cat_id(IntEnum):
        """Дополнительные поля имеют категории (cat_id)"""
        cable_lines=2
        '''Кабельные линии'''
        radio=6
        '''Радиооборудование'''
        buildings=7
        '''Здания'''
        switch=8
        '''Коммутаторы'''
        mediaconverters=9
        '''Медиаконвертеры'''
        system_devices=10
        '''Системные устройства'''
        tariffs=12
        '''Тарифы (только для ручных биллингов)'''
        additional_services=13
        '''Дополнительные услуги (только для ручных биллингов)'''
        nodes=14
        '''Сооружения связи'''
        odf=15
        '''Кроссы/ODF'''
        vlan=16
        '''VLAN'''
        tasks=17
        '''Задания'''
        auto=18
        '''Автотранспорт'''
        advertising_camps=19
        '''Рекламные кампании'''
        custom_devices=20
        '''Произвольные устройства'''
        traders=21
        '''Поставщики'''
        splitters=23
        '''Делители/Уплотнители'''
        owners=24
        '''Собственники'''
        inventory=25
        '''ТМЦ'''
        cable_channels=26
        '''Кабельные каналы'''
        cable_traces=27
        '''Кабельные трассы (кабельных линий)'''
        customers=28
        '''Абоненты'''
        keys=29
        '''Ключи'''
        name_inventory=30
        '''Наименования ТМЦ'''
        addresses=40
        '''Адресные единицы'''
        storages=48
        '''Склады'''
        map_objects=102
        '''Объекты на карте'''
        employee=999
        '''Сотрудники'''

    class In_type_id(IntEnum):
        """
        Дополнительные поля имеют тип поля (type) 
        """
        text=1
        '''Текст'''
        number=2
        '''Число'''
        flag=3
        '''Флаг'''
        list_once=4
        '''Выбор из списка'''
        text_area=5
        '''Текстовое поле'''
        list_custom_once=6
        '''Выбор из списка (в т.ч. свой вариант)'''
        date=7
        '''Дата'''
        list_custom_multiply=8
        '''Выбор из списка (несколько значений)'''

    @smart_model
    class Get_list(BaseModel):
        id: int
        name: vStr
        position: int
        type: vStr
        is_required: int
        available_value: Any = None

    @api_method(Get_list)
    def get_list(self, *, section: In_cat_id | Literal['house','node','task','switch','inventory']) -> ApiRetSData[Get_list]: 
        """Получение списка полей

        Обязательные параметры:
            section - категория дополнительных полей [house|node|task|switch|inventory|...значения из In_cat_id...]
        """
        ...

    @api_method(int)
    def add_field(self, *, cat_id: In_cat_id, name: str, type: In_type_id = None, size: int = None, max_size: int = None, is_active: vFlag = None, position: int = None, is_require: vFlag = None) -> ApiRetSData[int]: 
        """Добавление дополнительного поля

        Обязательные параметры:
            cat_id - категория дополнительных полей
            name - наименование

        Необязательные параметры:
            type - тип поля
            size - размер поля
            max_size - максимальный размер поля
            is_active - флаг - поле включено
            position - позиция поля среди остальных
            is_require - флаг - обязательное к заполнению
        """
        ...

    @api_method(bool)
    def edit_field(self, *, cat_id: In_cat_id, id: int,  type: In_type_id = None, size: int = None, max_size: int = None, is_active: vFlag = None, position: int = None, is_require: vFlag = None, value_list: Any | List = None) -> ApiRetBool: 
        """Редактирование дополнительного поля 

        Обязательные параметры:
            cat_id - категория
            id - id поля

        Необязательные параметры:
            type - тип поля
            size - размер поля
            max_size - максимальный размер поля
            is_active - флаг - поле включено
            position - позиция поля среди остальных
            is_require - флаг - обязательное к заполнению
            value_list - возможные значения для типа поля "Выбор из списка" (разделитель - вертикальная черта "|")
        """
        params = locals()
        params.pop('self',None)
        if isinstance(value_list,list):
            params['value_list'] = "|".join(str(x) for x in value_list)
        return params

    @api_method(bool)
    def delete_field(self, *, cat_id: In_cat_id, id: int) -> ApiRetBool:
        """Удаление дополнительного поля (удаляется только если нет записей с этим доп.полем)

        Обязательные параметры:
            cat_id - категория
            id - id поля
        """
        ...

    @smart_model
    class Get_value(BaseModel):
        field_id: int
        object_id: int
        value: vStr

    @api_method(Get_value)
    def get_value(self, *, field_id: int, cat_id: In_cat_id = None, object_id: int = None, value: str = None) -> ApiRetSData[Get_value]: 
        """Получение значений полей

        Обязательные параметры:
            field_id - id поля
        
        Необязательные параметры:
            cat_id - категория
            object_id - id объекта (по которому значение поля)
            value - значение поля
        """
        ...

    @api_method(bool)
    def change_value(self, *, cat_id: In_cat_id, field_id: int, object_id: int, value: Any) -> ApiRetBool: 
        """Изменение значения доп.поля 

        В случае отсутствия такого доп.поля у объекта - оно будет создано.

        Обязательные параметры:
            cat_id - категория
            field_id - id дополнительного поля
            object_id - id объекта
            value - значение
        """
        ...

    @smart_model
    class In_change_value_mass:
        object_id: int
        value: vStr

    @api_method(bool)
    def change_value_mass(self, *, cat_id: In_cat_id, field_id: int, data: List[In_change_value_mass] | dict) -> ApiRetBool:
        """Массовое изменение значения доп.поля для множества объектов

        В случае отсутствия такого доп.поля у объекта - оно будет создано.

        Обязательные параметры:
            cat_id - категория (см.выше справочник)
            field_id - id дополнительного поля
            data[] - id объекта|значение
            data[] - id объекта|значение
            data[] - id объекта|значение
            ...

            Пример параметра data:
                data = {
                    'data[333]':'значение для объекта с id=333',
                    'data[123]':'значение для объекта с id=123',
                    ...
                    }
            или
                data = [
                    Additional_data.In_change_value_mass(object_id=333,value='значение для объекта с id=333'),
                    Additional_data.In_change_value_mass(object_id=123,value='значение для объекта с id=123'), 
                    ...
                    ]
        """
        v_data:dict = {}
        if isinstance(data,list):
            for v in data: v_data[f"data[{v.object_id}]"]=v.value
        elif isinstance(data,dict):
            for k,v in data.items():
                try: v_data[f"data[{int(k)}]"]=v
                except: v_data[k]=v
        elif isinstance(data,str):
            v_data = {data}
        return {'cat_id':cat_id,'field_id':field_id} | v_data
from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method

class Inventory(BaseCategory):
    """Действия с ТМЦ и складом"""

    @api_method(int)
    def add_inventory(self, *, 
            inventory_catalog_id: int, 
            trader_id: int, 
            storage_id: int, 
            amount: int = None, 
            cost: float = None, 
            comment: str = None, 
            sn: str = None, 
            barcode: str = None, 
            inventory_number: str = None, 
            document_number: str = None, 
            additional_data_ip: str = None, 
            additional_data_mac: str = None, 
            is_check_serial_number: vFlag = None)-> ApiRetSData[int]:
        """Приход ТМЦ

            Обязательные параметры:
                inventory_catalog_id - ID наименования ТМЦ
                trader_id - ID поставщика
                storage_id - ID склада, на который выполнить приход
            Необязательные параметры:
                amount - количество (по-умолчанию: 1)
                cost - стоимость (по-умолчанию: 0)
                comment - заметки
                sn - серийный номер
                barcode - штрихкод
                inventory_number - инвентарный номер
                document_number - номер документа прихода
                document_date - дата документа прихода
                additional_data_ip - IP-адрес (для ТМЦ-оборудования)
                additional_data_mac - MAC-адрес (для ТМЦ-оборудования)
                is_check_serial_number - проверять на совпадение серийный номер с уже существующими ТМЦ
        """
        ...

    @api_method(int)
    def add_inventory_assortment(self, *, section_id: int, name: str, unit_name: str = None, is_require_serial_number: vFlag = None, is_require_mac: vFlag = None) -> ApiRetSData[int]:
        """Добавление наименования ТМЦ

            Обязательные параметры:
                section_id - id секции каталога товаров
                name - наименование
            Необязательные параметры:
                unit_name - единица измерения
                is_require_serial_number - флаг - требовать ввода серийного номера при приходе ТМЦ
                is_require_mac - флаг - требовать ввода MAC-адреса при приходе ТМЦ
        """
        ...

    @api_method(int)
    def add_inventory_section(self, *, name: str, typer: int = None, parent_id: int = None, is_show_on_map: vFlag = None) -> ApiRetSData[int]:
        """Добавление раздела каталога товаров

            Обязательные параметры:
                name - наименование
            Необязательные параметры:
                typer - id спецпризнака (по-умолчанию: 0)
                parent_id - id родительского раздела каталога
                is_show_on_map - флаг - отображать ли объекты этого раздела слоем на карте
        """
        ...

    @api_method(bool)
    def add_inventory_to_operation(self, *, operation_id: int, inventory_id: int, amount: int = None) -> ApiRetBool:
        """Добавление ТМЦ в операцию

            Обязательные параметры:
                operation_id - id операции
                inventory_id - id ТМЦ (оно должно находится на счёте-источнике операции)
            Необязательные параметры:
                amount - количество ТМЦ (если более 1 единицы в ТМЦ)
        """
        ...

    @api_method(bool)
    def change_arg_ip(self, *, id: int, value: str) -> ApiRetBool:
        """Изменение IP-адреса в параметрах ТМЦ

            Обязательные параметры:
                id - ID ТМЦ
                value - IP-адрес
        """
        ...

    @api_method(bool)
    def change_arg_mac(self, *, id: int, value: str) -> ApiRetBool:
        """Изменение MAC-адреса в параметрах ТМЦ

            Обязательные параметры:
                id - ID ТМЦ
                value - IP-адрес
        """
        ...

    @api_method(bool)
    def change_comment(self, *, id: int, value: str) -> ApiRetBool:
        """Изменение заметки ТМЦ

            Обязательные параметры:
                id - ID ТМЦ
                value - заметка
        """
        ...

    @api_method(bool)
    def change_price(self, *, id: int, value: str) -> ApiRetBool:
        """Изменение стоимости ТМЦ

            Обязательные параметры:
                id - ID ТМЦ
                value - заметка
        """
        ...

    @api_method(bool)
    def change_serial_number(self, *, id: int, value: str) -> ApiRetBool:
        """Изменение серийного номера у ТМЦ

            Обязательные параметры:
                id - ID ТМЦ
                value - заметка
        """
        ...
    
    @api_method(bool)
    def delete_inventory(self, *, id: int) -> ApiRetBool:
        """Удаление СПИСАННОГО ТМЦ

            Обязательные параметры:
                id - id ТМЦ (ТМЦ обязательно должно быть списанным)
        """
        ...
    
    @api_method(bool)
    def edit_inventory_assortment(self, *, id: int, name: str = None, unit_name: str = None, is_require_serial_number: vFlag = None, is_require_mac: vFlag = None) -> ApiRetBool:
        """Редактирование наименования ТМЦ

            Обязательные параметры:
                id - id наименования
            Необязательные параметры:
                name - наименование
                unit_name - единица измерения
                is_require_serial_number - флаг - требовать ввода серийного номера при приходе ТМЦ
                is_require_mac - флаг - требовать ввода MAC-адреса при приходе ТМЦ
        """
        ...

    @api_method(bool)
    def edit_inventory_section(self, *, id: int, name: str = None, parent_id: int = None, is_show_on_map: vFlag = None) -> ApiRetBool:
        """Редактирование раздела каталога товаров

            Обязательные параметры:
                id - id раздела каталога
            Необязательные параметры:
                name - наименование
                parent_id - id родительского раздела каталога
                is_show_on_map - флаг - отображать ли объекты этого раздела слоем на карте
        """
        ...

    @smart_model
    class Get_inventory(BaseModel):
        id: int
        name: vStr
        catalog_id: int
        section_catalog_id: int
        section_name: vStr
        measure: vStr
        seller_id: int
        amount: int
        comment: vStr
        cost: int
        serial_number: vStr
        inventory_number: vStr
        barcode: vStr
        location_type_id: int
        location_subaccount: int
        location_object_id: int

    @api_method(Get_inventory)
    def get_inventory(self, *, id: int) -> ApiRetSData[Get_inventory]:
        """Получение информации о ТМЦ

            Обязательные параметры:
                id - ID ТМЦ
        """
        ...
    
    @smart_model
    class Get_inventory_amount(BaseModel):
        id: int
        document_number: vStr
        document_date: vStr
        location_type: vStr
        catalog_id: int
        amount: int
        cost: int
        acount: vStr
        inventory_type_id: int
        inventory_number: int
        serial_number: vStr
        object_id: int

    @api_method(Get_inventory_amount)
    def get_inventory_amount(self, *, 
            location: Literal['storage','employee','customer','node','task'], 
            object_id: int | str = None, 
            inventory_type_id: int | str = None, 
            section_id: int | str = None) -> ApiRetSData[Get_inventory_amount]:
        """Получение списка ТМЦ

            Обязательные параметры:
                location - категория учёта [storage|employee|customer|node|task]
            Необязательные параметры:
                object_id - id объекта учёта (можно через запятую)
                inventory_type_id - id наименования ТМЦ (можно через запятую)
                section_id - id секции каталога товаров (можно через запятую)
        """
        ...

    @smart_model
    class Get_inventory_catalog(BaseModel):
        id: int
        name: vStr
        inventory_section_catalog_id: int
        base_equipment_uuid: int
        unit_name: vStr

    @api_method(Get_inventory_catalog)
    def get_inventory_catalog(self, *, id: int | str = None, section_id: int | str = None) -> ApiRetSData[Get_inventory_catalog]:
        """Получение списка разделов каталога

            Необязательные параметры
                id - ID наименования ТМЦ (можно через запятую)
                section_id - ID типа ТМЦ (можно через запятую)
        """
        ...

    @api_method(int)
    def get_inventory_catalog_id_by_name(self, *, name: str) -> ApiRetSData[int]:
        """Получение ID наименования ТМЦ по его названию

            Обязательные параметры:
                name - наименование
        """
        ...

    @api_method(int)
    def get_inventory_id(self, *, data_typer: Literal['barcode','inventory_number','serial_number','mac','ip'], data_value: int | str, is_all_data: vFlag = None) -> ApiRetSData[int]:
        """Получение ID ТМЦ по входящим данным

            Обязательные параметры:
                data_typer - тип данных, которые проверяем (возможные значения: barcode, inventory_number, serial_number, mac, ip)
                data_value - значение
            Необязательные параметры:
                is_all_data - флаг - возвращать все найденные ТМЦ, а не только одно
        """
        ...

    @smart_model
    class Get_inventory_section_catalog(BaseModel):
        id: int
        name: vStr
        type_id: int
        parent_id: int
    
    @api_method(Get_inventory_section_catalog)
    def get_inventory_section_catalog(self) -> ApiRetSData[Get_inventory_section_catalog]:
        """Получение наименований каталога ТМЦ"""
        ...
    
    @smart_model
    class Get_inventory_storage(BaseModel):
        id: int
        name: vStr
        description: vStr | None
        employee_access: List[int]
        employee_access_read: List[int]

    @api_method(Get_inventory_storage)
    def get_inventory_storage(self) -> ApiRetSData[Get_inventory_storage]:
        """Получение списка складов"""
        ...
    
    @smart_model
    class Get_operation(BaseModel):
        id: int
        date: vStr
        employee_id: int
        comment: vStr
        src_account_type: int
        src_account_sub: int
        src_account_object_id: int
        dst_account_type: int
        dst_account_sub: int
        dst_account_object_id: int
        inventory_ids: List[int]

    @overload
    def get_operation(self, *,id: int | str, src_account: str = None, dst_account: str = None, date_start: str = None, date_finish: str = None, inventory_id: int = None, employee_id: int = None, inventory_assortment_id: int = None) -> ApiRetSData[Get_operation]: ...
    @overload
    def get_operation(self, *, src_account: str, id: int | str = None, dst_account: str = None, date_start: str = None, date_finish: str = None, inventory_id: int = None, employee_id: int = None, inventory_assortment_id: int = None) -> ApiRetSData[Get_operation]: ...
    @overload
    def get_operation(self, *, dst_account: str, id: int | str = None, src_account: str = None, date_start: str = None, date_finish: str = None, inventory_id: int = None, employee_id: int = None, inventory_assortment_id: int = None) -> ApiRetSData[Get_operation]: ...
    @overload
    def get_operation(self, *, date_start: str, id: int | str = None, src_account: str = None, dst_account: str = None, date_finish: str = None, inventory_id: int = None, employee_id: int = None, inventory_assortment_id: int = None) -> ApiRetSData[Get_operation]: ...
    @overload
    def get_operation(self, *, date_finish: str, id: int | str = None, src_account: str = None, dst_account: str = None, date_start: str = None, inventory_id: int = None, employee_id: int = None, inventory_assortment_id: int = None) -> ApiRetSData[Get_operation]: ...
    @overload
    def get_operation(self, *, inventory_id: int, id: int | str = None, src_account: str = None, dst_account: str = None, date_start: str = None, date_finish: str = None, employee_id: int = None, inventory_assortment_id: int = None) -> ApiRetSData[Get_operation]: ...
    @overload
    def get_operation(self, *, employee_id: int, id: int | str = None, src_account: str = None, dst_account: str = None, date_start: str = None, date_finish: str = None, inventory_id: int = None, inventory_assortment_id: int = None) -> ApiRetSData[Get_operation]: ...
    @overload
    def get_operation(self, *, inventory_assortment_id: int, id: int | str = None, src_account: str = None, dst_account: str = None, date_start: str = None, date_finish: str = None, inventory_id: int = None, employee_id: int = None) -> ApiRetSData[Get_operation]: ...

    @api_method(Get_operation)
    def get_operation(self, *,
            id: int | str = None, 
            src_account: str = None, 
            dst_account: str = None, 
            date_start: str = None, 
            date_finish: str = None, 
            inventory_id: int = None, 
            employee_id: int = None, 
            inventory_assortment_id: int = None) -> ApiRetSData[Get_operation]:
        """Получение информации по операциям

            Необязательные параметры (но должно быть хоть что-то):
                id - ID операции (можно несколько значений через запятую)
                src_account - счёт-кредита (откуда)
                dst_account - счёт-дебита (куда)
                date_start - дата начала периода
                date_finish - дата окончания периода
                inventory_id - id ТМЦ
                employee_id - id сотрудника - инициатора операции
                inventory_assortment_id - id наименования ТМЦ
        """
        ...
    
    @api_method(int)
    def split_inventory(self, *, id: int, amount: int) -> ApiRetSData[int]:
        """Разделение ТМЦ

            Обязательные параметры:
                id - id ТМЦ
                amount - требуемое количество
        """
        ...
    
    @api_method(int)
    def transfer_inventory(self, *, inventory_id: int, dst_account: str, comment: str = None, employee_id: int = None) -> ApiRetSData[int]:
        """Перемещение ТМЦ

            Обязательные параметры:
                inventory_id - ID ТМЦ
                dst_account - Счет-получатель
            Необязательные параметры
                comment - заметки
                employee_id - ID сотрудника - автора операции
        """
        ...
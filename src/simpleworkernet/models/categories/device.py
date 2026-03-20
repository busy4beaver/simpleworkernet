from typing import overload, List, Any, Literal, Annotated
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method 

class Device(BaseCategory):
    """Оборудование"""

    @api_method(bool)
    def add_mark(self, *, object_id: int, mark_id: int) -> ApiRetBool:
        """Добавление метки

            Обязательные параметры:
                object_id - id устройства
                mark_id - ID метки
        """
        ...
    
    @smart_model
    class Get_connected_ont_information(BaseModel):
        date_info: vStr
        mac: vStr
        sn: vStr
        olt_device_id: int
        olt_pon_port: vStr
        olt_iface_number: int | None
        iface_name: vStr
        iface_state: int
        vendor: vStr
        model: vStr
        firmware: vStr
        hardware: vStr
        distance: int
        description: vStr
        level_onu_rx: float
        level_onu_tx: float
        level_olt_rx: float
        is_unknown: int
    
    @api_method(Get_connected_ont_information)
    def get_connected_ont_information(self, *, device_id: int | str = None, level_onu_rx_min: float = None, level_onu_rx_max: float = None) -> ApiRetSData[Get_connected_ont_information]:
        """Получение информации о подключенных ONU к OLT (сохраненная информация из базы. Прямой опрос не выполняется)

            Необязательные параметры:
                device_id - ID OLT (можно через запятую)
                level_onu_rx_min - минимальный входящий уровень сигнала на ONU (выбрать записи с уровнем менее чем...)
                level_onu_rx_max - максимальный входящий уровень сигнала на ONU (выбрать записи с уровнем выше чем...)
        """
        ...
    
    @smart_model
    class Get_current_ont_data(BaseModel):
        onu_rx_level: float
        unixtime: int
        date: vStr
        is_actual_info: int
    
    @api_method(Get_current_ont_data)
    def get_current_ont_data(self, *, id: int) -> ApiRetSData[Get_current_ont_data]:
        """Получение некоторой текущей информации по ONU с OLT

            Обязательные параметры:
                id - id устройства (ONU)
        """
        ...
    
    class In_device_data_typer(StrEnum):
        ip = 'ip'
        mac = 'mac'
        inventory_number = 'inventory_number'
        serial_number = 'serial_number'
        additional_field_ = additional_field
    
    @api_method(int)
    def get_device_id(self, *, data_typer: Literal['ip', 'mac', 'inventory_number', 'serial_number'] | In_device_data_typer | Annotated[str, "pattern: additional_field_\\d+"], data_value: Any) -> ApiRetSData[int]:
        """Получение ID устройства по входящим данным

            Обязательные параметры:
                data_typer - тип данных, которые проверяем (возможные значения: ip, mac, inventory_number, serial_number, additional_field_XXX)
                data_value - значение
        """
        ...
    
    @smart_model
    class Get_data(BaseModel):
        @smart_model
        class Ifaces(BaseModel):
            ifIndex:int
            ifType: int
            ifTypeText: vStr
            ifName: vStr
            ifNumber: int
            ifDescr: vStr
            ifSpeed: int
            caption: vStr
            isChecked: int
            position:int
        id: int
        name: vStr
        inventory_section_type_id: int
        entrance: int | None
        ip: vStr
        host: vStr
        mac: vStr
        comment: vStr
        date_add: vStr
        inventory_id: int
        location: vStr
        uplink_iface: Any
        dnlink_iface: Any
        node_id: int
        customer_id: int | None
        interfaces: int
        activity_time: vStr
        uplink_iface_array: Any
        dnlink_iface_array: Any
        is_online: int
        mark: List[int]
        ifaces: List[Ifaces]
        snmp_proto: int
        snmp_community: vStr
        snmp_port: int
        telnet_login: vStr
        telnet_pass: vStr
        additional_data: Any = None

    @api_method(Get_data)
    def get_data(self, *, 
            object_type: Literal['switch','onu','olt','radio','all'], 
            customer_id: int = None, 
            dataset: str = None, 
            is_online: int = None, 
            is_hide_ifaces_data: vFlag = None, 
            is_hide_access_data: vFlag = None, 
            is_with_ip: vFlag = None, 
            node_id: int = None, 
            object_id: int | str = None) -> ApiRetSData[Get_data]:
        """Получение информации об устройствах

            Обязательные параметры:
                object_type - Тип устройства [switch|onu|olt|radio|all]
            Необязательные параметры:
                customer_id - id абонента (можно через запятую)
                dataset - список полей, которые выводить в выдаче (через запятую)
                is_online - флаг - выбирать только активные устройства (1 - активные, -1 - неактивные)
                is_hide_ifaces_data - флаг - скрывать развёрнутую информацию по интерфейсам оборудования
                is_hide_access_data - флаг - скрывать информацию по параметрам доступа к оборудованию
                is_with_ip - флаг - только с IP-адресами
                node_id - id сооружения связи (можно через запятую)
                object_id - id объекта для выборки
        """
        ...

    @smart_model
    class Get_iface_info(BaseModel):
        @smart_model
        class Iface(BaseModel):
            @smart_model
            class Raw(BaseModel):
                if_index:int
                name: vStr
                status_admin: bool
                status_oper: bool
                type: vStr
                port_speed_mbit: int
                sort_key: int
                description: vStr
            ifIndex: int
            ifName: vStr
            ifNumber: int
            ifDescr: vStr
            ifHighSpeed: int
            ifAdminStatus: bool
            ifOperStatus: bool
            baseType: str
            position: int
            count: int
            raw: Raw
            isPonIface: int
            ponIfaceNumber: int
        time: int
        iface: List[Iface]
    
    @api_method(Get_iface_info)
    def get_iface_info(self, *, id: int) -> ApiRetSData[Get_iface_info]:
        """Получение текущей информации по интерфейсам (напрямую с устройства)

            Обязательные параметры:
                id - id устройства
        """
        ...
    
    @smart_model
    class Get_iface_mac(BaseModel):
        ifaceName: vStr
        ifacePort: int
        ifaceStack: int
        macCount: int

    @api_method(Get_iface_mac)
    def get_iface_mac(self, *, object_id: int) -> ApiRetSData[Get_iface_mac]:
        """Список интерфейсов с MAC-адресами на устройстве

            Обязательные параметры:
                object_id - id устройства для выборки
        """
        ...
    
    @smart_model
    class Get_mac_list(BaseModel):
        object_id: int
        mac: vStr
        port: vStr
        vlan_id: int
        date_first: vStr
        date_last: vStr
    
    @api_method(Get_mac_list)
    def get_mac_list(self, *, interface_list: int | str = None, object_id: int = None) -> ApiRetSData[Get_mac_list]:
        """Получение списка MAC-адресов, которые были найдены на устройстве

            Обязательные параметры:
                нет
            Необязательные параметры:
                interface_list - Номер интерфейса по которому выводить список (можно через запятую)
                object_id - id устройства для выборки
        """
        ...
    
    @smart_model
    class Get_ont_data(BaseModel):
        id: int
        device_id: int
        mac: vStr
        sn: vStr
        sn_second: vStr
        date_add: vStr
        iface_olt_number: vStr
        iface_number: int | None
        iface_name: vStr
        iface_state: int
        vendor: vStr
        model: vStr
        firmware: vStr
        hardware: vStr
        distance: int
        description: vStr
        reason_offline: vStr
        is_unknown: int
        level_onu_rx: float
        level_onu_tx: float
        level_olt_rx: float
        is_level_bad: int
        level_min: float
        level_max: float
        onu_device_id: int

    @overload
    def get_ont_data(self, *, device_id: int) -> ApiRetSData[Get_ont_data]: ...
    @overload
    def get_ont_data(self, *, id: int | str) -> ApiRetSData[Get_ont_data]: ...

    @api_method(Get_ont_data)
    def get_ont_data(self, device_id = None, id = None) -> ApiRetSData[Get_ont_data]:
        """Получение последней информации по ONU

            Обязательные параметры:
                id - MAC-адрес или серийный номер (id)
                или
                device_id - id устройства (ONU)
        """
        ...
    
    @smart_model
    class Get_pon_level_history(BaseModel):
        device_id: int
        pon_iface: vStr
        date_from: vStr
        date_to: vStr
        level: float

    @overload
    def get_pon_level_history(self, *, onu_name: str, limit: int = None, order_by: str = None, is_desc: vFlag = None) -> ApiRetSData[Get_pon_level_history]: ...
    @overload
    def get_pon_level_history(self, *, device_id: int, limit: int = None, order_by: str = None, is_desc: vFlag = None) -> ApiRetSData[Get_pon_level_history]: ...
    @overload
    def get_pon_level_history(self, *, onu_device_id: int, limit: int = None, order_by: str = None, is_desc: vFlag = None) -> ApiRetSData[Get_pon_level_history]: ...
    
    @api_method(Get_pon_level_history)
    def get_pon_level_history(self, *, onu_name=None, device_id=None, onu_device_id=None, limit=None, order_by=None, is_desc=None) -> ApiRetSData[Get_pon_level_history]:
        """Получение истории PON-уровней сигналов по ONU

            Обязательные параметры:
                onu_name - MAC-адрес или серийный номер ONU (без разделителей)
                или
                device_id - id устройства (OLT)
                или
                onu_device_id - id устройства (ONU)
            Необязательные параметры:
                limit - ограничение списка выводимых данных
                order_by - поле сортировки данных
                is_desc - флаг - сортировка в обратном порядке
        """
        ...

    # @api_method()
    # def get_relation_customers(self, *, device_id: int , port_start: int = None, port_finish: int = None):
    #     """Получение информации о зависимых абонентах

    #         Обязательные параметры:
    #             device_id - id устройства
    #         Необязательные параметры:
    #             port_start - начальный номер порта
    #             port_finish - конечный номер порта
    #     """
    #     ...
    
    @api_method(bool)
    def delete_mark(self, *, object_id: int, mark_id: int) -> ApiRetBool:
        """Снятие метки

            Обязательные параметры:
                object_type - Тип устройства [switch] (до версии 3.19beta1)
                object_id - id устройства
                mark_id - ID метки
        """
        ...
    
    @api_method()
    def read_fdb(self, *, device_id: int):
        """Чтение FDB-таблицы с устройства (может выполняться продолжительное время)

            Обязательные параметры:
                device_id - id устройства
        """
        ...
    
    @api_method(bool)
    def set_data(self, *, object_id: int, param: Literal['ip','mac','comment','iface_count','downlink_port','uplink_port','date_last_activity'], value: Any) -> ApiRetBool:
        """Изменение информации об устройстве

            Обязательные параметры:
                object_type - Тип устройства [switch] (до версии 3.19beta1)
                object_id - id устройства
                param - тип параметра для изменения [ip|mac|comment|iface_count|downlink_port|uplink_port|date_last_activity]
                value - данные (может быть пустым)
        """
        ...
    
    @api_method(bool)
    def set_iface_state(self, *, device_id: int, iface: int, state: vFlag) -> ApiRetBool:
        """Изменение состояния интерфейса на устройстве

            Обязательные параметры:
                device_id - id устройства
                iface - номер интерфейса
                state - состояние [1|0]
        """
        ...
    
    @api_method()
    def find_mac(self, *, mac: str) -> Any:
        """Поиск MAC-адреса в истории опроса по оборудованию

            Обязательные параметры:
                mac - MAC-адрес (верхний регистр без разделителей)
        """
        ...
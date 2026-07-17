from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model, CollapsedField
from ..primitives import vStr, vFlag, GeoPoint, additional_data, additional_field
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method
from ...smartdata.metadata import SegmentType

class Module(BaseCategory):
    """Внешние запросы от модулей"""

    @smart_model
    class Get_api_information(BaseModel):
        version: vStr
        date: vStr

    @api_method(Get_api_information)
    def get_api_information(self) -> ApiRetSData[Get_api_information]:
        """Используемая версия API"""
        ...

    @api_method()
    def get_city_district_list(self): 
        """Адреса. Районы в населённых пунктах"""
        ...

    @smart_model
    class Get_city_list(BaseModel):
        id: int
        name: vStr

    @api_method(BaseModel)
    def get_city_list(self) -> ApiRetSData[Get_city_list]: 
        """Адреса. Населённые пункты"""
        ...

    @smart_model
    class Get_connect_list(BaseModel):
        @smart_model
        class Item(BaseModel):
            type: vStr
            id: int
            direction: int
            interface: int
        customer: List[Item]
        switch: List[Item]
        other: List[Item]

    @api_method(Get_connect_list)
    def get_connect_list(self, *, object_type: Literal['customer','switch','other'] = None, object_id: int | str = None) -> ApiRetSData[Get_connect_list]: 
        """Коммутация объектов (абонентов/оборудования) между собой"""
        ...

    @smart_model
    class Get_device_list(BaseModel):
        id: int
        type_id: vStr
        model_id: int
        ip: vStr
        mac: vStr
        house_id: int | None
        node_id: int | None
        entrance: int
        location: vStr
        comment: vStr
        geo: vStr
        date_activity: vStr
        date_create: vStr
        telnet_port: int | None
        snmp_version: vStr
        snmp_port: int
        snmp_read_community: vStr
        software_version: vStr

    @api_method(Get_device_list)
    def get_device_list(self, *, device_type: Literal['switch','radio','other'] = None) -> ApiRetSData[Get_device_list]: 
        """Оборудование. Список устройств"""
        ...

    @smart_model
    class Get_device_model(BaseModel):
        id: int
        name: vStr
        type_id: vStr

    @api_method(Get_device_model)
    def get_device_model(self, *, device_type: Literal['switch','radio','other'] = None) -> ApiRetSData[Get_device_model]: 
        """Оборудование. Модели устройств"""
        ...

    @api_method()
    def get_device_type(self): 
        """Оборудование. Типы устройств"""
        ...

    @smart_model
    class Get_house_list(BaseModel):
        id: int
        number: vStr
        street_id: int
        parent_id: int
        parent_ids: List[int]
        floor: int
        entrance: int
        apartment: vStr
        full_name: vStr

    @api_method(Get_house_list)
    def get_house_list(self) -> ApiRetSData[Get_house_list]: 
        """Адреса. Дома"""
        ...

    @smart_model
    class Get_services_list(BaseModel):
        id: int
        name: vStr
        billing_id: int
        is_enable: int
        cost: int

    @api_method(Get_services_list)
    def get_services_list(self) -> ApiRetSData[Get_services_list]: 
        """Услуги/дополнительные услуги"""
        ...
    
    @smart_model
    class Get_street_list(BaseModel):
        id: int
        name: vStr
        city_id: int
        parent_id: int
        parent_ids: List[int]
        full_name: vStr

    @api_method(Get_street_list)
    def get_street_list(self) -> ApiRetSData[Get_street_list]: 
        """Адреса. Улицы"""
        ...
    
    # @api_method()
    # def get_supported_change_user_data_list(self): 
    #     """Поддерживаемые методы для изменения данных абонента через API"""
    #     ...

    # @api_method()
    # def get_supported_change_user_state(self, *, customer_id: int = None): 
    #     """Поддерживаемые статусы для изменения статуса работы абонента через API"""
    #     ...

    # @api_method()
    # def get_supported_change_user_tariff(self, *, customer_id: int = None): 
    #     """Поддерживаемые тарифные планы для изменения тарифа у абонента через API"""
    #     ...

    @api_method()
    def get_supported_method_list(self): 
        """Поддерживаемые методы API"""
        ...

    @smart_model
    class Get_system_information(BaseModel):
        @smart_model
        class Erp(BaseModel):
            name: vStr
            version: vStr
        date: vStr
        os: vStr
        erp: Erp

    @api_method(Get_system_information)
    def get_system_information(self) -> ApiRetSData[Get_system_information]: 
        """Системная информация"""
        ...

    @smart_model
    class Get_tariff_list(BaseModel):
        @smart_model
        class Speed(BaseModel):
            up: int
            down: int
        id: int
        name: vStr
        payment: int | float | None
        payment_full: int | float | None
        payment_interval: int
        speed: Speed
        traffic: int
        service_type: int
        additional_comment: vStr
        is_in_billing: int
        erp_id: int

    @api_method(Get_tariff_list)
    def get_tariff_list(self) -> ApiRetSData[Get_tariff_list]: 
        """Тарифные планы. Стандартные тарифы"""
        ...

    @smart_model
    class Get_user_additional_data_type_list(BaseModel):
        id: int
        name: vStr

    @api_method(Get_user_additional_data_type_list)
    def get_user_additional_data_type_list(self) -> ApiRetSData[Get_user_additional_data_type_list]: 
        """Типы дополнительных полей по абонентам"""
        ...
    
    @api_method()
    def get_user_group_list(self): 
        """Группы абонентов"""
        ...

    @smart_model
    class Get_user_history(BaseModel):
        date: vStr
        type: vStr
        name: vStr
        data: vStr
        comment: vStr

    @api_method(Get_user_history)
    def get_user_history(self, *, customer_id: int) -> ApiRetSData[Get_user_history]: 
        """История по абоненту"""
        ...

    @smart_model
    class Get_user_list(BaseModel):
        @smart_model
        class Agreement(BaseModel):
            number: vStr
            date: vStr
        @smart_model
        class Traffic(BaseModel):
            up: int
            down: int
            period = CollapsedField(type_filter=SegmentType.FLD)
        @smart_model
        class Phone(BaseModel):
            number: vStr
            flag_main: int = None
        @smart_model
        class Address(BaseModel):
            type: vStr
            house_id: int
        @smart_model
        class Tariff(BaseModel):
            id: int
            container_name = CollapsedField(type_filter=SegmentType.FLD)
        @smart_model
        class Service(BaseModel):
            cost: vStr
            comment: vStr
            date_add: vStr
        @smart_model
        class Ip_mac(BaseModel):
            ip: vStr
            mac: vStr
        @smart_model
        class Billing(BaseModel):
            id: int
            uuid: vStr
        @smart_model
        class Additional_data(BaseModel):
            id: int
            value: vStr
        id: int
        login: vStr
        full_name: vStr
        flag_corporate: int
        balance: int | float
        state_id: int
        agreement: List[Agreement]
        traffic: List[Traffic]
        date_create: vStr
        date_connect: vStr
        date_positive_balance: vStr
        is_disable: int
        is_potential: int
        phone: List[Phone]
        address: List[Address]
        is_in_billing: int
        crc_billing: Any
        date_activity_inet: vStr
        date_activity: vStr
        billing_id: int
        tariff: List[Tariff]
        service: List[Service]
        comment: vStr
        ip_mac: List[Ip_mac]
        comment2: vStr
        billing: Billing = None
        manager_id: int = None
        additional_customer_data: List[Additional_data] = None
        additional_data: List[Additional_data]  = None
        group: Any = None
        @smart_model
        class Mark(BaseModel):
            id: int
        mark: List[Mark] = None
        @smart_model
        class Tag(BaseModel):
            id: int
            date_add: vStr
        tag: List[Tag] = None
        @smart_model
        class Email(BaseModel):
            address: vStr
            flag_main: int
        email: List[Email] = None
        credit: Any = None
        discount: Any = None

    @api_method(Get_user_list)
    def get_user_list(self, *, customer_id: int = None) -> ApiRetSData[Get_user_list]: 
        """Абоненты/клиенты"""
        ...

    @smart_model
    class Get_user_messages(BaseModel):
        id: int
        user_id: int
        msg_date: vStr
        subject: vStr
        text: vStr

    @api_method(Get_user_messages)
    def get_user_messages(self) -> ApiRetSData[Get_user_messages]: 
        """Сообщения абонентов"""
        ...

    @smart_model
    class Get_user_state_list(BaseModel):
        id: int
        name: vStr
        functional: vStr

    @api_method(Get_user_state_list)
    def get_user_state_list(self) -> ApiRetSData[Get_user_state_list]: 
        """Типы статусов абонентов (конфигуратор статусов)"""
        ...

    @smart_model
    class Get_user_tags(BaseModel):
        id: int
        name: vStr

    @api_method(Get_user_tags)
    def get_user_tags(self) -> ApiRetSData[Get_user_tags]: 
        """Метки для абонентов"""
        ...

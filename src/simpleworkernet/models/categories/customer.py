from typing import overload, List, Any, Literal
from enum import IntEnum, StrEnum
from ..base import BaseCategory, BaseModel, smart_model, CollapsedField
from ..primitives import vStr, vFlag, GeoPoint
from ...core.typing import ApiRetSData, ApiRetBool
from ...utils.decorators import api_method 
from ...smartdata.metadata import SegmentType

class Customer(BaseCategory):
    """Действия с абонентами"""

    link_cat = 'customer'

    @api_method(int)
    def add(self, *, fio: str = None, codeti: int = None, is_potential: vFlag = None, is_corporate: vFlag = None, billing_id: int = None, billing_customer_id: int = None) -> ApiRetSData[int]:
        """Добавление абонента

            Необязательные параметры:
                fio - наименование абонента
                codeti - id абонента в биллинге
                is_potential - флаг - потенциальный абонент
                is_corporate - флаг - юридическое лицо
                billing_id - id биллинга (является обязательным, если это не потенциальный абонент)
                billing_customer_id - id абонента в биллинге (является обязательным, если это не потенциальный абонент)
        """
        ...

    @smart_model
    class Abon_hist(BaseModel):
        Typer: vStr
        DateDo: vStr
        empoyee_id: int | None
        Amount: int
        Comment: vStr

    @api_method(Abon_hist)
    def abon_hist(self, *, customer_id: int) -> ApiRetSData[Abon_hist]:
        """Вывод операций с абонентом (финансовые и прочие)

            Обязательные параметры:
                customer_id - ID абонента
        """
        ...
    
    @api_method(bool)
    def change_balance(self, *, customer_id: int, amount: float, comment: str, employee_id: int = None) -> ApiRetBool:
        """Изменение баланса (операция прихода/расхода)

            Обязательные параметры:
                customer_id - ID абонента
                amount - Сумма
                comment - Заметки к операции
            Необязательные параметры:
                employee_id - ID сотрудника
        """
        ...

    @api_method(bool)
    def change_billing(self, *, customer_id: int, billing_id: int, billing_user_id: int = None) -> ApiRetBool:
        """Изменение биллинга

            Обязательные параметры:
                customer_id - id абонента
                billing_id - id биллинга
            Необязательные параметры:
                billing_user_id - id абонента в биллинге
        """
        ...

    @api_method(bool)
    def change_date_connect(self, *, customer_id: int, value: str) -> ApiRetBool:
        """Изменение даты подключения

            Обязательные параметры:
                customer_id - ID абонента
                value - дата
        """
        ...

    @api_method(bool)
    def delete(self, *, id: int) -> ApiRetBool:
        """Удаление абонента

            Обязательные параметры:
                id - id абонента
        """
    ...

    @api_method(bool)
    def edit(self, *, 
            id: int, 
            account_number: int  = None, 
            agreement_date: str = None, 
            agreement_number: int = None, 
            apartment_number: str = None, 
            comment: str = None, 
            coordinates: str = None, 
            date_activity: str = None, 
            date_activity_inet: str = None, 
            date_connect: str = None, 
            email: str = None, 
            entrance: int = None, 
            flag_corporate: vFlag = None, 
            floor: int = None, 
            group_id: int = None, 
            house_id: int = None, 
            is_potential: vFlag = None, 
            login: str = None, 
            manager_id: int = None, 
            name: str = None, 
            parent_id: int = None, 
            phone0: str = None, 
            phone1: str = None, 
            phone2: str = None, 
            phone3: str = None, 
            phone4: str = None) -> ApiRetBool:
        """Редактирование абонента

            Обязательные параметры:
                id - id абонента
            Необязательные параметры:
                account_number - номер лицевого счёта
                agreement_date - дата договора
                agreement_number - номер договора
                apartment_number - номер квартиры
                comment - заметки
                coordinates - координаты в текстовом виде через запятую (пример: 47.839628,35.140553)
                date_activity - дата активности в сети
                date_activity_inet - дата активности в интернете
                date_connect - дата подключения
                email - адрес электронной почты
                entrance - номер подъезда
                flag_corporate - флаг - юридическое лицо
                floor - этаж
                group_id - id группы
                house_id - id дома
                is_potential - флаг - потенциальный абонент
                login - логин
                manager_id - id сотрудника-менеджера
                name - наименование абонента
                parent_id - id родительского абонента (для дочернего абонента)
                phone0 - номер мобильного телефона
                phone1 - номер домашнего телефона
                phone2 - номер дополнительного телефона 1
                phone3 - номер дополнительного телефона 2
                phone4 - номер дополнительного телефона 3
        """
        ...

    @api_method(int)
    def get_activity_counter(self, *, type: Literal['net', 'internet', 'personal_area']) -> int | None:
        """Получение счетчика активных абонентов

            Обязательные параметры:
                type - тип счетчика (Возможные значения: net, internet, personal_area)
        """
        ...

    @api_method(int)
    def get_abon_id(self, *, 
            data_typer: Literal['account', 'billing_uid', 'codeti', 'dognumber', 'ip', 'login', 'mac', 'mail', 'phone'], 
            data_value: int | str, 
            is_skip_old: vFlag = None) -> ApiRetSData[int]:
        """Получение ID абонента по входящим данным

            Обязательные параметры:
                data_typer - тип данных, которые проверяем (возможные значения: account, billing_uid, codeti, dognumber, ip, login, mac, mail, phone)
                data_value - значение
            Необязательные параметры:
                is_skip_old - флаг - не выполнять поиск среди бывших абонентов
        """
        ...

    @smart_model
    class Get_customer_group(BaseModel):
        id: int
        name: vStr

    @api_method(Get_customer_group)
    def get_customer_group(self) -> ApiRetSData[Get_customer_group]:
        """Получение списка групп абонентов

            Обязательные параметры:
                нет
            Необязательные параметры:
                нет
        """
        ...
    
    @api_method(int)
    def get_customers_id(self, *, 
            account_number: int = None, 
            address_unit_id: int = None, 
            appartment: int | str = None, 
            balance_from: float = None, 
            balance_to: float = None, 
            billing_id: int = None, 
            billing_uuid: int = None, 
            date_connect_from: vStr = None, 
            date_connect_to: vStr = None,
            dependence_device_id: int = None,
            house_id: int = None,
            is_corporate: vFlag = None,
            is_ex: vFlag = None,
            manager_id: int = None,
            mark_id: int = None,
            name: str = None,
            state_id: int = None,
            tariff_id: int = None,
            limit: int = None,
            is_like: vFlag = None) -> ApiRetSData[int]:
        """Получение списка ID абонентов по входящим условиям

            Обязательные параметры:
                нет
            Необязательные параметры (но должно быть указано хотя бы одно условие):
                account_number - номер лицевого счёта
                address_unit_id - id адресной единицы
                appartment - номер квартиры
                balance_from - баланс (с)
                balance_to - баланс (до)
                billing_id - id номера биллинга
                billing_uuid - id абонента в биллинге
                date_connect_from - дата подключения (с)
                date_connect_to - дата подключения (до)
                dependence_device_id - id устройства, от которого зависят абоненты
                house_id - id дома
                is_corporate - флаг - юридическое лицо
                is_ex - флаг - бывшие абоненты
                manager_id - id менеджера (0 для поиска без менеджера)
                mark_id - id метки
                name - ФИО/название абонента
                state_id - id статуса
                tariff_id - id тарифа
                limit - максимальное количество записей, что вернуть в ответе
                is_like - флаг - использовать сравнение подстроки там где это возможно (а не полное совпадение)
        """
        ...

    @smart_model
    class Get_data(BaseModel):
        @smart_model
        class Agreement(BaseModel):
            number: vStr | None
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
            cost: vStr | None
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
        login: vStr | None
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
        comment: vStr | None
        ip_mac: List[Ip_mac]
        comment2: vStr | None
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
    
    @overload
    def get_data(self, *, customer_id: int) -> ApiRetSData[Get_data]: ...
    @overload
    def get_data(self, *, account_number: int, billing_id: int) -> ApiRetSData[Get_data]: ...

    @api_method(Get_data)
    def get_data(self, *, customer_id: int = None, account_number: int = None, billing_id: int = None) -> ApiRetSData[Get_data]:
        """Получение информации по абоненту

            Обязательные параметры:
                customer_id - ID абонента
                либо
                account_number - номер лицевого счета абонента
                И
                billing_id - ID биллинга
        """
        ...

    @api_method(None)
    def get_ip_port_device_commutation(self) -> Any:
        """Получение IP,MAC-адресов абонентов с привязкой к коммутаторам (в т.ч. для работы с DHCP)"""
        ...
    
    @api_method(str)
    def get_last_ip(self) -> str:
        """Получение последнего используемого IP-адреса для абонентов"""
        ...
    
    @api_method(None)
    def get_mac_history(self, *, customer_id: int) -> Any:
        """Получение истории изменения MAC-адресов по абоненту

            Обязательные параметры:
                customer_id - id абонента
        """
        ...
    
    @api_method(int)
    def get_max_agreement_number(self, *, billing_id: int = None) -> str:
        """Получение максимального занятого номера договора (числового)

            Необязательные параметры:
                billing_id - id биллинга абонентов, среди которых выполнять выборку
        """
        ...
    
    @api_method(bool)
    def ip_add(self, *, customer_id: int, value: str, mac: str = None) -> ApiRetBool:
        """Добавление IP-адреса

            Обязательные параметры:
                customer_id - ID абонента
                value - IP в формате "X.X.X.X"
            Необязательные параметры:
                mac - MAC абонента
        """
        ...
    
    @api_method(bool)
    def ip_delete(self, *, customer_id: int, value: str) -> ApiRetBool:
        """Удаление IP-адреса

            Обязательные параметры:
                customer_id - id абонента
                value - ip или "-1" для записей без IP-адреса (только с MAC-адресом) или "all" для всех адресов
        """
        ...
    
    @api_method(bool)
    def ip_subnet_add(self, *, customer_id: int, ip: str, subnet: int) -> ApiRetBool:
        """Добавление подсети IP-адресов для абонента
        
            Обязательные параметры:
                customer_id - id абонента
                ip - начальный ip-адрес
                subnet - маска подсети/VLSM (например: 24)
        """
        ...
    
    @api_method(bool)
    def ip_subnet_delete(self, *, customer_id: int, ip: str) -> ApiRetBool:
        """Удаление подсети IP-адресов у абонента

            Обязательные параметры:
                customer_id - id абонента
                ip - начальный ip-адрес
        """
        ...
    
    @api_method(bool)
    def mark_add(self, *, customer_id: int, mark_id: int) -> ApiRetBool:
        """Добавление метки на абоненте

            Обязательные параметры:
                customer_id - id абонента
                mark_id - id метки
        """
        ...
    
    @api_method(bool)
    def mark_delete(self, *, customer_id:int , mark_id: int) -> ApiRetBool:
        """Удаление метки с абонента

            Обязательные параметры:
                customer_id - id абонента
                mark_id - id метки
        """
        ...
    
    # @api_method(None)
    # def merge(self, *, dst_id: int, src_id: int):
    #     """Объединение абонентов

    #         Обязательные параметры:
    #             dst_id - id основного абонента
    #             src_id - id вторичного абонента (информацию которого переносим к основному)
    #     """
    #     ...
    
    @smart_model
    class Msg(BaseModel):
        Id: int
        DateMsg: vStr
        employee_id: int
        MsgTyper: vStr
        Text: vStr
    
    @overload
    def msg(self, *, customer_id: int, date_add_from: str = None, date_add_to: str = None, employee_id: int = None) -> ApiRetSData[Msg]: ...    
    @overload
    def msg(self, *, date_add_from: str, customer_id: int = None, date_add_to: str = None, employee_id: int = None) -> ApiRetSData[Msg]: ...
    @overload
    def msg(self, *, date_add_to: str, customer_id: int = None, date_add_from: str = None, employee_id: int = None) -> ApiRetSData[Msg]: ...
    @overload
    def msg(self, *, employee_id: int, customer_id: int = None, date_add_from: str = None, date_add_to: str = None) -> ApiRetSData[Msg]: ...

    @api_method(Msg)
    def msg(self, *, customer_id: int = None, date_add_from: str = None, date_add_to: str = None, employee_id: int = None) -> ApiRetSData[Msg]:
        """Вывод переписки с абонентом

            Необязательные параметры (но должно быть что-то одно):
                customer_id - ID абонента
                date_add_from - дата сообщения (с)
                date_add_to - дата сообщения (до)
                employee_id - id сотрудника-автора сообщения
        """
        ...
    
    @api_method(int)
    def msg_add(self, *, customer_id: int, text: str, is_arc: vFlag = None) -> ApiRetSData[int]:
        """Добавление сообщения от абонента

            Обязательные параметры:
                customer_id - id абонента
                text - Текст сообщения
            Необязательные параметры:
                is_arc - флаг - поместить сообщение в архив
        """
        ...
    
    # @api_method(None)
    # def msg_add_to_customer(self, *, employee_id: int, customer_id: int, text: int, is_arc: vFlag = None):
    #     """Добавление сообщения от сотрудника к абоненту

    #         Обязательные параметры:
    #             employee_id - id сотрудника
    #             customer_id - id абонента
    #             text - Текст сообщения
    #         Необязательные параметры:
    #             is_arc - флаг - поместить сообщение в архив
    #     """
    #     ...
    
    @api_method(bool)
    def pass_change(self, *, customer_id: int, pass_new: str, pass_old: str = None) -> ApiRetBool:
        """Смена пароля на вход в ЛК

            Обязательные параметры:
                customer_id - ID абонента
                pass_new - новый пароль
            Дополнительные параметры:
                pass_old - текущий пароль
        """
        ...
    
    # @api_method(None)
    # def service_add(self, customer_id, service_id, price=None, comment=None):
    #     """Добавление доп.услуги

    #         Обязательные параметры:
    #             customer_id - id абонента
    #             service_id - id доп.услуги
    #         Необязательные параметры:
    #             price - индивидуальная стоимость
    #             comment - заметки
    #     """
    #     ...
    
    # @api_method(None)
    # def service_remove(self, customer_id, service_id):
    #     """Удаление доп.услуги

    #         Обязательные параметры:
    #             customer_id - id абонента
    #             service_id - id доп.услуги
    #     """
    #     ...
    
    @api_method(bool)
    def set_mac_by_ip(self, *, ip: str, mac: str) -> ApiRetBool:
        """Указание MAC-адреса для IP-адреса абонента

            Обязательные параметры:
                ip - IP-адрес абонента (например: 192.168.0.1)
                mac - MAC-адрес абонента (например: 00:11:22:33:44:55)
        """
        ...
    
    @api_method(bool)
    def state_change(self, *, customer_id: int, state_id: int) -> ApiRetBool:
        """Изменение статуса работы у абонента

            Обязательные параметры:
                customer_id - ID абонента
                state_id - ID статуса абонента (0 - стоп, 1 - пауза, 2 - активен)
        """
        ...
    
    @api_method(bool)
    def tarif_change(self, *, customer_id: int, tarif: int) -> ApiRetBool:
        """Смена тарифа абоненту

            Обязательные параметры:
                customer_id - ID абонента
                tarif - ID нового тарифа
        """
        ...
    
    @api_method(bool)
    def to_ex(self, *, customer_id: int) -> ApiRetBool:
        """Перевод абонента в категорию "Бывшие абоненты"

            Обязательные параметры:
                customer_id - ID абонента
        """
        ...
    
    @api_method(bool)
    def to_normal(self, *, customer_id: int) -> ApiRetBool:
        """Перевод абонента в в обычный статус (из "Бывших абонентов")

            Обязательные параметры:
                customer_id - (для версии 3.17 и позже) ID абонента
        """
        ...
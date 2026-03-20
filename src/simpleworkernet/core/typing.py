from typing import Any, Union, List
from ..smartdata.core import SmartData, T

type ApiRetBool = Union[bool, None]
type ApiRetSData[T] = Union[SmartData[T], None]
type ApiRet = Union[ApiRetBool, ApiRetSData, List[T], Any]
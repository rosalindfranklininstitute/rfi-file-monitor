from abc import ABC, abstractmethod
from typing import Any, Sequence, Dict, Optional
import importlib.resources

import yaml

class Preference(ABC):

    @abstractmethod
    def __init__(self, key: str, default: Any):
        self._key: str = key
        self._default: Any = default

    @property
    def key(self) -> str:
        return self._key

    @property
    def default(self) -> Any:
        return self._default

class BooleanPreference(Preference):
    def __init__(self, key: str, default: bool = False):
        super().__init__(key, default)

TestBooleanPreference1 = BooleanPreference(
    key = "Boolean Pref1",
    default = True)

TestBooleanPreference2 = BooleanPreference(
    key = "Boolean Pref2",
    default = False)

TestBooleanPreference3 = BooleanPreference(
    key = "Boolean Pref3")

class ListPreference(Preference):
    def __init__(self, key: str, values: Sequence[str], default: Optional[str] = None):
        if default and default not in values:
            raise ValueError('default has to be within values array!')
        if not default:
            default = values[0]
        super().__init__(key, default)
        self._values = values

    @property
    def values(self) -> Sequence[str]:
        return self._values

TestListPreference1 = ListPreference(
    key = 'List Pref1',
    values = ('Option1', 'Option2', 'Option3'))

TestListPreference2 = ListPreference(
    key = 'List Pref2',
    values = ('Option1', 'Option2', 'Option3'),
    default = 'Option3')

class DictPreference(Preference):
    def __init__(self, key: str, values: Dict[str, Any], default: Optional[str] = None):
        if default and default not in values:
            raise ValueError('default has to be within values dict!')
        if not default:
            default = list(values.keys())[0]
        super().__init__(key, default)
        self._values = values

    @property
    def values(self) -> Dict[str, Any]:
        return self._values

    @classmethod
    def from_file(cls, key: str, yaml_file, default: Optional[str] = None):
        with open(yaml_file, 'r') as f:
            yaml_dict = yaml.safe_load(stream=f)
        return cls(key, yaml_dict, default)

TestDictPreference1 = DictPreference(
    key = 'Dict Pref1',
    values = dict(option1='option1', option2=dict(option2='option2'), option3=list('option3')),
    default = 'option2'
)

TestDictPreference2 = DictPreference(
    key = 'Dict Pref2',
    values = dict(option1='option1', option2=dict(option2='option2'), option3=list('option3'))
)

with importlib.resources.path('rfi_file_monitor.data', 'rfi-instruments.yaml') as f:
    TestDictPreference3 = DictPreference.from_file(
        key='Dict Pref3 From File',
        yaml_file=f,
    )
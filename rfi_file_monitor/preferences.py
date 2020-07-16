from abc import ABC, abstractmethod
from typing import Any, Sequence, Dict, Optional
from pathlib import PurePath

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
    @property
    @classmethod
    @abstractmethod
    def values(cls) -> Dict[str, Any]:
        pass

    @property
    @classmethod
    def default(cls):
        #pylint: disable=no-member
        return cls.values.keys()[0]

class DictFromFilePreference(DictPreference):
    @property
    @classmethod
    @abstractmethod
    def file(cls) -> PurePath:
        pass

    @property
    @classmethod
    def values(cls) -> Dict[str, Any]:
        return cls.cache

    @property
    @classmethod
    def cache(cls) -> dict:
        if not hasattr(cls, '_cache'):
            #pylint: disable=no-member
            with cls.file.open('r') as f:
                cls._cache = yaml.safe_load(stream=f)
        return cls._cache



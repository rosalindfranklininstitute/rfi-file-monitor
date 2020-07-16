from abc import ABC, abstractmethod
from typing import Any, Sequence, Dict
from pathlib import PurePath

import yaml

class Preference(ABC):
    @property
    @classmethod
    @abstractmethod
    def key(cls) -> str:
        pass

    @property
    @classmethod
    @abstractmethod
    def default(cls) -> Any:
        pass

class BooleanPreference(Preference):
    default = False

class ListPreference(Preference):
    @property
    @classmethod
    @abstractmethod
    def values(cls) -> Sequence[str]:
        pass

class TestListPreference1(ListPreference):
    key = 'List Pref1'
    values = ('Option1', 'Option2', 'Option3')
    default = values[0]

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

class TestBooleanPreference1(BooleanPreference):
    key = "Boolean Pref1"
    default = True

class TestBooleanPreference2(BooleanPreference):
    key = "Boolean Pref2"
    default = False

class TestBooleanPreference3(BooleanPreference):
    key = "Boolean Pref3"

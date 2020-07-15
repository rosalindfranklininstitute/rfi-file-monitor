from abc import ABC, abstractmethod
from typing import Any

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

class TestBooleanPreference1(BooleanPreference):
    key = "Boolean Pref1"
    default = True

class TestBooleanPreference2(BooleanPreference):
    key = "Boolean Pref2"
    default = False

class TestBooleanPreference3(BooleanPreference):
    key = "Boolean Pref3"

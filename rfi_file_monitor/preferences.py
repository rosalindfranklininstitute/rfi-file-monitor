from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence, Dict, Optional, NamedTuple, Type
import importlib.resources

import yaml
from munch import Munch

from .operation import Operation
from .engine import Engine
from rfi_file_monitor.utils import (
    INSTRUMENT_CONFIG_FILEPATH,
    TEST_INSTRUMENT_CONFIG_FILEPATH,
)


class Preference(ABC):
    @abstractmethod
    def __init__(self, key: str, default: Any, description: Optional[str]):
        self._key: str = key
        self._default: Any = default
        self._description = description

    @property
    def key(self) -> str:
        return self._key

    @property
    def default(self) -> Any:
        return self._default

    @property
    def description(self):
        return self._description


class BooleanPreference(Preference):
    def __init__(
        self, key: str, default: bool = False, description: Optional[str] = None
    ):
        super().__init__(key, default, description)


TestBooleanPreference1 = BooleanPreference(
    key="Boolean Pref1",
    default=True,
    description="This is a description for Boolean Pref1",
)

TestBooleanPreference2 = BooleanPreference(key="Boolean Pref2", default=False)

TestBooleanPreference3 = BooleanPreference(
    key="Boolean Pref3", description="This is a description for Boolean Pref3"
)


class ListPreference(Preference):
    def __init__(
        self,
        key: str,
        values: Sequence[str],
        default: Optional[str] = None,
        description: Optional[str] = None,
    ):
        if default and default not in values:
            raise ValueError("default has to be within values array!")
        if not default:
            default = values[0]
        super().__init__(key, default, description)
        self._values = values

    @property
    def values(self) -> Sequence[str]:
        return self._values


TestListPreference1 = ListPreference(
    key="List Pref1",
    values=("Option1", "Option2", "Option3"),
    description="This is a description for List Pref1",
)

TestListPreference2 = ListPreference(
    key="List Pref2",
    values=("Option1", "Option2", "Option3"),
    default="Option3",
)


class DictPreference(Preference):
    def __init__(
        self,
        key: str,
        values: Dict[str, Any],
        default: Optional[str] = None,
        description: Optional[str] = None,
    ):
        if default and default not in values:
            raise ValueError("default has to be within values dict!")
        if not default:
            default = list(values.keys())[0]
        super().__init__(key, default, description)
        self._values = values

    @property
    def values(self) -> Dict[str, Any]:
        return self._values

    @classmethod
    def from_file(
        cls,
        key: str,
        yaml_file,
        default: Optional[str] = None,
        description: Optional[str] = None,
    ):
        with open(yaml_file, "r") as f:
            yaml_dict = yaml.safe_load(stream=f)
        return cls(key, yaml_dict, default, description)


TestDictPreference1 = DictPreference(
    key="Dict Pref1",
    values=dict(
        option1="option1",
        option2=dict(option2="option2"),
        option3=list("option3"),
    ),
    default="option2",
    description="This is a description for Dict Pref1",
)

TestDictPreference2 = DictPreference(
    key="Dict Pref2",
    values=dict(
        option1="option1",
        option2=dict(option2="option2"),
        option3=list("option3"),
    ),
)

with importlib.resources.path(
    "rfi_file_monitor.data", "rfi-instruments.yaml"
) as f:
    TestDictPreference3 = DictPreference.from_file(
        key="Dict Pref3 From File",
        yaml_file=f,
        description="This is a description for Dict Pref3 From File",
    )


class StringPreference(Preference):
    def __init__(
        self, key: str, default: str = "", description: Optional[str] = None
    ):
        super().__init__(key, default, description)


TestStringPreference1 = StringPreference(
    key="String Pref1",
    description="This is a description for String Pref1",
)

TestStringPreference2 = StringPreference(
    key="String Pref2",
    default="String Pref2 default value",
)

AllowedFilePatternsPreference = StringPreference(
    key="Allowed File Patterns",
    description="These comma separated file patterns will be added automatically to the allowed patterns of all operations and engines that support them. Use cautiously!!",
)

IgnoredFilePatternsPreference = StringPreference(
    key="Ignored File Patterns",
    description="These comma separated file patterns will be added automatically to the ignored patterns of all operations and engines that support them.",
    default="*.swp,*.swx,*.DS_Store",
)

if INSTRUMENT_CONFIG_FILEPATH.is_file():
    InstrumentSetup = DictPreference.from_file(
        key="Instrument Setup",
        yaml_file=INSTRUMENT_CONFIG_FILEPATH,
        description="This is the instrument description. Instruments can be specified in a instrument-prefs.yml file inside the instrument-config directory.",
    )
elif TEST_INSTRUMENT_CONFIG_FILEPATH.is_file():
    InstrumentSetup = DictPreference.from_file(
        key="Instrument Setup",
        yaml_file=TEST_INSTRUMENT_CONFIG_FILEPATH,
        description="This is a default instrument. Instruments can be specified in a instrument-prefs.yml file inside the instrument-config directory.",
    )
else:
    InstrumentSetup = DictPreference(
        key="Instrument Setup",
        values={
            "test-instrument": {
                "techniques": {"test-instrument-technique": ["None"]}
            },
        },
        description="This is a default instrument. Instruments can be specified in a instrument-prefs.yml file inside the instrument-config directory.",
    )


class Preferences(NamedTuple):
    settings: Munch[Preference, Any]
    operations: Munch[Type[Operation], bool]
    engines: Munch[Type[Engine], bool]

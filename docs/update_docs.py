# this script copies the pango docs to the github-pages docs while translating them into markdown

from pathlib import Path
from typing import List
import xml.etree.ElementTree as ET
import re

SIZES = {
    "xx-large": "#",
    "x-large": "##",
    "large": "###",
    "medium": "####",
}

DOCS_DIR = Path(__file__).resolve(strict=True).parent

SOURCES = (
    (
        "_engines",
        DOCS_DIR.parent.joinpath("rfi_file_monitor", "engines", "docs"),
    ),
    (
        "_operations",
        DOCS_DIR.parent.joinpath("rfi_file_monitor", "operations", "docs"),
    ),
    ("misc", DOCS_DIR.parent.joinpath("rfi_file_monitor", "docs")),
)

for _dest, _source in SOURCES:
    print(f"{_dest=}")
    print(f"{_source=}")
    for _src in _source.glob("*.pango"):
        print(f"{_src=}")
        if _src.name.startswith("template"):
            continue

        dest = DOCS_DIR.joinpath(_dest, _src.name).with_suffix(".md")
        old_contents = _src.read_text().splitlines()

        # process first line
        if not old_contents[0].strip().startswith('<span size="xx-large">'):
            raise Exception(
                f'Invalid file {_src.name}: must start with <span size="xx-large">'
            )

        # get title
        title_tag = ET.fromstring(old_contents[0])
        title = title_tag.text

        new_contents: List[str] = []
        supported_file_formats_found = False
        exported_file_format_found = False
        matches = []

        for _line in old_contents:
            # _line = _line.strip()
            if _line.startswith("<span") and _line.endswith("</span>"):
                tag = ET.fromstring(_line)
                text = tag.text
                size = tag.attrib["size"]
                if len(tag.attrib) > 1:
                    raise Exception(
                        "<span> tags can only contain the size attribute"
                    )
                new_contents.append(f"{SIZES[size]} {text}")
            elif "<span" in _line:
                raise Exception(
                    "<span> blocks are currently only supported for titles"
                )
            elif _line == "<tt>":
                # this is coarse, ideally the whole block should be read and the language guessed with pygments
                new_contents.append("```json")
            elif _line == "</tt>":
                new_contents.append("```")
            else:
                new_contents.append(_line)

            if _line == "":
                continue

            if _dest == "_operations":
                if "Supported File Formats" in _line:
                    supported_file_formats_found = True
                elif supported_file_formats_found:
                    if matches := re.findall(r"<b>(\w+)</b>", _line):
                        supported_file_formats_found = False
            elif _dest == "_engines":
                if "Exported File Format" in _line:
                    exported_file_format_found = True
                elif exported_file_format_found:
                    if matches := re.findall(r"<b>(\w+)</b>", _line):
                        exported_file_format_found = False

        if _dest == "_operations":
            if supported_file_formats_found or not matches:
                raise Exception(
                    "Supported File Formats title found but no corresponding values"
                )

            preface = [
                "---",
                "layout: default",
                f"title: {title}",
                f"supported: [{', '.join(matches)}]" "",
                "---",
                "",
            ]
        elif _dest == "_engines":
            if exported_file_format_found or len(matches) != 1:
                raise Exception(
                    "Exported File Format title found but no corresponding value"
                )

            preface = [
                "---",
                "layout: default",
                f"title: {title}",
                f"exported: {matches[0]}" "",
                "---",
                "",
            ]
        elif _dest == "misc":
            preface = [
                "---",
                "layout: default",
                f"title: {title}",
                "",
                "---",
                "",
            ]

        dest.write_text("\n".join(preface + new_contents))

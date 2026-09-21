"""
Minimal parser for KiCad 7 .kicad_sym S-expression symbol libraries.
Returns pin geometry (number, name, x, y, rotation, electrical type) so the
schematic generator can compute absolute pin positions for wire stubs / no
connect flags without needing the KiCad GUI.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

KICAD_SYM_DIR = "/usr/share/kicad/symbols"


@dataclass
class Pin:
    number: str
    name: str
    x: float
    y: float
    rotation: int
    etype: str  # electrical pin type: input/output/passive/power_in/... (kicad_sch doesn't need this but useful)


def _find_balanced(text: str, start: int) -> str:
    depth = 0
    j = start
    while True:
        if text[j] == '(':
            depth += 1
        elif text[j] == ')':
            depth -= 1
            if depth == 0:
                return text[start:j + 1]
        j += 1


@lru_cache(maxsize=None)
def _load_lib(filename: str) -> str:
    with open(f"{KICAD_SYM_DIR}/{filename}") as f:
        return f.read()


def _symbol_block(libtext: str, symname: str) -> str | None:
    key = f'(symbol "{symname}"'
    i = libtext.find(key)
    if i < 0:
        return None
    return _find_balanced(libtext, i)


PIN_HEADER_RE = re.compile(
    r'\(pin (\w+) \w+ \(at ([\-0-9.]+) ([\-0-9.]+) (\d+)\)'
)
NAME_RE = re.compile(r'\(name "([^"]*)"')
NUMBER_RE = re.compile(r'\(number "([^"]*)"')
EXTENDS_RE = re.compile(r'\(symbol "[^"]+" \(extends "([^"]+)"\)')


def get_pins(lib_file: str, symbol_name: str) -> list[Pin]:
    """lib_file like 'Device.kicad_sym'; symbol_name like 'R' or 'AP2112K-3.3'."""
    text = _load_lib(lib_file)
    block = _symbol_block(text, symbol_name)
    if block is None:
        raise ValueError(f"Symbol {symbol_name} not found in {lib_file}")

    m = EXTENDS_RE.search(block)
    if m:
        base_pins = get_pins(lib_file, m.group(1))
        # extended symbols can still override Footprint/etc but pins come from base
        return base_pins

    pins = []
    for hm in PIN_HEADER_RE.finditer(block):
        etype, x, y, rot = hm.groups()
        pin_block = _find_balanced(block, hm.start())
        name = NAME_RE.search(pin_block).group(1)
        number = NUMBER_RE.search(pin_block).group(1)
        pins.append(Pin(number=number, name=name, x=float(x), y=float(y),
                         rotation=int(rot), etype=etype))
    return pins


CUSTOM_SYM_FILE = "/home/user/Schematics/Maverick1000/kicad/libraries/symbols/SKYWARD_Custom.kicad_sym"


@lru_cache(maxsize=None)
def _load_custom() -> str:
    with open(CUSTOM_SYM_FILE) as f:
        return f.read()


def get_pins_custom(symbol_name: str) -> list[Pin]:
    text = _load_custom()
    block = _symbol_block(text, symbol_name)
    if block is None:
        raise ValueError(f"Symbol {symbol_name} not found in {CUSTOM_SYM_FILE}")
    pins = []
    for hm in PIN_HEADER_RE.finditer(block):
        etype, x, y, rot = hm.groups()
        pin_block = _find_balanced(block, hm.start())
        name = NAME_RE.search(pin_block).group(1)
        number = NUMBER_RE.search(pin_block).group(1)
        pins.append(Pin(number=number, name=name, x=float(x), y=float(y),
                         rotation=int(rot), etype=etype))
    return pins


def get_pins_for_lib_id(lib_id: str) -> list[Pin]:
    """lib_id like 'Device:R' (stock) or 'SKYWARD_Custom:CM4_Connector_100'."""
    lib, sym = lib_id.split(":", 1)
    if lib == "SKYWARD_Custom":
        return get_pins_custom(sym)
    return get_pins(f"{lib}.kicad_sym", sym)

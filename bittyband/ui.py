#!/usr/bin/env python3

from . import uicurses
from .config import ConfigError 

def get_ui():
    if uicurses.is_available():
        return uicurses.UiCurses
    else:
        raise ConfigError("No user-interfaces available.")


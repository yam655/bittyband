#!/bin/env python3

from .commands import Commands
from .keymaps import KeyMaps
from .player import PushButtonPlayer
from .ui import get_ui

def app(config):
    keymap = KeyMaps(config)
    pbplayer = PushButtonPlayer(config)
    ui_maker = get_ui()
    cmds = Commands(config, pbplayer)
    ui = ui_maker(config, keymap, cmds)

    if config["project"]["mode"] != "test":
        pbplayer.open()
        ui.jam()


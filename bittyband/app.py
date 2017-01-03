#!/bin/env python3

from .commands import Commands
from .keymaps import KeyMaps
from .player import PushButtonPlayer
from .ui import get_ui
from .cmdrecorder import CommandRecorder

def app(config):
    keymaps = KeyMaps(config)
    pbplayer = PushButtonPlayer(config)
    ui_maker = get_ui()
    cmds = Commands(config, pbplayer)
    recorder = CommandRecorder(config)
    ui = ui_maker(config, keymaps, cmds, recorder)

    if config["instance"]["mode"] != "test":
        pbplayer.start()
        try:
            ui.jam()
        finally:
            pbplayer.end()
    else:
        keymaps.test()


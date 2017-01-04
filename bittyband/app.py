#!/bin/env python3

import sys

from .commands import Commands
from .keymaps import KeyMaps
from .player import PushButtonPlayer
from .ui import get_ui
from .cmdrecorder import CommandRecorder
from .lister import Lister

def app(config):
    keymaps = KeyMaps(config)
    pbplayer = PushButtonPlayer(config)
    ui_maker = get_ui()

    if config["instance"]["mode"] == "gui":
        recorder = CommandRecorder(config)
        cmds = Commands(config, pbplayer, recorder)
        ui = ui_maker(config, keymaps, cmds, recorder)
        pbplayer.start()
        recorder.start()
        try:
            ui.jam()
        finally:
            pbplayer.end()
            recorder.end()

    elif config["instance"]["mode"] == "list":
        lister = Lister(config)
        cmds = Commands(config, pbplayer, None)
        ui = ui_maker(config, None, cmds, None, lister=lister)
        pbplayer.start()
        try:
            ui.list_it()
        finally:
            pbplayer.end()

    elif config["instance"]["mode"] == "test":
        keymaps.test()


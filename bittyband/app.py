#!/bin/env python3

import sys

from .commands import Commands
from .keymaps import KeyMaps
from .player import PushButtonPlayer
from .ui import get_ui
from .cmdrecorder import CommandRecorder
from .lister import Lister
from .bgplayer import BackgroundDrums

def app(config):
    keymaps = KeyMaps(config)
    pbplayer = PushButtonPlayer(config)
    ui_maker = get_ui()
    background = BackgroundDrums(config, pbplayer)

    if config["instance"]["mode"] == "gui":
        recorder = CommandRecorder(config)
        cmds = Commands(config, pbplayer, recorder, background)
        ui = ui_maker(config, keymaps, cmds, recorder)
        pbplayer.start()
        recorder.start()
        background.start()
        try:
            ui.jam()
        finally:
            background.end()
            pbplayer.end()
            recorder.end()

    elif config["instance"]["mode"] == "list":
        lister = Lister(config)
        cmds = Commands(config, pbplayer, None, background)
        ui = ui_maker(config, None, cmds, None, lister=lister)
        pbplayer.start()
        background.end()
        try:
            ui.list_it()
        finally:
            background.end()
            pbplayer.end()

    elif config["instance"]["mode"] == "test":
        keymaps.test()


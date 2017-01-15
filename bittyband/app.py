#!/bin/env python3

import sys

from .commands import Commands
from .keymaps import KeyMaps
from .player import PushButtonPlayer
from .ui import get_ui
from .cmdrecorder import CommandRecorder
from .lister import Lister
from .bgplayer import BackgroundDrums
from .importer import ImporterBackend

def app(config):
    keymaps = KeyMaps(config)
    pbplayer = PushButtonPlayer(config)
    ui_maker = get_ui()
    background = BackgroundDrums(config, pbplayer)

    if config["instance"]["mode"] == "gui":
        recorder = CommandRecorder(config)
        cmds = Commands(config, pbplayer, recorder, background)
        ui = ui_maker(config=config, keymaps=keymaps, commands=cmds, cmdrecorder=recorder)
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
        cmds = Commands(config, pbplayer, None, background)
        lister = Lister(config, cmds)
        ui = ui_maker(config=config, commands=cmds, lister=lister)
        pbplayer.start()
        background.start()
        try:
            ui.list_it()
        finally:
            background.end()
            pbplayer.end()

    elif config["instance"]["mode"] == "import":
        importer = ImporterBackend(config)
        ui = ui_maker(config=config, importer=importer, player=pbplayer)
        pbplayer.start()
        try:
            ui.import_it()
        finally:
            pbplayer.end()

    elif config["instance"]["mode"] == "test":
        keymaps.test()

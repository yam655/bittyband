#!/bin/env python3

import sys

from .commands import Commands
from .player import PushButtonPlayer
from .ui import get_ui
from .cmdrecorder import CommandRecorder
from .jamlister import JamLister
from .bgplayer import BackgroundDrums
from .importer import ImporterBackend

def app(config):
    ui_maker = get_ui()
    wiring = {}
    wiring["ui"] = ui = ui_maker(config)
    wiring["push_player"] = PushButtonPlayer(config)
    wiring["metronome"] = BackgroundDrums(config)
    wiring["push_commands"] = Commands(config)

    need_for_mode = []
    mode = lambda: True
    if config["instance"]["mode"] == "gui" or config["instance"]["mode"] == "jam":
        wiring["push_recorder"] = CommandRecorder(config)
        need_for_mode = ["push_player", "push_recorder", "metronome"]
        mode = ui.start_jam

    elif config["instance"]["mode"] == "list":
        wiring["jam_lister"] = JamLister(config)
        need_for_mode = ["push_player", "metronome"]
        mode = ui.start_list

    elif config["instance"]["mode"] == "import":
        wiring["import_lister"] = ImporterBackend(config)
        mode = ui.start_import

    elif config["instance"]["mode"] == "test":
        pass

    for v in wiring.values():
        v.wire(**wiring)
    for thing in need_for_mode:
        wiring[thing].start()
    try:
        mode()
    finally:
        for thing in need_for_mode:
            wiring[thing].end()

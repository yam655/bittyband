#!/bin/env python3

import sys

from .importer import CsvPlayer
from .commands import Commands
from .player import PushButtonPlayer
from .ui import get_ui
from .cmdrecorder import CommandRecorder
from .jamlister import JamLister
from .bgplayer import BackgroundDrums, BackgroundNull
from .importer import Importer
from .importlister import ImportLister

def app(config):
    ui_maker = get_ui()
    wiring = {}
    wiring["ui"] = ui = ui_maker(config)
    wiring["push_player"] = PushButtonPlayer(config)
    wiring["push_commands"] = Commands(config)
    wiring["metronome"] = BackgroundDrums(config)

    need_for_mode = []
    mode = lambda: True
    if config["instance"]["mode"] == "gui" or config["instance"]["mode"] == "jam":
        wiring["push_recorder"] = CommandRecorder(config)
        need_for_mode = ["push_player", "push_recorder", "metronome"]
        mode = ui.start_jam

    elif config["instance"]["mode"] == "list":
        wiring["jam_lister"] = JamLister(config)
        wiring["metronome"] = BackgroundNull(config)
        need_for_mode = ["push_player", "metronome"]
        mode = ui.start_list

    elif config["instance"]["mode"] == "import":
        wiring["import_lister"] = ImportLister(config)
        wiring["importer"] = Importer(config)
        wiring["csv_player"] = CsvPlayer(config)
        need_for_mode = ["push_player", "csv_player"]
        mode = ui.start_import

    elif config["instance"]["mode"] == "import-file":
        wiring["import_lister"] = ImportLister(config)
        wiring["importer"] = Importer(config)
        wiring["csv_player"] = CsvPlayer(config)
        need_for_mode = ["push_player", "csv_player"]
        mode = ui.start_import_file

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

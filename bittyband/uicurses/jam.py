#!/usr/bin/env python3

import curses

from ..keymaps import KeyMaps

class JamScreen:

    def __init__(self, config):
        self.config = config
        self.keymap = KeyMaps(config).jam_map

    def wire(self, *, push_commands, push_recorder, ui, **kwargs):
        self.commands = push_commands
        self.command_log = push_recorder
        self.ui = ui

    def __call__(self, stdscr, args=()):
        stdscr.keypad(True)
        stdscr.scrollok(True)

        self.stdscr = stdscr
        ch = ""
        command = ""
        self.command_log.add("mark_good")
        first_preset = "preset_0"
        self.commands.execute(first_preset)
        self.command_log.add(first_preset)

        while command != "quit":
            if command is None:
                self.ui.putln("Unknown key: '{}' (len:{})".format(ch, len(ch)))
            elif command != "":
                self.command_log.add(command)
                self.commands.execute(command)
            ch = self.ui.get_key()
            command = self.keymap.get(ch)
        self.commands.do_silence("silence")
        self.commands.do_panic()
        self.command_log.add("mark_bad")

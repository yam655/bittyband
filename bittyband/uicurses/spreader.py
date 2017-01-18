
import curses

from .genericlister import GenericLister

class Spreader(GenericLister):
    idle_cmd = None
    time = None
    exit_func = None

    def __init__(self, config):
        super().__init__(config)

    def wire(self, **kwargs):
        GenericLister.wire(self, **kwargs)

    def get_key(self):
        key = None
        while key is None:
            key = self.ui.get_key(timeout=0.7)
            if self.idle_cmd is not None:
                self.idle_cmd()
        return key

    def register_idle(self, idle_cmd):
        self.idle_cmd = idle_cmd

    def refresh_status(self):
        max_y, max_x = self.stdscr.getmaxyx()
        self.stdscr.hline(max_y - 2, 0, "=", max_x)
        self.display_time(no_refresh=True)
        self.stdscr.chgat(max_y - 2, 0, curses.A_BOLD)
        self.stdscr.refresh()

    def on_exit(self, func):
        self.exit_func = func

    def display_time(self, text = None, *, no_refresh=False):
        max_y, max_x = self.stdscr.getmaxyx()
        if text is not None:
            self.time = "[{}]".format(text)
        if self.time is not None:
            self.stdscr.addstr(max_y - 2, max_x - len(self.time), self.time)
        if not no_refresh:
            self.stdscr.chgat(max_y - 2, max_x - len(self.time), curses.A_BOLD)
            self.stdscr.refresh()

    def _quit_cmd(self, line):
        self.running = False
        if self.exit_func is not None:
            self.exit_func()
        return False

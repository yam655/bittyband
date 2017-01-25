#!/usr/bin/env python3

class ExportTxt:
    filename = None

    def __init__(self, config, filenm):
        self.filename = filenm
        self.lines = []
        self.trail = []
        self.cur = []

    def start(self):
        pass

    def end(self):
        if len(self.cur) > 0:
            self.lines.append("".join(self.cur))
        if len(self.trail) > 0:
            self.lines.extend(self.trail)
        with self.filename.open("wt") as out:
            out.write("\n".join(self.lines))

    def new_track(self, *, copyright = None, tagline = None, poet=None,
                  title, filename = None, **kwargs):
        if len(self.trail) > 0:
            self.lines.extend(self.trail)
        self.trail = []

        if len(self.lines) > 0:
            self.lines.append("")
            if title is None:
                self.lines.append("----")
                self.lines.append("")

        if title is not None:
            self.lines.append(title)
            self.lines.append("=" * len(title))
            self.lines.append("")

        if poet:
            self.lines.append("By: {}".format(poet))
            self.lines.append("")

        if copyright:
            self.trail.append(copyright)
        if tagline:
            self.trail.append(tagline)
        if len(self.trail) > 0:
            self.trail.insert(0, "")

    def unknown_track(self):
        if len(self.lines) > 0:
            self.lines.append("")

        title = "Unknown Track"
        self.lines.append(title)
        self.lines.append("=" * len(title))
        self.lines.append("")

    def player(self):
        pass

    def sync_comment(self, cmt):
        pass

    def feed_comment(self, cmt, channel=None):
        pass

    def feed_time(self, nu, de):
        pass

    def feed_other(self, cmd, channel=None):
        pass

    def feed_lyric(self, lyric):
        if lyric is None or lyric == "":
            return
        lyric = str(lyric)
        if lyric.startswith("/"):
            self.lines.append("".join(self.cur))
            self.cur = []
            lyric = lyric[1:]
        elif lyric.startswith("\\"):
            self.lines.append("".join(self.cur))
            self.lines.append("")
            self.cur = []
            lyric = lyric[1:]
        needSpace = False
        for lyr in lyric.replace("~"," ").split():
            if lyr == "" or lyr == "_":
                continue
            if lyr == "--":
                needSpace = False
                continue
            if needSpace:
                self.cur.append(" ")
            else:
                needSpace = True
            self.cur.append(lyr)
        if needSpace:
            self.cur.append(" ")

    def feed_midi(self, *what, ui=None, abbr=None, channel=None, time=None):
        pass

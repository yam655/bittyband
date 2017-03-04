#!/busr/bin/env python3
import mido

from ..midinames import getLyForMidiNote
from ..utils.time import from_human_duration, human_duration


class BeaterCommands:
    def __init__(self, beater):
        self.beater = beater
        self.last_bpm_tap = ""
        self.last_nudge = ""

    def wire(self, *, ui, import_lister, beat_player, push_player, **kwargs):
        self.ui = ui
        self.import_lister = import_lister
        self.beat_player = beat_player
        self.push_player = push_player

    def _do_play(self, line):
        self.start_segment = self.order[line]
        self.start_line = line
        self.end_segment = None
        self.playing_row = None
        if self.beat_player.playing:
            self.beat_player.pause()
            self.beat_player.silence()
        else:
            self.beat_player.silence()
            self.beat_player.seek(self.start_line)
            self.beat_player.play()

    def _do_play_chords(self, line):
        self.start_segment = self.order[line]
        self.start_line = line
        self.end_segment = None
        self.playing_row = None
        if self.beat_player.playing:
            self.beat_player.pause()
            self.player.pause()
            self.beat_player.silence()
        else:
            self.beat_player.silence()
            self.player.pause()
            self.beat_player.seek(self.start_line)
            self.beat_player.play()

    def _do_play_segment(self, *, line, advertise=True):
        if line == len(self.order) - 1:
            self.spreader.show_status("Can not play last segment")
            self.playing_row = None
            return False
        self.start_segment = self.order[line]
        self.start_line = line
        self.playing_row = line
        self.end_segment = self.order[line + 1]
        if advertise:
            self.spreader.show_status("Playing current line".format(human_duration(self.start_segment), human_duration(self.end_segment)))
        self.beat_player.seek(self.start_line)
        self.beat_player.play()

    def _do_repeat_mark(self, *, line):
        datum = self.data.get(self.order[line])
        if datum.get("mark_idx", -1) < 0:
            self.spreader.show_status("This line isn't in a marked section")
            return False
        self.playing_row = None
        self.start_line = datum["mark_idx"]
        end_line = self.start_line
        while end_line < len(self.order) and self.data.get(self.order[end_line]).get("mark_idx",-1) == self.start_line:
            end_line += 1
        if end_line >= len(self.order):
            end_line = len(self.order) - 1

        start_secs = self.order[line]
        self.start_segment = start_secs
        self.end_segment = self.order[end_line]
        starting_at = ""
        if line != self.start_line:
            starting_at = " starting at {}".format(human_duration(start_secs))
        self.spreader.show_status("Playing: {} to {}{}".format(human_duration(self.start_segment), human_duration(self.end_segment), starting_at))
        self.player.seek(self.start_segment)
        self.player.play()
        self.player.seek(self.start_segment)
        self.player.play()
        self.csv_player.seek(self.start_line)
        self.csv_player.play()

    def _do_delete(self, *, line):
        if line == 0 or line == len(self.order) - 1:
            self.spreader.show_status("Can't delete top or bottom")
            return False
        item = self.order[line]
        del self.data[item]
        del self.order[line]
        self.spreader.invalidate = True
        self.changed = True
        return True

    def _do_idle(self):
        pass
        # if not self.player:
        #     self.spreader.show_status(self.bits["title"])
        #     self._start_player()
        # t = self.player.time
        # if self.player.playing and self.end_segment is not None and t >= self.end_segment:
        #     self.player.seek(self.start_segment)
        #     self.csv_player.seek(self.start_line)
        #     self.player.play()
        #     self.csv_player.play()
        # # display = human_duration(t, floor=True)
        # # self.spreader.display_time(display)
        # # display = human_duration(self.order[self.csv_player.line-1], floor=1)
        # # self.spreader.display_line(display)
        # row = self.playing_row
        # if row is not None and row != self.spreader.active:
        #     self._do_play_segment(line=self.spreader.active, advertise=False)
        # if not self.player.playing:
        #     if len(self.order) != len(self.data):
        #         self.update_order()
        #         self._propagate()
        #         self.spreader.refresh()
        #     elif self._need_propagate:
        #         self._propagate()
        #         self.spreader.refresh()

    def _do_tap(self, *, line):
        offset = self.player.time
        if offset not in self.data:
            self.add_row(offset)
        self.spreader.show_status(human_duration(offset, 3))
        self.changed = True
        return False

    def _split_words(self, line):
        box = self.beater.beat_box
        datum = box.data[box.order[line]]
        words = self.break_on_lily_words(datum["lyric"])
        if line == len(self.order):
            self.spreader.show_status("Can't do that on the last line.")
            return True
        segments = len(words)
        available_space = box.order[line+1] - self.order[line]
        offset = available_space / segments
        starting_at = box.order[line]
        for idx in range(1,segments):
            location = starting_at + offset * idx
            if location in box.data:
                self.spreader.show_status("Woah. Didn't expect {} to be present. Stopping.".format(location))
                return True
            box.add_row(location, lyric=words[idx])
        datum["lyric"] = words[0]
        return False

    def _do_beat_repeat(self, bpm, *, line):
        if line < 0 or bpm is None:
            return self.last_bpm_tap
        box = self.beater.beat_box
        self.last_bpm_tap = bpm
        if bpm.lower() == "word" or bpm.lower() == "words":
            self._split_words(line)
        i = 0
        while i < len(bpm) and bpm[i].isnumeric():
            i += 1
        end = i
        while i < len(bpm) and bpm[i].isspace():
            i += 1
        if i >= len(bpm):
            self.spreader.show_status("Unrecognized rate: " + bpm)
            return True

        try:
            rep = int(bpm[:end])
        except ValueError:
            self.spreader.show_status("Illegal rate: " + bpm)
            return True

        if bpm[i] in "Xx/@":
            i += 1
        check = self.parse_timecode(timecode = bpm[i:], line = line)
        if check is None:
            self.spreader.show_status("Problem parsing rate: {} (around {})".format(bpm, bpm[i:]))
            return True
        offset = check - box.order[line]
        location = box.order[line]
        bottom = box.order[-1]
        x = 0
        while x < rep:
            location += offset
            if location < 0.0 or location > bottom:
                break
            if location not in box.data:
                box.add_row(location)
            x += 1
        self.spreader.show_status("{} rows added every {}".format(x, human_duration(offset, 3)))
        self.changed = True
        return False

    _track_change_states = ["", "crap", "resume", "unknown", "track"]

    def _do_track(self, *, line):
        box = self.beater.beat_box
        datum = box.data[box.order[line]]
        got = datum.get("track-change","")
        if got == "":
            last = ""
            for i in range(line - 1, -1, -1):
                d = self.data[box.order[line]]
                last = d.get("track-change", "")
                if last != "":
                    got = last
                    break

        idx = self._track_change_states.index(got)
        idx += 1
        if idx >= len(self._track_change_states):
            idx = 0
        datum["track-change"] = self._track_change_states[idx]
        self._need_propagate = True
        self.spreader.refresh_line(line)
        self.changed = True
        return True

    _chord_options = ["", "chord", "rest", "resume"]
    _chord_mode = "progression"
    _chord_selections = 2

    def _do_chord(self, *, line):
        box = self.beater.beat_box
        datum = box.data[box.order[line]]

        if self._chord_mode == "progression":
            got = datum.get("chord-change", "")
            idx = self._chord_options.index(got)
            idx += 1
            if idx >= len(self._chord_options):
                idx = 0
            datum["chord-change"] = self._chord_options[idx]
        elif self._chord_mode == "selection":
            idx = datum.get("chord-selection", 0)
            if idx == "":
                idx = -1
            else:
                idx = int(idx)
            idx += 1
            if idx >= self._chord_selections:
                idx = 0
            datum["chord-selection"] = idx

        datum["chord_ui"] = "??"
        self.spreader.refresh_line(line)
        self._need_propagate = True
        self.changed = True
        return True

    def _do_chord_backwards(self, *, line):
        box = self.beater.beat_box
        datum = box.data[self.order[line]]

        if self._chord_mode == "progression":
            return self._do_chord(line=line)
        elif self._chord_mode == "selection":
            idx = datum.get("chord-selection", 0)
            if idx == "":
                idx = -1
            else:
                idx = int(idx)
            idx -= 1
            if idx < 0:
                idx = self._chord_selections - 1
            datum["chord-selection"] = idx

        datum["chord_ui"] = "??"
        self.spreader.refresh_line(line)
        self._need_propagate = True
        self.changed = True
        return True

    def _do_jump(self, timecode, *, line):
        location = self.parse_timecode(timecode=timecode, line=line)
        if location is None:
            self.spreader.show_status("Invalid timecode or offset: {}".format(timecode))
        else:
            self._perform_jump(location)

    def _perform_jump(self, location, callback=None, callback_args={}):
        box = self.beater.beat_box
        newline = None
        if location in box.data:
            try:
                newline = box.order.index(location)
            except ValueError:
                box.update_order()
                newline = box.order.index(location)
        if newline is None:
            self.changed = True
            was_c_playing = self.beater.beat_player.playing
            box.add_row(location)
            if was_c_playing:
                self.beater.beat_player.pause()
            if callback is not None:
                callback(location, **callback_args)
            self._do_idle()
            newline = box.order.index(location)
            self.beater.beat_player.seek(newline)
            if was_c_playing:
                self.beater.beat_player.play()
        self.spreader.move_to(newline)

    def _do_lyric(self, lyric, *, line):
        box = self.beater.beat_box
        if line < 0 or lyric is None:
            return box.data[box.order[-line]].get("lyric","")
        box.data[box.order[line]]["lyric"] = lyric.strip()
        box.changed = True
        return True

    def _do_line_mark(self, *, line):
        box = self.beater.beat_box
        box.changed = True
        lyric = box.data[box.order[line]].get("lyric", "")
        if lyric == "":
            box.data[box.order[line]]["lyric"] = "/"
            return
        if lyric[0] == '/':
            box.data[box.order[line]]["lyric"] = "\\" + box.data[box.order[line]]["lyric"][1:]
        elif lyric[0] == '\\':
            box.data[box.order[line]]["lyric"] = box.data[box.order[line]]["lyric"][1:]
        else:
            box.data[box.order[line]]["lyric"] = "/" + box.data[box.order[line]]["lyric"]
        return True

    def _do_mark(self, mark, *, line):
        box = self.beater.beat_box
        if line < 0 or mark is None:
            return box.data[box.order[-line]].get("mark","")
        box.data[box.order[line]]["mark"] = mark
        self.changed = True
        return True

    def _do_clone_up(self, *, line):
        self._do_clone(line, -1)

    def _do_clone_down(self, *, line):
        self._do_clone(line, +1)

    def _do_clone(self, line, dir = 1):
        box = self.beater.beat_box
        base = box.order[line]
        if line + 1 == len(box.order):
            return False
        next = box.order[line+dir]
        offset = (next - base) / 2
        if offset < 0.0005 and offset > -0.0005:
            return False
        loc = base + offset
        self._perform_jump(loc, callback=box.clone_goodies, callback_args={"from_loc":base})

    def _do_nudge(self, offset, *, line):
        return self._perform_nudge(offset, line)

    def _do_nudge_next(self, offset, *, line):
        self._perform_nudge(offset, line + 1)
        self.spreader.move_to(line)
        return False


    def _perform_nudge(self, offset, line):
        box = self.beater.beat_box
        if offset == "":
            return False
        if offset is None or line < 0:
            return self.last_nudge
        if line <= 0 or line >= len(box.order) -1:
            self.spreader.show_status("Can't nudge top or bottom.")
            return False
        orig_offset = offset
        try:
            offset = float(offset)
        except ValueError:
            self.spreader.show_status("Invalid offset: {}".format(offset))
            return False
        base = box.order[line]
        location = base + offset
        if line > 0 and box.order[line-1] > location:
            self.spreader.show_status("Invalid offset: {}; can't go over {}".format(offset, box.order[line - 1]))
            return False
        if line < len(box.order) - 1 and box.order[line+1] < location:
            self.spreader.show_status("Invalid offset: {}; can't go under {}".format(offset, box.order[line + 1]))
            return False
        self.last_nudge = orig_offset
        self._perform_jump(location, callback=box.swap_goodies, callback_args={"from_loc": box.order[line]})
        line_now = line
        if offset < 0:
            line_now += 1
        self._do_delete(line=line_now)
        self.spreader.move_to(line+1)
        self._do_idle()
        self.spreader.move_to(line)
        return False

    def _do_shift_up(self, *, line):
        self._do_shift(line, -1)

    def _do_shift_down(self, *, line):
        self._do_shift(line, +1)

    def _do_shift(self, line, dir = 1):
        box = self.beater.beat_box
        base = box.order[line]
        if line + 1 == len(box.order):
            return
        next = box.order[line+dir]
        offset = (next - base) / 2
        if offset < 0.0005 and offset > -0.0005:
            return
        loc = base + offset
        self._perform_jump(loc, callback=box.swap_goodies, callback_args={"from_loc":base})

    def _do_swap_up(self, *, line):
        box = self.beater.beat_box
        if line > 0:
            box.swap_goodies(box.order[line], box.order[line - 1])
            self.spreader.move_to(line - 1)
            self._do_idle()
            self.spreader.move_to(line)

    def _do_swap_down(self, *, line):
        box = self.beater.beat_box
        if line < len(box.order) - 1:
            box.swap_goodies(box.order[line], box.order[line + 1])
            self.spreader.move_to(line + 1)
            self._do_idle()
            self.spreader.move_to(line)

    def _do_export_midi(self, filename, *, line):
        if filename is None or len(filename.strip()) == 0:
            self.beater.export_midi(self.beater.project_dir / "{}.midi".format("export"))
        else:
            self.beater.export_midi(self.beater.project_dir / filename)
        return False

    def _do_export_lily(self, filename, *, line):
        if filename is None or len(filename.strip()) == 0:
            self.beater.export_ly(self.beater.project_dir / "{}.ly".format("export"))
        else:
            self.beater.export_ly(self.beater.project_dir / filename)
        return False

    def _do_export_txt(self, filename, *, line):
        if filename is None or len(filename.strip()) == 0:
            self.beater.export_txt(self.beater.project_dir / "{}.txt".format("export"))
        else:
            self.beater.export_txt(self.beater.project_dir / filename)
        return False

    def _do_lead_rest(self, *, line):
        box = self.beater.beat_box
        self.changed = True
        datum = box.data[box.order[line]]
        datum["note"] = ""
        datum["note_ui"] = "-"
        return True

    def _do_up_note(self, *, line):
        box = self.beater.beat_box
        datum = box.data[box.order[line]]
        track_id = datum.get("track_id", -1)
        got = datum.get("note","")
        if got == "":
            got = self.last_note
            if got == "" or got is None:
                song_stuff = self.song_data.get(track_id)
                got = song_stuff["key_note"]
        else:
            got += 1
            if got >= 128:
                got -= 120
        got = abs(got) % 128
        self.last_note = got
        datum["note"] = got
        datum["note_ui"] = getLyForMidiNote(got)
        self.changed = True
        return True

    def _do_down_note(self, *, line):
        box = self.beater.beat_box
        datum = box.data[box.order[line]]
        track_id = datum.get("track_id", -1)
        got = datum.get("note","")
        if got == "":
            got = self.last_note
            if got == "" or got is None:
                song_stuff = self.song_data.get(track_id)
                got = song_stuff["key_note"]
        else:
            got -= 1
            if got < 0:
                got += 120
        got = abs(got) % 128
        self.last_note = got
        datum["note"] = got
        datum["note_ui"] = getLyForMidiNote(got)
        self.changed = True
        return True

    def _do_up_octave(self, *, line):
        box = self.beater.beat_box
        datum = box.data[box.order[line]]
        track_id = datum.get("track_id", -1)
        got = datum.get("note","")
        if got == "":
            got = self.last_note
            if got == "" or got is None:
                song_stuff = box.song_data.get(track_id)
                got = song_stuff["key_note"]
        else:
            got += 12
            if got >= 128:
                got -= 120
        got = abs(got) % 128
        self.last_note = got
        datum["note"] = got
        datum["note_ui"] = getLyForMidiNote(got)
        self.changed = True
        return True

    def _do_down_octave(self, *, line):
        box = self.beater.beat_box
        datum = box.data[box.order[line]]
        track_id = datum.get("track_id", -1)
        got = datum.get("note","")
        if got == "":
            got = self.last_note
            if got == "" or got is None:
                song_stuff = box.song_data.get(track_id)
                got = song_stuff["key_note"]
        else:
            got -= 12
            if got < 0:
                got += 120
                if got >= 128:
                    got -= 12
        got = abs(got) % 128
        self.last_note = got
        datum["note"] = got
        datum["note_ui"] = getLyForMidiNote(got)
        self.changed = True
        return True

    def _do_up_on_scale(self, *, line):
        box = self.beater.beat_box
        datum = box.data[box.order[line]]
        track_id = datum.get("track_id", -1)
        song_stuff = box.song_data.get(track_id)
        if song_stuff is None:
            song_stuff = box.find_song_data(track_id)
        got = datum.get("note","")
        if got == "":
            got = self.last_note
        if got == "" or got is None:
            got = song_stuff["key_note"]

        key_note = song_stuff["key_note"]
        adjusted_for_key = got
        while adjusted_for_key < key_note:
            adjusted_for_key += 12
        while adjusted_for_key >= key_note + 12:
            adjusted_for_key -= 12
        offset_from_key = adjusted_for_key - key_note
        trial = None
        for scale_offset in song_stuff["scale_parsed"]:
            if scale_offset > offset_from_key:
                trial = scale_offset
                break
        if trial is None:
            trial = song_stuff["scale_parsed"][0] + 12
        trial = trial + key_note + got - adjusted_for_key
        if trial < 0:
            trial += 120
        if trial >= 120:
            trial -= 120
        self.last_note = trial
        datum["note"] = trial
        datum["note_ui"] = getLyForMidiNote(trial)
        self.changed = True
        return True

    def _do_down_on_scale(self, *, line):
        box = self.beater.beat_box
        datum = box.data[box.order[line]]
        track_id = datum.get("track_id", -1)
        song_stuff = box.song_data.get(track_id)
        if song_stuff is None:
            song_stuff = box.find_song_data(track_id)
        got = datum.get("note","")
        if got == "":
            got = self.last_note
        if got == "" or got is None:
            got = song_stuff["key_note"]

        key_note = song_stuff["key_note"]
        adjusted_for_key = got
        while adjusted_for_key < key_note:
            adjusted_for_key += 12
        while adjusted_for_key >= key_note + 12:
            adjusted_for_key -= 12
        offset_from_key = adjusted_for_key - key_note
        trial = None
        for scale_offset in song_stuff["scale_parsed"][::-1]:
            if scale_offset < offset_from_key:
                trial = scale_offset
                break
        if trial is None:
            trial = song_stuff["scale_parsed"][-1] - 12
        trial = trial + key_note + got - adjusted_for_key
        if trial < 0:
            trial += 120
        if trial >= 120:
            trial -= 120
        self.last_note = trial
        datum["note"] = trial
        datum["note_ui"] = getLyForMidiNote(trial)
        self.changed = True
        return True

    def _do_sample_note(self, *, line):
        box = self.beater.beat_box
        datum = box.data[box.order[line]]
        self.beater.beat_player.set_lead_note(datum["note"] )
        self.spreader.show_status("Sampling note...")
        self.ui.get_key(timeout=0.2)
        self.beat_player.set_lead_note(None)
        self.spreader.show_status("Done...")
        return False

    def _do_automate(self, *, line):
        Automate().process(self)
        return False

    def _do_backup(self, *, line):
        box = self.beater.beat_box
        box.backup()
        self.spreader.show_status("Backup complete.")
        return True

    def prepare_keys(self, spreader):
        self.spreader = spreader
        spreader.register_idle(self._do_idle)
        spreader.on_exit(self.save)
        """ Key commands:
            ^J : Go to line and repeat
            ^N : shift down by half
            ^P : shift up by half
            '@' : jump to or create by timecode
            '.' : mark current audio location as a beat
            '"' / 'L' / 'l' : enter lyrics for row
                - Start with '/' for new line.
                - Start with '\\' for new row
            "'" - Take lead note up an octave
            "," - take lead note down an octave
            "]" - shift note up one by scale
            "[" - shift note down one by scale
            "}" - shift note up by one half-tone
            "{" - shift note down by one half-tone
            "/" : change the line separator indicator in the lyrics
            ";" - sample the lead note
            ":" : repeat the marked section
            'a' / 'A' : automate
            'C' / 'c' : change the chord
            'D' / 'd' : delete row
            'E' / 'e' : export to MIDI
            'H' / 'h' : play just the MIDI
            'j' : shift down by half
            'k' : shift up by half
            'J' : clone down by half
            'K' : clone up by half
            'M' / 'm' : set a marker
                - Start with '*' or '-' for a "point" marker (currently normal markers unimplemented)
            'N' / 'n' : nudge explicitly
            'P' / 'p' : play Audio + MIDI
            'R' / 'r' : set note to REST
            'S' / 's' : save a backup
            'T' / 't' : mark as start of track
            'W' : swap with above line
            'w' : swap with below line
            'X' / 'x' : export as plain text
            'Y' / 'y' : export to Lilypond

        """
        # spreader.register_key(self._do_play, "P", "p", arg="...slow", prompt="Playing...",
        #                     description="Play this file.")
        # spreader.register_key(self._do_play_segment, "^J",
        #                       description="Go to and repeat")
        # spreader.register_key(self._do_tap, ".",
        #                       description="Mark a beat")
        # spreader.register_key(self._do_delete, "D", "d",
        #                       description="delete a row")
        # spreader.register_key(self._do_jump, "@", arg="?str", prompt="What time code?",
        #                       description="Jump to or create by timecode")
        # spreader.register_key(self._do_track, "t", "T",
        #                       description="Mark as start of track")
        # spreader.register_key(self._do_lyric, '"', "L", 'l', arg="?str", prompt="Lyric?", query=True,
        #                       description="Enter lyric for this note")
        # spreader.register_key(self._do_mark, "M", "m", arg="?str", prompt="How would you like to mark it?",query=True,
        #                       description="Mark this segment with some text.")
        # spreader.register_key(self._do_chord, "c",
        #                       description="Change the chord")
        # spreader.register_key(self._do_chord_backwards, "C",
        #                       description="Change the chord")
        # spreader.register_key(self._do_play_chords, "h", "H",
        #                       description="Play just the chords")
        # spreader.register_key(self._do_shift_down, "j","^N",
        #                       description="Shift this note half way between the current spot and the one below it.")
        # spreader.register_key(self._do_shift_up, "k", "^P",
        #                       description="Shift this note half way between the current spot and the one above it.")
        # spreader.register_key(self._do_clone_down, "J",
        #                       description="Clone this note half way between the current spot and the one below it.")
        # spreader.register_key(self._do_clone_up, "K",
        #                       description="Clone this note half way between the current spot and the one above it.")
        spreader.register_key(self._do_export_midi, "e", "E", arg="?str",
                            prompt="Export to MIDI (^G to cancel; ENTER to name 'export.midi'.]",
                            description="Export to MIDI")
        spreader.register_key(self._do_export_lily, "y", "Y", arg="?str",
                            prompt="Export to Lilypond (^G to cancel; ENTER to name 'export.ly'.]",
                            description="Export to Lilypond file")
        spreader.register_key(self._do_export_txt, "x", "X", arg="?str",
                            prompt="Export to plain text  (^G to cancel; ENTER to name 'export.txt'.]",
                            description="Export to text file")
        # spreader.register_key(self._do_backup, "S", "s", arg="...slow", prompt="Backing up...",
        #                       description="Save a backup of the song data")
        # spreader.register_key(self._do_line_mark, "/",
        #                       description="change the line separator indicator in the lyrics")
        # spreader.register_key(self._do_up_octave, "'",
        #                       description="Push the lead note up an octave")
        # spreader.register_key(self._do_down_octave, ",",
        #                       description="Push the lead note down an octave")
        # spreader.register_key(self._do_up_note, "}",
        #                       description="Push the lead note up an octave")
        # spreader.register_key(self._do_down_note, "{",
        #                       description="Push the lead note down an octave")
        # spreader.register_key(self._do_up_on_scale, "]",
        #                       description="Push the lead note up an octave")
        # spreader.register_key(self._do_down_on_scale, "[",
        #                       description="Push the lead note down an octave")
        # spreader.register_key(self._do_sample_note, ";",
        #                       description="Sample the current lead note")
        # spreader.register_key(self._do_lead_rest, "R", "r",
        #                       description="Set lead note to rest")
        # spreader.register_key(self._do_nudge, "n", arg="?str", prompt="Nudge the current line up or down in seconds:",
        #                       description="Nudge this note explicitly between the current spot and the two around it it.")
        # spreader.register_key(self._do_nudge_next, "N", arg="?str", prompt="Nudge the next line up or down in seconds:",
        #                       description="Nudge the next row (making current note longer/shorter).")
        # spreader.register_key(self._do_repeat_mark, ":",
        #                       description="Repeat the marked section")
        # spreader.register_key(self._do_beat_repeat, "B", "b", arg="?str",
        #                       prompt="How many and at what rate? (like: 6x120bpm or 3x2@120bpm")
        # spreader.register_key(self._do_swap_up, "W",
        #                       description="Swap data with line above")
        # spreader.register_key(self._do_swap_down, "w",
        #                       description="Swap data with line below")
        # spreader.register_key(self._do_automate, "a", "A",
        #                       description="Automate finding the notes")


    def parse_timecode(self, *, timecode, line):
        if timecode is None or timecode.strip() == "":
            return None
        box = self.beater.beat_box
        timecode = timecode.lower().strip()
        if ":" in timecode:
            location = from_human_duration(timecode)
        elif timecode.endswith("beat") or timecode.endswith("beats"):
            if timecode.endswith("beat"):
                timecode = timecode[:-4].strip()
            else:
                timecode = timecode[:-5].strip()
            negate = 1
            if timecode.startswith("-"):
                negate = -1
                timecode = timecode[1:].strip()
            trial = 1
            if len(timecode) > 0:
                try:
                    trial = float(timecode)
                except ValueError:
                    return None
            next = line+1
            if next == len(self.order):
                next -= 1
            offset = self.order[next]  - self.order[line]
            location = self.order[line] + offset * trial * negate

        elif timecode.endswith("bpm") or timecode.endswith("b"):
            if timecode.endswith("b"):
                timecode = timecode[:-1].strip()
            else:
                timecode = timecode[:-3].strip()
            negate = 1
            if timecode.startswith("-"):
                negate = -1
                timecode = timecode[1:]
            if "@" in timecode:
                s = timecode.split("@", 1)
            elif "/" in timecode:
                s = timecode.split("/", 1)
            elif "x" in timecode:
                s = timecode.split("x", 1)
            else:
                s = ["1", timecode]
            try:
                offset = mido.bpm2tempo(int(s[-1].strip())) / 1000000 * int(s[0].strip()) * negate

            except ValueError:
                return None
            location = box.order[line] + offset

        else:
            try:
                offset = float(timecode)
            except ValueError:
                return None
            location = box.order[line] + offset
        return location

    def save(self):
        self.beater.beat_box.save()

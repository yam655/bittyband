import json
from configparser import ConfigParser
from pathlib import Path

from ..utils.time import human_duration, filename_iso_time
from ..utils.cmdutils import parse_chords, parse_sequence, parse_scale
from ..midinames import getLyForMidiNote


class BeatBox:
    def __init__(self, config, import_file, bits):
        self.import_file = import_file
        self.project_dir = Path(config["instance"]["project_dir"])
        self.beats = []
        self.notes = []
        self.changed = False
        from_dict = {}
        self.bits = bits
        self.json_file = Path(bits["metadata"]).with_suffix(".json")
        if self.json_file.exists() and self.json_file.stat().st_size > 0:
            with self.json_file.open() as inf:
                from_dict = json.load(inf)
        if from_dict:
            self.beats = from_dict.get('beats', self.beats)
            self.notes = from_dict.get('notes', self.notes)
        self.metadata = ConfigParser(inline_comment_prefixes = None)
        self.metadata.read(bits["metadata"])

    def toDict(self):
        ret = {}
        ret['notes'] = self.notes
        ret['beats'] = self.beats
        return ret

    def new_beat(self, location):
        self.changed = True
        beat = { 'start-loc': location, 'notes':[] }
        self.beats.append(beat)
        return beat

    def add_note(self, location, note, vel, prev_note):
        self.changed = True
        if len(self.notes) > 0 and self.notes[-1]["midi"] == int(note):
            return self.notes[-1]
        r = {'location':location, 'midi': int(note), 'velocity': float(vel)}
        self.notes.append(r)
        return r

    # def clone_goodies(self, to_loc, from_loc):
    #     self.changed = True
    #     data_from = self.data[from_loc]
    #     data_to = self.data[to_loc]
    #     for k in data_from.keys():
    #         if k == "location":
    #             continue
    #         data_to[k] = data_from[k]
    #
    # def swap_goodies(self, to_loc, from_loc):
    #     self.changed = True
    #     data_from = self.data[from_loc]
    #     data_to = self.data[to_loc]
    #     for k in data_from.keys():
    #         if k == "location":
    #             continue
    #         data_to[k], data_from[k] = data_from[k], data_to.get(k,"")

    # def add_row(self, location, *, mark="", lyric="", note=""):
    #     if location in self.data:
    #         raise IndexError("location {} already present in data".format(location))
    #     if self.order and location > self.order[-1]:
    #         if int(location) != int(self.order[-1]):
    #             raise IndexError("location {} can't be bigger than file: {}".format(location, self.order[-1]))
    #     if location < 0:
    #         raise IndexError("location {} can't be less than zero".format(location))
    #     note_ui = "-"
    #     if note != "":
    #         note_ui = getLyForMidiNote(note)
    #     row = {"location":location, "mark":mark, "lyric":lyric, "track_ui":"", "chord_ui":"",
    #            "chord-change":"", "chord-selection": 0, "track-change":"", "note":note, "note_ui":note_ui}
    #     self.data[location]  = row
    #     return row
    #
    # def update_order(self):
    #     self.order = list(self.data.keys())
    #     self.order.sort()
    #     self.save()

    def save(self):
        if not self.changed:
            return
        with self.json_file.open("w") as outf:
            json.dump(self.toDict(), outf)
        with open(str(self.bits["metadata"]), 'w') as meta:
            self.metadata.write(meta)

    # def backup(self):
    #     dsecs = self.json_file.stat().st_mtime
    #     meta_file = Path(self.bits["metadata"])
    #     msecs = meta_file.stat().st_mtime
    #     secs = max(dsecs, msecs)
    #     suffix = filename_iso_time(secs)
    #     backup_data = self.json_file.with_name("{}-{}{}".format(self.json_file.stem, suffix, self.json_file.suffix))
    #     backup_meta = meta_file.with_name("{}-{}{}".format(meta_file.stem, suffix, meta_file.suffix))
    #     with backup_data.open("w") as outf:
    #         json.dump(self, outf)
    #     with backup_meta.open('w') as meta:
    #         self.metadata.write(meta)

    # def set_defaults_for_song(self, song):
    #     basis = self.find_song_data(song)
    #     out = self.metadata[str(song)]
    #     out["bpm"] = str(basis.get("bpm", "120"))
    #     out["lily_key"] = basis.get("lily_key", r"g \major")
    #     out["copyright"] = basis.get("copyright", "")
    #     if "tagline" in basis:
    #         out["tagline"] = basis["tagline"]
    #     out["poet"] = basis.get("poet", "")
    #     out["time"] = basis.get("time", "4/4")
    #     out["key"] = basis.get("key", "67")
    #     out["scale"] = basis.get("scale", "1 2 3 4 5 6 7")
    #     out["lead_instrument"] = str(basis.get("lead_instrument","0"))
    #     out["pad_instrument"] = str(basis.get("pad_instrument","0"))
    #     out["pad_offset"] = str(basis.get("pad_offset","-12"))
    #     out["pad_chords"] = basis.get("pad_chords", "1")
    #     out["pad_sequence"] = basis.get("pad_sequence", "I")
    #     out["pad_velocity"] = str(basis.get("pad_velocity", 64))
    #     out["pad_selections"] = basis.get("pad_selections","")

    # def need_propagate(self):
    #     return self._need_propagate
    #
    # def propagate(self):
    #     self._need_propagate = False
    #     last_track = "unknown"
    #     last_chord = "rest"
    #     self._tracks = []
    #     chord_idx = -1
    #     if str(0.0) in self.metadata:
    #         this_track = self.find_song_data(0.0)
    #     else:
    #         this_track = self.find_song_data(-1)
    #     self.song_data[-1] = this_track
    #     chord_values = this_track["pad_chord_seq"]
    #     chord_names = this_track.get("pad_sequence","").split("-")
    #     chord_selections = this_track.get("pad_selections","").split()
    #     chord_data = this_track.get("pad_chords_parsed",{})
    #     last_mark = -1
    #     idx = -1
    #     for location in self.order:
    #         idx += 1
    #         datum = self.data.get(location)
    #         next_track = datum.get("track-change", "")
    #         next_chidx = None
    #         next_chord = None
    #         if self._chord_mode == "progression":
    #             next_chord = datum.get("chord-change", "")
    #         else:
    #             next_chidx = datum.get("chord-selection", 0)
    #         mark = datum.get("mark","")
    #         if mark != "":
    #             if mark[0] not in ".-*@+=: ":
    #                 last_mark = idx
    #         datum["mark_idx"] = last_mark
    #         if next_track == "":
    #             if last_track == "unknown":
    #                 datum["track_ui"] = "  ?"
    #                 datum["track_id"] = -1
    #             elif last_track == "track":
    #                 datum["track_id"] = self._tracks[-1]
    #                 datum["track_ui"] = " {:02d}".format(len(self._tracks))
    #             elif last_track == "crap":
    #                 datum["track_ui"] = "  -"
    #                 datum["track_id"] = -1
    #         elif next_track == "unknown":
    #             datum["track_ui"] = "? ?"
    #             datum["track_id"] = -1
    #             last_track = next_track
    #         elif next_track == "track":
    #             last_track = next_track
    #             self._tracks.append(datum["location"])
    #             datum["track_id"] = self._tracks[-1]
    #             datum["track_ui"] = "*{:02d}".format(len(self._tracks))
    #             this_track = self.find_song_data(self._tracks[-1])
    #             self.song_data[self._tracks[-1]] = this_track
    #             chord_values = this_track["pad_chord_seq"]
    #             chord_names = this_track.get("pad_sequence", "").split("-")
    #             chord_selections = this_track.get("pad_selections", "").split()
    #             chord_data = this_track.get("pad_chords_parsed", {})
    #         elif next_track == "crap":
    #             last_track = next_track
    #             datum["track_ui"] = "- -"
    #             datum["track_id"] = -1
    #         elif next_track == "resume":
    #             if len(self._tracks) == 0:
    #                 datum["track_ui"] = "/ ?"
    #                 datum["track_id"] = -1
    #                 last_track = "unknown"
    #             else:
    #                 datum["track_id"] = self._tracks[-1]
    #                 datum["track_ui"] = "+{:02d}".format(len(self._tracks))
    #                 last_track = "track"
    #
    #         if next_chord == None:
    #             if next_chidx == "":
    #                 ch = "r"
    #                 if 0 <= chord_idx < len(chord_selections) -1:
    #                     ch = chord_selections[chord_idx]
    #                 if ch == "" or ch == "_" or ch == '"':
    #                     ch = "r"
    #                 if ch == "r":
    #                     datum["chord_value"] = tuple()
    #                 else:
    #                     datum["chord_value"] = None
    #                 datum["chord_ui"] = " " + ch
    #             elif isinstance(next_chidx, (int, float)) or next_chidx.isnumeric():
    #                 idx = next_chidx
    #                 if isinstance(next_chidx, (str, float)):
    #                     idx = int(next_chidx)
    #                 ch = None
    #                 if len(chord_selections) > 0:
    #                     ch = chord_selections[idx % len(chord_selections)]
    #                 if ch is None:
    #                     datum["chord_ui"] = " "
    #                     datum["chord_value"] = tuple()
    #                 elif ch == "" or ch == "_" or ch == '"':
    #                     idx = chord_idx
    #                     ch = chord_selections[idx % len(chord_selections)]
    #                     if ch == "r":
    #                         datum["chord_ui"] = " r"
    #                     else:
    #                         datum["chord_ui"] = " " + ch
    #                     datum["chord_value"] = None
    #                 elif ch == "r":
    #                     chord_idx = idx
    #                     datum["chord_ui"] = "-r"
    #                     datum["chord_value"] = tuple()
    #                 else:
    #                     chord_idx = idx
    #                     datum["chord_ui"] = ">"+ ch
    #                     datum["chord_value"] = chord_data[ch]
    #             else:
    #                 raise ValueError(repr(next_chidx))
    #         elif next_chord == "":
    #             if last_chord == "chord":
    #                 datum["chord_value"] = None
    #                 datum["chord_ui"] = " " + chord_names[chord_idx]
    #             elif last_chord == "rest":
    #                 datum["chord_value"] = None
    #                 datum["chord_ui"] = " : "
    #         elif next_chord == "chord":
    #             last_chord = next_chord
    #             chord_idx += 1
    #             if chord_idx >= len(chord_values):
    #                 chord_idx = 0
    #             datum["chord_value"] = chord_values[chord_idx]
    #             datum["chord_ui"] = ">" + chord_names[chord_idx]
    #         elif next_chord == "rest":
    #             last_chord = next_chord
    #             datum["chord_value"] = tuple()
    #             datum["chord_ui"] = "-:-".format(len(self._tracks))
    #         elif next_chord == "resume":
    #             datum["chord_value"] = chord_values[chord_idx]
    #             datum["chord_ui"] = "}" + chord_names[chord_idx]
    #             last_chord = "chord"
    #     self.metadata["audio"]["tracks"] = str(len(self._tracks))
    #     self._chord_selections = 0
    #     old_mode = self._chord_mode
    #     self._chord_mode = "progression"
    #     for t in self._tracks:
    #         if str(t) not in self.metadata:
    #             self.metadata.add_section(str(t))
    #             self.set_defaults_for_song(t)
    #         if self.data[t].get("mark","") == "":
    #             self.data[t]["mark"] = "Track @{}".format(human_duration(t,0))
    #         self.metadata[str(t)]["title"] = self.data[t]["mark"]
    #         selection = self.metadata[str(t)].get("pad_selections","")
    #         if selection != "":
    #             c = len(selection.strip().split())
    #             if c != 0:
    #                 self._chord_mode = "selection"
    #                 if c > self._chord_selections:
    #                     self._chord_selections = c
    #     if old_mode != self._chord_mode:
    #         self.propagate()

    def get_order(self):
        return list(range(len(self.beats)))

    def get_line(self, what, max_len):
        return str(what)
        # datum = self.data[what]
        # padout=max_len - 25
        # marklen = int(padout // 3)
        # lyrlen = int(padout * 2 // 3)
        # loc = human_duration(datum["location"], floor=3)
        # lyrlen -= len(loc) - 9
        # return "{human_time} {note_ui:5.5} {lyric:{lyrlen}.{lyrlen}} {chord_ui:5.5} {track_ui: >3.3} {mark:{marklen}.{marklen}}".format(
        #     marklen=marklen, lyrlen=lyrlen,
        #     human_time=loc, **datum)

    # def find_song_data(self, song):
    #     ret = {}
    #     ret.update(self.config["preset_0"])
    #     if str(song) in self.metadata:
    #         song_meta = self.metadata[str(song)]
    #     else:
    #         song_meta = {}
    #     for k in song_meta.keys():
    #         if song_meta[k].strip() != "":
    #             ret[k] = song_meta[k]
    #     ret["key_note"] = int(ret.get("key","60"))
    #     ret["scale_parsed"] = parse_scale(ret.get("scale", "1 2 3 4 5 6 7").strip())
    #     ret["lead_instrument"] = int(ret.get("lead_instrument","0"))
    #     ret["pad_instrument"] = int(ret.get("pad_instrument","0"))
    #     ret["pad_offset"] = int(ret.get("pad_offset","-12"))
    #     ret["pad_chords_parsed"] = parse_chords(ret.get("pad_chords", "1"), ret["scale_parsed"], ret["key_note"] + ret["pad_offset"])
    #     ret["pad_chord_seq"] = parse_sequence(ret.get("pad_sequence", "I"), ret["pad_chords_parsed"])
    #     ret["pad_velocity"] = int(ret.get("pad_velocity", 64))
    #     ret["lead_velocity"] = int(ret.get("lead_velocity", 64))
    #     return ret

    # def clean(self):
    #     for r in self.data.values():
    #         r.setdefault("lyric", "")
    #         r.setdefault("chord-change", "")
    #         r.setdefault("chord-selection", 0)
    #         r.setdefault("track-change", "")
    #         r.setdefault("note", "")
    #         note = r.get("note", "")
    #         if note == "":
    #             r["note_ui"] = "-"
    #         else:
    #             r["note_ui"] = getLyForMidiNote(note)
    #
    #     self.propagate()



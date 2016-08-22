# -*- coding: utf-8 -*-

import sublime
import sublime_plugin
import os
import re
import Default

DEBUG = False


class AnsiCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        v = self.view
        if v.settings().get("ansi_enabled"):
            return
        v.settings().set("ansi_enabled", True)
        v.settings().set("color_scheme", "Packages/User/SublimeANSI/ansi.tmTheme")
        v.settings().set("draw_white_space", "none")

        DEFAULT = -1
        BLACK = 0
        RED = 1
        GREEN = 2
        YELLOW = 3
        BLUE = 4
        MAGENTA = 5
        CYAN = 6
        WHITE = 7

        COLOR_MAP = {
          DEFAULT: 'default',
          BLACK: 'black',
          RED: 'red',
          GREEN: 'green',
          YELLOW: 'yellow',
          BLUE: 'blue',
          MAGENTA: 'magenta',
          CYAN: 'cyan',
          WHITE: 'white'
        }

        bold = False
        color = WHITE
        bg_color = DEFAULT
        text = ''
        start = 0
        spans = []
        offset = 0

        s = v.substr(sublime.Region(0, v.size()))
        for m in re.finditer(r'\x1b\[([\d;]*)m', s):
          if start != m.start():
            spans.append((start - offset, m.start() - offset, bold, color, bg_color))
            text += s[start:m.start()]

          codes = m.group(1).split(';')
          if codes != ['']:
            for code in map(int, codes):
              if code == 0:
                bold = False
                color = WHITE
                bg_color = DEFAULT
              elif code == 1:
                bold = True
              elif 30 <= code <= 37:
                color = code - 30
              elif 40 <= code <= 47:
                bg_color = code - 40
          else:
            bold = False
            color = WHITE
            bg_color = DEFAULT

          start = m.end()
          offset += len(m.group())

        if start != len(s):
          spans.append((start - offset, len(s) - offset, bold, color, bg_color))
          text += s[start:]

        # Removing ansi escape codes
        ansi_codes = v.find_all(r'\x1b\[([\d;]*)m')
        ansi_codes.reverse()
        v.set_scratch(True)
        v.set_read_only(False)
        for r in ansi_codes:
            v.erase(edit, r)
        v.set_read_only(True)

        settings = sublime.load_settings("ansi.sublime-settings")
        ANSI_FG = settings.get("ANSI_FG", {})
        ANSI_BG = settings.get("ANSI_BG", {})
        for s in spans:
          if COLOR_MAP[s[3]] not in ANSI_FG or COLOR_MAP[s[4]] not in ANSI_BG:
            continue
          ansi_scope = COLOR_MAP[s[3]] + ("_light_" if s[2] else "_") + COLOR_MAP[s[4]]
          sum_regions = v.get_regions(ansi_scope) + [sublime.Region(s[0], s[1])]
          v.add_regions(ansi_scope, sum_regions, ansi_scope, '', sublime.DRAW_NO_OUTLINE)


class UndoAnsiCommand(sublime_plugin.WindowCommand):

    def run(self):
        view = self.window.active_view()
        view.settings().erase("ansi_enabled")
        view.settings().erase("color_scheme")
        view.settings().erase("draw_white_space")
        view.set_read_only(False)
        view.set_scratch(False)
        settings = sublime.load_settings("ansi.sublime-settings")
        for bg in settings.get("ANSI_BG", {}).keys():
            for fg in settings.get("ANSI_FG", {}).keys():
                ansi_scope = "{0}_{1}".format(fg, bg)
                view.erase_regions(ansi_scope)
        self.window.run_command("undo")


class AnsiEventListener(sublime_plugin.EventListener):

    def on_new_async(self, view):
        self.assign_event_listner(view)

    def on_load_async(self, view):
        self.assign_event_listner(view)

    def assign_event_listner(self, view):
        view.settings().add_on_change("CHECK_FOR_ANSI_SYNTAX", lambda: self.detect_syntax_change(view))
        if view.settings().get("syntax") == "Packages/SublimeANSI/ANSI.tmLanguage":
            view.run_command("ansi")

    def detect_syntax_change(self, view):
        if view.settings().get("syntax") == "Packages/SublimeANSI/ANSI.tmLanguage":
            view.run_command("ansi")
        elif view.settings().get("ansi_enabled"):
            view.window().run_command("undo_ansi")


class AnsiColorBuildCommand(Default.exec.ExecCommand):

    process_on_data = False
    process_on_finish = True

    @classmethod
    def update_build_settings(cls):
        print("updating ANSI build settings...")
        settings = sublime.load_settings("ansi.sublime-settings")
        val = settings.get("ANSI_process_trigger", "on_finish")
        if val == "on_finish":
            cls.process_on_data = False
            cls.process_on_finish = True
        elif val == "on_data":
            cls.process_on_data = True
            cls.process_on_finish = False

    def process_ansi(self):
        view = self.output_view
        if view.settings().get("syntax") == "Packages/SublimeANSI/ANSI.tmLanguage":
            view.settings().set("ansi_enabled", False)
            view.run_command('ansi')

    def on_data(self, proc, data):
        super(AnsiColorBuildCommand, self).on_data(proc, data)
        if self.process_on_data:
            self.process_ansi()

    def on_finished(self, proc):
        super(AnsiColorBuildCommand, self).on_finished(proc)
        if self.process_on_finish:
            self.process_ansi()


CS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>name</key><string>Ansi</string>
<key>settings</key><array><dict><key>settings</key><dict>
<key>background</key><string>%s</string>
<key>caret</key><string>%s</string>
<key>foreground</key><string>%s</string>
<key>gutter</key><string>%s</string>
<key>gutterForeground</key><string>%s</string>
<key>invisibles</key><string>%s</string>
<key>lineHighlight</key><string>%s</string>
<key>selection</key><string>%s</string>
</dict></dict>
%s</array></dict></plist>
"""

ANSI_SCOPE = "<dict><key>scope</key><string>{0}_{1}</string><key>settings</key><dict><key>background</key><string>{2}</string><key>foreground</key><string>{3}</string></dict></dict>\n"


def generate_color_scheme(cs_file):
    print("Regenerating ANSI color scheme...")
    cs_scopes = ""
    settings = sublime.load_settings("ansi.sublime-settings")
    for bg_name, bg_color in settings.get("ANSI_BG", {}).items():
        for fg_name, fg_color in settings.get("ANSI_FG", {}).items():
            cs_scopes += ANSI_SCOPE.format(fg_name, bg_name, bg_color, fg_color)
    g = settings.get("GENERAL")
    vals = [g['background'], g['caret'], g['foreground'], g['gutter'], g['gutterForeground'], g['invisibles'], g['lineHighlight'], g['selection'], cs_scopes]
    theme = CS_TEMPLATE % tuple(vals)
    with open(cs_file, 'w') as color_scheme:
        color_scheme.write(theme)


def plugin_loaded():
    ansi_cs_dir = os.path.join(sublime.packages_path(), "User", "SublimeANSI")
    if not os.path.exists(ansi_cs_dir):
        os.makedirs(ansi_cs_dir)
    cs_file = os.path.join(ansi_cs_dir, "ansi.tmTheme")
    if not os.path.isfile(cs_file):
        generate_color_scheme(cs_file)
    settings = sublime.load_settings("ansi.sublime-settings")
    AnsiColorBuildCommand.update_build_settings()
    settings.add_on_change("ANSI_COLORS_CHANGE", lambda: generate_color_scheme(cs_file))
    settings.add_on_change("ANSI_SETTINGS_CHANGE", lambda: AnsiColorBuildCommand.update_build_settings())
    for window in sublime.windows():
        for view in window.views():
           AnsiEventListener().assign_event_listner(view)

def plugin_unloaded():
    settings = sublime.load_settings("ansi.sublime-settings")
    settings.clear_on_change("ANSI_COLORS_CHANGE")
    settings.clear_on_change("ANSI_SETTINGS_CHANGE")

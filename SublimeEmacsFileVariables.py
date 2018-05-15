# Support for Emacs-style in-band "File Variables"

import sublime
import sublime_plugin
import re
import os

# http://www.gnu.org/software/emacs/manual/html_node/emacs/Specifying-File-Variables.html
FILEVARS_RE = r'.*-\*-\s*(.+?)\s*-\*-.*'
FILEVARS_HEAD_TAIL_LINE_COUNTS = 5

all_syntaxes = {}

def syntax_definition_paths():
    for f in sublime.find_resources("*.tmLanguage"):
        yield f
    for f in sublime.find_resources("*.sublime-syntax"):
        yield f

def discover_syntaxes():
    syntax_definition_paths = []
    for p in sublime.find_resources("*.sublime-syntax"):
        syntax_definition_paths.append(p)
    for p in sublime.find_resources("*.tmLanguage"):
        syntax_definition_paths.append(p)

    for path in syntax_definition_paths:
        mode = os.path.splitext(os.path.basename(path))[0].lower()
        all_syntaxes[mode] = path

    # Load custom mappings from the settings file
    package_settings = sublime.load_settings("SublimeEmacsFileVariables.sublime-settings")

    if package_settings.has("mode_mappings"):
        for mode, syntax in package_settings.get("mode_mappings").items():
            all_syntaxes[mode] = all_syntaxes[syntax.lower()]

    if package_settings.has("user_mode_mappings"):
        for mode, syntax in package_settings.get("user_mode_mappings").items():
            all_syntaxes[mode] = all_syntaxes[syntax.lower()]

discover_syntaxes()

# ------------------------------------------------------------

class SublimeEmacsFileVariables(sublime_plugin.ViewEventListener):
    @classmethod
    def is_applicable(cls, settings):
        # We don't want to be active in parts of Sublime's UI other than the actual code editor.
        return not settings.get('is_widget')

    def on_load(self):
        if self.view.file_name() == "":
            # We only care about views representing actual files on disk.
            return

        self.parse_filevars()

    def on_post_save(self):
        self.parse_filevars()

    def parse_filevars(self):
        view = self.view

        # Grab lines from beginning of view
        regionEnd = view.text_point(FILEVARS_HEAD_TAIL_LINE_COUNTS, 0)
        region = sublime.Region(0, regionEnd)
        lines = view.lines(region)
        # Get the last line in the file
        line = view.line(view.size())
        # Add the last N lines of the file to the lines list
        for i in range(1, FILEVARS_HEAD_TAIL_LINE_COUNTS):
            # Add the line to the list of lines
            lines.append(line)
            # Move the line to the previous line
            line = view.line(line.a - 1)

        # Look for filevars
        for line in lines:
            m = re.match(FILEVARS_RE, view.substr(line))
            if not m:
                continue

            filevars = m.group(1).lower()

            for component in filevars.split(';'):
                keyValueMatch = re.match(r'\s*(st-|sublime-text-|sublime-|sublimetext-)?(.+):\s*(.+)\s*', component)
                if not keyValueMatch:
                    continue

                key, value = keyValueMatch.group(2), keyValueMatch.group(3)
                keyIsSublimeSpecific = bool(keyValueMatch.group(1))

                if keyIsSublimeSpecific:
                    # Convert stringly-typed booleans to proper Python booleans.
                    if value.lower() == 'true':
                        value = True
                    elif value.lower() == 'false':
                        value = False

                    self.set(key, value)
                elif key == "coding":
                    # http://www.gnu.org/software/emacs/manual/html_node/emacs/Coding-Systems.html
                    # http://www.gnu.org/software/emacs/manual/html_node/emacs/Specify-Coding.html
                    match = re.match('(?:.+-)?(unix|dos|mac)', value)
                    if not match:
                        continue
                    value = match.group(1)
                    if value == "dos":
                        value = "windows"
                    if value == "mac":
                        value = "CR"
                    self.set("line_endings", value)
                elif key == "indent-tabs-mode":
                    if value == "nil" or value.strip == "0":
                        self.set('translate_tabs_to_spaces', True)
                    else:
                        self.set('translate_tabs_to_spaces', False)
                elif key == "mode":
                    if value in all_syntaxes:
                        self.set('syntax', all_syntaxes[value])
                elif key == "tab-width":
                    self.set('tab_size', int(value))

            # We found and processed a filevars line, so do not look for more.
            break

    def set(self, key, value):
        view = self.view
        #print("%s: setting view setting '%s' to '%s'" % (self.__class__.__name__, key, value))
        if key == "line_endings":
            view.set_line_endings(value)
        else:
            view.settings().set(key, value)

# Support for Emacs-style in-band "File Variables"

import sublime
import sublime_plugin
import re
import os

# http://www.gnu.org/software/emacs/manual/html_node/emacs/Specifying-File-Variables.html
FILEVARS_RE = r'.*-\*-\s*(.+?)\s*-\*-.*'
FILEVARS_MAX_LINES = 5

# TODO(DH): Do the init_syntax_files work at plugin load time, not on-demand.
# TODO(DH): EventListener -> ViewEventListener ?
# TODO(DH): Use ViewEventListener.is_applicable to reject views with 'is_widget' setting. Later, early-out for views not backed by a file (view.file_name()). See my 'skip-non-editor-views' branch for reference.

class SublimeEmacsFileVariables(sublime_plugin.EventListener):

    package_settings = None

    def __init__(self):
        self._modes = {}

    def init_syntax_files(self):
        for syntax_file in self.find_syntax_files():
            name = os.path.splitext(os.path.basename(syntax_file))[0].lower()
            self._modes[name] = syntax_file

        # Load custom mappings from the settings file
        self.package_settings = sublime.load_settings("EmacsFileVariables.sublime-settings")

        if self.package_settings.has("mode_mappings"):
            for mode, syntax in self.package_settings.get("mode_mappings").items():
                self._modes[mode] = self._modes[syntax.lower()]

        if self.package_settings.has("user_mode_mappings"):
            for mode, syntax in self.package_settings.get("user_mode_mappings").items():
                self._modes[mode] = self._modes[syntax.lower()]

    def find_syntax_files(self):
        for f in sublime.find_resources("*.tmLanguage"):
            yield f
        for f in sublime.find_resources("*.sublime-syntax"):
            yield f

    def on_load(self, view):
        self.parse_filevars(view)

    def on_post_save(self, view):
        self.parse_filevars(view)

    def parse_filevars(self, view):
        if not self._modes:
            self.init_syntax_files()

        # Grab lines from beginning of view
        regionEnd = view.text_point(FILEVARS_MAX_LINES, 0)
        region = sublime.Region(0, regionEnd)
        lines = view.lines(region)
        # Get the last line in the file
        line = view.line(view.size())
        # Add the last N lines of the file to the lines list
        for i in range(1, FILEVARS_MAX_LINES):
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

                    self.set(view, key, value)
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
                    self.set(view, "line_endings", value)
                elif key == "indent-tabs-mode":
                    if value == "nil" or value.strip == "0":
                        self.set(view, 'translate_tabs_to_spaces', True)
                    else:
                        self.set(view, 'translate_tabs_to_spaces', False)
                elif key == "mode":
                    if value in self._modes:
                        self.set(view, 'syntax', self._modes[value])
                elif key == "tab-width":
                    self.set(view, 'tab_size', int(value))

            # We found and processed a filevars line, so do not look for more.
            break

    def set(self, view, key, value):
        #print("%s: setting view setting '%s' to '%s'" % (self.__class__.__name__, key, value))
        if key == "line_endings":
            view.set_line_endings(value)
        else:
            view.settings().set(key, value)

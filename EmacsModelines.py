# Emacs-like modeline parser
#
# Parses any '-*- ... -*-'-style modeline within the first 5 lines of a
# view, and sets a few variables.

# URLref: [Emacs - Specifying File Variables] http://www.gnu.org/software/emacs/manual/html_node/emacs/Specifying-File-Variables.html @@ http://www.webcitation.org/66xWWwjTt
# URLref: [Emacs - Coding Systems] http://www.gnu.org/software/emacs/manual/html_node/emacs/Coding-Systems.html @@ http://www.webcitation.org/66xX3pMc1
# URLref: [Emacs - Specifying a File's Coding System] http://www.gnu.org/software/emacs/manual/html_node/emacs/Specify-Coding.html @@ http://www.webcitation.org/66xZ1nDWp

import sublime
import sublime_plugin
import re
import os

MODELINE_RE = r'.*-\*-\s*(.+?)\s*-\*-.*'
MODELINE_MAX_LINES = 5

# TODO(DH): Remove ST2 codepath(s)
# TODO(DH): Remove on_activated(...) handling, or put it behind a setting (default off)
# TODO(DH): Do the init_syntax_files work at plugin load time.
# TODO(DH): EventListener -> ViewEventListener ?
# TODO(DH): Use ViewEventListener.is_applicable to reject views with 'is_widget' setting. Later, early-out for views not backed by a file (view.file_name()). See my 'skip-non-editor-views' branch for reference.

def to_json_type(v):
    # from "https://github.com/SublimeText/Modelines/blob/master/sublime_modelines.py"
    """"Convert string value to proper JSON type.
    """
    if v.lower() in ('true', 'false'):
        v = v[0].upper() + v[1:].lower()

    try:
        return eval(v, {}, {})
    except:
        raise ValueError("Could not convert to JSON type.")


class EmacsModelinesListener(sublime_plugin.EventListener):

    package_settings = None

    def __init__(self):
        self._modes = {}

    def init_syntax_files(self):
        for syntax_file in self.find_syntax_files():
            name = os.path.splitext(os.path.basename(syntax_file))[0].lower()
            self._modes[name] = syntax_file

        # Load custom mappings from the settings file
        self.package_settings = sublime.load_settings("EmacsModelines.sublime-settings")

        if self.package_settings.has("mode_mappings"):
            for modeline, syntax in self.package_settings.get("mode_mappings").items():
                self._modes[modeline] = self._modes[syntax.lower()]

        if self.package_settings.has("user_mode_mappings"):
            for modeline, syntax in self.package_settings.get("user_mode_mappings").items():
                self._modes[modeline] = self._modes[syntax.lower()]

    def find_syntax_files(self):
        # ST3
        if hasattr(sublime, 'find_resources'):
            for f in sublime.find_resources("*.tmLanguage"):
                yield f
            for f in sublime.find_resources("*.sublime-syntax"):
                yield f
        else:
            for root, dirs, files in os.walk(sublime.packages_path()):
                for f in files:
                    if f.endswith(".tmLanguage") or f.endswith("*.sublime-syntax"):
                        langfile = os.path.relpath(os.path.join(root, f), sublime.packages_path())
                        # ST2 (as of build 2181) requires unix/MSYS style paths for the 'syntax' view setting
                        yield os.path.join('Packages', langfile).replace("\\", "/")

    def on_load(self, view):
        self.parse_modelines(view)

    def on_activated(self, view):
        self.parse_modelines(view)

    def on_post_save(self, view):
        self.parse_modelines(view)

    def parse_modelines(self, view):
        if not self._modes:
            self.init_syntax_files()

        # Grab lines from beginning of view
        regionEnd = view.text_point(MODELINE_MAX_LINES, 0)
        region = sublime.Region(0, regionEnd)
        lines = view.lines(region)
        # Get the last line in the file
        line = view.line(view.size())
        # Add the last N lines of the file to the lines list
        for i in range(1, MODELINE_MAX_LINES):
            # Add the line to the list of lines
            lines.append(line)
            # Move the line to the previous line
            line = view.line(line.a - 1)

        # Look for modeline regexp
        for line in lines:
            m = re.match(MODELINE_RE, view.substr(line))
            if not m:
                continue

            modeline = m.group(1).lower()

            for component in modeline.split(';'):
                keyValueMatch = re.match(r'\s*(st-|sublime-text-|sublime-|sublimetext-)?(.+):\s*(.+)\s*', component)
                if not keyValueMatch:
                    continue

                key, value = keyValueMatch.group(2), keyValueMatch.group(3)
                keyIsSublimeSpecific = bool(keyValueMatch.group(1))

                if keyIsSublimeSpecific:
                    self.set(view, key, to_json_type(value))
                elif key == "coding":
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

            # We found a mode-line, so stop processing
            break

    def set(self, view, key, value):
        #print("%s: setting view setting '%s' to '%s'" % (self.__class__.__name__, key, value))
        if key == "line_endings":
            view.set_line_endings(value)
        else:
            view.settings().set(key, value)

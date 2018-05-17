# Support for Emacs-style in-band "File Variables"
#
# http://www.gnu.org/software/emacs/manual/html_node/emacs/Specifying-File-Variables.html

import sublime
import sublime_plugin
import re
import os

# Look for the filevars line in the first N lines of the file only.
FILEVARS_HEAD_LINE_COUNT = 5

FILEVARS_RE = r'.*-\*-\s*(.+?)\s*-\*-.*'

modeToSyntaxLUT = None


class SublimeEmacsFileVariables(sublime_plugin.ViewEventListener):
    @classmethod
    def is_applicable(cls, settings):
        # We don't want to be active in parts of Sublime's UI other than the actual code editor.
        return not settings.get('is_widget')

    def discover_package_syntaxes(self):
        global modeToSyntaxLUT
        modeToSyntaxLUT = {}

        syntax_definition_paths = []
        for p in sublime.find_resources("*.sublime-syntax"):
            syntax_definition_paths.append(p)
        for p in sublime.find_resources("*.tmLanguage"):
            syntax_definition_paths.append(p)

        for path in syntax_definition_paths:
            mode = os.path.splitext(os.path.basename(path))[0].lower()
            modeToSyntaxLUT[mode] = path

        # Load custom mappings from the settings file
        package_settings = sublime.load_settings(
            "SublimeEmacsFileVariables.sublime-settings")

        if package_settings.has("mode_mappings"):
            for mode, syntax in package_settings.get("mode_mappings").items():
                modeToSyntaxLUT[mode] = modeToSyntaxLUT[syntax.lower()]

        if package_settings.has("user_mode_mappings"):
            for mode, syntax in package_settings.get(
                    "user_mode_mappings").items():
                modeToSyntaxLUT[mode] = modeToSyntaxLUT[syntax.lower()]

        #print(modeToSyntaxLUT)

    def on_load(self):
        self.act()

    def on_activated(self):
        self.act()

    def on_post_save(self):
        self.act()

    def act(self):
        # We only care about views representing actual files on disk.
        if not self.view.file_name() or self.view.is_scratch():
            return

        global modeToSyntaxLUT
        if not modeToSyntaxLUT:
            self.discover_package_syntaxes()

        filevars = self.parse_filevars()
        if filevars:
            self.process_filevars(filevars)

    def parse_filevars(self):
        view = self.view

        # Grab lines from beginning of view
        regionEnd = view.text_point(FILEVARS_HEAD_LINE_COUNT, 0)
        region = sublime.Region(0, regionEnd)
        lines = view.lines(region)

        # Look for filevars
        for line in lines:
            m = re.match(FILEVARS_RE, view.substr(line))
            if m:
                return m.group(1)
        return None

    def process_filevars(self, filevars):
        global modeToSyntaxLUT

        for component in filevars.lower().split(';'):
            keyValueMatch = re.match(
                r'\s*(st-|sublime-text-|sublime-|sublimetext-)?(.+):\s*(.+)\s*',
                component)
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

                self.set_view_setting(key, value)
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
                self.set_view_setting("line_endings", value)
            elif key == "indent-tabs-mode":
                # Convert string representations of Emacs Lisp values to proper Python booleans.
                value = value.lower() != 'nil' and value.lower() != '()'

                self.set_view_setting('translate_tabs_to_spaces', not value)
            elif key == "mode":
                if value in modeToSyntaxLUT:
                    self.set_view_setting('syntax', modeToSyntaxLUT[value])
            elif key == "tab-width":
                self.set_view_setting('tab_size', int(value))

    def set_view_setting(self, key, value):
        view = self.view
        #print("%s: setting view setting '%s' to '%s'" % (self.__class__.__name__, key, value))
        if key == "line_endings":
            view.set_line_endings(value)
        else:
            view.settings().set(key, value)

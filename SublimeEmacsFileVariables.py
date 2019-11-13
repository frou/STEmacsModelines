import sublime
import sublime_plugin
import re
import os

# Look for the filevars line in the first N lines of the file only.
FILEVARS_HEAD_LINE_COUNT = 5

FILEVARS_RE = r".*-\*-\s*(.+?)\s*-\*-.*"

mode_to_syntax_lut = None


class SublimeEmacsFileVariables(sublime_plugin.ViewEventListener):
    def act(self):
        # We only care about views representing actual files on disk.
        if not self.view.file_name() or self.view.is_scratch():
            return

        global mode_to_syntax_lut
        if not mode_to_syntax_lut:
            self.discover_package_syntaxes()

        filevars = self.parse_filevars()
        if filevars:
            self.process_filevars(filevars)

    def discover_package_syntaxes(self):
        global mode_to_syntax_lut
        mode_to_syntax_lut = {}

        syntax_definition_paths = []
        for p in sublime.find_resources("*.sublime-syntax"):
            syntax_definition_paths.append(p)
        for p in sublime.find_resources("*.tmLanguage"):
            syntax_definition_paths.append(p)

        for path in syntax_definition_paths:
            mode = os.path.splitext(os.path.basename(path))[0].lower()
            mode_to_syntax_lut[mode] = path

        # Load custom mappings from the settings file
        package_settings = sublime.load_settings(
            "SublimeEmacsFileVariables.sublime-settings"
        )

        if package_settings.has("mode_mappings"):
            for mode, syntax in package_settings.get("mode_mappings").items():
                mode_to_syntax_lut[mode] = mode_to_syntax_lut[syntax.lower()]

        if package_settings.has("user_mode_mappings"):
            for mode, syntax in package_settings.get("user_mode_mappings").items():
                mode_to_syntax_lut[mode] = mode_to_syntax_lut[syntax.lower()]

        # print(mode_to_syntax_lut)

    def parse_filevars(self):
        view = self.view

        # Grab lines from beginning of view
        region_end = view.text_point(FILEVARS_HEAD_LINE_COUNT, 0)
        region = sublime.Region(0, region_end)
        lines = view.lines(region)

        # Look for filevars
        for line in lines:
            m = re.match(FILEVARS_RE, view.substr(line))
            if m:
                return m.group(1)
        return None

    def process_filevars(self, filevars):
        global mode_to_syntax_lut

        for component in filevars.lower().split(";"):
            key_value_match = re.match(
                r"\s*(st-|sublime-text-|sublime-|sublimetext-)?(.+):\s*(.+)\s*",
                component,
            )
            if not key_value_match:
                continue

            key, value = key_value_match.group(2), key_value_match.group(3)
            key_is_sublime_specific = bool(key_value_match.group(1))

            if key_is_sublime_specific:
                # Convert stringly-typed booleans to proper Python booleans.
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False

                self.set_view_setting(key, value)
            elif key == "coding":
                # http://www.gnu.org/software/emacs/manual/html_node/emacs/Coding-Systems.html
                # http://www.gnu.org/software/emacs/manual/html_node/emacs/Specify-Coding.html
                match = re.match("(?:.+-)?(unix|dos|mac)", value)
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
                value = value.lower() != "nil" and value.lower() != "()"

                self.set_view_setting("translate_tabs_to_spaces", not value)
            elif key == "mode":
                if value in mode_to_syntax_lut:
                    self.set_view_setting("syntax", mode_to_syntax_lut[value])
                else:
                    sublime.status_message(
                        '{0}: {1} "{2}" does not match any known syntax'.format(
                            self.__class__.__name__, key, value
                        )
                    )
            elif key == "tab-width":
                self.set_view_setting("tab_size", int(value))

    def set_view_setting(self, key, value):
        view = self.view
        # print("%s: setting view setting '%s' to '%s'" % (self.__class__.__name__, key, value))
        if key == "line_endings":
            view.set_line_endings(value)
        else:
            view.settings().set(key, value)

    # Overrides --------------------------------------------------

    @classmethod
    def is_applicable(cls, settings):
        # We don't want to be active in parts of Sublime's UI other than the actual code editor.
        # REF: https://forum.sublimetext.com/t/api-how-to-tell-whether-a-view-object-represents-an-unusual-view/36756
        return not settings.get("is_widget")

    def on_load(self):
        self.act()

    def on_activated(self):
        self.act()

    def on_post_save(self):
        self.act()

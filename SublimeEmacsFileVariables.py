import itertools
import re
from pathlib import Path
from typing import ClassVar, Dict, Set

import sublime
import sublime_plugin

# @todo Rename this GitHub repo (my fork of the original) from STEmacsModelines to STEmacsFileVariables


class SublimeEmacsFileVariables(sublime_plugin.ViewEventListener):
    # Look for the filevars line in the first N lines of the file only.
    FILEVARS_HEAD_LINE_COUNT = 5

    FILEVARS_RE = r".*-\*-\s*(.+?)\s*-\*-.*"

    mode_to_syntax_lut: ClassVar[Dict[str, str]] = {}

    # Overrides begin ------------------------------------------------------------------

    @classmethod
    def is_applicable(cls, settings):
        return not settings.get("is_widget")

    def on_load(self):
        self.common_handler()

    def on_activated(self):
        self.common_handler()

    def on_post_save(self):
        self.common_handler()

    # Overrides end --------------------------------------------------------------------

    def common_handler(self):
        # We don't want to be active in parts of Sublime's UI other than actual
        # code-editing views.
        #
        # NOTE: The "is_widget" check in ::is_applicable is necessary but no longer
        # sufficient, since as of ST4, Output Panels are no longer considered widgets.
        if self.view.element() is not None or self.view.settings().get("terminus_view"):
            return

        if not self.mode_to_syntax_lut:
            self.discover_package_syntaxes()

        filevars = self.parse_filevars()
        if filevars:
            self.process_filevars(filevars)

    def discover_package_syntaxes(self):
        package_settings = sublime.load_settings(
            "SublimeEmacsFileVariables.sublime-settings"
        )

        syntax_discovery_blocklist: Set[str] = set(
            package_settings.get("syntax_discovery_blocklist", [])  # pyright: ignore
        )
        syntax_definition_paths = [
            p
            for p in itertools.chain(
                sublime.find_resources("*.tmLanguage"),
                sublime.find_resources("*.sublime-syntax"),
            )
            if p not in syntax_discovery_blocklist
        ]
        # print(syntax_definition_paths)

        for path in syntax_definition_paths:
            self.register_mode(Path(path).stem, path)
        # print(self.mode_to_syntax_lut)

        mode_mappings: Dict[str, str] = package_settings.get("mode_mappings", {})  # pyright: ignore
        user_mode_mappings: Dict[str, str] = package_settings.get(
            "user_mode_mappings", {}
        )  # pyright: ignore
        for from_mode, to_mode in itertools.chain(
            mode_mappings.items(), user_mode_mappings.items()
        ):
            self.register_mode(
                from_mode,
                # @todo Handle this lookup raising
                self.mode_to_syntax_lut[to_mode.lower()],
            )
        # print(self.mode_to_syntax_lut)

    def register_mode(self, mode_name: str, syntax_path: str):
        mode_name_lower = mode_name.lower()

        if existing_syntax_path := self.mode_to_syntax_lut.get(mode_name_lower):
            self.log(
                f"`mode: {mode_name}` will give {syntax_path!r} precedence over {existing_syntax_path!r}"
            )

        self.mode_to_syntax_lut[mode_name_lower] = syntax_path

    def log(self, msg, status_bar=False):
        line = f"[{self.__class__.__name__}] {msg}"
        print(line)  # noqa: T201
        if status_bar:
            sublime.status_message(line)

    def parse_filevars(self):
        view = self.view

        # Grab lines from beginning of view
        region_end = view.text_point(self.FILEVARS_HEAD_LINE_COUNT, 0)
        region = sublime.Region(0, region_end)
        lines = view.lines(region)

        # Look for filevars
        for line in lines:
            m = re.match(self.FILEVARS_RE, view.substr(line))
            if m:
                return m.group(1)
        return None

    def process_filevars(self, filevars):  # noqa: C901
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
                try:
                    self.set_view_setting("syntax", self.mode_to_syntax_lut[value])
                except KeyError:
                    self.log(
                        f"{key} {value!r} does not match any known syntax",
                        status_bar=True,
                    )
            elif key == "tab-width":
                self.set_view_setting("tab_size", int(value))

    def set_view_setting(self, key, value):
        view = self.view
        # print("%s: setting view setting '%s' to '%s'" % (self.__class__.__name__, key, value))
        if key == "line_endings":
            view.set_line_endings(value)
        elif key == "syntax":
            view.assign_syntax(value)
        else:
            view.settings().set(key, value)

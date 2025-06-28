# HTML Settings Export Reborn
# Copyright Slashee the Cow 2025-
#
# Based on CuraHtmlDoc by 5@xes
# https://github.com/5axes/CuraHtmlDoc/
#--------------------------------------------------------------------------------------------------
# Version history (Reborn edition)
# v1.2.1:
#   - Fixed up some CSS with which I may have gotten a bit too careless using search + replace before.
#   - Wrapped CSS class names in double hyphens to avoid collisions.
#   - Prepended minified CSS class names with double underscores to avoid collisions (my insurance wishes I always went to this much effort to avoid collisions).
#   - Updated a function or two that weren't ready for the New Era of CSS Class Names.
# v1.2.0:
#   - Profile comparison! Two different profiles side by side is what everyone wanted, right? Even works for different printers!
#   - That did require a significant refactor internally (as if I hadn't done that once already... *sigh*)
#   - Output HTML code is now made smaller (~45% reduction) with a few tricks:
#       - Crimes against spaces. If somebody wants me to turn myself in, just tell me where and buy me a plane ticket.
#       - Severely abbreviating CSS class names in the output (but severely making them more safe on the inside!)
#       - Comments stripped (if you want to see why I did stuff... look at the source. They're not stripped there.)
#       - Adding a fair amount of size to the plugin to reduce the size of the output. It's paradoxatastic!
#   - Added printer name to output (seems like it should have been there before, but anyway.)
#   - Tracked down and took care of a couple of elusive "which extruder" settings for single extruder exports.
# v1.1.0:
#   - Added search function to output page. That actually required next to no effort here in the backend, it's all JS and CSS, just had to add classes to some elements it generates programmatically.
#   - Show/hide disabled/local settings now change their button text depending on state. That's all JS. All I had to do in here was fill in some placeholder strings. Does that make it worth listing here?
# v1.0.0:
#   - Made it an Extension instead of a Tool. Menu option seems much more logical than tool button.
#   - ^^^ meant I could ditch **a bunch** of Tool related stuff which I don't even know why some of it was apparently necessary.
#   - **Extensive** refactoring. Like a "knock all the walls down and start over" kind of renovation.
#   - This remodelling includes removing oodles of duplicate code. While it's fine if your house has two bathrooms and you renovate it to have two bathrooms, that doesn't apply to code.
#   - What little Qt is in here, dropped Qt 5 support because I have enough on my hands as it is. This makes Cura 5.0 a minimum.
#   - Removed autosave setting. Generating this is a somewhat fragile process and I really don't want to get in the way of gcode saving.
#   - Children of a setting now use a graphical indicator to indicate their depth in the tree instead of increasing indents (hard to tell apart) which used CSS classes numbered [l,2,3,4,5] (look at the first one)
#   - HTML output is now generated in advance and written all at once instead of literally thousands of individual writes over time locking up file I/O.
#   - Large chunks of HTML now loaded from individual files instead of ungainly string literals.
#   - Managed to make those large chunks localisable despite that.
#   - Cleaned up CSS, formatting it and removing unused classes. And adding new, used ones.
#   - Output HTML markup now much more clean with things like indents and new lines. And being valid.
#   - Generated HTML now consistently follows HTML5 standards instead of using deprecated elements and having traces of XHTML.
#   - Removed unnecessary tags and elements from HTML output that only worked because of how forgiving browsers are.
#   - Date/time practically guaranteed to be in system locale's format instead of a hard coded format.
#   - Rounded values like "material cost" to be human-friendly. If you care about a millionth of a cent's worth of filament, hire an accountant to care for you.
#   - Thumbnail generation now uses "last slice" as a primary source and falls back to trying to take a Snapshot (which I have found unreliable) as a backup.
#   - Setting sections can now be collapsed to make scrolling through the whole thing less of a slog.
#   - Now shows all categories of settings for each extruder, including the ones where *most* (but not all) of the settings are shared (except the "Dual Extrusion" settings).
#   - Completely hides (not just disables) multi extruder settings like extruder number and prime towers when using a single extruder machine. I said all categories, not all settings.
#   - Added zebra striping to rows to aid readability.
#   - Lists of settings should now look "easy to read" instead of "like a spreadsheet".
#   - Significantly improved error handling in the now much less likely situation there's a problem.
#   - Added sticky header with the name, profile and visibility buttons, so you don't have to go to the top of the page to find the visibility buttons.
#   - Added "warning" colouring for values in addition to errors.
#   - Error and warning colouring should now look more consistent (and yet different for alternating positions).
#   - Settings for all extruders are now in a single table per category for added readability and less duplicity. I know exactly what that word means. I chose it carefully.
#   - Defaults to (but doesn't overwrite, because I like don't like messing with other peoples' things) Cura's last used save folder.
#   - Made "show/hide user changed settings" button useful in that it toggles showing **only** user changes.
#   - Now uses Python standard library functions to both check for a web browser and open the page in it instead of an unholy mix of Python and Qt.

import configparser  # The script lists are stored in metadata as serialised config files.
import datetime
import difflib
import html
import locale
import os
import re
import webbrowser

from dataclasses import InitVar, dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Optional

from cura.CuraApplication import CuraApplication
from cura.CuraVersion import CuraVersion
from cura.Snapshot import Snapshot
from cura.Utils.Threading import call_on_qt_thread
from PyQt6.QtCore import QBuffer
from PyQt6.QtWidgets import QFileDialog
from UM.Extension import Extension
from UM.i18n import i18nCatalog
from UM.Logger import Logger
from UM.Message import Message
from UM.Qt.Duration import DurationFormat
from UM.Resources import Resources
from UM.Settings.ContainerStack import ContainerStack
from UM.Settings.InstanceContainer import InstanceContainer
from UM.Settings.Models.SettingPreferenceVisibilityHandler import \
    SettingPreferenceVisibilityHandler

i18n_cura_catalog = i18nCatalog("cura")
i18n_printer_catalog = i18nCatalog("fdmprinter.def.json")
i18n_extruder_catalog = i18nCatalog("fdmextruder.def.json")

class ExportMode(Enum):
    """More stuffup-proof than just using a string literal"""
    REPORT = auto()
    COMPARE = auto()

class CssClasses(Enum):
    """It occurred to me I was using CSS classes as magic strings"""
    def __init__(self, full_name: str, abbr_name: str):  # Runs for each item in Enum
        self._full_name = full_name
        self._abbr_name = abbr_name

    # These ones referenced in Python code
    CATEGORY = ("--category--", "__a")
    CATEGORY_HEADER = ("--category-header--", "__b")
    CENTRE = ("--centre--", "__c")
    CHILD_SPACER = ("--child-spacer--", "__d")
    COLLAPSIBLE_SETTING = ("--collapsible-setting--", "__e")
    COMPARE_DIFFERENT = ("--compare-diff--", "__f")
    ERROR_ERROR = ("--error--", "__g")
    ERROR_WARNING = ("--warning--", "__h")
    POSTS_SETTINGS = ("--posts-settings--", "__i")
    SETTING_DISABLED = ("--disabled--", "__j")
    SETTING_HIDDEN = ("--hidden--", "__k")
    SETTING_LABEL = ("--setting-label--", "__l")
    SETTING_LOCAL = ("--local--", "__m")
    SETTING_NORMAL = ("--normal--", "__n")
    SETTING_ROW = ("--setting-row--", "__o")
    SETTING_VALUE = ("--setting-value--", "__p")
    SETTING_VISIBLE = ("--visible--", "__q")
    SOME_DISABLED = ("--some-disabled--", "__r")
    SOME_HIDDEN = ("--some-hidden--", "__s")
    SOME_LOCAL = ("--some-local--", "__t")
    THUMBNAIL = ("--thumbnail--", "__u")
    TWO_COLUMN_LEFT = ("--two-column-left--", "__v")
    TWO_COLUMN_RIGHT = ("--two-column-right--", "__w")

    # These ones only referenced in template files
    HEADER_CONTENT_WRAPPER = ("--header-content-wrapper--", "__x")
    HEADER_ROW = ("--header-row--", "__y")
    HEADER_ROW_BOTTOM = ("--header-bottom-row--", "__z")
    HEADER_ROW_TOP = ("--header-top-row--", "__aa")
    HEADER_TEXT = ("--header-text--", "__ab")
    MAIN_CONTENT_WRAPPER = ("--main-content-wrapper--", "__ac")
    PROFILE_NAME = ("--profile-name--", "__ad")
    PROJECT_NAME = ("--project_name--", "__ae")
    SETTING_VISIBILITY = ("--setting-visibility--", "__af")
    STICKY_HEADER = ("--sticky-header--", "__ag")
    TEXT_CENTRE = ("--text-centre--", "__ah")

    @property
    def full(self) -> str:
        return self._full_name

    @property
    def abbr(self) -> str:
        return self._abbr_name

@dataclass
class CategorySetting:
    """Holds each setting so I can combine them all at the end of a category"""
    label: str = ""
    key: str = ""
    value: list[str] = field(default_factory = list)
    setting_type: str = ""
    css_class: list[str] = field(default_factory = list)
    # Keep separate from CSS so I can track things like disabled separately to errors
    error_class: list[str] = field(default_factory = list)
    child_level: int = 0
    children: dict[Optional[dict[str,"CategorySetting"]]] = field(default_factory = dict)
    skip: bool = False
    extruders: int = 1

    extruder_count: InitVar[int] = 1

    def __post_init__(self, extruder_count: int):
        """Pre-populate lists so no pesky IndexErrors crop up"""
        self.extruders = extruder_count
        self.value = [""] * extruder_count
        self.css_class = [""] * extruder_count
        self.error_class = [""] * extruder_count

    def internal_representation(self) -> str:
        """Format a string to be used for the HTML <title> attribute as a tooltip"""
        return f"{self.key}: {self.setting_type}"

    def make_td_no_children(self, cell_indent: int = 0) -> list[str]:
        """Makes a <td> cell for each extruder for this setting (no recursion)"""

        td_lines = []

        cell_class = []
        cell_tooltip = []
        for i, value in enumerate(self.value):
            if self.skip:
                value = ""
                self.error_class[i] = ""
                self.css_class[i] = ""
                cell_class.append("")
            else:
                if self.error_class[i]:
                    cell_class.append(self.error_class[i])
                elif self.css_class[i]:
                    cell_class.append(self.css_class[i])
                else:
                    cell_class.append("")
            # Set tooltip based on class
            cell_tooltip.append(HTMLSettingsExportReborn.css_class_to_human_readable(cell_class[i]))
            display_value = html.escape(value.replace("<br>", "\n")).replace("\n", "<br>")  # For when you want a safely escaped value which is subsequently unescaped.
            td_lines.append(indent(f'<td class="{(cell_class[i] + " " + CssClasses.SETTING_VALUE.full) if cell_class[i] else CssClasses.SETTING_VALUE.full}" title="{html.escape(cell_tooltip[i])}">{display_value}</td>', cell_indent))
        return td_lines

@dataclass
class BlankSetting(CategorySetting):
    """Holds a blank setting to use when comparing items.
    It does however need the correct number of extruders."""

    def make_td_no_children(self, cell_indent: int = 0) -> list[str]:
        """We're a blank so return empty cells"""
        td_lines = []
        for _ in range(self.extruders):
            td_lines.append(indent(f'<td class="{CssClasses.SETTING_VALUE.full}"></td>', cell_indent))
        return td_lines

@dataclass
class SettingProfile:
    """Holds all the settings of a profile for comparison"""
    # Outer key is category, inner key is Cura's internal key
    settings: dict[str, list[CategorySetting]] = field(default_factory = dict)
    # Map Cura's internal key to translated labels
    settings_labels: dict[str, str] = field(default_factory = dict)
    profile_name: str = ""
    preset_name: str = ""
    printer_name: str = ""
    extruder_count: int = 1
    global_changed_settings: list[Any] = field(default_factory = list)
    extruder_changed_settings: list[list[Any]] = field(default_factory = list)
    visible_settings: list[Any] = field(default_factory = list)

    def get_flattened_category_dict(self, category: list | dict) -> dict[str, Any]:
        flattened_dict = {}

        items_to_process = []
        if isinstance(category, dict):
            items_to_process = (category.values())
        elif isinstance(category, list):
            items_to_process = category
        else:
            raise TypeError(f"SettingProfile.get_flattened_category_dict got something that wasn't a dict or a list: {category}")

        for item in items_to_process:
            new_key = getattr(item, "key", None)
            if new_key is None and isinstance(item, dict):
                new_key = item.get("key")
            
            if new_key is not None: # Only add to flattened_dict if we found a valid key
                flattened_dict[new_key] = item
            else:
                Logger.log("w", f"Skipping item in flattening as no valid key found: {item} (type: {type(item)})")

            children = getattr(item, "children", None)
            if children is None and isinstance(item, dict):
                children = item.get("children")
            
            if children: # Only recurse if children exist
                flattened_dict.update(self.get_flattened_category_dict(children))
        return flattened_dict

    def get_flattened_all_categories_dict(self) -> dict[str, Any]:
        flattened_dict = {}
        for category, category_dict in self.settings.items():
            flattened_dict[category] = self.get_flattened_category_dict(category_dict)
        return flattened_dict
    

    # Used to produce the headers
    categories: InitVar[list[str]] = ["resolution", "shell", "top_bottom", "infill", "material",
                               "speed", "travel", "cooling", "dual", "support", "platform_adhesion",
                               "meshfix", "blackmagic", "experimental", "machine_settings"]
    # machine_settings needs to be treated specially but it's easier to call it out specifically later
    # Easier both than overriding __init__ or expecting users to provide a list

    def __post_init__(self, categories: list[str]):
        for category in categories:
            self.settings[category] = []
            self.settings_labels[category] = ""

class CompareProfiles:

    def __init__(self, profile_a: SettingProfile, profile_b: SettingProfile):
        self.profile_a = profile_a
        self.profile_b = profile_b

        # Get number of extruders (required for blank settings)
        self.extruders_a = profile_a.extruder_count
        self.extruders_b = profile_b.extruder_count
        self.total_extruders = self.extruders_a + self.extruders_b

        # Get flattened versions of all categories
        self.profile_a_settings: dict[str, CategorySetting] = profile_a.get_flattened_all_categories_dict()
        self.profile_b_settings: dict[str, CategorySetting] = profile_b.get_flattened_all_categories_dict()

        # Do a lot of things to get a combined list of keys
        self.category_keys: dict[str, list[str]] = {}
        # Both profiles should have the same list of categores but just in case
        all_combined_categories = list(self.profile_a_settings.keys())
        all_combined_categories.extend([key for key in list(self.profile_b_settings.keys()) if key not in all_combined_categories])
        for category in all_combined_categories:
            current_category_a_settings_dict = self.profile_a_settings.get(category, {})
            current_category_b_settings_dict = self.profile_b_settings.get(category, {})
            #try:
            setting_keys_a = list(current_category_a_settings_dict.keys())
            setting_keys_b = list(current_category_b_settings_dict.keys())
            # Logger.log("d", f'category = {category}\nsetting_keys_a = {setting_keys_a}\nsetting_keys_b = {setting_keys_b}')
            aligned_list_a, aligned_list_b = self.align_setting_lists(
                setting_keys_a, setting_keys_b
            )
            # Logger.log("d", f'category = {category}\naligned_list_a = {aligned_list_a}\naligned_list_b = {aligned_list_b}')
            combined_list = self.combine_aligned_lists(aligned_list_a, aligned_list_b)
            self.category_keys[category] = combined_list
            #except KeyError as e:
            #    Logger.logException("w", f"CompareProfiles.__init__() did not find category {category} in one profile: {e}")
            #    self.category_keys[category] = self.profile_a_settings[category] if category in self.profile_a_settings else self.profile_b_settings[category]

        # Fill any blanks for settings which don't exist in one profile
        # In theory I just made sure both profiles have all categories so hopefully it doesn't raise an exception.
        for category, category_setting_keys in self.category_keys.items():
            #try:
            current_category_a = self.profile_a_settings.get(category, {})
            current_category_b = self.profile_b_settings.get(category, {})
            #except KeyError as e:
            #    Logger.logException("w", f"CompareProfiles.()__init__() did not find category {category} in both settings dictionaries: {e}")
            #   continue
            # Logger.log("d", f'current_category_a = {current_category_a}\ncategory = {category}\ncategory_setting_keys = {category_setting_keys}')
            for key in category_setting_keys:
                # In theory they have to be in at least one profile to be in the keys so I'm not checking to see if it doesn't exist in either
                if key not in current_category_a:
                    label_for_blank_a = ""
                    # Safely get the label for the BlankSetting
                    if key in current_category_b: # Prioritize label from profile B if it exists there
                        label_for_blank_a = current_category_b[key].label
                    elif key in self.profile_a.settings_labels: # Fallback to top-level settings_labels
                        label_for_blank_a = self.profile_a.settings_labels[key]
                    elif key in self.profile_b.settings_labels:
                        label_for_blank_a = self.profile_b.settings_labels[key]
                    else: # Final fallback, use the key itself if no label found
                        label_for_blank_a = key
                    current_category_a[key] = BlankSetting(key = key, label = label_for_blank_a, extruder_count = self.extruders_a)
                if key not in current_category_b:
                    label_for_blank_b = ""
                    if key in current_category_a: # Prioritize label from profile A if it exists there
                        label_for_blank_b = current_category_a[key].label
                    elif key in self.profile_b.settings_labels:
                        label_for_blank_b = self.profile_b.settings_labels[key]
                    elif key in self.profile_a.settings_labels:
                        label_for_blank_b = self.profile_a.settings_labels[key]
                    else:
                        label_for_blank_b = key
                    current_category_b[key] = BlankSetting(key = key, label = label_for_blank_b, extruder_count = self.extruders_b)
            
    def align_setting_lists(self,
        list_a: list[Any],
        list_b: list[Any],
        blank_placeholder: str = ""
    ) -> tuple[list[Any], list[Any]]:
        """
        Aligns two lists, inserting placeholders for missing items to maintain relative order.
        """
        matcher = difflib.SequenceMatcher(None, list_a, list_b)
        aligned_a = []
        aligned_b = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                # Items are common to both lists, align them directly
                for k in range(i2 - i1):
                    aligned_a.append(list_a[i1 + k])
                    aligned_b.append(list_b[j1 + k])
            elif tag == 'delete':
                # Items exist only in list_a
                for k in range(i2 - i1):
                    aligned_a.append(list_a[i1 + k])
                    aligned_b.append(blank_placeholder)
            elif tag == 'insert':
                # Items exist only in list_b
                for k in range(j2 - j1):
                    aligned_a.append(blank_placeholder)
                    aligned_b.append(list_b[j1 + k])
            elif tag == 'replace':
                # Items in list_a are "replaced" by items in list_b
                # This is the tricky part for exact desired output, as difflib
                # defines a block as a replacement. We'll simply interleave them
                # based on their original presence.
                len_a_seg = i2 - i1
                len_b_seg = j2 - j1
                max_len_seg = max(len_a_seg, len_b_seg)

                for k in range(max_len_seg):
                    val_a = list_a[i1 + k] if k < len_a_seg else blank_placeholder
                    val_b = list_b[j1 + k] if k < len_b_seg else blank_placeholder
                    aligned_a.append(val_a)
                    aligned_b.append(val_b)

        return aligned_a, aligned_b

    def combine_aligned_lists(self, list_a: list[Any], list_b: list[Any]) -> list[Any]:
        combined_list = []
        for i in range(len(list_a)):
            if list_a[i]:
                # Just take item straight from A
                combined_list.append(list_a[i])
            elif list_b[i]:
                # Item exists in B but not A
                combined_list.append(list_b[i])
            else:
                raise ValueError(f"CompareProfiles.combine_aligned_lists found falsy values in both lists at index {i}")
        return combined_list

    def make_setting_row(self, category, setting_key, base_indent: int = 0) -> str:
        """Has the label and settings from both profiles """
        setting_row: list[str] = []
        cell_tooltip: str = ""
        label_a: str = ""
        label_b: str = ""
        child_level: int = -1
        row_css_classes = []

        setting_a: CategorySetting = self.profile_a_settings[category][setting_key]
        setting_b: CategorySetting = self.profile_b_settings[category][setting_key]

        # *Theoretically* the internal representation and child level should be
        # the same if they both exist, so might as well take it from profile A.
        if not isinstance(setting_a, BlankSetting):
            label_a = setting_a.label
            row_css_classes.extend(setting_a.css_class)
            cell_tooltip = setting_a.internal_representation()
            child_level = setting_a.child_level
        if not isinstance(setting_b, BlankSetting):
            label_b = setting_b.label
            row_css_classes.extend(setting_b.css_class)
            if cell_tooltip == "":
                cell_tooltip = setting_b.internal_representation()
            if child_level == -1:
                child_level = setting_b.child_level

        # Skip this if they're both blank
        if isinstance(setting_a, BlankSetting) and isinstance(setting_b, BlankSetting) \
            or setting_a.skip and setting_b.skip:
            return ""

        label: str = ""
        if label_a == label_b:
            label = label_a
        elif label_a and not label_b:
            label = label_a
        elif label_b and not label_a:
            label = label_b
        else:
            # They both exist but they're not the same. Did you change language on me between profiles? Profile A wins.
            label = label_a

        # Figure out if they're different
        min_extruders = min(len(setting_a.value), len(setting_b.value))
        different = setting_a.value[:min_extruders] != setting_b.value[:min_extruders]

        row_css_class = HTMLSettingsExportReborn.get_css_row_class(row_css_classes)
        setting_row.append(indent(f'<tr class="{CssClasses.SETTING_ROW.full}{(" " + row_css_class) if row_css_class else ""}{(" " + CssClasses.COMPARE_DIFFERENT.full) if different else ""}">', base_indent))
        child_prefix = HTMLSettingsExportReborn.CHILD_SPACER * child_level
        label = html.escape(label).replace("\n", "<br>")
        setting_row.append(indent(f'<td title="{html.escape(cell_tooltip)}" class="{CssClasses.SETTING_LABEL.full}">{child_prefix}{label}</td>', base_indent + 1))

        setting_row.extend(setting_a.make_td_no_children(base_indent + 1))
        setting_row.extend(setting_b.make_td_no_children(base_indent + 1))
        setting_row.append(indent("</tr>", base_indent))
        return "\n".join(setting_row)

    def make_th_cells(self, base_indent: int = 0) -> str:
        """Make <th> cells for profile A/B, extruder #"""
        th_cells: list[str] = []
        th_cells.append(indent(f'<th>{html.escape(catalog.i18nc("@setting:label", "Setting"))}</th>', base_indent))
        for i in range(self.profile_a.extruder_count):
            th_cells.append(indent(f'<th class="{CssClasses.CENTRE.full}">{html.escape(catalog.i18nc("@compare:profile_a", "Profile A"))}\n{html.escape(catalog.i18nc("@compare:extruder_label", "Extruder #"))}{i + 1}</th>'.replace("\n", "<br>"), base_indent))
        for i in range(self.profile_b.extruder_count):
            th_cells.append(indent(f'<th class="{CssClasses.CENTRE.full}">{html.escape(catalog.i18nc("@compare:profile_a", "Profile B"))}\n{html.escape(catalog.i18nc("@compare:extruder_label", "Extruder #"))}{i + 1}</th>'.replace("\n", "<br>"), base_indent))
        return th_cells


#Resources.addSearchPath(  # Don't have any translations so not really needed right now.
#    os.path.join(os.path.abspath(os.path.dirname(__file__)),'resources')
#)  # Plugin translation file import

catalog = i18nCatalog("htmlsettingsexport")

if catalog.hasTranslationLoaded():
    Logger.log("i", "HTML Settings Export translation loaded")

def indent(string: str, level: int = 0) -> str:
    return f'{chr(9) * level}{string}'  # Heresy in plugin code. Space savings in HTML.

class HTMLSettingsExportReborn(Extension):

    # "consts" for the placeholders in HTML where these strings are used.
    # (They're in the Python so they can be dynamically localised with i18n)
    # For the buttons:
    # default = default in HTML, probably going to be overwritten by the JS on load.
    # disabled = not doing its thing (so the text is to do its thing).
    # enabled = doing its thing (so the text is to set things back to normal).
    HTML_REPLACEMENT_TITLE: str = "$$$TITLE$$$"
    HTML_REPLACEMENT_LANG: str = "$$$LANG$$$"
    HTML_REPLACEMENT_TABLE_COLUMNS: str = "$$$TABLE_COLUMNS$$$"
    HTML_REPLACEMENT_DISABLED_SETTINGS_DEFAULT: str = "$$$DISABLED_SETTINGS_DEFAULT$$$"
    HTML_REPLACEMENT_DISABLED_SETTINGS_DISABLED: str = "$$$DISABLED_SETTINGS_DISABLED$$$"
    HTML_REPLACEMENT_DISABLED_SETTINGS_ENABLED: str = "$$$DISABLED_SETTINGS_ENABLED$$$"
    HTML_REPLACEMENT_VISIBLE_SETTINGS_DEFAULT: str = "$$$VISIBLE_SETTINGS_DEFAULT$$$"
    HTML_REPLACEMENT_VISIBLE_SETTINGS_DISABLED: str = "$$$VISIBLE_SETTINGS_DISABLED$$$"
    HTML_REPLACEMENT_VISIBLE_SETTINGS_ENABLED: str = "$$$VISIBLE_SETTINGS_ENABLED$$$"
    HTML_REPLACEMENT_LOCAL_CHANGES_DEFAULT: str = "$$$LOCAL_CHANGES_DEFAULT$$$"
    HTML_REPLACEMENT_LOCAL_CHANGES_DISABLED: str = "$$$LOCAL_CHANGES_DISABLED$$$"
    HTML_REPLACEMENT_LOCAL_CHANGES_ENABLED: str = "$$$LOCAL_CHANGES_ENABLED$$$"
    HTML_REPLACEMENT_DIFFERENT_SETTINGS_DEFAULT: str = "$$$DIFFERENT_SETTINGS_DEFAULT$$$"
    HTML_REPLACEMENT_DIFFERENT_SETTINGS_DISABLED: str = "$$$DIFFERENT_SETTINGS_DISABLED$$$"
    HTML_REPLACEMENT_DIFFERENT_SETTINGS_ENABLED: str = "$$$DIFFERENT_SETTINGS_ENABLED$$$"
    HTML_REPLACEMENT_PROJECT_TITLE: str = "$$$PROJECT_NAME$$$"
    HTML_REPLACEMENT_PROFILE_NAME: str = "$$$PROFILE_NAME$$$"
    HTML_REPLACEMENT_PROFILE_A: str = "$$$PROFILE_A$$$"
    HTML_REPLACEMENT_PROFILE_A_NAME: str = "$$$PROFILE_A_NAME$$$"
    HTML_REPLACEMENT_PROFILE_B: str = "$$$PROFILE_B$$$"
    HTML_REPLACEMENT_PROFILE_B_NAME: str = "$$$PROFILE_B_NAME$$$"
    HTML_REPLACEMENT_PRINTER_A_NAME: str = "$$$PRINTER_A_NAME$$$"
    HTML_REPLACEMENT_PRINTER_B_NAME: str = "$$$PRINTER_B_NAME$$$"
    HTML_REPLACEMENT_SEARCH_PLACEHOLDER: str = "$$$SEARCH_SETTINGS_PLACEHOLDER$$$"
    HTML_REPLACEMENT_CLEAR_SEARCH: str = "$$$CLEAR_SEARCH$$$"

    CHILD_SPACER = f'<div class="{CssClasses.CHILD_SPACER.full}">►</div>'
    
    def __init__(self):
        super().__init__()

        self._application = CuraApplication.getInstance()

        self._preferences = self._application.getPreferences()

        self._plugin_dir = os.path.dirname(__file__)

        self._export_mode: ExportMode = ExportMode.REPORT
        self._compare_profile_a: SettingProfile = None
        self._compare_profile_b: SettingProfile = None
        self._profile_compare: CompareProfiles = None

        self._minify_output = True

        self._export_fail = False  # I catch so many exceptions I sometimes end up with blank files

        # Set up menu item
        self.setMenuName("HTML Settings Export")
        self.addMenuItem(catalog.i18nc("@menu:export", "Export settings"), self._save_report_html)
        self.addMenuItem("  ", lambda: None)
        self.addMenuItem(catalog.i18nc("@menu:compare_first", "Store first profile for comparison"), self._save_profile_a)
        self.addMenuItem(catalog.i18nc("@menu:make_comparison", "Export comparison with first profile"), self._save_compare_html)

    def _save_profile_a(self):
        self._compare_profile_a = self._get_setting_profile()
        Message(catalog.i18nc("@message:saved_profile_a", "Profile stored for comparison"), title = catalog.i18nc("@message:plugin_title", "HTML Settings Export Reborn"), lifetime = 15).show()

    def _save_compare_html(self):
        if self._compare_profile_a is None:
            Message(catalog.i18nc("@message:no_profile_a", "Please store a profile first"), title = catalog.i18nc("@message:plugin_title", "HTML Settings Export Reborn")).show()
            return
        self._compare_profile_b = self._get_setting_profile()
        self._profile_compare = CompareProfiles(self._compare_profile_a, self._compare_profile_b)
        self._export_mode = ExportMode.COMPARE
        self._save_settings_html()

    def _save_report_html(self):
        self._export_mode = ExportMode.REPORT
        self._save_settings_html()

    def _save_settings_html(self):
        # output_filename = os.path.abspath(os.path.join(self._plugin_dir, "cura_settings.html"))
        output_filename = self._get_file_save_path(self._application.getPrintInformation().jobName + ".html")
        if not output_filename:
            # User cancelled save dialog
            Logger.log("d", "User cancelled save for HTML export")
            return
        self._export_fail = False
        
        try:
            output_page = self._assemble_html()
            if not self._export_fail:
                with open(output_filename, "w", encoding="utf-8") as page:
                    page.write(output_page)
            else:
                raise Exception("self._export_fail triggered")
        except Exception as e:
            Logger.logException("e", f"Exception while trying to save HTML settings: {e}")
            Message(title = catalog.i18nc("@plugin_name", "HTML Settings Export Reborn"),
                    text = catalog.i18nc("@export_exception", "Error while trying to save HTML settings. Please check log file.")).show()
            return
        Logger.log("i", f"HTML settings export successful to {output_filename}")

        try:
            webbrowser.open_new_tab(output_filename)
        except Exception as e:
            Message(title = catalog.i18nc("@plugin_name", "HTML Settings Export Reborn"),
                    text = catalog.i18nc("@export_browser_fail", "Could not open a web browser to display output file.\nPlease navigate to where you saved the file and open it manually.")).show()
            Logger.log("e", f"HTMLSettingsExportReborn could not open a web browser to display output file {output_filename}\n{e}")

    def _get_file_save_path(self, suggested_name: str = "cura settings.html") -> Optional[str]:
        dialog = QFileDialog()

        dialog.setWindowTitle(catalog.i18nc("@save:dialog_title", "Save HTML Settings Export"))
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)

        # Set HTML filter string
        html_filter = catalog.i18nc("@save:html_filter", "HTML Files (*.html *.htm)")
        dialog.setNameFilters([
            html_filter,
            "All Files (*)"
        ])

        dialog.selectNameFilter(html_filter)

        # Get default file save path from last Cura save location
        default_directory = self._preferences.getValue("local_file/dialog_save_path")
        if default_directory and os.path.exists(default_directory):
            dialog.setDirectory(default_directory)
        else:
            dialog.setDirectory(os.path.expanduser("~"))  # Default to user's home directory

        dialog.selectFile(suggested_name)

        if not dialog.exec():
            # User cancelled the save
            return None

        file_name = dialog.selectedFiles()[0]
        selected_filter = dialog.selectedNameFilter()

        if selected_filter == html_filter:
            _, ext = os.path.splitext(file_name)
            if ext.lower() not in [".html", ".htm"]:
                # Add a .html extension if the HTML name filter is selected but they didn't add the extension
                file_name += ".html"

        return file_name

    def _load_file_with_replacements(self, filename: str, replacements: dict[str,str], strip_comments: Optional[str] = None) -> str:
        """Loads a file then replaces the keys in the dict with the values"""
        if strip_comments is None:
            strip_comments = self._minify_output
        
        file: str = ""
        try:
            with open(filename, "r", encoding="utf-8") as file_handle:
                file = file_handle.read()
        except Exception:
            Logger.logException("e", f"Exception trying to read {filename}")
            self._export_fail = True
            return ""
        
        for key, value in replacements.items():
            #Logger.log("d", f"Replacing {key} with {value}")
            file = file.replace(key, html.escape(str(value)))

        if strip_comments:
            # Remove HTML comments
            file = re.sub(r'(?s)\s*<!--.*?-->', "", file)
            # Remove CSS / JS Block comments
            file = re.sub(r'(?s)\s*/\*.*?\*/', "", file)
            # Remove single line JS comments
            file = re.sub(r'\s*//.*', "", file)
            
        return file

    def _minify_css_classes(self, page: str) -> str:
        """Reduce output file size by replacing full CSS class names in plugin code with abbreviations"""
        replacement_dict = {cls.full: cls.abbr for cls in CssClasses}
        for key, value in replacement_dict.items():
            search = r'(^|[\s"\'{}#:>+\~\[\],().=\\])(?:' + re.escape(key) + r')([\s"\'{}#:>+\~\[\],().=\\]|$)'
            mini = r'\g<1>' + value + r'\g<2>'
            #Logger.log("d", f'Regex search for {key} = {search} to replace with {mini}')
            page = re.sub(search, mini, page)
        comments_section = []
        comments_section.append("<!-- CSS class reference:")
        # Sort by the abbreviation (the value in the dictionary)
        for full_name, abbr in sorted(replacement_dict.items(), key=lambda item: item[1]):
            comments_section.append(f'{abbr}: {full_name}')
        comments_section.append("-->")
        html_split_end = page.rpartition("</html>")
        page = html_split_end[0] + "\n".join(comments_section) + "\n" + html_split_end[1] + html_split_end[2]
        return page

    def _make_tr_2_cells(self, key: str, value: Any, tr_indent: int = 0, row_class: str = None) -> str:
        """Generates an HTML table row string name/data pair."""
        # chr(34) is " which I can't escape in an f-string expression in Python 3.10
        new_tr = []
        new_tr.append(indent(f'<tr{(" class=" + (chr(34)) + row_class + chr(34)) if row_class else ""}>', tr_indent))
        new_tr.append(indent(f'<td class="{CssClasses.TWO_COLUMN_LEFT.full}">{key}</td><td class="{CssClasses.TWO_COLUMN_RIGHT.full}">{value}</td>', tr_indent + 1))
        new_tr.append(indent('</tr>', tr_indent))
        return "\n".join(new_tr)

    def _make_ol_from_list(self, items: list, base_indent_level: int = 0, prefix: str = "", suffix: str = "", return_single_item: bool = True) -> str:
        """Makes a HTML <ol> from a list of items and indents it."""
        if return_single_item and len(items) == 1:
            return f"{prefix}{items[0]}{suffix}"
        
        list_item_htmls = [indent(f'<li>{prefix}{item}{suffix}</li>', base_indent_level + 2) for item in items]

        return("\n" +
               indent('<ol>', base_indent_level + 1) + "\n"
               "\n".join(list_item_htmls) + "\n" +
               indent('</ol>', base_indent_level + 1)
               )

    def _get_setting_profile(self) -> SettingProfile:
        global_stack = self._application.getGlobalContainerStack()
        machine_manager = self._application.getMachineManager()
        extruder_stacks = self._application.getExtruderManager().getActiveExtruderStacks()
        extruder_count = self._application.getGlobalContainerStack().getProperty("machine_extruder_count", "value")

        empty_presets = ("", "empty", None)
        profile_name = global_stack.qualityChanges.getMetaData().get("name", "")
        if profile_name in empty_presets:
            profile_name = catalog.i18nc("@page:missing_profile_name", "Default Profile")

        # Preset / Intent (for UM printers)
        preset_name = global_stack.qualityChanges.getMetaData().get("name", "")
        if preset_name in empty_presets:
            preset_name = machine_manager.activeIntentCategory
        if preset_name in empty_presets:
            preset_name = catalog.i18nc("@page:missing_profile_name", "None")


        Logger.log("d", f"_get_setting_profile about to run with profile_name = {profile_name}")
        profile = SettingProfile(profile_name = profile_name, preset_name = preset_name, extruder_count = extruder_count)
        profile.global_changed_settings = global_stack.getTop().getAllKeys()
        profile.extruder_changed_settings = [extruder.getTop().getAllKeys() for extruder in extruder_stacks]
        profile.visible_settings = SettingPreferenceVisibilityHandler().getVisible()
        profile.printer_name = global_stack.definition.getName()
        for category in profile.settings:
            category_settings, category_label = self._get_category_settings_list(
                category, extruder_stacks, profile,
                i18n_printer_catalog if category != "machine_settings" else i18n_extruder_catalog)
            profile.settings[category] = category_settings
            profile.settings_labels[category] = category_label

        return profile



    def _assemble_html(self) -> str:
        # Information sources
        global_stack = self._application.getGlobalContainerStack()
        machine_manager = self._application.getMachineManager()
        print_information = self._application.getPrintInformation()
        extruder_stack = self._application.getExtruderManager().getActiveExtruderStacks()

        #self._modified_global_settings = global_stack.getTop().getAllKeys()
        #self._modified_extruder_settings = [extruder.getTop().getAllKeys() for extruder in extruder_stack]
        #self._visible_settings = SettingPreferenceVisibilityHandler().getVisible()
        
        output_html: list[str] = []

        # Get locale specific things all at once in case the system's locale
        # is different to Cura's so we change it for the shortest time possible.
        original_locale = None
        formatted_date_time = None
        
        try:
            # 1. Save the current locale settings.
            # This returns a tuple containing the settings for all categories.
            original_locale = locale.setlocale(locale.LC_ALL)
            
            # 2. Attempt to set the locale to the system's default.
            # An empty string "" tells Python to use environment variables.
            locale.setlocale(locale.LC_ALL, "")

            # Get current date and time
            now = datetime.now()
            # Format using locale-specific date and time, separated by a space
            formatted_date_time = now.strftime("%x %X") 
            
        except locale.Error as e:
            # If locale setting fails (e.g., locale not supported on the OS),
            # log a warning and proceed with a default, non-locale-specific format.
            Logger.log("e", f"Could not set system locale for date/time formatting: {e}. Using ISO format as fallback.")
            now = datetime.now()
            # Fallback to ISO format, or any other default you prefer
            formatted_date_time = now.isoformat(sep=' ', timespec='seconds') 
            # You'd then use this fallback `formatted_date_time` in your HTML
            
        finally:
            # 3. CRUCIALLY: Restore the original locale settings.
            # This `finally` block ensures this happens even if an exception occurs.
            if original_locale is not None:
                try:
                    locale.setlocale(locale.LC_ALL, original_locale)
                except locale.Error as e:
                    # Log if restoring locale fails (should be rare if `original_locale` was valid)
                    Logger.log("e", f"Failed to restore original locale: {e}")

        if self._export_mode == ExportMode.REPORT:
            # Get a thumbnail first because it might take a little bit of time
            encoded_snapshot: str = None
            snapshot = self._createSnapshot()
            if snapshot:
                thumbnail_buffer = QBuffer()
                
                thumbnail_buffer.open(QBuffer.OpenModeFlag.ReadWrite)
                        
                snapshot.save(thumbnail_buffer, "PNG")
                encoded_snapshot = thumbnail_buffer.data().toBase64().data().decode("utf-8")

        
        # Indent level for rows in the top table
        # html > body > div > table
        info_indent: int = 4

        # Indent level for each <details> block
        # html > body > div
        details_indent: int = 3

        # Indent level for each setting row
        # html > body > div > details > table > tbody
        setting_indent: int = 6

        # Get print quality settings for each extruder
        # Categories appear in the same order they do in Cura's print quality settings panel
        #settings_categories = ["resolution", "shell", "top_bottom", "infill", "material",
                               #"speed", "travel", "cooling", "dual", "support", "platform_adhesion",
                               #"meshfix", "blackmagic", "experimental"]
        setting_profile = self._get_setting_profile()
        #Logger.log("d", f"setting_profile has just been created, and setting_profile.profile_name = {setting_profile.profile_name}")

        # Get settings for each category
        #for i, stack in enumerate(extruder_stack):
        #    for category in settings_categories:
        #        output_html.extend(self._get_category_settings(category, stack, info_indent -1, i if extruder_count > 1 else -1, i18n_printer_catalog))



        empty_presets = ("", "empty", None)
        # Preset / Intent (for UM printers)
        preset_name = setting_profile.preset_name
        if preset_name == machine_manager.activeIntentCategory:
            um_intent = True
        else:
            um_intent = False
        profile_name = setting_profile.profile_name

        # Add header with CSS and start of page
        start_html_file = os.path.abspath(os.path.join(self._plugin_dir, "html_start.html"))
        report_sticky_html_file = os.path.abspath(os.path.join(self._plugin_dir, "html_sticky_report.html"))
        compare_sticky_html_file = os.path.abspath(os.path.join(self._plugin_dir, "html_sticky_compare.html"))
        main_start_html_file = os.path.abspath(os.path.join(self._plugin_dir, "html_main_start.html"))
        
        start_html_replacements = {
            self.HTML_REPLACEMENT_TITLE: catalog.i18nc("@page:title", "Cura Print Settings"),
            self.HTML_REPLACEMENT_LANG: catalog.i18nc("@page:language", "en"),
            self.HTML_REPLACEMENT_TABLE_COLUMNS: setting_profile.extruder_count if self._export_mode == ExportMode.REPORT else self._profile_compare.total_extruders
        }
        sticky_replacements: dict[str, str] = {
            self.HTML_REPLACEMENT_LOCAL_CHANGES_DEFAULT: catalog.i18nc("@button:local_changes", "Toggle only user changes"),
            self.HTML_REPLACEMENT_VISIBLE_SETTINGS_DEFAULT: catalog.i18nc("@button:visible_settings", "Toggle visible settings"),
            self.HTML_REPLACEMENT_DISABLED_SETTINGS_DEFAULT: catalog.i18nc("@button:unused_settings", "Toggle disabled settings"),
            self.HTML_REPLACEMENT_SEARCH_PLACEHOLDER: catalog.i18nc("@page:search_placeholder", "Search settings..."),
            self.HTML_REPLACEMENT_CLEAR_SEARCH: catalog.i18nc("@button:clear_search", "Clear"),
        }
        # Logger.log("d", f"Before sticky_replacements, setting_profile.profile_name = {setting_profile.profile_name}")
        if self._export_mode == ExportMode.REPORT:
            report_replacements = {
                self.HTML_REPLACEMENT_PROJECT_TITLE: print_information.jobName,
                self.HTML_REPLACEMENT_PROFILE_NAME: setting_profile.profile_name,
            }
            sticky_replacements.update(report_replacements)
        elif self._export_mode == ExportMode.COMPARE:
            compare_replacements = {
                self.HTML_REPLACEMENT_PROFILE_A: catalog.i18nc("@sticky:profile_a", "Profile A"),
                self.HTML_REPLACEMENT_PROFILE_A_NAME: self._profile_compare.profile_a.profile_name + f' ({self._profile_compare.profile_a.preset_name})',
                self.HTML_REPLACEMENT_PROFILE_B: catalog.i18nc("@sticky:profile_b", "Profile B"),
                self.HTML_REPLACEMENT_PROFILE_B_NAME: self._profile_compare.profile_b.profile_name + f' ({self._profile_compare.profile_b.preset_name})',
                self.HTML_REPLACEMENT_PRINTER_A_NAME: self._profile_compare.profile_a.printer_name,
                self.HTML_REPLACEMENT_PRINTER_B_NAME: self._profile_compare.profile_b.printer_name,
                self.HTML_REPLACEMENT_DIFFERENT_SETTINGS_DEFAULT: catalog.i18nc("@button:different_settings", "Toggle different settings"),
            }
            sticky_replacements.update(compare_replacements)
        else:
            self._export_fail = True
            raise ValueError(f'Invalid export_mode: {self._export_mode}')
        sticky_html: str = self._load_file_with_replacements(report_sticky_html_file if self._export_mode == ExportMode.REPORT else compare_sticky_html_file, sticky_replacements)
        #Logger.log("d", f"Sticky replacements: {sticky_replacements}")
        start_html: str = self._load_file_with_replacements(start_html_file, start_html_replacements)

        # Yes I realise it's just one line but it doesn't belong in the sticky
        main_start_html: str = self._load_file_with_replacements(main_start_html_file, {})

        output_html.append(start_html)
        output_html.append(sticky_html)
        output_html.append(main_start_html)

        if self._export_mode == ExportMode.REPORT:
            output_html.append(indent('<table "border="1" cellpadding="3">', info_indent - 1))
            # Project name
            output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Project Name"), print_information.jobName), info_indent))
            # Printer name
            output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Printer"), setting_profile.printer_name), info_indent))
            # Thumbnail
            if encoded_snapshot:
                output_html.append(indent(f'<tr><td colspan="2"><img class="{CssClasses.THUMBNAIL.full}" src="data:image/png;base64,{encoded_snapshot}" width="300" height="300", alt="{print_information.jobName}"></td></tr>', info_indent))
            # Date/time
            output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Date/time"), formatted_date_time), info_indent))
            # Cura version
            output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Cura Version"), CuraVersion), info_indent))

            output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Intent") if um_intent else catalog.i18nc("@label", "Profile"), preset_name), info_indent))
            # Quality profile
            output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Quality Profile"), profile_name), info_indent))
            # Extruders enabled/materials (multiple extruders)
            if setting_profile.extruder_count > 1:
                extruders_enabled: list = []
                extruder_materials: list = []
                for extruder in extruder_stack:
                    extruders_enabled.append(extruder.getMetaDataEntry("enabled"))
                    extruder_materials.append(extruder.material.getMetaData().get("material", ""))
                # Enabled extruders
                extruders_enabled_html = self._make_ol_from_list(extruders_enabled, base_indent_level = info_indent)
                output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Extruders enabled"), extruders_enabled_html), info_indent))
                # Materials
                extruder_materials_html = self._make_ol_from_list(extruder_materials, base_indent_level = info_indent)
                output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Extruder materials"), extruder_materials_html), info_indent))
            # Material (single extruder)
            else:
                output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Material"), extruder_stack[0].material.getMetaData().get("material", "")), info_indent))
            # Material weight
            output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Material weight used"), self._make_ol_from_list(list((round(x, 1) for x in print_information.materialWeights)), base_indent_level = info_indent, suffix = "g")), info_indent))
            # Material length
            output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Material length used"), self._make_ol_from_list(list((round(x, 2) for x in print_information.materialLengths)), info_indent, suffix = "m")), info_indent))
            # Material cost
            cura_currency = str(self._preferences.getValue("cura/currency"))
            output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Material cost"), self._make_ol_from_list(list((round(x, 2) for x in print_information.materialCosts)), info_indent, prefix = cura_currency)), info_indent))
            # Printing time
            output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Estimated print time"), print_information.currentPrintTime.getDisplayString(DurationFormat.Format.Long)), info_indent))
            # Close basic information table
            output_html.append(indent('</table>', info_indent - 1))


        # Actually output from our SettingProfile
        if self._export_mode == ExportMode.REPORT:
            for category, category_settings in setting_profile.settings.items():
                category_label = setting_profile.settings_labels[category]

                details_open = True  # Almost always true
                if category == "dual" and setting_profile.extruder_count == 1:
                    details_open = False
                output_html.append(self._make_category_header(category_label, setting_profile.extruder_count, details_indent, category, details_open))
                for setting in category_settings:
                    output_html.append(self._make_category_setting_row(setting, setting_indent))
                output_html.append(self._make_category_footer(details_indent))
        elif self._export_mode == ExportMode.COMPARE:
            for category, category_settings in self._profile_compare.category_keys.items():
                # If you've changed your language between profiles you'll have to live with your first choice
                category_label = self._profile_compare.profile_a.settings_labels[category]

                details_open = True  # Almost always true
                if category == "dual" and setting_profile.extruder_count == 1:
                    details_open = False
                output_html.append(self._make_category_header(category_label, self._profile_compare.total_extruders, details_indent, category, details_open))
                for setting in category_settings:
                    output_html.append(self._profile_compare.make_setting_row(category, setting, setting_indent))
                output_html.append(self._make_category_footer(details_indent))
        # Get settings for each extruder
        #extruder_settings, extruder_label = self._get_category_settings_list("machine_settings", extruder_stack, i18n_extruder_catalog)
        #output_html.append(self._make_category_header(extruder_label, details_indent, "machine_settings"))
        #for setting in extruder_settings:
        #    output_html.append(self._make_category_setting_row(setting, setting_indent))
        #output_html.append(self._make_category_footer(details_indent))

        if self._export_mode == ExportMode.REPORT:
            scripts_list = global_stack.getMetaDataEntry("post_processing_scripts")
            if scripts_list :
                # Get post-processing scripts
                output_html.append(self._make_category_header(catalog.i18nc("@label", "Post-processing scripts"), setting_profile.extruder_count, details_indent, "post_processing_scripts", two_column=True, two_column_titles=[catalog.i18nc("@settings:post_name", "Post-processor name"), catalog.i18nc("@settings:post_settings", "Post-processor settings")]))
                for script_str in scripts_list.split("\n"):
                    if not script_str:
                        continue
                    script_str = script_str.replace(r"\\\n", "\n").replace(r"\\\\", "\\\\")  # Unescape escape sequences.
                    script_parser = configparser.ConfigParser(interpolation=None)
                    script_parser.optionxform = str  # type: ignore  # Don't transform the setting keys as they are case-sensitive.
                    try:
                        script_parser.read_string(script_str)
                    except configparser.Error as e:
                        Logger.log("e", f"Stored post-processing scripts have syntax errors: {e}")
                        continue
                    for script_name, settings in script_parser.items():  # There should only be one, really! Otherwise we can't guarantee the order or allow multiple uses of the same script.
                        if script_name == "DEFAULT":  # ConfigParser always has a DEFAULT section, but we don't fill it. Ignore this one.
                            continue
                        setting_param = ""
                        for setting_key, setting_value in settings.items():
                            setting_param += f'{html.escape(setting_key)}: {html.escape(setting_value)}<br>'  # Have to escape it here because I'm deliberately adding the <br>s
                        output_html.append(self._make_tr_2_cells(html.escape(script_name), setting_param.rstrip("<br>"), info_indent + 1, CssClasses.POSTS_SETTINGS.full))

                output_html.append(self._make_category_footer(details_indent))

        end_html_file = os.path.abspath(os.path.join(self._plugin_dir, "html_end.html"))
        end_html_replacements: dict[str, str] = {
            self.HTML_REPLACEMENT_DISABLED_SETTINGS_DISABLED: catalog.i18nc("@button:settings_disabled_disabled", "Hide disabled settings"),
            self.HTML_REPLACEMENT_DISABLED_SETTINGS_ENABLED: catalog.i18nc("@button:settings_disabled_enabled", "Show disabled settings"),
            self.HTML_REPLACEMENT_VISIBLE_SETTINGS_DISABLED: catalog.i18nc("@button:settings_visible_disabled", "Hide settings not visible in profile"),
            self.HTML_REPLACEMENT_VISIBLE_SETTINGS_ENABLED: catalog.i18nc("@button:settings_visible_enabled", "Show settings not visible in profile"),
            self.HTML_REPLACEMENT_LOCAL_CHANGES_DISABLED: catalog.i18nc("@button:settings_local_disabled", "Filter to only user changes"),
            self.HTML_REPLACEMENT_LOCAL_CHANGES_ENABLED: catalog.i18nc("@button:settings_local_enabled", "Remove user changes filter"),
            self.HTML_REPLACEMENT_DIFFERENT_SETTINGS_DISABLED: catalog.i18nc("@button:settings_different_disabled", "Filter to only different settings"),
            self.HTML_REPLACEMENT_DIFFERENT_SETTINGS_ENABLED: catalog.i18nc("@button:settings_different_enabled", "Remove different settings filter"),
        }

        end_html = self._load_file_with_replacements(end_html_file, end_html_replacements)

        output_html.append(end_html)
        # Get rid of any blank lines
        output_html = [line for line in output_html if line.strip() != ""]
        
        output_html = "\n".join(output_html)
        if self._minify_output:
            output_html = self._minify_css_classes(output_html)
        return output_html
        

    def _single_extruder_skip_setting(self, setting_name: str, setting_value: any) -> bool:
        """
        Determines if a setting should be skipped in the HTML output,
        specifically for single-extruder machines.

        :param setting_name: The unique ID of the setting (e.g., "extruder_prime_x_position").
        :param setting_value: The current value of the setting.
        :return: True if the setting should be skipped, False otherwise.
        """

        # These keywords are hidden regardless of value
        multi_extruder_blacklist: list[str] = ["prime_tower", "prime_blob", "extruder_switch"]
        for keyword in multi_extruder_blacklist:
            if keyword in setting_name:
                return True
        
        # These keywords have their value checked
        multi_extruder_keywords: list[str] = ["extruder"]
        multi_extruder_invalid_values: list[str] = ["-1", "0", "1"]
        for keyword in multi_extruder_keywords:
            if keyword in setting_name and str(setting_value) in multi_extruder_invalid_values:
                return True

        return False

    def _make_category_header(self, text: str, extruder_count: int, base_indent: int, category_key: str, details_open: bool = True, two_column: bool = False, two_column_titles: list[str] = None) -> str:
        category_header: list[str] = []
        category_header.append(indent(f'<details class="{CssClasses.COLLAPSIBLE_SETTING.full} setting-{category_key}"{" open" if details_open else ""}>', base_indent))
        category_header.append(indent(f'<summary class="{CssClasses.CATEGORY_HEADER.full}"><h2>{html.escape(text)}</h2></summary>', base_indent + 1))
        category_header.append(indent(f'<table class="{CssClasses.CATEGORY.full}">', base_indent + 1))
        category_header.append(indent('<thead>', base_indent + 2))
        category_header.append(indent('<tr>', base_indent + 3))
        # I think this is the most defensive thing I've ever written
        if two_column:
            if two_column_titles is None or not isinstance(two_column_titles, list):
                two_column_titles = ["", ""]
            else:
                match len(two_column_titles):
                    case 0:
                        two_column_titles = ["", ""]
                    case 1:
                        two_column_titles.append("")
                    case _:
                        two_column_titles = two_column_titles[:2]  # Handles len() == 2 fine
            # Ensure all elements are strings, replacing non-strings with empty strings
            two_column_titles = [item if isinstance(item, str) else "" for item in two_column_titles]
            for title in two_column_titles:
                category_header.append(indent(f'<th>{html.escape(title)}</th>', base_indent + 4))
        elif self._export_mode == ExportMode.COMPARE:
            category_header.extend(self._profile_compare.make_th_cells(base_indent + 4))
        else:
            # If self_export_mode wasn't valid it should have raised an exception well before now
            category_header.append(indent(f'<th>{html.escape(catalog.i18nc("@setting:label", "Setting"))}</th>', base_indent + 4))
            for i in range(extruder_count):
                category_header.append(indent(f'<th>{html.escape(catalog.i18nc("@settings:extruder", "Extruder"))} #{i + 1}</th>', base_indent + 4))
        category_header.append(indent('</tr>', base_indent + 3))
        category_header.append(indent('</thead>', base_indent + 2))
        category_header.append(indent('<tbody>', base_indent + 2))
        return "\n".join(category_header)

    def _make_category_setting_row(self, setting: CategorySetting, base_indent: int = 0) -> str:
        if setting.skip:
            return ""
        row_css_class = self.get_css_row_class(setting.css_class)
        category_setting_html_lines: list[str] = []
        category_setting_html_lines.append(indent(f'<tr class="{CssClasses.SETTING_ROW.full}{(" " + row_css_class) if row_css_class else ""}">', base_indent))
        cell_tooltip = setting.internal_representation()
        child_prefix = self.CHILD_SPACER * setting.child_level
        category_setting_html_lines.append(indent(f'<td title="{html.escape(cell_tooltip)}" class="{CssClasses.SETTING_LABEL.full}">{child_prefix}{html.escape(setting.label)}</td>', base_indent + 1))
        for i, value in enumerate(setting.value):
            if setting.error_class[i]:
                cell_class = setting.error_class[i]
            elif setting.css_class[i]:
                cell_class = setting.css_class[i]
            else:
                cell_class = ""
            class_tooltip = self.css_class_to_human_readable(cell_class if cell_class else row_css_class)
            display_value = html.escape(value.replace("<br>", "\n")).replace("\n", "<br>")  # For when you want a safely escaped value which is subsequently unescaped.
            category_setting_html_lines.append(indent(f'<td class="{cell_class + (" " + CssClasses.SETTING_VALUE.full) if cell_class else CssClasses.SETTING_VALUE.full}" title="{html.escape(class_tooltip)}">{display_value}</td>', base_indent + 1))
        category_setting_html_lines.append(indent('</tr>', base_indent))
        for child_key in setting.children:
            if setting.children[child_key] is not None:  # Shouldn't be None, but in case it is
                category_setting_html_lines.append(self._make_category_setting_row(setting.children[child_key], base_indent))
        return "\n".join(category_setting_html_lines)

    def _make_category_footer(self, base_indent: int):
        return f'{indent("</tbody>", base_indent + 2)}\n{indent("</table>", base_indent + 1)}\n{indent("</details>", base_indent)}'

    @staticmethod
    def get_css_row_class(classes: list[str] | str) -> str:
        if isinstance(classes, str):
            return classes

        classes = [value for value in classes if value != ""]

        # local > disabled > hidden > normal
        possible_classes = (CssClasses.SETTING_LOCAL.full, CssClasses.SETTING_DISABLED.full, CssClasses.SETTING_HIDDEN.full, CssClasses.SETTING_NORMAL.full)
        for possible_class in possible_classes:
            if all(css_class == possible_class for css_class in classes):
                return possible_class
        for full_class, some_class in zip(possible_classes[:-1], (CssClasses.SOME_LOCAL.full, CssClasses.SOME_DISABLED.full, CssClasses.SOME_HIDDEN.full)):
            if any(css_class == full_class for css_class in classes):
                return some_class
        return CssClasses.SETTING_NORMAL.full  # Fallback if they're all normal

    @staticmethod
    def css_class_to_human_readable(css_class: str) -> str:
        match css_class:
            case CssClasses.SETTING_LOCAL.full:
                return catalog.i18nc("@setting:class_local", "User set")
            case CssClasses.SETTING_NORMAL.full:
                return catalog.i18nc("@setting:class_normal", "")
            case CssClasses.SETTING_HIDDEN.full:
                return catalog.i18nc("@setting:class_hidden", "Hidden")
            case CssClasses.SETTING_DISABLED.full:
                return catalog.i18nc("@setting:class_disabled", "Disabled")
            case CssClasses.ERROR_WARNING.full:
                return catalog.i18nc("@settings:class_warning", "Value warning")
            case CssClasses.ERROR_ERROR.full:
                return catalog.i18nc("@settings:class_error", "Value error")
            case _:
                return catalog.i18nc("@settings:class_fallthrough", "")

    def _get_category_settings_list(self, category_key: str, extruder_stack, profile: SettingProfile, local_catalog: i18nCatalog, children_local_stack: bool = False) -> tuple[list[CategorySetting], str]:
        # Get translated category name... just make sure we're in a category
        translation_key = category_key + " label"
        category_translated = category_key  # We'll get value in a second, just use key as a fallback
        if extruder_stack[0].getProperty(category_key, "type") == "category":
            category_label = extruder_stack[0].getProperty(category_key, "label")
            category_translated = local_catalog.i18nc(translation_key, category_label)
        else:
            # This should only be run on the top level of categories
            return ([], "")
        category_settings: list[CategorySetting] = []

        children_keys_list: list[str] = []
        if children_local_stack:
            # Parse all extruders in case they have different settings
            for extruder in extruder_stack:
                for child in extruder.getSettingDefinition(category_key).children:
                    if child not in children_keys_list:
                        children_keys_list.append(child)
        else:
            children_keys_list = [child_def.key for child_def in self._application.getGlobalContainerStack().getSettingDefinition(category_key).children]

        for child_key in children_keys_list:
            category_settings.append(self._get_setting(child_key, category_key, extruder_stack, profile, local_catalog, 0, children_local_stack))

        return (category_settings, category_translated)

    def _get_setting(self, key: str, category_key: str, extruder_stack, profile: SettingProfile, local_catalog: i18nCatalog, child_level: int = 0, children_local_stack: bool = False, recursive = True) -> CategorySetting:
        setting = CategorySetting(key = key, child_level = child_level, extruder_count = len(extruder_stack))
        
        for i, extruder in enumerate(extruder_stack):
            # Check to see if the value exists and bail if it doesn't
            css_class: str = ""
            setting_value = extruder.getProperty(key, "value")
            if setting_value is None:
                setting.css_class[i] = CssClasses.SETTING_DISABLED.full
                continue
            # Add the label, if it isn't already there
            if not setting.label:
                translation_key = key + " label"
                setting.label = local_catalog.i18nc(translation_key, extruder.getProperty(key, "label"))
            
            setting_type = extruder.getProperty(key, "type")
            
            # Set the type so we can use it as an internal representation later
            if not setting.setting_type:
                setting.setting_type = str(setting_type)

            # Figure out if it needs some special styling
            if not extruder.getProperty(key, "enabled"):
                css_class = CssClasses.SETTING_DISABLED.full
            elif key in profile.global_changed_settings or key in profile.extruder_changed_settings[i]:
                css_class = CssClasses.SETTING_LOCAL.full
            elif key not in profile.visible_settings:
                css_class = CssClasses.SETTING_HIDDEN.full
            else:
                css_class = CssClasses.SETTING_NORMAL.full
            setting.css_class[i] = css_class

            setting_string = ""
            setting_error: str = ""
            
            setting_type_str = str(setting_type)
            match setting_type_str:
                case "optional_extruder":
                    # If it's not -1 it seems to be stringly typed... sometimes?
                    if setting_value == -1 or setting_value == "-1":
                        setting_string = catalog.i18nc("@setting:unchanged", "Not overridden")
                    else:
                        setting_value = int(setting_value) + 1
                        setting_string = str(setting_value)

                case "extruder":
                    setting_value = int(setting_value) + 1
                    setting_string = str(setting_value)

                case "int" | "float":
                    # Pretty sure all the extruder ones are one of the above types but just in case
                    if profile.extruder_count > 1 and "extruder_nr" in key:
                        if setting_value == -1:
                            setting_string = catalog.i18nc("@setting:unchanged", "Not overridden")
                        else:
                            setting_value += 1
                            
                    if setting_string == "":  # Skip all this if I set it to a string earlier
                        if setting_type_str == "float":
                            setting_string = str(float(round(setting_value, 4))).rstrip("0").rstrip(".")  # Drop trailing zeroes and decimal point if it's a whole number
                        else:
                            setting_string = str(int(setting_value))

                        minimum_value = extruder.getProperty(key, "minimum_value")
                        maximum_value = extruder.getProperty(key, "maximum_value")
                        minimum_value_warning = extruder.getProperty(key, "minimum_value_warning")
                        maximum_value_warning = extruder.getProperty(key, "maximum_value_warning")

                        try:  # I'm None checking but it never hurts to have a safety net
                            if minimum_value is not None:
                                minimum_value = float(minimum_value)
                            if maximum_value is not None:
                                maximum_value = float(maximum_value)
                            if minimum_value_warning is not None:
                                minimum_value_warning = float(minimum_value_warning)
                            if maximum_value_warning is not None:
                                maximum_value_warning = float(maximum_value_warning)

                            if (minimum_value is not None and setting_value < minimum_value) or \
                            (maximum_value is not None and setting_value > maximum_value):
                                setting_error = CssClasses.ERROR_ERROR.full
                            elif (minimum_value_warning is not None and setting_value < minimum_value_warning) or \
                                (maximum_value_warning is not None and setting_value > maximum_value_warning):
                                setting_error = CssClasses.ERROR_WARNING.full
                        except (ValueError, TypeError) as e:
                            Logger.log("e", f"Error trying to convert minimum/maximum value for {key}: {e}")
                            Message(title = catalog.i18nc("@plugin_name", "HTML Settings Export Reborn"),
                            text = catalog.i18nc("@export_exception", "Error while trying to save HTML settings. Please check log file.")).show()
                            self._export_fail = True
                case "enum":
                    option_translation_key = key + "option" + str(setting_value)
                    options = extruder.getProperty(key, "options")
                    untranslated_option = options[str(setting_value)]
                    setting_string = local_catalog.i18nc(option_translation_key, untranslated_option)

                case _:
                    setting_string = str(setting_value).replace("\n", "<br>")

            setting_string += str(extruder.getProperty(key, "unit")) if extruder.getProperty(key, "unit") else ""
            setting.value[i] = setting_string
            if setting_error:
                setting.error_class[i] = setting_error

            if profile.extruder_count == 1 and category_key != "machine_settings":
                if self._single_extruder_skip_setting(key, setting_value):
                    setting.skip = True

        if recursive:
            children_keys_list: list[str] = []
            if children_local_stack:
                # Parse all extruders in case they have different settings
                for extruder in extruder_stack:
                    for child in extruder.getSettingDefinition(key).children:
                        if child not in children_keys_list:
                            children_keys_list.append(child)
            else:
                children_keys_list = [child_def.key for child_def in self._application.getGlobalContainerStack().getSettingDefinition(key).children]

            for child_key in children_keys_list:
                setting.children[child_key] = self._get_setting(child_key, category_key, extruder_stack, profile, local_catalog, child_level + 1, children_local_stack)

            return setting

    @call_on_qt_thread  # must be called from the main thread because of OpenGL
    def _createSnapshot(self):
        backend = self._application.getBackend()
        snapshot = None if getattr(backend, "getLatestSnapshot", None) is None else backend.getLatestSnapshot()
        if snapshot is not None:
            return snapshot
        Logger.log("d", "Creating thumbnail image...")
        if not CuraApplication.getInstance().isVisible:
            Logger.log("w", "Can't create snapshot when renderer not initialized.")
            return None
        try:
            snapshot = Snapshot.snapshot(width=300, height=300)
        except Exception as e:
            Logger.logException("w", f"Failed to create snapshot image: {e}")
            return None
        if snapshot is None:
            Message(title = catalog.i18nc("@plugin_name", "HTML Settings Export Reborn"),
                    text = catalog.i18nc("@error_snapshot", "Error encountered while generating a thumbnail.\nPlease try slicing the scene then exporting again.")).show()
        return snapshot
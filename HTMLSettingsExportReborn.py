# HTML Settings Export Reborn
# Copyright Slashee the Cow 2025-
#
# Based on CuraHtmlDoc by 5@xes
# https://github.com/5axes/CuraHtmlDoc/
#--------------------------------------------------------------------------------------------------
# Version history (Reborn edition)
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
import html
import locale
import os
import webbrowser

from dataclasses import InitVar, dataclass, field
from datetime import datetime
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
from UM.Scene.Selection import Selection
from UM.Settings.ContainerStack import ContainerStack
from UM.Settings.InstanceContainer import InstanceContainer
from UM.Settings.Models.SettingPreferenceVisibilityHandler import \
    SettingPreferenceVisibilityHandler


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
    children: list[Optional["CategorySetting"]] = field(default_factory = list)
    skip: bool = False

    extruder_count: InitVar[int] = 1

    def __post_init__(self, extruder_count: int):
        """Pre-populate lists so no pesky IndexErrors crop up"""
        self.value = [""] * extruder_count
        self.css_class = [""] * extruder_count
        self.error_class = [""] * extruder_count

    def internal_representation(self) -> str:
        """Format a string to be used for the HTML <title> attribute as a tooltip"""
        return f"{self.key}: {self.setting_type}"



i18n_cura_catalog = i18nCatalog("cura")
i18n_printer_catalog = i18nCatalog("fdmprinter.def.json")
i18n_extruder_catalog = i18nCatalog("fdmextruder.def.json")

#Resources.addSearchPath(  # Don't have any translations so not really needed right now.
#    os.path.join(os.path.abspath(os.path.dirname(__file__)),'resources')
#)  # Plugin translation file import

catalog = i18nCatalog("htmlsettingsexport")

if catalog.hasTranslationLoaded():
    Logger.log("i", "HTML Settings Export translation loaded")

def indent(string: str, level: int = 0) -> str:
    return f'{"    " * level}{string}'
    
class HTMLSettingsExportReborn(Extension):

    # "consts" for the placeholders in HTML where these strings are used.
    # (They're in the Python so they can be dynamically localised with i18n)
    # For the buttons:
    # default = default in HTML, probably going to be overwritten by the JS on load.
    # disabled = not doing its thing (so the text is to do its thing).
    # enabled = doing its thing (so the text is to set things back to normal).
    HTML_REPLACEMENT_TITLE: str = "$$$TITLE$$$"
    HTML_REPLACEMENT_LANG: str = "$$$LANG$$$"
    HTML_REPLACEMENT_DISABLED_SETTINGS_DEFAULT: str = "$$$DISABLED_SETTINGS_DEFAULT$$$"
    HTML_REPLACEMENT_DISABLED_SETTINGS_DISABLED: str = "$$$DISABLED_SETTINGS_DISABLED$$$"
    HTML_REPLACEMENT_DISABLED_SETTINGS_ENABLED: str = "$$$DISABLED_SETTINGS_ENABLED$$$"
    HTML_REPLACEMENT_VISIBLE_SETTINGS_DEFAULT: str = "$$$VISIBLE_SETTINGS_DEFAULT$$$"
    HTML_REPLACEMENT_VISIBLE_SETTINGS_DISABLED: str = "$$$VISIBLE_SETTINGS_DISABLED$$$"
    HTML_REPLACEMENT_VISIBLE_SETTINGS_ENABLED: str = "$$$VISIBLE_SETTINGS_ENABLED$$$"
    HTML_REPLACEMENT_LOCAL_CHANGES_DEFAULT: str = "$$$LOCAL_CHANGES_DEFAULT$$$"
    HTML_REPLACEMENT_LOCAL_CHANGES_DISABLED: str = "$$$LOCAL_CHANGES_DISABLED$$$"
    HTML_REPLACEMENT_LOCAL_CHANGES_ENABLED: str = "$$$LOCAL_CHANGES_ENABLED$$$"
    HTML_REPLACEMENT_PROJECT_TITLE: str = "$$$PROJECT_NAME$$$"
    HTML_REPLACEMENT_PROFILE_NAME: str = "$$$PROFILE_NAME$$$"
    HTML_REPLACEMENT_SEARCH_PLACEHOLDER: str = "$$$SEARCH_SETTINGS_PLACEHOLDER$$$"
    HTML_REPLACEMENT_CLEAR_SEARCH: str = "$$$CLEAR_SEARCH$$$"
    CHILD_SPACER = '<div class="child-spacer">►</div>'
    
    def __init__(self):
        super().__init__()

        self._application = CuraApplication.getInstance()

        self._preferences = self._application.getPreferences()

        self._modified_global_settings: list = []
        self._modified_extruder_settings: list = []
        self._visible_settings: list = []

        self._plugin_dir = os.path.dirname(__file__)
        self._single_extruder: bool = False
        self._extruder_count: int = 1

        self._export_fail = False  # I catch so many exceptions I sometimes end up with blank files

        # Set up menu item
        self.setMenuName("HTML Settings Export")
        self.addMenuItem("Export settings", self._save_settings_html)

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

    def _make_tr_2_cells(self, key: str, value: Any, tr_indent: int = 0, row_class: str = None) -> str:
        """Generates an HTML table row string name/data pair."""
        # chr(34) is " which I can't escape in an f-string expression in Python 3.10
        return indent(f'<tr{(" class=" + (chr(34)) + row_class + chr(34)) if row_class else ""}><td class="two-column-left">{key}</td><td class="two-column-right">{value}</td></tr>', tr_indent)

    def _make_ol_from_list(self, items: list, base_indent_level: int = 0, prefix: str = "", suffix: str = "", return_single_item: bool = True) -> str:
        """Makes a HTML <ol> from a list of items and indents it."""
        if return_single_item and len(items) == 1:
            return f"{prefix}{items[0]}{suffix}"
        
        list_item_htmls = [indent(f'<li>{prefix}{item}{suffix}</li>', base_indent_level + 2) for item in items]

        return("\n" +
               indent('<ol>', base_indent_level + 1) +
               "\n".join(list_item_htmls) + "\n" +
               indent('</ol>', base_indent_level + 1)
               )

    def _assemble_html(self) -> str:
        # Information sources
        global_stack = self._application.getGlobalContainerStack()
        machine_manager = self._application.getMachineManager()
        print_information = self._application.getPrintInformation()
        extruder_stack = self._application.getExtruderManager().getActiveExtruderStacks()
        self._extruder_count = global_stack.getProperty("machine_extruder_count", "value")
        self._single_extruder = self._extruder_count == 1

        self._modified_global_settings = global_stack.getTop().getAllKeys()
        self._modified_extruder_settings = [extruder.getTop().getAllKeys() for extruder in extruder_stack]
        self._visible_settings = SettingPreferenceVisibilityHandler().getVisible()
        
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


        # Add header with CSS and start of page
        start_html_file = os.path.abspath(os.path.join(self._plugin_dir, "html_start.html"))
        start_html: str = ""
        try:
            with open(start_html_file, "r", encoding="utf-8") as start:
                start_html = start.read()
        except Exception:
            Logger.logException("e", "Exception trying to read html_start.html")
            self._export_fail = True
            return ""
        profile_name = global_stack.qualityChanges.getMetaData().get("name", "")
        if profile_name in ("", "empty", None):
            profile_name = catalog.i18nc("@page:missing_profile_name", "Default Profile")
        start_html = (start_html.replace(self.HTML_REPLACEMENT_TITLE, catalog.i18nc("@page:title", "Cura Print Settings"))
                                .replace(self.HTML_REPLACEMENT_LANG, catalog.i18nc("@page:language", "en"))
                                .replace(self.HTML_REPLACEMENT_LOCAL_CHANGES_DEFAULT, catalog.i18nc("@button:local_changes", "Toggle only user changes"))
                                .replace(self.HTML_REPLACEMENT_VISIBLE_SETTINGS_DEFAULT, catalog.i18nc("@button:visible_settings", "Toggle visible settings"))
                                .replace(self.HTML_REPLACEMENT_DISABLED_SETTINGS_DEFAULT, catalog.i18nc("@button:unused_settings", "Toggle disabled settings"))
                                .replace(self.HTML_REPLACEMENT_PROJECT_TITLE, print_information.jobName)
                                .replace(self.HTML_REPLACEMENT_PROFILE_NAME, profile_name)
                                .replace(self.HTML_REPLACEMENT_SEARCH_PLACEHOLDER, catalog.i18nc("@page:search_placeholder", "Search settings..."))
                                .replace(self.HTML_REPLACEMENT_CLEAR_SEARCH, catalog.i18nc("@button:clear_search", "Clear"))
        )

        output_html.append(start_html)
        output_html.append(indent('<table "border="1" cellpadding="3">', info_indent - 1))
        # Project name
        output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Project Name"), print_information.jobName), info_indent))
        # Thumbnail
        if encoded_snapshot:
            output_html.append(indent(f'<tr><td colspan="2"><img class="thumbnail" src="data:image/png;base64,{encoded_snapshot}" width="300" height="300", alt="{print_information.jobName}"></td></tr>', info_indent))
        # Date/time
        output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Date/time"), formatted_date_time), info_indent))
        # Cura version
        output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Cura Version"), CuraVersion), info_indent))
        # Preset / Intent (for UM printers)
        preset_name = global_stack.qualityChanges.getMetaData().get("name", "")
        if preset_name == "empty":
            preset_name = machine_manager.activeIntentCategory
            um_intent = True
        else:
            um_intent = False
        output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Intent") if um_intent else catalog.i18nc("@label", "Profile"), preset_name), info_indent))
        # Quality profile
        output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Quality Profile"), global_stack.quality.getMetaData().get("name", "")), info_indent))
        # Extruders enabled/materials (multiple extruders)
        if self._extruder_count > 1:
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

        # Get print quality settings for each extruder
        # Categories appear in the same order they do in Cura's print quality settings panel
        settings_categories = ["resolution", "shell", "top_bottom", "infill", "material",
                               "speed", "travel", "cooling", "dual", "support", "platform_adhesion",
                               "meshfix", "blackmagic", "experimental"]

        # Get settings for each category
        #for i, stack in enumerate(extruder_stack):
        #    for category in settings_categories:
        #        output_html.extend(self._get_category_settings(category, stack, info_indent -1, i if extruder_count > 1 else -1, i18n_printer_catalog))
        for category in settings_categories:
            # Get settings for all extruders in advance
            category_settings, category_label = self._get_category_settings_list(category, extruder_stack, i18n_printer_catalog)

            details_open = True  # Almost always true
            if category == "dual" and self._single_extruder:
                details_open = False
            output_html.append(self._make_category_header(category_label, details_indent, category, details_open))
            for setting in category_settings:
                output_html.append(self._make_category_setting_row(setting, setting_indent))
            output_html.append(self._make_category_footer(details_indent))

        # Get settings for each extruder
        extruder_settings, extruder_label = self._get_category_settings_list("machine_settings", extruder_stack, i18n_extruder_catalog)
        output_html.append(self._make_category_header(extruder_label, details_indent, "machine_settings"))
        for setting in extruder_settings:
            output_html.append(self._make_category_setting_row(setting, setting_indent))
        output_html.append(self._make_category_footer(details_indent))


        scripts_list = global_stack.getMetaDataEntry("post_processing_scripts")
        if scripts_list :
            # Get post-processing scripts
            output_html.append(self._make_category_header(catalog.i18nc("@label", "Post-processing scripts"), details_indent, "post_processing_scripts", two_column=True, two_column_titles=[catalog.i18nc("@settings:post_name", "Post-processor name"), catalog.i18nc("@settings:post_settings", "Post-processor settings")]))
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
                    output_html.append(self._make_tr_2_cells(html.escape(script_name), setting_param.rstrip("<br>"), info_indent + 1, "posts-settings"))

            output_html.append(self._make_category_footer(details_indent))

        end_html_file = os.path.abspath(os.path.join(self._plugin_dir, "html_end.html"))
        end_html: str = ""
        try:
            with open(end_html_file, "r", encoding="utf-8") as end:
                end_html = end.read()
        except Exception:
            Logger.logException("e", "Exception trying to read html_end.html")
            self._export_fail = True
            return ""
        end_html = (end_html.replace(self.HTML_REPLACEMENT_DISABLED_SETTINGS_DISABLED, catalog.i18nc("@button:settings_disabled_disabled", "Hide disabled settings"))
                            .replace(self.HTML_REPLACEMENT_DISABLED_SETTINGS_ENABLED, catalog.i18nc("@button:settings_disabled_enabled", "Show disabled settings"))
                            .replace(self.HTML_REPLACEMENT_VISIBLE_SETTINGS_DISABLED, catalog.i18nc("@button:settings_visible_disabled", "Hide settings not visible in profile"))
                            .replace(self.HTML_REPLACEMENT_VISIBLE_SETTINGS_ENABLED, catalog.i18nc("@button:settings_visible_enabled", "Show settings not visible in profile"))
                            .replace(self.HTML_REPLACEMENT_LOCAL_CHANGES_DISABLED, catalog.i18nc("@button:settings_local_disabled", "Show only user changes"))
                            .replace(self.HTML_REPLACEMENT_LOCAL_CHANGES_ENABLED, catalog.i18nc("@button:settings_local_enabled", "Show all settings")))
        output_html.append(end_html)
        
        return "\n".join(output_html)

    def _single_extruder_skip_setting(self, setting_name: str, setting_value: any) -> bool:
        """
        Determines if a setting should be skipped in the HTML output,
        specifically for single-extruder machines.

        :param setting_name: The unique ID of the setting (e.g., "extruder_prime_x_position").
        :param setting_value: The current value of the setting.
        :return: True if the setting should be skipped, False otherwise.
        """

        if not self._single_extruder:
            return False

        # These keywords are hidden regardless of value
        multi_extruder_blacklist: list[str] = ["prime_tower", "prime_blob", "extruder_switch"]
        for keyword in multi_extruder_blacklist:
            if keyword in setting_name:
                return True
        
        # These keywords have their value checked
        multi_extruder_keywords: list[str] = ["extruder"]
        multi_extruder_invalid_values: list[str] = ["-1", "0"]
        for keyword in multi_extruder_keywords:
            if keyword in setting_name and str(setting_value) in multi_extruder_invalid_values:
                return True

        return False

    def _make_category_header(self, text: str, base_indent: int, category_key: str, details_open: bool = True, two_column: bool = False, two_column_titles: list[str] = None) -> str:
        category_header: list[str] = []
        category_header.append(indent(f'<details class="collapsible-setting setting-{category_key}"{" open" if details_open else ""}>', base_indent))
        category_header.append(indent(f'<summary class="category-header"><h2>{html.escape(text)}</h2></summary>', base_indent + 1))
        category_header.append(indent('<table class="category">', base_indent + 1))
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
        else:
            category_header.append(indent(f'<th>{html.escape(catalog.i18nc("@setting:label", "Setting"))}</th>', base_indent + 4))
            for i in range(self._extruder_count):
                category_header.append(indent(f'<th>{html.escape(catalog.i18nc("@settings:extruder", "Extruder"))} #{i + 1}</th>', base_indent + 4))
        category_header.append(indent('</tr>', base_indent + 3))
        category_header.append(indent('</thead>', base_indent + 2))
        category_header.append(indent('<tbody>', base_indent + 2))
        return "\n".join(category_header)

    def _make_category_setting_row(self, setting: CategorySetting, base_indent: int = 0) -> str:
        if setting.skip:
            return ""
        row_css_class = self._get_css_row_class(setting.css_class)
        category_setting_html_lines: list[str] = []
        category_setting_html_lines.append(indent(f'<tr class="setting-row{(" " + row_css_class) if row_css_class else ""}">', base_indent))
        cell_tooltip = setting.internal_representation()
        child_prefix = self.CHILD_SPACER * setting.child_level
        category_setting_html_lines.append(indent(f'<td title="{html.escape(cell_tooltip)}" class="setting-label">{child_prefix}{html.escape(setting.label)}</td>', base_indent + 1))
        for i, value in enumerate(setting.value):
            if setting.error_class[i]:
                cell_class = setting.error_class[i]
            elif setting.css_class[i]:
                cell_class = setting.css_class[i]
            else:
                cell_class = ""
            class_tooltip = self._css_class_to_human_readable(cell_class if cell_class else row_css_class)
            display_value = html.escape(value.replace("<br>", "\n")).replace("\n", "<br>")
            category_setting_html_lines.append(indent(f'<td class="{cell_class + " setting-value" if cell_class else "setting-value"}" title="{html.escape(class_tooltip)}">{display_value}</td>', base_indent + 1))
        category_setting_html_lines.append(indent('</tr>', base_indent))
        for child in setting.children:
            if child:  # Shouldn't be None, but in case it is
                category_setting_html_lines.append(self._make_category_setting_row(child, base_indent))
        return "\n".join(category_setting_html_lines)

    def _make_category_footer(self, base_indent: int):
        return f'{indent("</tbody>", base_indent + 2)}\n{indent("</table>", base_indent + 1)}\n{indent("</details>", base_indent)}'

    def _get_css_row_class(self, classes: list[str] | str) -> str:
        if isinstance(classes, str):
            return classes

        # local > disabled > hidden > normal
        possible_classes = ("local", "disabled", "hidden", "normal")
        for possible_class in possible_classes:
            if all(css_class == possible_class for css_class in classes):
                return possible_class
        for possible_class in possible_classes[:-1]:
            # We don't want "some-normal"
            if any(css_class == possible_class for css_class in classes):
                return f"some-{possible_class}"
        return "normal"  # Fallback if they're all normal

    def _css_class_to_human_readable(self, css_class: str) -> str:
        match css_class:
            case "local":
                return catalog.i18nc("@setting:class_local", "User set")
            case "normal":
                return catalog.i18nc("@setting:class_normal", "")
            case "hidden":
                return catalog.i18nc("@setting:class_hidden", "Hidden")
            case "disabled":
                return catalog.i18nc("@setting:class_disabled", "Disabled")
            case "warning":
                return catalog.i18nc("@settings:class_warning", "Value warning")
            case "error":
                return catalog.i18nc("@settings:class_error", "Value error")
            case _:
                return catalog.i18nc("@settings:class_fallthrough", "")

    def _get_category_settings_list(self, category_key: str, extruder_stack, local_catalog: i18nCatalog, children_local_stack: bool = False) -> tuple[list[CategorySetting], str]:
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
            category_settings.append(self._get_setting(child_key, category_key, extruder_stack, local_catalog, 0, children_local_stack))

        return (category_settings, category_translated)

    def _get_setting(self, key: str, category_key: str, extruder_stack, local_catalog: i18nCatalog, child_level: int = 0, children_local_stack: bool = False) -> CategorySetting:
        setting = CategorySetting(key = key, child_level = child_level, extruder_count = len(extruder_stack))
        
        for i, extruder in enumerate(extruder_stack):
            # Check to see if the value exists and bail if it doesn't
            css_class: str = ""
            setting_value = extruder.getProperty(key, "value")
            if setting_value is None:
                setting.css_class[i] = "disabled"
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
                css_class = "disabled"
            elif key in self._modified_global_settings or key in self._modified_extruder_settings[i]:
                css_class = "local"
            elif key not in self._visible_settings:
                css_class = "hidden"
            else:
                css_class = "normal"
            setting.css_class[i] = css_class

            setting_string = ""
            setting_error: str = ""
            
            setting_type_str = str(setting_type)
            match setting_type_str:
                case "optional_extruder":
                    # If it's not -1 it seems to be stringly typed
                    if setting_value == -1:
                        setting_string = catalog.i18nc("@setting:unchanged", "Not overridden")
                    else:
                        setting_value = int(setting_value) + 1
                        setting_string = str(setting_value)

                case "extruder":
                    setting_value = int(setting_value) + 1
                    setting_string = str(setting_value)

                case "int" | "float":
                    # Pretty sure all the extruder ones are one of the above types but just in case
                    if not self._single_extruder and "extruder_nr" in key:
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
                                setting_error = "error"
                            elif (minimum_value_warning is not None and setting_value < minimum_value_warning) or \
                                (maximum_value_warning is not None and setting_value > maximum_value_warning):
                                setting_error = "warning"
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

            if self._single_extruder and category_key != "machine_settings":
                if self._single_extruder_skip_setting(key, setting_value):
                    setting.skip = True

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
            setting.children.append(self._get_setting(child_key, category_key, extruder_stack, local_catalog, child_level + 1, children_local_stack))

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
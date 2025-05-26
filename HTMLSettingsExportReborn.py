# HTML Settings Export Reborn
# Copyright Slashee the Cow 2025-
#
# Based on CuraHtmlDoc by 5@xes
# https://github.com/5axes/CuraHtmlDoc/
#--------------------------------------------------------------------------------------------------
# Version history (Reborn edition)
# v1.0.0:
#   - Made it an Extension instead of a Tool. Menu option seems much more logical than tool button.
#   - ^^^ meant I could ditch **a bunch** of Tool related stuff which I don't even know why some of it was apparently necessary.
#   - **Extensive** refactoring. Like a "knock all the walls down and start over" kind of renovation.
#   - This remodelling includes removing oodles of duplicate code. While it's fine if your house has two bathrooms and you renovate it to have two bathrooms, that doesn't apply to code.
#   - What little Qt is in here, dropped Qt 5 support because I have enough on my hands as it is. This makes Cura 5.0 a minimum.
#   - Removed autosave setting. Generating this is a somewhat fragile process and I really don't want to get in the way of gcode saving.
#   - Cleaned up CSS, removing unused classes. Fixed a group that was numbered "l, 2, 3, 4, 5" (look carefully at the first one).
#   - HTML output is now generated in advance and written all at once instead of literally thousands of individual writes over time locking up file I/O and the GIL.
#   - Large chunks of HTML now loaded from individual files instead of ungainly string literals.
#   - Added symbols (in addition to the padding) to more clearly indicate parent/child relationships.
#   - Output HTML markup now much more clean with things like indents and new lines. And being valid.
#   - Generated HTML now consistently follows HTML5 standards instead of using deprecated elements and having traces of XHTML.
#   - Removed unnecessary tags and elements from HTML output that only work because of how forgiving browsers are.
#   - Date/time practically guaranteed to be in system locale's format instead of a hard coded format.

import os
import datetime
import locale
import platform
import tempfile
import html
import webbrowser
import configparser  # The script lists are stored in metadata as serialised config files.

from datetime import datetime
from typing import cast, Dict, List, Optional, Tuple, Any, Set

from PyQt6.QtCore import Qt, QObject, QBuffer, QUrl
from PyQt6.QtGui import QDesktopServices
from numpy import maximum


from cura.CuraApplication import CuraApplication
from cura.CuraVersion import CuraVersion  # type: ignore
from cura.Utils.Threading import call_on_qt_thread
from cura.Snapshot import Snapshot

from UM.Extension import Extension
from UM.Settings.Models.SettingPreferenceVisibilityHandler import SettingPreferenceVisibilityHandler
from UM.Logger import Logger
from UM.Message import Message
from UM.Preferences import Preferences
from UM.Qt.Duration import DurationFormat
from UM.Scene.Selection import Selection
from UM.Settings.InstanceContainer import InstanceContainer
from UM.Settings.ContainerStack import ContainerStack

from UM.Resources import Resources
from UM.i18n import i18nCatalog

i18n_cura_catalog = i18nCatalog("cura")
i18n_printer_catalog = i18nCatalog("fdmprinter.def.json")
i18n_extruder_catalog = i18nCatalog("fdmextruder.def.json")

Resources.addSearchPath(
    os.path.join(os.path.abspath(os.path.dirname(__file__)),'resources')
)  # Plugin translation file import

catalog = i18nCatalog("htmlsettingsexport")

if catalog.hasTranslationLoaded():
    Logger.log("i", "HTML Settings Export translation loaded")

def indent(string: str, level: int = 0) -> str:
    return f'{"    " * level}{string}'
    
class HTMLSettingsExportReborn(Extension):

    HTML_REPLACEMENT_TITLE: str = "$$$TITLE$$$"
    HTML_REPLACEMENT_LANG: str = "$$$LANG$$$"
    HTML_REPLACEMENT_UNUSED_SETTINGS: str = "$$$UNUSED_SETTINGS$$$"
    HTML_REPLACEMENT_VISIBLE_SETTINGS: str = "$$$VISIBLE_SETTINGS$$$"
    HTML_REPLACEMENT_LOCAL_CHANGE_SETTINGS: str = "$$$LOCAL_CHANGE_SETTINGS$$$"
    CHILD_SPACER = '<div class="child_spacer">►</div>'
    
    def __init__(self):
        super().__init__()

        self._application = CuraApplication.getInstance()

        self._preferences = self._application.getPreferences()

        self._modified_global_settings: list = []
        self._visible_settings: list = []

        # Set up menu item
        self.setMenuName("HTML Settings Export")
        self.addMenuItem("Export settings", self._save_settings_html)

    def _save_settings_html(self):
        try:
            with open("cura_settings.html", "w", encoding="utf-8") as page:
                page.write(self._assemble_html())
        except Exception as e:
            Logger.logException("e", f"Exception while trying to save HTML settings: {e}")
 
    def _has_browser(self):
        try:
            webbrowser.get()
            return True
        except webbrowser.Error:
            return False
        
    def _openHtmlPage(self,page_name):
        # target = os.path.join(tempfile.gettempdir(), page_name)
        with open(page_name, 'w', encoding='utf-8') as fhandle:
            self._write(fhandle)
            
        if not self._has_browser() :
            Logger.log("d", "openHtmlPage default browser not defined") 
            Message(text = catalog.i18nc("@message","Default browser not defined open \n %s") % (page_name), title = catalog.i18nc("@info:title", "Warning ! Doc Html Cura")).show()
            
        QDesktopServices.openUrl(QUrl.fromLocalFile(page_name))
        
    def _onWriteStarted(self, output_device):
        '''Save HTML page when gcode is saved.'''
        try:
            if self._auto_save :                   
                print_information = CuraApplication.getInstance().getPrintInformation() 
                file_html = print_information.jobName + ".html"
                # Folder Doesn't Exist Anymore
                if not os.path.isdir(self._filefolder) : 
                    self._filefolder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "HtmlDoc")
                    Message(text = catalog.i18nc("@message","Save path set to : \n %s") % self._filefolder, title = catalog.i18nc("@title", "Cura Html Doc")).show()               
                
                self._doc_file = os.path.join(self._filefolder, file_html)
                # self._openHtmlPage(self._doc_file)
                # Just Save the file
                with open(self._doc_file, 'w', encoding='utf-8') as fhandle:
                    self._write(fhandle)

        except Exception:
            # We really can't afford to have a mistake here, as this would break the sending of g-code to a device
            # (Either saving or directly to a printer). The functionality of the slice data is not *that* important.
            # But we should be notified about these problems of course.
            Logger.logException("e", "Exception raised in _onWriteStarted")

    def _make_tr_2_cells(self, key: str, value: Any, row_class: str = None) -> str:
        """Generates an HTML table row string."""
        # chr(34) is " which I can't escape in an f-string expression in Python 3.10
        return f'<tr{("class " + (chr(34)) + row_class + chr(34)) if row_class else ""}><td class="w-50">{key}</td><td colspan="2">{value}</td></tr>'

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
        global_stack = CuraApplication.getInstance().getGlobalContainerStack()
        machine_manager = CuraApplication.getInstance().getMachineManager()
        print_information = CuraApplication.getInstance().getPrintInformation()
        extruder_stack = CuraApplication.getInstance().getExtruderManager().getActiveExtruderStacks()
        extruder_count = global_stack.getProperty("machine_extruder_count", "value")

        self._modified_global_settings = global_stack.getTop().getAllKeys()
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

        
        # How indented this section should be at the "root" level of the page output
        # Which in this case is inside <html><body><table>
        info_indent: int = 3

        # Add header with CSS and start of page
        start_html: str = ""
        try:
            with open("html_start.html", "r", encoding="utf-8") as start:
                start_html = start.read()
        except Exception:
            Logger.logException("e", "Exception trying to read html_start.html")
            return ""
        start_html = (start_html.replace(self.HTML_REPLACEMENT_TITLE, catalog.i18nc("@page:title", "Cura Print Settings"))
                                .replace(self.HTML_REPLACEMENT_LANG, catalog.i18nc("@page:language", "en"))
                                .replace(self.HTML_REPLACEMENT_LOCAL_CHANGE_SETTINGS, catalog.i18nc("@button:local_changes", "Show/hide user changed settings"))
                                .replace(self.HTML_REPLACEMENT_VISIBLE_SETTINGS, catalog.i18nc("@button:visible_settings", "Show/hide visible settings"))
                                .replace(self.HTML_REPLACEMENT_UNUSED_SETTINGS, catalog.i18nc("@button:unused_settings", "Show/hide unused settings")))

        output_html.append(start_html)
        output_html.append(indent('<table width="100%" "border="1" cellpadding="3">', info_indent - 1))
        # Project name
        output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Project Name"), print_information.jobName)), info_indent)
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
        if extruder_count > 1:
            extruders_enabled: list = []
            extruder_materials: list = []
            for extruder in extruder_stack:
                extruders_enabled.append(extruder.getMetaDataEntry("enabled"))
                extruder_materials.append(extruder.material.getMetaData().get("material", ""))
            # Enabled extruders
            extruders_enabled_html = self._make_ol_from_list(extruders_enabled, info_indent)
            output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Extruders enabled"), extruders_enabled_html), info_indent))
            # Materials
            extruder_materials_html = self._make_ol_from_list(extruder_materials, info_indent)
            output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Extruder materials"), extruder_materials_html), info_indent))
        # Material (single extruder)
        else:
            output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Material"), extruder_stack[0].material.getMetaData().get("material", "")), info_indent))
        # Material weight
        output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Material weight used"), self._make_ol_from_list((round(x, 1) for x in print_information.materialWeights), info_indent, suffix = "g"), info_indent)))
        # Material length
        output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Material length used"), self._make_ol_from_list((round(x, 2) for x in print_information.materialLengths), info_indent, suffix = "m"), info_indent)))
        # Material cost
        cura_currency = str(self._preferences.getValue("cura/currency"))
        output_html.append(indent(self._make_tr_2_cells(catalog.i18nc("@label", "Material cost"), self._make_ol_from_list((round(x, 2) for x in print_information.materialCosts), info_indent, prefix = cura_currency), info_indent)))
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
        for i, stack in enumerate(extruder_stack):
            for category in settings_categories:
                output_html.extend(self._get_category_settings(category, stack, info_indent -1, i if extruder_count > 1 else -1, i18n_printer_catalog))

        # Get settings for each extruder
        for i, extruder in enumerate(extruder_stack):
            output_html.extend(self._get_category_settings("machine_settings", extruder, info_indent -1, i, i18n_extruder_catalog, True))

        # Get post-processing scripts
        output_html.append(self._make_category_header(catalog.i18nc("@label", "Post-processing scripts"), info_indent - 1))

        scripts_list = global_stack.getMetaDataEntry("post_processing_scripts")
        if scripts_list :
            for script_str in scripts_list.split("\n"):
                if not script_str:
                    continue
                script_str = script_str.replace(r"\\\n", "\n").replace(r"\\\\", "\\\\")  # Unescape escape sequences.
                script_parser = configparser.ConfigParser(interpolation=None)
                script_parser.optionxform = str  # type: ignore  # Don't transform the setting keys as they are case-sensitive.
                try:
                    script_parser.read_string(script_str)
                except configparser.Error as e:
                    Logger.error(f"Stored post-processing scripts have syntax errors: {e}")
                    continue
                for script_name, settings in script_parser.items():  # There should only be one, really! Otherwise we can't guarantee the order or allow multiple uses of the same script.
                    if script_name == "DEFAULT":  # ConfigParser always has a DEFAULT section, but we don't fill it. Ignore this one.
                        continue
                    setting_param = ""
                    for setting_key, setting_value in settings.items():
                        setting_param += f'{setting_key}: {setting_value}<br>'
                    output_html.append(self._make_category_setting_row(script_name, setting_param.rstrip("<br>"), info_indent + 1))

        output_html.append(self._make_category_footer(info_indent - 1))

        end_html: str = ""
        try:
            with open("html_end.html", "r", encoding="utf-8") as end:
                end_html = end.read()
        except Exception:
            Logger.logException("e", "Exception trying to read html_start.html")
            return ""
        output_html.append(end_html)
        
        return "\n".join(output_html)

    def _make_category_header(self, text: str, base_indent: int):
        header_string = f'<details open><summary><h2>{text}</h2></summary>'
        return f'{indent(header_string, base_indent)}\n{indent('<table class="category">', base_indent + 1)}'

    def _make_category_setting_row(self, setting: str, value: str, indent_level: str, row_class: str = "", value_class: str = "", child_depth: int = 0) -> str:
        # Gotta use chr(34) " there or else it'd be a triple double quote
        row_string = f'<tr class="{row_class}"><td>{self.CHILD_SPACER * child_depth}{setting}</td><td{(" class = " + value_class + chr(34)) if value_class else ""}>{value}</td></tr>'
        return f'{indent(row_string, indent_level)}'

    def _make_category_footer(self, base_indent: int):
        return f'{indent('</table>', base_indent + 1)}\n{indent('</details>', base_indent)}'

    def _get_category_settings(self, category_name: str, stack: ContainerStack, base_indent_level: int, extruder_index: int, local_catalog: i18nCatalog, children_local_stack: bool = False) -> list[str]:
        category_output: list[str] = []

        # Apparently necessary to get translated 
        translation_key = category_name + " label"
        # Set extruder prefix (or lack thereof for single extruder machines)
        extruder_prefix: str = f'{catalog.i18nc("@label", "Extruder")} {(extruder_index + 1)}: ' if extruder_index >= 0 else ""

        # Get translated category name... just make sure we're in a category
        if stack.getProperty(category_name, "type") == "category":
            category_label = stack.getProperty(category_name, "label")
            category_translated = local_catalog.i18nc(translation_key, category_label)
            category_output.append(self._make_category_header(extruder_prefix + category_translated, base_indent_level))
        else:
            # This should only be run on the top level of categories
            return []

        setting_indent_level = base_indent_level + 2

        if children_local_stack:
            children_list = stack.getSettingDefinition(category_name).children
        else:
            children_list = self._application.getGlobalContainerStack().getSettingDefinition(category_name).children
        
        for child in children_list:
            category_output.extend(self._list_category_setting(stack, child.key, setting_indent_level, local_catalog, 0, children_local_stack))

        category_output.append(self._make_category_footer(base_indent_level))

        return category_output

    def _list_category_setting(self, stack, key: str, indent_level: int, local_catalog: i18nCatalog, depth: int = 0, children_local_stack: bool = False) -> list[str]:
        setting_output = []
        translation_key = key + " label"
        
        row_class: str = ""
        if not stack.getProperty(key, "enabled"):
            row_class = "disabled"
        elif key in self._modified_global_settings:
            row_class = "local"
        elif key not in self._visible_settings:
            row_class = "hidden"
        else:
            row_class = "normal"

        untranslated_label = stack.getProperty(key, "label")
        translated_label = local_catalog.i18nc(translation_key, untranslated_label)

        setting_type = stack.getProperty(key, "type")
        setting_value = stack.getProperty(key, "value")
        setting_string: str = ""
        setting_class: str = ""

        match str(setting_type):
            case "float":
                setting_string = str(float(round(setting_value, 4))).rstrip("0").rstrip(".")  # Drop trailing zeroes and decimal point if it's a whole number

                minimum_value = stack.getProperty(key, "minimum_value")
                maximum_value = stack.getProperty(key, "maximum_value")
                minimum_value_warning = stack.getProperty(key, "minimum_value_warning")
                maximum_value_warning = stack.getProperty(key, "maximum_value_warning")

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
                        setting_class = "error"
                    elif (minimum_value_warning is not None and setting_value < minimum_value_warning) or \
                         (maximum_value_warning is not None and setting_value > maximum_value_warning):
                        setting_class = "warning"
                except (ValueError, TypeError) as e:
                    Logger.log("e", f"Error trying to convert minimum/maximum value for {key}: {e}")

            case "enum":
                option_translation_key = key + "option" + str(setting_value)
                options = stack.getProperty(key, "options")
                untranslated_option = options[str(setting_value)]
                setting_string = local_catalog.i18nc(option_translation_key, untranslated_option)

            case _:
                setting_string = str(setting_value).replace("\n", "<br>")

        setting_string += str(stack.getProperty(key, "unit")) if stack.getProperty(key, "unit") else ""

        setting_output.append(self._make_category_setting_row(translated_label, setting_string, indent_level + depth, row_class, setting_class, depth))

        if children_local_stack:
            children_list = stack.getSettingDefinition(key).children
        else:
            children_list = self._application.getGlobalContainerStack().getSettingDefinition(key).children

        for child in children_list:
            setting_output.extend(self._list_category_setting(stack, child.key, indent_level, local_catalog, depth + 1, children_local_stack))

        return setting_output
            
    def _write(self, stream):
        # Current File path
        # Logger.log("d", "stream = %s", os.path.abspath(stream.name))   
        stream.write("""<!DOCTYPE html>
            <meta charset='UTF-8'>
            <head>
                <title>Cura Settings Export</title>
                <style>
                    div.error { background-color: red; }
                    tr.category td { font-size: 1.1em; background-color: rgb(142,170,219); }
                    tr.disabled td { background-color: #eaeaea; color: #717171; }
                    tr.local td { background-color: #77DD77; }
                    tr.visible td { background-color: #FFEE92; }
                    body.hide-disabled tr.disabled { display: none; }
                    body.hide-local tr.visible { display: none; }
                    body.hide-visible tr.normal { display: none; }
                    .val { width: 200px; text-align: right; }
                    .w-10 { width: 10%; }
                    .w-50 { width: 50%; }
                    .w-70 { width: 70%; }
                </style>
            </head>
            <body lang=EN>
        \n""")
        
        machine_manager = CuraApplication.getInstance().getMachineManager()        
        stack = CuraApplication.getInstance().getGlobalContainerStack()

        #global_stack = machine_manager.activeMachine
        global_stack = CuraApplication.getInstance().getGlobalContainerStack()
    
        # modified paramater
        self._modified_global_parameters = global_stack.getTop().getAllKeys()
        # Logger.logException("d", "Modified {}".format(self._modified_global_param))
                
        TitleTxt = catalog.i18nc("@label","Print settings")
        ButtonTxt_Enable = catalog.i18nc("@action:label","Show/Hide Parameter Enable")
        ButtonTxt_Visible = catalog.i18nc("@action:label","Show/Hide Parameter Standard")
        ButtonTxt_Modi = catalog.i18nc("@action:label","Show/Hide Parameter Visible")
        
        stream.write("<h1>" + TitleTxt + "</h1>\n")
        stream.write("<button id='enabled'>" + ButtonTxt_Enable + "</button><P>\n")
        stream.write("<button id='visible'>" + ButtonTxt_Visible + "</button><P>\n")
        stream.write("<button id='local'>" + ButtonTxt_Modi + "</button><P>\n")

        # Script       
        stream.write("""<script>
                            var enabled = document.getElementById('enabled');
                            enabled.addEventListener('click', function() {
                                document.body.classList.toggle('hide-disabled');
                            });
                        </script>\n""")
        stream.write("""<script>
                            var local = document.getElementById('local');
                            local.addEventListener('click', function() {
                                document.body.classList.toggle('hide-local');
                            });
                        </script>\n""")
        stream.write("""<script>
                            var visible = document.getElementById('visible');
                            visible.addEventListener('click', function() {
                                document.body.classList.toggle('hide-visible');
                            });
                        </script>\n""")                        
        #Get extruder count
        extruder_count=stack.getProperty("machine_extruder_count", "value")
        print_information = CuraApplication.getInstance().getPrintInformation()
        
        stream.write("<table width='100%' border='1' cellpadding='3'>")
        # Job
        self._WriteTd(stream,catalog.i18nc("@label","Job Name"),print_information.jobName)

        # Attempt to add a thumbnail
        snapshot = self._createSnapshot()
        if snapshot:
            thumbnail_buffer = QBuffer()
            

            thumbnail_buffer.open(QBuffer.OpenModeFlag.ReadWrite)
                    
            snapshot.save(thumbnail_buffer, "PNG")
            encodedSnapshot = thumbnail_buffer.data().toBase64().data().decode("utf-8")

            # thumbnail_file = zipfile.ZipInfo(THUMBNAIL_PATH)
            # Don't try to compress snapshot file, because the PNG is pretty much as compact as it will get
            # archive.writestr(thumbnail_file, thumbnail_buffer.data()) 
            # Logger.log("d", "stream = {}".format(encodedSnapshot))
            stream.write("<tr><td colspan='3'><center><img src='data:image/png;base64," + str(encodedSnapshot)+ "' width='300' height='300' alt='" + print_information.jobName + "' title='" + print_information.jobName + "' /></cente></td></tr>" )            
              
        # File
        # self._WriteTd(stream,"File",os.path.abspath(stream.name))
        # Date
        self._WriteTd(stream,"Date",datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
       
        # Version  
        self._WriteTd(stream,"Cura Version",CuraVersion)
            
        # Profile || Intent for Ultimaker Machine
        P_Name = global_stack.qualityChanges.getMetaData().get("name", "")
        if P_Name=="empty":
            P_Name = machine_manager.activeIntentCategory
            self._WriteTd(stream,catalog.i18nc("@label","Intent"),P_Name)
        else:
            self._WriteTd(stream,catalog.i18nc("@label","Profile"),P_Name)
        
        # Quality
        Q_Name = global_stack.quality.getMetaData().get("name", "")
        self._WriteTd(stream,catalog.i18nc("@label:table_header","Quality"),Q_Name)
                
        # Material
        # extruders = list(global_stack.extruders.values())  
        extruder_stack = CuraApplication.getInstance().getExtruderManager().getActiveExtruderStacks()       

        for Extrud in extruder_stack:
            PosE = int(Extrud.getMetaDataEntry("position"))
            PosE += 1
            
            M_Name = Extrud.material.getMetaData().get("material", "")
            
            MaterialStr="%s %s : %d"%(catalog.i18nc("@label", "Material"),catalog.i18nc("@label", "Extruder"),PosE)
            self._WriteTd(stream,MaterialStr,M_Name)
            
            if extruder_count>1:
                M_Enabled = Extrud.getMetaDataEntry("enabled")
                EnabledStr="%s %s : %d"%(catalog.i18nc("@label", "Extruder"),catalog.i18nc("@label", "Enabled"),PosE)
                self._WriteTd(stream,EnabledStr,M_Enabled)
            
        total_material_weight: float = 0
        #   materialWeights
        total_material_weight: float = sum(print_information.materialWeights)
        if total_material_weight > 0:
            material_weight_output= f"{round(total_material_weight,1)}g"
            self._WriteTd(stream,catalog.i18nc("@label","Material estimation"),material_weight_output)
            # self._WriteTd(stream,catalog.i18nc("@label","Filament weight"),str(print_information.materialWeights)) 
            M_Length= str(print_information.materialLengths).rstrip("]").lstrip("[")
            
            M_Length="{0:s} m".format(M_Length)
            self._WriteTd(stream,catalog.i18nc("@text","Material usage"),M_Length)
            
            original_preferences = CuraApplication.getInstance().getPreferences() #Copy only the preferences that we use to the workspace.
            Currency = original_preferences.getValue("cura/currency")
            price=str(print_information.materialCosts).rstrip("]").lstrip("[")
            # Logger.log("d", "Currency = %s",Currency)
            # Logger.log("d", "price = %s",Currency)
            # Logger.log("d", "materialCosts = %s",print_information.materialCosts)
            
            if "," in price :
                M_Price= price.replace(',',Currency) + Currency
                self._WriteTd(stream,catalog.i18nc("@label","Filament Cost"),M_Price)            
            else :
                M_Price= str(round(float(price),2)) + " " + Currency
                self._WriteTd(stream,catalog.i18nc("@label","Filament Cost"),M_Price)
            
            #   Print time
            P_Time = catalog.i18nc("@text","%d D %d H %d Mn")%(print_information.currentPrintTime.days,print_information.currentPrintTime.hours,print_information.currentPrintTime.minutes)
            self._WriteTd(stream,catalog.i18nc("@label","Printing Time"),P_Time)   
            # self._WriteTd(stream,catalog.i18nc("@label","Print time"),str(print_information.currentPrintTime.getDisplayString(DurationFormat.Format.ISO8601)))
        
        
        # Define every section to get the same order as in the Cura Interface
        # Modification from global_stack to extruders[0]
        if extruder_count>1 :
            i=0
            # for Extrud in list(global_stack.extruders.values()):
            for Extrud in extruder_stack :       
                i += 1                        
                self._doTree(Extrud,"resolution",stream,0,i)
                self._doTree(Extrud,"shell",stream,0,i)

                self._doTree(Extrud,"top_bottom",stream,0,i)

                self._doTree(Extrud,"infill",stream,0,i)
                self._doTree(Extrud,"material",stream,0,i)
                self._doTree(Extrud,"speed",stream,0,i)
                self._doTree(Extrud,"travel",stream,0,i)
                self._doTree(Extrud,"cooling",stream,0,i)

                self._doTree(Extrud,"dual",stream,0,i)
        else:
            self._doTree(extruder_stack[0],"resolution",stream,0,0)
            self._doTree(extruder_stack[0],"shell",stream,0,0)
            self._doTree(extruder_stack[0],"top_bottom",stream,0,0)

            self._doTree(extruder_stack[0],"infill",stream,0,0)
            self._doTree(extruder_stack[0],"material",stream,0,0)
            self._doTree(extruder_stack[0],"speed",stream,0,0)
            self._doTree(extruder_stack[0],"travel",stream,0,0)
            self._doTree(extruder_stack[0],"cooling",stream,0,0)

        self._doTree(extruder_stack[0],"support",stream,0,0)
        self._doTree(extruder_stack[0],"platform_adhesion",stream,0,0)
        
        if extruder_count>1 :
            i=0
            for Extrud in extruder_stack:
                i += 1
                self._doTree(Extrud,"meshfix",stream,0,i)    
                self._doTree(Extrud,"blackmagic",stream,0,i)  
                self._doTree(Extrud,"experimental",stream,0,i)
        else:
            self._doTree(extruder_stack[0],"meshfix",stream,0,0)    
            self._doTree(extruder_stack[0],"blackmagic",stream,0,0)  
            self._doTree(extruder_stack[0],"experimental",stream,0,0)       
        
        self._doTree(extruder_stack[0],"machine_settings",stream,0,0)

        i=0
        for Extrud in extruder_stack:
            i += 1
            self._doTreeExtrud(Extrud,"machine_settings",stream,0,i)

        # This Method is smarter but unfortunatly settings are not in the same ordrer as the Cura interface
        # for key in global_stack.getAllKeys():
        #     if global_stack.getProperty(key,"enabled") == True:
        #         if global_stack.getProperty(key,"type") == "category":
        #             self._doTree(global_stack,key,stream,0)
   
        #----------------------------------------
        #  Add Script List in the HTML Log File
        #----------------------------------------
        script_list = []
        scripts_list = global_stack.getMetaDataEntry("post_processing_scripts")
        if scripts_list :
            stream.write("<tr class='category'>")
            stream.write("<td colspan='3'>" + catalog.i18nc("@label","Postprocessing Scripts") + "</td>")
            stream.write("</tr>\n")        
            for script_str in scripts_list.split("\n"):  # Encoded config files should never contain three newlines in a row. At most 2, just before section headers.
                        if not script_str:  # There were no scripts in this one (or a corrupt file caused more than 3 consecutive newlines here).
                            continue
                        script_str = script_str.replace(r"\\\n", "\n").replace(r"\\\\", "\\\\")  # Unescape escape sequences.
                        script_parser = configparser.ConfigParser(interpolation=None)
                        script_parser.optionxform = str  # type: ignore  # Don't transform the setting keys as they are case-sensitive.
                        try:
                            script_parser.read_string(script_str)
                        except configparser.Error as e:
                            Logger.error("Stored post-processing scripts have syntax errors: {err}".format(err = str(e)))
                            continue
                        for script_name, settings in script_parser.items():  # There should only be one, really! Otherwise we can't guarantee the order or allow multiple uses of the same script.
                            if script_name == "DEFAULT":  # ConfigParser always has a DEFAULT section, but we don't fill it. Ignore this one.
                                continue
                            setting_param = ""
                            for setting_key, setting_value in settings.items():
                                setting_param += setting_key + " : " + setting_value + "<br>"
                            self._WriteTdNormal(stream,script_name,setting_param)
                        
        stream.write("</table>")
        stream.write("</body>")
        stream.write("</html>")
        return True

    def _WriteTdNormal(self,stream,Key,ValStr):

        stream.write("<tr class='normal'>")
        stream.write("<td class='w-50'>" + Key + "</td>")
        stream.write("<td colspan='2'>" + str(ValStr) + "</td>")
        stream.write("</tr>\n")
        
    def _WriteTd(self,stream,Key,ValStr):

        stream.write("<tr>")
        stream.write("<td class='w-50'>" + Key + "</td>")
        stream.write("<td colspan='2'>" + str(ValStr) + "</td>")
        stream.write("</tr>\n")
            
               
    def _doTree(self,stack,key,stream,depth,extrud):   
        #output node
        Info_Extrud=""
        definition_key=key + " label"
        ExtruderStrg = catalog.i18nc("@label", "Extruder")
        top_of_stack = cast(InstanceContainer, stack.getTop())  # Cache for efficiency.
        top_container = CuraApplication.getInstance().getGlobalContainerStack().getTop()
        changed_setting_keys = top_of_stack.getAllKeys() 
        self._visible_settings = SettingPreferenceVisibilityHandler().getVisible()      
        
        if stack.getProperty(key,"type") == "category":
            stream.write("<tr class='category'>")
            if extrud>0:
                untranslated_label=stack.getProperty(key,"label")
                translated_label=i18n_printer_catalog.i18nc(definition_key, untranslated_label) 
                Pos = int(stack.getMetaDataEntry("position"))   
                Pos += 1
                Info_Extrud="%s : %d %s"%(ExtruderStrg,Pos,translated_label)
            else:
                untranslated_label=stack.getProperty(key,"label")
                translated_label=i18n_printer_catalog.i18nc(definition_key, untranslated_label)
                Info_Extrud=str(translated_label)
            stream.write("<td colspan='3'>" + str(Info_Extrud) + "</td>")
            #stream.write("<td class=category>" + str(key) + "</td>")
            stream.write("</tr>\n")
        else:
            if stack.getProperty(key,"enabled") == False:
                stream.write("<tr class='disabled'>")
            else:
                if key in self._modified_global_param or key in changed_setting_keys : # changed_setting_keys:
                    stream.write("<tr class='local'>")
                else:
                    if key in self._visible_settings :
                        stream.write("<tr class='visible'>")
                    else :
                        stream.write("<tr class='normal'>")
            
            # untranslated_label=stack.getProperty(key,"label").capitalize()
            untranslated_label=stack.getProperty(key,"label")           
            translated_label=i18n_printer_catalog.i18nc(definition_key, untranslated_label)
            
            stream.write("<td class='w-70 pl-"+str(depth)+"'>" + ("►&nbsp;&nbsp;" * depth) + str(translated_label) + "</td>")
            
            GetType=stack.getProperty(key,"type")
            GetVal=stack.getProperty(key,"value")
            
            if str(GetType)=='float':
                # GelValStr="{:.2f}".format(GetVal).replace(".00", "")  # Formatage
                GelValStr="{:.4f}".format(GetVal).rstrip("0").rstrip(".") # Formatage thanks to r_moeller
                try:
                    minimum_value=float(stack.getProperty(key,"minimum_value"))
                    maximum_value=float(stack.getProperty(key,"maximum_value"))
                    
                    if GetVal > maximum_value or GetVal < minimum_value :
                        Logger.log("d", "Error = {} ; {} ; {}".format(GetVal,minimum_value,maximum_value))
                        GelValStr="<div class='error'>{:.4f}".format(GetVal).rstrip("0").rstrip(".")+"</div>" # Formatage thanks to r_moeller
                except:
                    pass 
            else:
                # enum = Option list
                if str(GetType)=='enum':
                    definition_option=key + " option " + str(GetVal)
                    get_option=str(GetVal)
                    GetOption=stack.getProperty(key,"options")
                    GetOptionDetail=GetOption[get_option]
                    GelValStr=i18n_printer_catalog.i18nc(definition_option, GetOptionDetail)
                    # Logger.log("d", "GetType_doTree = %s ; %s ; %s ; %s",definition_option, GelValStr, GetOption, GetOptionDetail)
                else:
                    GelValStr=str(GetVal).replace(r"\n", "<br>")
            
            stream.write("<td class='val'>" + GelValStr + "</td>")
            
            stream.write("<td class='w-10'>" + str(stack.getProperty(key,"unit")) + "</td>")
            stream.write("</tr>\n")

            depth += 1

        #look for children
        if len(CuraApplication.getInstance().getGlobalContainerStack().getSettingDefinition(key).children) > 0:
            for i in CuraApplication.getInstance().getGlobalContainerStack().getSettingDefinition(key).children:       
                self._doTree(stack,i.key,stream,depth,extrud)                
    
    def _doTreeExtrud(self,stack,key,stream,depth,extrud):   
        #output node
        Info_Extrud=""
        definition_key=key + " label"
        ExtruderStrg = catalog.i18nc("@label", "Extruder")
        top_of_stack = cast(InstanceContainer, stack.getTop())  # Cache for efficiency.
        changed_setting_keys = top_of_stack.getAllKeys()
        
        if stack.getProperty(key,"type") == "category":
            if extrud>0:
                untranslated_label=stack.getProperty(key,"label")
                translated_label=i18n_extruder_catalog.i18nc(definition_key, untranslated_label)
                Pos = int(stack.getMetaDataEntry("position"))   
                Pos += 1                
                Info_Extrud="%s : %d %s"%(ExtruderStrg,Pos,translated_label)
            else:
                untranslated_label=stack.getProperty(key,"label")
                translated_label=i18n_extruder_catalog.i18nc(definition_key, untranslated_label)
                Info_Extrud=str(translated_label)
            stream.write("<tr class='category'><td colspan='3'>" + str(Info_Extrud) + "</td>")
            stream.write("</tr>\n")
        else:
            if stack.getProperty(key,"enabled") == False:
                stream.write("<tr class='disabled'>")
            else:
                if key in self._modified_global_param or key in changed_setting_keys : #changed_setting_keys:
                    stream.write("<tr class='local'>")
                else:
                    if key in self._visible_settings :
                        stream.write("<tr class='visible'>")
                    else :
                        stream.write("<tr class='normal'>")
            
            # untranslated_label=stack.getProperty(key,"label").capitalize()
            untranslated_label=stack.getProperty(key,"label")           
            translated_label=i18n_extruder_catalog.i18nc(definition_key, untranslated_label)
            
            stream.write("<td class='w-70 pl-"+str(depth)+"'>" + str(translated_label) + "</td>")
            
            GetType=stack.getProperty(key,"type")
            GetVal=stack.getProperty(key,"value")
            if str(GetType)=='float':
                # GelValStr="{:.2f}".format(GetVal).replace(".00", "")  # Formatage
                    
                GelValStr="{:.4f}".format(GetVal).rstrip("0").rstrip(".") # Formatage thanks to r_moeller
                try:
                    minimum_value=float(stack.getProperty(key,"minimum_value"))
                    maximum_value=float(stack.getProperty(key,"maximum_value"))
                    
                    if GetVal > maximum_value or GetVal < minimum_value :
                        Logger.log("d", "Error = {} ; {} ; {}".format(GetVal,minimum_value,maximum_value))
                        GelValStr="<div class='error'>{:.4f}".format(GetVal).rstrip("0").rstrip(".")+"</div>" # Formatage thanks to r_moeller
                except:
                    pass               

            else:
                # enum = Option list
                if str(GetType)=='enum':
                    definition_option=key + " option " + str(GetVal)
                    get_option=str(GetVal)
                    GetOption=stack.getProperty(key,"options")
                    GetOptionDetail=GetOption[get_option]
                    GelValStr=i18n_printer_catalog.i18nc(definition_option, GetOptionDetail)
                    # Logger.log("d", "GetType_doTree = %s ; %s ; %s ; %s",definition_option, GelValStr, GetOption, GetOptionDetail)
                else:
                    GelValStr=str(GetVal).replace(r"\n", "<br>")
                
            stream.write("<td class='val'>" + GelValStr + "</td>")
            
            stream.write("<td class='w-10'>" + str(stack.getProperty(key,"unit")) + "</td>")
            stream.write("</tr>\n")

            depth += 1

        #look for children
        if len(stack.getSettingDefinition(key).children) > 0:
            for i in stack.getSettingDefinition(key).children:       
                self._doTreeExtrud(stack,i.key,stream,depth,extrud)
    # Compatibility Cura 4.10 and upper
    @call_on_qt_thread  # must be called from the main thread because of OpenGL
    def _createSnapshot(self):
        Logger.log("d", "Creating thumbnail image...")
        if not CuraApplication.getInstance().isVisible:
            Logger.log("w", "Can't create snapshot when renderer not initialized.")
            return None
        try:
            snapshot = Snapshot.snapshot(width = 300, height = 300)
        except:
            Logger.logException("w", "Failed to create snapshot image")
            return None

        return snapshot
           
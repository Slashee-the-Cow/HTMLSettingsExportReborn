#-----------------------------------------------------------------------------------------------------------
# Copyright (c) 2023 5@xes
# CuraHtmlDoc is released under the terms of the AGPLv3 or higher.
#-----------------------------------------------------------------------------------------------------------
#
# Version 0.0.2 : simplify the source code
#-----------------------------------------------------------------------------------------------------------

import os
import time
import platform
import tempfile
import html
import webbrowser

from datetime import datetime
from typing import cast, Dict, List, Optional, Tuple, Any, Set

VERSION_QT5 = False
try:
    from PyQt6.QtCore import Qt, QObject, QBuffer, QUrl
    from PyQt6.QtGui import QDesktopServices
except ImportError:
    from PyQt5.QtCore import Qt, QObject, QBuffer, QUrl
    from PyQt5.QtGui import QDesktopServices
    VERSION_QT5 = True


from cura.CuraApplication import CuraApplication
from cura.CuraVersion import CuraVersion  # type: ignore
from cura.Utils.Threading import call_on_qt_thread
from cura.Snapshot import Snapshot

from UM.Application import Application
from UM.Tool import Tool
from UM.Event import Event
from UM.Logger import Logger
from UM.Message import Message
from UM.Scene.Selection import Selection
from UM.Settings.InstanceContainer import InstanceContainer
from UM.Qt.Duration import DurationFormat
from UM.Preferences import Preferences

from UM.Resources import Resources
from UM.i18n import i18nCatalog

i18n_cura_catalog = i18nCatalog("cura")
i18n_catalog = i18nCatalog("fdmprinter.def.json")
i18n_extrud_catalog = i18nCatalog("fdmextruder.def.json")

encode = html.escape

Resources.addSearchPath(
    os.path.join(os.path.abspath(os.path.dirname(__file__)))
)  # Plugin translation file import

catalog = i18nCatalog("curahtmldoc")

if catalog.hasTranslationLoaded():
    Logger.log("i", "Cura Html Doc Plugin translation loaded!")
    
class CuraHtmlDoc(Tool):
    def __init__(self):
        super().__init__()

        self._filefolder = ""
        self._auto_save = False

        self.Major=1
        self.Minor=0

        # Logger.log('d', "Info Version CuraVersion --> " + str(Version(CuraVersion)))
        Logger.log('d', "Info CuraVersion --> " + str(CuraVersion))
        
        # Test version for Cura Master
        # https://github.com/smartavionics/Cura
        if "master" in CuraVersion :
            self.Major=4
            self.Minor=20
        else:
            try:
                self.Major = int(CuraVersion.split(".")[0])
                self.Minor = int(CuraVersion.split(".")[1])
            except:
                pass
                
        self._toolbutton_item = None  # type: Optional[QObject]
        self._tool_enabled = False

        self._doc_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "HtmlDoc", "Sample.html")
        self._filefolder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "HtmlDoc")
        
        self._application = CuraApplication.getInstance()
        self._controller = self.getController()
        
        self.setExposedProperties("FileFolder", "AutoSave")

        self._preferences = self._application.getPreferences()
        # auto_save
        self._preferences.addPreference("CuraHtmlDoc/auto_save", False)
        self._auto_save = bool(self._preferences.getValue("CuraHtmlDoc/auto_save"))        

        # filefolder
        self._preferences.addPreference("CuraHtmlDoc/folder", False)
        self._filefolder = self._preferences.getValue("CuraHtmlDoc/folder")   

        # Folder Doesn't Exist
        if not os.path.isdir(self._filefolder) : 
            self._filefolder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "HtmlDoc")
            Message(text = catalog.i18nc("@message","Save path set to : \n %s") % self._filefolder, title = catalog.i18nc("@title", "Cura Html Doc")).show()
            self._preferences.setValue("CuraHtmlDoc/folder", self._filefolder)
                    
        # Before to Exit
        self._application.getOnExitCallbackManager().addCallback(self._onExitCallback)        

        # Part of code for forceToolEnabled Copyright (c) 2022 Aldo Hoeben / fieldOfView ( Source MeasureTool )
        self._application.engineCreatedSignal.connect(self._onEngineCreated)
        Selection.selectionChanged.connect(self._onSelectionChanged)
        self._controller.activeStageChanged.connect(self._onActiveStageChanged)
        self._controller.activeToolChanged.connect(self._onActiveToolChanged)
        
        self._application.getOutputDeviceManager().writeStarted.connect(self._onWriteStarted)
        
        self._selection_tool = None  # type: Optional[Tool]    
        
    # -------------------------------------------------------------------------------------------------------------
    # Origin of this code for forceToolEnabled Copyright (c) 2022 Aldo Hoeben / fieldOfView ( Source MeasureTool )
    # def _onSelectionChanged
    # def _onActiveStageChanged
    # def _onActiveToolChanged
    # def _findToolbarIcon
    # def _forceToolEnabled
    # -------------------------------------------------------------------------------------------------------------
    def _onSelectionChanged(self) -> None:
        if not self._toolbutton_item:
            return
        self._application.callLater(lambda: self._forceToolEnabled())

    def _onActiveStageChanged(self) -> None:
        ActiveStage = self._controller.getActiveStage().stageId
        self._tool_enabled = ActiveStage == "PrepareStage" or ActiveStage == "PreviewStage"
        if not self._tool_enabled:
            self._controller.setSelectionTool(self._selection_tool or "SelectionTool")
            self._selection_tool = None
            if self._controller.getActiveTool() == self:
                self._controller.setActiveTool(self._getNoneTool())
        self._forceToolEnabled()

    def _onActiveToolChanged(self) -> None:
        if self._controller.getActiveTool() != self:
            self._controller.setSelectionTool(self._selection_tool or "SelectionTool")
            self._selection_tool = None

    def _findToolbarIcon(self, rootItem: QObject) -> Optional[QObject]:
        for child in rootItem.childItems():
            class_name = child.metaObject().className()
            if class_name.startswith("ToolbarButton_QMLTYPE") and child.property("text") == catalog.i18nc("@label", "CuraHtmlDoc"):
                return child
            elif (
                class_name.startswith("QQuickItem")
                or class_name.startswith("QQuickColumn")
                or class_name.startswith("Toolbar_QMLTYPE")
            ):
                found = self._findToolbarIcon(child)
                if found:
                    return found
        return None
        
    def _forceToolEnabled(self, passive=False) -> None:
        if not self._toolbutton_item:
            return
        try:
            if self._tool_enabled:
                self._toolbutton_item.setProperty("enabled", True)
                if self._application._previous_active_tool == "CuraHtmlDoc" and not passive:
                    self._controller.setActiveTool(self._application._previous_active_tool)
            else:
                self._toolbutton_item.setProperty("enabled", False)
                if self._controller.getActiveTool() == self and not passive:
                    self._controller.setActiveTool(self._getNoneTool())
        except RuntimeError:
            Logger.log("w", "The toolbutton item seems to have gone missing; trying to find it back.")
            main_window = self._application.getMainWindow()
            if not main_window:
                return

            self._toolbutton_item = self._findToolbarIcon(main_window.contentItem())
            
    def _onEngineCreated(self) -> None:
        main_window = self._application.getMainWindow()
        if not main_window:
            return
            
        self._toolbutton_item = self._findToolbarIcon(main_window.contentItem())
        self._forceToolEnabled()

    def event(self, event: Event) -> bool:
        result = super().event(event)

        if not self._tool_enabled:
            return result

        # overridden from ToolHandle.event(), because we also want to show the handle when there is no selection
        # disabling the tool oon Event.ToolDeactivateEvent is properly handled in ToolHandle.event()
        if event.type == Event.ToolActivateEvent:
            if self._handle:
                self._handle.setParent(self.getController().getScene().getRoot())
                self._handle.setEnabled(True)

            self._selection_tool = self._controller._selection_tool
            self._controller.setSelectionTool(None)

            self._application.callLater(lambda: self._forceToolEnabled(passive=True))

        if event.type == Event.ToolDeactivateEvent:
            self._controller.setSelectionTool(self._selection_tool or "SelectionTool")
            self._selection_tool = None

            self._application.callLater(lambda: self._forceToolEnabled(passive=True))

        if self._selection_tool:
            self._selection_tool.event(event)

        return result
    # -------------------------------------------------------------------------------------------------------------
    def _onExitCallback(self)->None:
        ''' Called as Cura is closing to ensure that the Html Doc file were saved before exiting 
            Code must be change in a futur release not decided what to do here exactly V0.0.2   
        '''
        # Save the Html file 
        try:
            Logger.log("d", "onExitCallback")
        except:
            pass
        
        self._application.triggerNextExitCheck()        
        
    def getFileFolder(self) -> str:
        # Logger.log("d", "File folder {}".format(self._filefolder))
        return self._filefolder

    def setFileFolder(self, value: str) -> None:
        self._doc_file = value        
        # Save and Open the HTML file
        self._openHtmlPage(self._doc_file)
        # with open(str(value), "wt") as stream:
        #     self._write(stream)
        self._filefolder = os.path.dirname(self._doc_file)
        self._preferences.setValue("CuraHtmlDoc/folder", self._filefolder)
        Logger.log("w", "Filefolder set to {}".format(self._filefolder))
        Message(text = catalog.i18nc("@message","Doc succesfully Saved : \n %s") % value, title = catalog.i18nc("@title", "Cura Html Doc")).show()

    def getAutoSave(self )-> bool:
        return self._auto_save

    def setAutoSave(self, value: bool) -> None:
        # Logger.log("w", "SetAutoSave {}".format(value))
        self._auto_save = value
        self.propertyChanged.emit()
        self._preferences.setValue("CuraHtmlDoc/auto_save", self._auto_save)

    def _getFallbackTool(self) -> str:
        try:
            return self._controller._fallback_tool
        except AttributeError:
            return "TranslateTool"

    def _getNoneTool(self) -> str:
        try:
            return self._controller._fallback_tool
        except AttributeError:
            return None

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
    
    def _write(self, stream):
        # Current File path
        # Logger.log("d", "stream = %s", os.path.abspath(stream.name))   
        stream.write("""<!DOCTYPE html>
            <meta charset='UTF-8'>
            <head>
                <title>Cura Settings Export</title>
                <style>
                    tr.category td { font-size: 1.1em; background-color: rgb(142,170,219); }
                    tr.disabled td { background-color: #eaeaea; color: #717171; }
                    tr.local td { background-color: #77DD77; }
                    body.hide-disabled tr.disabled { display: none; }
                    body.hide-local tr.normal { display: none; }
                    .val { width: 200px; text-align: right; }
                    .w-10 { width: 10%; }
                    .w-50 { width: 50%; }
                    .w-70 { width: 70%; }
                    .pl-l { padding-left: 20px; }
                    .pl-2 { padding-left: 40px; }
                    .pl-3 { padding-left: 60px; }
                    .pl-4 { padding-left: 80px; }
                    .pl-5 { padding-left: 100px; }
                </style>
            </head>
            <body lang=EN>
        \n""")
        
        machine_manager = CuraApplication.getInstance().getMachineManager()        
        stack = CuraApplication.getInstance().getGlobalContainerStack()

        #global_stack = machine_manager.activeMachine
        global_stack = CuraApplication.getInstance().getGlobalContainerStack()

        TitleTxt = catalog.i18nc("@label","Print settings")
        ButtonTxt = catalog.i18nc("@action:label","Visible settings")
        ButtonTxt2 = catalog.i18nc("@action:label","Custom selection")

        stream.write("<h1>" + TitleTxt + "</h1>\n")
        stream.write("<button id='enabled'>" + ButtonTxt + "</button><P>\n")
        stream.write("<button id='local'>" + ButtonTxt2 + "</button><P>\n")

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
            
            if VERSION_QT5:
                thumbnail_buffer.open(QBuffer.ReadWrite)
            else:
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
        # platform
        self._WriteTd(stream,"Os",str(platform.system()) + " " + str(platform.version()))
       
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
            
        MAterial=0
        #   materialWeights
        for Mat in list(print_information.materialWeights):
            MAterial=MAterial+Mat
        if MAterial>0:
            M_Weight= "{:.1f} g".format(MAterial).rstrip("0").rstrip(".")
            self._WriteTd(stream,catalog.i18nc("@label","Material estimation"),M_Weight)
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
                # Shell before 4.9 and now walls
                self._doTree(Extrud,"shell",stream,0,i)
                # New section Arachne and 4.9 ?
                if self.Major > 4 or ( self.Major == 4 and self.Minor >= 9 ) :
                    self._doTree(Extrud,"top_bottom",stream,0,i)

                self._doTree(Extrud,"infill",stream,0,i)
                self._doTree(Extrud,"material",stream,0,i)
                self._doTree(Extrud,"speed",stream,0,i)
                self._doTree(Extrud,"travel",stream,0,i)
                self._doTree(Extrud,"cooling",stream,0,i)

                self._doTree(Extrud,"dual",stream,0,i)
        else:
            self._doTree(extruder_stack[0],"resolution",stream,0,0)
            # Shell before 4.9 and now walls
            self._doTree(extruder_stack[0],"shell",stream,0,0)
            # New section Arachne and 4.9 ?
            if self.Major > 4 or ( self.Major == 4 and self.Minor >= 9 ) :
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

        stream.write("</table>")
        stream.write("</body>")
        stream.write("</html>")
        return True

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
        changed_setting_keys = top_of_stack.getAllKeys()            

        if stack.getProperty(key,"type") == "category":
            stream.write("<tr class='category'>")
            if extrud>0:
                untranslated_label=stack.getProperty(key,"label")
                translated_label=i18n_catalog.i18nc(definition_key, untranslated_label) 
                Pos = int(stack.getMetaDataEntry("position"))   
                Pos += 1
                Info_Extrud="%s : %d %s"%(ExtruderStrg,Pos,translated_label)
            else:
                untranslated_label=stack.getProperty(key,"label")
                translated_label=i18n_catalog.i18nc(definition_key, untranslated_label)
                Info_Extrud=str(translated_label)
            stream.write("<td colspan='3'>" + str(Info_Extrud) + "</td>")
            #stream.write("<td class=category>" + str(key) + "</td>")
            stream.write("</tr>\n")
        else:
            if stack.getProperty(key,"enabled") == False:
                stream.write("<tr class='disabled'>")
            else:
                if key in changed_setting_keys:
                    stream.write("<tr class='local'>")
                else:
                    stream.write("<tr class='normal'>")
            
            # untranslated_label=stack.getProperty(key,"label").capitalize()
            untranslated_label=stack.getProperty(key,"label")           
            translated_label=i18n_catalog.i18nc(definition_key, untranslated_label)
            
            stream.write("<td class='w-70 pl-"+str(depth)+"'>" + str(translated_label) + "</td>")
            
            GetType=stack.getProperty(key,"type")
            GetVal=stack.getProperty(key,"value")
            
            if str(GetType)=='float':
                # GelValStr="{:.2f}".format(GetVal).replace(".00", "")  # Formatage
                GelValStr="{:.4f}".format(GetVal).rstrip("0").rstrip(".") # Formatage thanks to r_moeller
            else:
                # enum = Option list
                if str(GetType)=='enum':
                    definition_option=key + " option " + str(GetVal)
                    get_option=str(GetVal)
                    GetOption=stack.getProperty(key,"options")
                    GetOptionDetail=GetOption[get_option]
                    GelValStr=i18n_catalog.i18nc(definition_option, GetOptionDetail)
                    # Logger.log("d", "GetType_doTree = %s ; %s ; %s ; %s",definition_option, GelValStr, GetOption, GetOptionDetail)
                else:
                    GelValStr=str(GetVal)
            
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
                translated_label=i18n_extrud_catalog.i18nc(definition_key, untranslated_label)
                Pos = int(stack.getMetaDataEntry("position"))   
                Pos += 1                
                Info_Extrud="%s : %d %s"%(ExtruderStrg,Pos,translated_label)
            else:
                untranslated_label=stack.getProperty(key,"label")
                translated_label=i18n_extrud_catalog.i18nc(definition_key, untranslated_label)
                Info_Extrud=str(translated_label)
            stream.write("<tr class='category'><td colspan='3'>" + str(Info_Extrud) + "</td>")
            stream.write("</tr>\n")
        else:
            if stack.getProperty(key,"enabled") == False:
                stream.write("<tr class='disabled'>")
            else:
                if key in changed_setting_keys:
                    stream.write("<tr class='local'>")
                else:
                    stream.write("<tr class='normal'>")
            
            # untranslated_label=stack.getProperty(key,"label").capitalize()
            untranslated_label=stack.getProperty(key,"label")           
            translated_label=i18n_extrud_catalog.i18nc(definition_key, untranslated_label)
            
            stream.write("<td class='w-70 pl-"+str(depth)+"'>" + str(translated_label) + "</td>")
            
            GetType=stack.getProperty(key,"type")
            GetVal=stack.getProperty(key,"value")
            if str(GetType)=='float':
                # GelValStr="{:.2f}".format(GetVal).replace(".00", "")  # Formatage
                GelValStr="{:.4f}".format(GetVal).rstrip("0").rstrip(".") # Formatage thanks to r_moeller
            else:
                # enum = Option list
                if str(GetType)=='enum':
                    definition_option=key + " option " + str(GetVal)
                    get_option=str(GetVal)
                    GetOption=stack.getProperty(key,"options")
                    GetOptionDetail=GetOption[get_option]
                    GelValStr=i18n_catalog.i18nc(definition_option, GetOptionDetail)
                    # Logger.log("d", "GetType_doTree = %s ; %s ; %s ; %s",definition_option, GelValStr, GetOption, GetOptionDetail)
                else:
                    GelValStr=str(GetVal)
                
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
           
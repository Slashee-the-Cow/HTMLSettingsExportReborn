#-----------------------------------------------------------------------------------------------------------
# Copyright (c) 5@xes
#-----------------------------------------------------------------------------------------------------------

VERSION_QT5 = False
try:
    from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot, QUrl
    from PyQt6.QtGui import QDesktopServices
except ImportError:
    from PyQt5.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot, QUrl
    from PyQt5.QtGui import QDesktopServices
    VERSION_QT5 = True

from UM.Tool import Tool
from UM.Event import Event
from UM.Logger import Logger
from UM.Message import Message
from UM.Scene.Selection import Selection
from cura.CuraApplication import CuraApplication

from UM.i18n import i18nCatalog

import time
import threading
import traceback
import os

from typing import  Optional

from UM.Application import Application
from UM.Resources import Resources

Resources.addSearchPath(
    os.path.join(os.path.abspath(os.path.dirname(__file__)))
)  # Plugin translation file import

catalog = i18nCatalog("curahtmldoc")

if catalog.hasTranslationLoaded():
    Logger.log("i", "Cura Html Doc Plugin translation loaded!")
    
class CuraHtmlDoc(Tool):
    def __init__(self):
        super().__init__()

        self._path = ""
        self._filefolder = ""
        self._auto_save = False

        self._toolbutton_item = None  # type: Optional[QObject]
        self._tool_enabled = False

        self._doc_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Htmldoc", "Htmldoc.html")
        self._filefolder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Htmldoc")
        
        self._application = CuraApplication.getInstance()
        self._controller = self.getController()
        self.setExposedProperties("FileFolder", "FilePath", "AutoSave")

        self._preferences = self._application.getPreferences()
        self._preferences.addPreference("CuraHtmlDoc/auto_save", False)
        # auto_save
        self._auto_save = bool(self._preferences.getValue("CuraHtmlDoc/auto_save"))        

        # Before to Exit
        self._application.getOnExitCallbackManager().addCallback(self._onExitCallback)        

        # Part of code for forceToolEnabled Copyright (c) 2022 Aldo Hoeben / fieldOfView ( Source MeasureTool )
        self._application.engineCreatedSignal.connect(self._onEngineCreated)
        Selection.selectionChanged.connect(self._onSelectionChanged)
        self._controller.activeStageChanged.connect(self._onActiveStageChanged)
        self._controller.activeToolChanged.connect(self._onActiveToolChanged)

        # self._application.fileLoaded.connect(self._onFileLoaded)
        self._application.fileCompleted.connect(self._onFileCompleted)

        
        self._selection_tool = None  # type: Optional[Tool]

    def _onFileLoaded(self) -> None:
        # Logger.log("d", "_onFileLoaded")
        if self._auto_save:
            Logger.log("d", "saveFile onFileLoaded")
            self.saveFile()

    def _onFileCompleted(self) -> None:
        if self._auto_save:
            Logger.log("d", "saveFile onFileCompleted")
            self.saveFile()

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
        ''' Called as Cura is closing to ensure that script were saved before exiting '''
        # Save the script 
        try:
            Logger.log("d", "onExitCallback")
            # with open(self._doc_file, "wt") as f:
            #     f.write(self._script)
        except AttributeError:
            pass
        
        Logger.log("d", "Save Done for : {}".format(self._doc_file))
        self._application.triggerNextExitCheck()  
   
    def saveCode(self):
        # with open(self._doc_file, "wt") as f:
        #    f.write(self._script)
        
        Message(text = "Script succesfully Saved : \n %s" % self._doc_file, title = catalog.i18nc("@title", "Live Scripting")).show()        

    def getFileFolder(self) -> str:
        # Logger.log("d", "Script folder {}".format(self._filefolder))
        return self._filefolder

    def setFileFolder(self, value: str) -> None:
        self._doc_file = self._path 
        # with open(str(value), "wt") as f:
        #     f.write(self._script)
        Message(text = "Doc succesfully Saved : \n %s" % value, title = catalog.i18nc("@title", "Cura Html Doc")).show()

    def getFilePath(self) -> str:
        return self._path

    def setFilePath(self, value: str) -> None:
        # Logger.log("d", "The New Script PATH {}".format(value))
        self._path = str(value)
        # self._doc_file = self._path 
        self.propertyChanged.emit()
        
        if self._auto_save:
            Logger.log("d", "_path {}".format(self._path))

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
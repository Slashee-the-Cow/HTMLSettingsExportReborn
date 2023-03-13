# Copyright (c) 2023 5axes
# CuraHtmlDoc is released under the terms of the AGPLv3 or higher.

VERSION_QT5 = False
try:
    from PyQt6.QtCore import QT_VERSION_STR
except ImportError:
    VERSION_QT5 = True
    
from . import CuraHtmlDoc

from UM.i18n import i18nCatalog
i18n_catalog = i18nCatalog("curahtmldoc")

def getMetaData():

    if not VERSION_QT5:
        QmlFile="qml/qml_qt6/CuraHtmlDoc.qml"
    else:
        QmlFile="qml/qml_qt5/CuraHtmlDoc.qml"
        
    return {
        "tool": {
            "name": i18n_catalog.i18nc("@label", "CuraHtmlDoc"),
            "description": i18n_catalog.i18nc("@label", "Cura Html Doc"),
            "icon": "Printer",
            "tool_panel": QmlFile,
            "weight": -200
        }
    }

def register(app):
    return { "tool": CuraHtmlDoc.CuraHtmlDoc() }

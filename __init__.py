# HTML Settings Export Reborn by Slashee the Cow
# Copyright Slashee the Cow 2025-
#
# Based on CuraHtmlDoc by 5axes

    
from . import HTMLSettingsExportReborn

from UM.i18n import i18nCatalog
i18n_catalog = i18nCatalog("htmlsettingsexport")

def getMetaData():
        
    return {}

def register(app):
    return { "extension": HTMLSettingsExportReborn.HTMLSettingsExportReborn() }

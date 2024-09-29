// Copyright (c) 2023 5@xes
// CuraHtmlDoc is released under the terms of the AGPLv3 or higher.
// proterties values
//   "FileFolder" : Path to file
//   "AutoSave"	  : AutoSave


import QtQuick 6.0
import QtQuick.Controls 6.0
import QtQuick.Dialogs 6.2
import QtQuick.Layouts 6.0

import UM 1.6 as UM
import Cura 1.7 as Cura

Item
{
	id: base

	function pathToUrl(path)
	{
		// Convert the path to a usable url
		var url = "file:///"
		url = url + path
		// Not sure of this last encode
		// url = encodeURIComponent(url)
		
		// Return the resulting url
		return url
	}
	
	function urlToStringPath(url)
	{
		// Convert the url to a usable string path
		var path = url.toString()
		path = path.replace(/^(file:\/{3})|(qrc:\/{2})|(http:\/{2})/, "")
		path = decodeURIComponent(path)

		// On Linux, a forward slash needs to be prepended to the resulting path
		// I'm guessing this is needed on Mac OS, as well, but can't test it
		if (Qt.platform.os === "linux" || Qt.platform.os === "osx" || Qt.platform.os === "unix") path = "/" + path
		
		// Return the resulting path
		return path
	}
			
	property variant catalog: UM.I18nCatalog { name: "curahtmldoc" }
	
	// TODO: these widths & heights are a bit too dependant on other objects in the qml...
    width: childrenRect.width
    height: childrenRect.height
	
	Column {
		id: runOptions
		width: childrenRect.width
		height: childrenRect.height

		Cura.PrimaryButton {
		    id: generateButton
			anchors.centerIn: topRect
			spacing: UM.Theme.getSize("default_margin").height
			// width: UM.Theme.getSize("setting_control").width
			height: UM.Theme.getSize("setting_control").height				
			text: catalog.i18nc("@label","Save As")
			onClicked: fileDialogSave.open()
		}

		FileDialog
		{
			id: fileDialogSave
			// fileUrl QT5 !
			onAccepted: UM.ActiveTool.setProperty("FileFolder", urlToStringPath(selectedFile))
			fileMode: FileDialog.SaveFile
			nameFilters: "*.html"
			currentFolder:pathToUrl(UM.ActiveTool.properties.getValue("FileFolder"))
		}
		
		UM.CheckBox {
			text: catalog.i18nc("@option:check","Auto save")
			checked: UM.ActiveTool.properties.getValue("AutoSave")
			onClicked: {
				UM.ActiveTool.setProperty("AutoSave", checked)
			}
		}
	}
}

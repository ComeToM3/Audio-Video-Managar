import QtQuick
import QtQuick.Controls
import AvmLibrary

Rectangle {
    id: root
    property alias text: field.text
    signal searchChanged(string text)

    height: 48
    radius: 18
    color: Theme.elev
    border.color: field.activeFocus ? Theme.iris : Theme.border
    border.width: field.activeFocus ? 2 : 1

    Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

    TextInput {
        id: field
        anchors.fill: parent
        anchors.leftMargin: Theme.spaceMd
        anchors.rightMargin: Theme.spaceMd
        verticalAlignment: Text.AlignVCenter
        color: Theme.ink
        font.family: Theme.fontUi
        font.pixelSize: 14
        clip: true
        Accessible.name: "Recherche bibliothèque"
        onTextChanged: root.searchChanged(text)
    }

    Text {
        anchors.fill: field
        verticalAlignment: Text.AlignVCenter
        text: "Rechercher un artiste ou un album…"
        color: Theme.muted
        font.family: Theme.fontUi
        font.pixelSize: 14
        visible: !field.text && !field.activeFocus
    }
}

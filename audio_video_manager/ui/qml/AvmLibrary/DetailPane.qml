import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import AvmLibrary

Rectangle {
    id: root
    color: Theme.elev
    radius: 24
    border.color: Theme.border
    border.width: 1
    clip: true

    property bool compact: false
    property bool hasSelection: false
    property string artist
    property string album
    property int year
    property string cover
    property string letter: "?"
    property string pathLabel
    property bool ready: true
    property bool missing: false
    property int trackCount: 0
    property var tracks: []

    opacity: hasSelection ? 1 : 0.92
    Behavior on opacity { NumberAnimation { duration: Theme.animMed } }

    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceMd
        spacing: Theme.spaceMd

        Rectangle {
            width: compact ? 96 : 120
            height: compact ? 96 : 120
            radius: Theme.radiusSm
            color: Theme.accent
            clip: true
            Layout.alignment: Qt.AlignVCenter

            Image {
                anchors.fill: parent
                source: root.cover
                fillMode: Image.PreserveAspectCrop
                visible: root.cover !== ""
                asynchronous: true
            }
            Text {
                anchors.centerIn: parent
                visible: root.cover === ""
                text: root.hasSelection ? root.letter : "—"
                color: Theme.ink
                font.family: Theme.fontDisplay
                font.pixelSize: 36
                font.bold: true
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            spacing: 4

            Text {
                text: root.hasSelection ? (root.artist + " — " + root.album) : "Sélectionnez un album"
                color: Theme.inkTitle
                font.family: Theme.fontDisplay
                font.pixelSize: compact ? 20 : 22
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                Accessible.name: "Détail album"
            }
            Text {
                visible: root.hasSelection
                text: (root.year > 0 ? (root.year + " · ") : "")
                      + root.trackCount + " piste(s)"
                      + (root.pathLabel ? (" · " + root.pathLabel) : "")
                color: Theme.muted
                font.family: Theme.fontUi
                font.pixelSize: 13
                elide: Text.ElideMiddle
                Layout.fillWidth: true
            }
        }

        Button {
            id: openBtn
            Layout.alignment: Qt.AlignVCenter
            text: "Ouvrir le dossier"
            enabled: root.hasSelection && !root.missing
            Accessible.name: "Ouvrir le dossier album"
            background: Rectangle {
                radius: Theme.radiusSm
                color: openBtn.enabled
                       ? (openBtn.down ? Theme.accentHover : Theme.accent)
                       : Theme.border
            }
            contentItem: Text {
                text: openBtn.text
                color: openBtn.enabled ? Theme.primaryInk : Theme.muted
                font.family: Theme.fontUi
                font.bold: true
                font.pixelSize: 13
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                padding: 12
            }
            onClicked: library.openAlbumFolder()
        }
    }

    // Liste pistes uniquement hors mode compact (repli Widgets garde la table)
    ListView {
        visible: !root.compact && root.hasSelection
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 0
        model: root.tracks
    }
}

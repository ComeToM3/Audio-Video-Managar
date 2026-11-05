import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Avm08a

Rectangle {
    id: root
    color: Theme.surface
    radius: Theme.radius
    border.color: Theme.border
    border.width: 1
    clip: true

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

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceMd
        spacing: Theme.spaceMd

        RowLayout {
            spacing: Theme.spaceMd
            Layout.fillWidth: true

            Rectangle {
                width: 96
                height: 96
                radius: Theme.radiusSm
                color: Theme.accent
                clip: true
                Layout.alignment: Qt.AlignTop

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
                    color: "#E8F3EE"
                    font.pixelSize: 36
                    font.bold: true
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                Text {
                    text: root.hasSelection ? (root.artist + " — " + root.album) : "Sélectionnez un album"
                    color: Theme.inkTitle
                    font.family: Theme.fontDisplay
                    font.pixelSize: 18
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Accessible.name: "Détail album"
                }
                Text {
                    visible: root.hasSelection
                    text: (root.year > 0 ? ("Année : " + root.year + " · ") : "") + root.trackCount + " piste(s)"
                    color: Theme.muted
                    font.pixelSize: 13
                }
                Text {
                    visible: root.hasSelection
                    text: "Dossier : " + root.pathLabel
                    color: Theme.muted
                    font.pixelSize: 12
                    elide: Text.ElideMiddle
                    Layout.fillWidth: true
                }
                Rectangle {
                    visible: root.hasSelection
                    width: chipTxt.implicitWidth + 14
                    height: 24
                    radius: 12
                    color: root.missing ? Theme.warnBg : Theme.okBg
                    Text {
                        id: chipTxt
                        anchors.centerIn: parent
                        text: root.missing ? "Fichiers manquants" : "Prêt"
                        color: root.missing ? Theme.warnInk : Theme.okInk
                        font.pixelSize: 11
                        font.bold: true
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.surfaceMute
            radius: Theme.radiusSm
            border.color: Theme.border
            clip: true

            ListView {
                id: trackList
                anchors.fill: parent
                anchors.margins: 8
                model: root.tracks
                clip: true
                spacing: 2
                Accessible.name: "Pistes de l’album"

                header: Text {
                    width: trackList.width
                    height: visible ? 28 : 0
                    visible: root.hasSelection && root.tracks.length === 0
                    text: "Aucune piste listée"
                    color: Theme.muted
                    font.pixelSize: 12
                    verticalAlignment: Text.AlignVCenter
                }

                delegate: Item {
                    width: trackList.width
                    height: 28
                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 12
                        Text {
                            width: 28
                            text: (modelData.number < 10 ? "0" : "") + modelData.number
                            color: Theme.muted
                            font.pixelSize: 12
                        }
                        Text {
                            width: Math.max(80, trackList.width - 100)
                            text: modelData.title
                            color: Theme.ink
                            font.pixelSize: 13
                            elide: Text.ElideRight
                        }
                        Text {
                            text: modelData.duration
                            color: Theme.muted
                            font.pixelSize: 12
                        }
                    }
                }
            }
        }

        Button {
            id: openBtn
            Layout.alignment: Qt.AlignRight
            text: "Ouvrir le dossier album"
            enabled: root.hasSelection && !root.missing
            Accessible.name: "Ouvrir le dossier album"
            background: Rectangle {
                radius: Theme.radiusSm
                color: openBtn.enabled ? (openBtn.down ? Theme.accentHover : Theme.accent) : Theme.border
            }
            contentItem: Text {
                text: openBtn.text
                color: openBtn.enabled ? "#FFFFFF" : Theme.muted
                font.bold: true
                font.pixelSize: 13
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                padding: 10
            }
            // Prototype : pas d’ouverture réelle (lecture seule / isolation)
            onClicked: { /* no-op volontaire AVM-08A */ }
        }
    }
}

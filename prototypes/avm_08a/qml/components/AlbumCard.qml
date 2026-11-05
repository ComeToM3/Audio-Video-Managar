import QtQuick
import QtQuick.Controls
import Avm08a

Item {
    id: root
    property string artist
    property string album
    property string cover
    property string letter: "?"
    property bool ready: true
    property bool missing: false
    property bool selected: false
    property int coverSize: Theme.coverMd

    signal clicked()

    width: coverSize + 16
    height: coverSize + 56

    scale: mouse.containsMouse || selected ? 1.03 : 1.0
    Behavior on scale { NumberAnimation { duration: Theme.animFast; easing.type: Easing.OutCubic } }

    Column {
        anchors.fill: parent
        spacing: Theme.spaceXs

        Rectangle {
            id: frame
            width: coverSize
            height: coverSize
            radius: Theme.radiusSm
            color: Theme.accent
            anchors.horizontalCenter: parent.horizontalCenter
            border.width: selected ? 2 : 0
            border.color: Theme.accent
            clip: true

            Image {
                anchors.fill: parent
                source: root.cover
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                visible: root.cover !== ""
            }

            Text {
                anchors.centerIn: parent
                visible: root.cover === ""
                text: root.letter
                color: "#E8F3EE"
                font.family: Theme.fontDisplay
                font.pixelSize: Math.max(28, coverSize * 0.28)
                font.bold: true
            }

            Rectangle {
                anchors.left: parent.left
                anchors.bottom: parent.bottom
                anchors.margins: 8
                width: chip.implicitWidth + 12
                height: 22
                radius: 11
                color: root.missing ? Theme.warnBg : Theme.okBg
                visible: true
                Text {
                    id: chip
                    anchors.centerIn: parent
                    text: root.missing ? "Manquant" : (root.ready ? "Prêt" : "…")
                    color: root.missing ? Theme.warnInk : Theme.okInk
                    font.pixelSize: 10
                    font.bold: true
                }
            }

            // Voile discret au survol
            Rectangle {
                anchors.fill: parent
                color: "#0A3D32"
                opacity: mouse.containsMouse ? 0.08 : 0
                Behavior on opacity { NumberAnimation { duration: Theme.animFast } }
            }
        }

        Text {
            width: coverSize
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.album
            color: Theme.inkTitle
            font.family: Theme.fontUi
            font.pixelSize: 12
            font.bold: true
            elide: Text.ElideRight
            horizontalAlignment: Text.AlignHCenter
        }
        Text {
            width: coverSize
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.artist
            color: Theme.muted
            font.family: Theme.fontUi
            font.pixelSize: 11
            elide: Text.ElideRight
            horizontalAlignment: Text.AlignHCenter
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    Accessible.name: artist + " — " + album
    Accessible.role: Accessible.Button
    Accessible.onPressAction: root.clicked()
}

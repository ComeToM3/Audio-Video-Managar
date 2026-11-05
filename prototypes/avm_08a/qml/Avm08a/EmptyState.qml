import QtQuick
import Avm08a

Item {
    id: root
    property string title: "Aucun album pour l’instant"
    property string subtitle: "Insérez un CD et utilisez « Archiver un disque » dans l’application principale."

    Column {
        anchors.centerIn: parent
        width: Math.min(420, parent.width - 48)
        spacing: Theme.spaceSm

        Rectangle {
            width: 56
            height: 56
            radius: 16
            color: Theme.accentSoft
            anchors.horizontalCenter: parent.horizontalCenter
            Text {
                anchors.centerIn: parent
                text: "♪"
                color: Theme.accent
                font.pixelSize: 26
            }
        }
        Text {
            width: parent.width
            text: root.title
            color: Theme.inkTitle
            font.family: Theme.fontDisplay
            font.pixelSize: 18
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }
        Text {
            width: parent.width
            text: root.subtitle
            color: Theme.muted
            font.pixelSize: 13
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }
    }
}

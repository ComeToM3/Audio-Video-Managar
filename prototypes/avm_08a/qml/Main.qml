import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Avm08a

ApplicationWindow {
    id: win
    width: 1120
    height: 740
    minimumWidth: 820
    minimumHeight: 560
    visible: true
    title: "AVM-08A · Prototype Bibliothèque (Qt Quick)"
    color: Theme.bg

    readonly property bool narrow: width < 980
    readonly property int coverSize: width >= 1400 ? Theme.coverLg : (narrow ? Theme.coverSm : Theme.coverMd)
    property int selectedRow: -1

    // Fond atmosphérique discret (pas plat unique)
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Theme.bg }
            GradientStop { position: 1.0; color: Theme.bgDeep }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: narrow ? Theme.spaceMd : Theme.spaceLg
        spacing: Theme.spaceMd

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spaceMd

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    text: "AudioVideo Manager"
                    color: Theme.inkTitle
                    font.family: Theme.fontDisplay
                    font.pixelSize: narrow ? 22 : 26
                    Accessible.name: "AudioVideo Manager"
                }
                Text {
                    text: "Ma bibliothèque · prototype QML isolé"
                    color: Theme.muted
                    font.pixelSize: 13
                }
                Text {
                    text: library.sourceLabel
                    color: Theme.muted
                    font.pixelSize: 11
                    opacity: 0.85
                }
            }

            Rectangle {
                width: badge.implicitWidth + 16
                height: 28
                radius: 14
                color: Theme.accentSoft
                Text {
                    id: badge
                    anchors.centerIn: parent
                    text: "Lecture seule"
                    color: Theme.inkTitle
                    font.pixelSize: 11
                    font.bold: true
                }
            }
        }

        SearchBar {
            Layout.fillWidth: true
            onSearchChanged: function (t) {
                library.search(t)
                win.selectedRow = -1
            }
        }

        // Composition principale : grille + détail
        SplitView {
            id: split
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: narrow ? Qt.Vertical : Qt.Horizontal

            handle: Rectangle {
                implicitWidth: narrow ? parent.width : 8
                implicitHeight: narrow ? 8 : parent.height
                color: "transparent"
            }

            // Grille pochettes
            Item {
                SplitView.preferredWidth: narrow ? parent.width : parent.width * 0.62
                SplitView.preferredHeight: narrow ? parent.height * 0.58 : parent.height
                SplitView.minimumWidth: 280
                SplitView.minimumHeight: 200

                GridView {
                    id: grid
                    anchors.fill: parent
                    clip: true
                    model: library.albums
                    cellWidth: coverSize + 28
                    cellHeight: coverSize + 72
                    cacheBuffer: 800
                    Accessible.name: "Liste des albums"
                    focus: true
                    KeyNavigation.tab: detail

                    delegate: AlbumCard {
                        artist: model.artist
                        album: model.album
                        cover: model.cover
                        letter: model.letter
                        ready: model.ready
                        missing: model.missing
                        selected: index === win.selectedRow
                        coverSize: win.coverSize
                        onClicked: {
                            win.selectedRow = index
                            library.selectRow(index)
                            grid.currentIndex = index
                        }
                    }

                    EmptyState {
                        anchors.fill: parent
                        visible: grid.count === 0
                        title: "Aucun album à afficher"
                        subtitle: "Ajustez la recherche, ou archivez un disque dans l’app Widgets."
                    }
                }
            }

            DetailPane {
                id: detail
                SplitView.preferredWidth: narrow ? parent.width : parent.width * 0.38
                SplitView.preferredHeight: narrow ? parent.height * 0.42 : parent.height
                SplitView.minimumWidth: 280
                SplitView.minimumHeight: 180
                hasSelection: library.hasSelection
                artist: library.selectedArtist
                album: library.selectedAlbum
                year: library.selectedYear
                cover: library.selectedCover
                letter: library.selectedLetter
                pathLabel: library.selectedPathLabel
                ready: library.selectedReady
                missing: library.selectedMissing
                trackCount: library.selectedTrackCount
                tracks: library.selectedTracks
            }
        }

        Text {
            Layout.fillWidth: true
            text: "AVM-08A · hors production · Widgets inchangés · pas d’écriture SQLite / FLAC"
            color: Theme.muted
            font.pixelSize: 10
            opacity: 0.7
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Component.onCompleted: {
        if (library.albumCount() > 0) {
            selectedRow = 0
            library.selectRow(0)
            grid.currentIndex = 0
        }
    }
}

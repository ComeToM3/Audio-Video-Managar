import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import AvmLibrary

// Racine Item pour QQuickWidget — Brume pastel AVM-08E
Item {
    id: win
    anchors.fill: parent

    readonly property bool narrow: width < 980
    readonly property int coverSize: width >= 1400 ? Theme.coverLg : (narrow ? Theme.coverSm : Theme.coverMd)
    property int selectedRow: -1
    property url paintUrl: (typeof atelierBg !== "undefined") ? atelierBg : ""

    Rectangle {
        anchors.fill: parent
        color: Theme.bg
        radius: Theme.radius
        clip: true
        Image {
            anchors.fill: parent
            source: win.paintUrl
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            opacity: 0.55
            visible: win.paintUrl !== ""
        }
        Rectangle {
            anchors.fill: parent
            color: "#B3FFFCF8"
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: narrow ? Theme.spaceMd : Theme.spaceLg
        spacing: Theme.spaceLg

        // Hero : typographie display + recherche
        GridLayout {
            Layout.fillWidth: true
            columns: narrow ? 1 : 2
            columnSpacing: Theme.spaceLg
            rowSpacing: Theme.spaceMd

            ColumnLayout {
                Layout.fillWidth: true
                Layout.columnSpan: 1
                spacing: Theme.spaceSm
                Text {
                    text: "Votre collection,\ndans la brume."
                    color: Theme.inkTitle
                    font.family: Theme.fontDisplay
                    font.pixelSize: narrow ? 28 : 40
                    font.bold: true
                    lineHeight: 1.05
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Accessible.name: "Votre collection, dans la brume"
                }
                Text {
                    text: "Pochettes d’abord. Surfaces teintées — la couleur caresse le regard."
                    color: Theme.muted
                    font.family: Theme.fontUi
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Layout.maximumWidth: 420
                }
                Text {
                    text: library.sourceLabel
                    color: Theme.muted
                    font.pixelSize: 12
                }
            }

            SearchBar {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignBottom
                onSearchChanged: function (t) {
                    library.search(t)
                    win.selectedRow = -1
                }
            }
        }

        // Grille pochettes
        GridView {
            id: grid
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: library.albums
            cellWidth: coverSize + 28
            cellHeight: coverSize + 64
            cacheBuffer: 900
            Accessible.name: "Liste des albums"
            focus: true

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
                subtitle: "Archivez un disque, ou élargissez la recherche."
            }
        }

        // Bandeau détail bas (maquette)
        DetailPane {
            id: detail
            Layout.fillWidth: true
            Layout.preferredHeight: hasSelection ? (narrow ? 168 : 148) : 0
            Layout.maximumHeight: narrow ? 200 : 160
            visible: hasSelection
            compact: true
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

    Component.onCompleted: {
        if (library.albumCount() > 0) {
            selectedRow = 0
            library.selectRow(0)
            grid.currentIndex = 0
        }
    }

    function reselectFirst() {
        if (library.albumCount() > 0) {
            selectedRow = 0
            library.selectRow(0)
            grid.currentIndex = 0
        } else {
            selectedRow = -1
        }
    }
}

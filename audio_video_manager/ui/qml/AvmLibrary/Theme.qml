pragma Singleton
import QtQuick

QtObject {
    // AVM-08E — Brume pastel
    readonly property color bg: "#F0EBE3"
    readonly property color bgDeep: "#E8ECF4"
    readonly property color surface: "#FFFCF8"
    readonly property color surfaceMute: "#FFFAF5"
    readonly property color elev: "#FFFAF5"
    readonly property color ink: "#2A2E3A"
    readonly property color inkTitle: "#17191F"
    readonly property color muted: "#5C6478"
    readonly property color accent: "#F1B65C"
    readonly property color accentHover: "#E0A44A"
    readonly property color accentSoft: "#F8E6C8"
    readonly property color iris: "#7D8FE8"
    readonly property color rose: "#D782A6"
    readonly property color jade: "#58B9AA"
    readonly property color border: "#D8DCE6"
    readonly property color warnBg: "#F8E6C8"
    readonly property color warnInk: "#6B4A12"
    readonly property color errBg: "#F3D9E6"
    readonly property color errInk: "#8A3A5C"
    readonly property color okBg: "#E8F5F2"
    readonly property color okInk: "#1F6B60"
    readonly property color primaryInk: "#17191F"
    readonly property color navActiveInk: "#6B4A12"

    readonly property int radius: 28
    readonly property int radiusSm: 16
    readonly property int spaceXs: 6
    readonly property int spaceSm: 10
    readonly property int spaceMd: 16
    readonly property int spaceLg: 24
    readonly property int spaceXl: 36

    readonly property int coverSm: 132
    readonly property int coverMd: 168
    readonly property int coverLg: 200

    readonly property string fontUi: "Outfit"
    readonly property string fontDisplay: "Fraunces"

    readonly property int animFast: 160
    readonly property int animMed: 260
}

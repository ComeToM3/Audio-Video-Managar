pragma Singleton
import QtQuick

QtObject {
    // Direction « archive chaleureuse » — évolution 06L pour Qt Quick
    readonly property color bg: "#F3F0E8"
    readonly property color bgDeep: "#EAE6DB"
    readonly property color surface: "#FFFFFF"
    readonly property color surfaceMute: "#FAF8F3"
    readonly property color ink: "#1A1F1C"
    readonly property color inkTitle: "#0A3D32"
    readonly property color muted: "#5A635C"
    readonly property color accent: "#1B7A5C"
    readonly property color accentHover: "#15684E"
    readonly property color accentSoft: "#DCEDE5"
    readonly property color border: "#E2DDD3"
    readonly property color warnBg: "#F5EBD3"
    readonly property color warnInk: "#6B4E00"
    readonly property color errBg: "#F4E0E0"
    readonly property color errInk: "#7A1010"
    readonly property color okBg: "#E8F3EE"
    readonly property color okInk: "#0A3D32"

    readonly property int radius: 14
    readonly property int radiusSm: 10
    readonly property int spaceXs: 6
    readonly property int spaceSm: 10
    readonly property int spaceMd: 16
    readonly property int spaceLg: 24
    readonly property int spaceXl: 36

    readonly property int coverSm: 112
    readonly property int coverMd: 140
    readonly property int coverLg: 168

    readonly property string fontUi: "Segoe UI"
    readonly property string fontDisplay: "Segoe UI Semibold"

    readonly property int animFast: 140
    readonly property int animMed: 220
}

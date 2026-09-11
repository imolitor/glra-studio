import QtQuick
import QtQuick.Controls.Basic
Button {
    id: b
    property bool primary: false
    property bool dark: false
    property int textSize: 13
    implicitHeight: 42
    implicitWidth: Math.max(80, label.implicitWidth + 28)
    focusPolicy: Qt.NoFocus
    hoverEnabled: true
    contentItem: Text {
        id: label; text: b.text; font.pixelSize: b.textSize; font.weight: Font.DemiBold
        color: !b.enabled ? "#95a1b3" : b.primary ? "white" : b.dark ? "#e8edf5" : "#253247"
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: 10
        color: !b.enabled ? (b.dark ? "#243043" : "#edf0f5") : b.primary ? (b.hovered ? "#285add" : "#356cf6") : b.hovered ? (b.dark ? "#303f52" : "#eaf0fb") : (b.dark ? "#243043" : "#f0f3f8")
        border.width: b.primary ? 0 : 1; border.color: b.dark ? "#354258" : "#e4e9f1"
        Behavior on color { ColorAnimation { duration: 130 } }
    }
}

import QtQuick
import QtQuick.Controls.Basic
Button {
    id: b
    property var entry
    property bool dark: false
    property bool compact: false
    property string caption: ""
    signal selected(int slot)
    implicitHeight: compact ? 36 : 88
    implicitWidth: compact ? 90 : 92
    padding: compact ? 0 : 6
    focusPolicy: Qt.NoFocus
    hoverEnabled: true
    onClicked: selected(entry.slot)
    Accessible.name: caption + ": " + entry.label
    ToolTip.visible: hovered; ToolTip.delay: 450
    ToolTip.text: entry.label + (entry.verified ? "" : " · verify before saving")
    background: Rectangle {
        radius: b.compact ? 9 : 12
        color: entry.awaitingVerification ? (b.dark ? "#48301c" : "#fff3e4") : entry.active ? "#cbf4e2" : entry.selected ? (b.dark ? "#213b68" : "#eaf0ff") : b.hovered ? (b.dark ? "#2b3a50" : "#f3f6fc") : (b.dark ? "#243042" : "#ffffff")
        border.width: entry.awaitingVerification ? 3 : entry.selected ? 2 : 1
        border.color: entry.awaitingVerification ? (b.dark ? "#ffad4d" : "#e78216") : entry.selected ? "#4a7aff" : b.dark ? "#3a485c" : "#dce3ee"
        Behavior on color { ColorAnimation { duration: 160 } }
        Rectangle { visible: !b.compact; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 5; height: 3; radius: 2; color: b.dark ? "#172132" : "#e7ecf4" }
    }
    contentItem: Item {
        Text { text: b.caption; anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 5; font.pixelSize: 10; color: b.dark ? "#a1aec2" : "#8592a7" }
        Text {
            anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; anchors.verticalCenterOffset: 7; anchors.margins: 4
            text: entry.label; font.pixelSize: b.compact ? 12 : entry.label.length>13 ? 12 : 15; font.weight: Font.DemiBold
            horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
            color: entry.selected ? (b.dark ? "#a9c4ff" : "#2756c8") : (b.dark ? "#f0f4fb" : "#253249")
        }
        Rectangle { visible: !entry.verified; width: 4; height: 4; radius: 2; anchors.top: parent.top; anchors.right: parent.right; anchors.margins: 6; color: "#c29652" }
    }
}

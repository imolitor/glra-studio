import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
ApplicationWindow {
    id: root
    width: 1260; height: 860; minimumWidth: 1110; minimumHeight: 840
    visible: true; title: "GLRA Studio"
    property bool dark: false
    property var data: studio.ui
    property color ink: dark ? "#edf3fc" : "#1c2c44"
    property color muted: dark ? "#9eacc1" : "#6e7e94"
    property color surface: dark ? "#1a2535" : "#ffffff"
    property color line: dark ? "#2d3a4e" : "#e3e9f2"
    color: dark ? "#111a28" : "#f5f7fb"
    font.family: "Helvetica Neue"
    palette.windowText: ink
    palette.text: ink
    palette.buttonText: ink
    palette.window: surface
    palette.base: surface
    onClosing: function(close) { if (data.busy || data.calibrating) { close.accepted=false; closeDialog.open() } }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 28; spacing: 22
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            Rectangle {
                width: 40; height: 40; radius: 12; color: "#356cf6"
                Grid { anchors.centerIn: parent; columns: 2; spacing: 3
                    Repeater { model: 4; Rectangle { width: 7; height: 7; radius: 2; color: "white"; opacity: index===3 ? .55 : 1 } }
                }
            }
            Text { text: "GLRA"; color: root.ink; font.pixelSize: 22; font.weight: Font.Bold; font.letterSpacing: -.5 }
            Text { text: "Studio"; color: root.muted; font.pixelSize: 22; font.weight: Font.Light }
            Item { Layout.fillWidth: true }
            Rectangle {
                implicitWidth: connectionLabel.implicitWidth+34; implicitHeight: 31; radius: 15; color: root.dark ? "#25364a" : "#eaf0f8"
                Text { id: connectionLabel; anchors.centerIn: parent; text: root.data.demo ? "DEMO MODE" : root.data.connected ? "●  PAD CONNECTED" : "○  WAITING FOR PAD"; font.pixelSize: 10; font.weight: Font.DemiBold; font.letterSpacing: .8; color: root.data.demo ? root.muted : root.data.connected ? (root.dark ? "#7be0ba" : "#218363") : root.muted }
            }
            StudioButton { text: root.dark ? "Light mode" : "Dark mode"; dark: root.dark; onClicked: root.dark=!root.dark }
            StudioButton { text: "Help"; dark: root.dark; implicitWidth: 66; onClicked: studio.openHelp() }
        }
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 5
                Text { text: "A little pad. Your shortcuts."; color: root.ink; font.pixelSize: 29; font.weight: Font.DemiBold; font.letterSpacing: -.8 }
                Text { text: "Select a control, capture a shortcut, and make it yours."; color: root.muted; font.pixelSize: 14 }
            }
            Item { Layout.fillWidth: true }
            ColumnLayout {
                spacing: 5
                Text { text: "G-LRA  k16_n3"; color: root.ink; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.alignment: Qt.AlignRight }
                Text { text: "16 keys  ·  3 dials  ·  Profile " + root.data.profile; color: root.muted; font.pixelSize: 12; Layout.alignment: Qt.AlignRight }
            }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 22
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true; color: root.surface; radius: 18; border.color: root.line
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 25; spacing: 16
                    RowLayout {
                        Text { text: "YOUR PAD"; font.pixelSize: 10; font.weight: Font.Bold; font.letterSpacing: 1.6; color: root.muted }
                        Item { Layout.fillWidth: true }
                        Text { text: root.data.connected ? "Click any key or dial action" : "Plug in your USB macropad"; color: root.muted; font.pixelSize: 11 }
                    }
                    Rectangle {
                        Layout.fillWidth: true; Layout.fillHeight: true; radius: 16; color: root.dark ? "#151e2c" : "#f2f5fa"; border.color: root.line
                        RowLayout {
                            anchors.fill: parent; anchors.margins: 18; spacing: 18
                            GridLayout {
                                Layout.fillWidth: true; Layout.alignment: Qt.AlignVCenter; columns: 4; rowSpacing: 11; columnSpacing: 10
                                Repeater {
                                    model: root.data.keys
                                    KeyTile {
                                        required property var modelData
                                        entry: modelData; dark: root.dark; caption: modelData.number.toString().padStart(2,"0")
                                        Layout.fillWidth: true; Layout.preferredHeight: 79; Layout.minimumWidth: 68
                                        enabled: !root.data.busy && !root.data.calibrating
                                        onSelected: function(slot) { studio.select(slot) }
                                    }
                                }
                            }
                            Rectangle { Layout.preferredWidth: 1; Layout.fillHeight: true; Layout.topMargin: 10; Layout.bottomMargin: 10; color: root.line }
                            ColumnLayout {
                                Layout.preferredWidth: 204; spacing: 12; Layout.alignment: Qt.AlignVCenter
                                Repeater {
                                    model: root.data.dials
                                    ColumnLayout {
                                        required property var modelData
                                        Layout.fillWidth: true; spacing: 7
                                        RowLayout {
                                            Layout.fillWidth: true
                                            Rectangle { width: 27; height: 27; radius: 14; color: root.dark ? "#344257" : "#dce4ef"; border.color: root.dark ? "#51617a" : "#bcc9dc"
                                                Rectangle { width: 3; height: 8; radius: 2; color: root.dark ? "#c5d2e6" : "#7c8da5"; anchors.horizontalCenter: parent.horizontalCenter; y: 3 }
                                            }
                                            Text { text: modelData.name; color: root.ink; font.pixelSize: 12; font.weight: Font.DemiBold }
                                        }
                                        RowLayout {
                                            Layout.fillWidth: true; spacing: 6
                                            KeyTile { entry: modelData.left; caption: "↶ LEFT"; compact: true; dark: root.dark; Layout.fillWidth: true; Layout.preferredWidth: 90; enabled: !root.data.busy && !root.data.calibrating; onSelected: function(slot) { studio.select(slot) } }
                                            KeyTile { entry: modelData.right; caption: "↷ RIGHT"; compact: true; dark: root.dark; Layout.fillWidth: true; Layout.preferredWidth: 90; enabled: !root.data.busy && !root.data.calibrating; onSelected: function(slot) { studio.select(slot) } }
                                        }
                                        KeyTile { entry: modelData.press; caption: "↓ PRESS"; compact: true; dark: root.dark; Layout.fillWidth: true; enabled: !root.data.busy && !root.data.calibrating; onSelected: function(slot) { studio.select(slot) } }
                                    }
                                }
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 8
                        Rectangle { width: 5; height: 5; radius: 3; color: "#c29652" }
                        Text { text: "Dot = verify the physical position before editing"; color: root.muted; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                        StudioButton { text: "Reload"; implicitWidth: 75; implicitHeight: 32; dark: root.dark; enabled: !root.data.busy && !root.data.calibrating; onClicked: studio.refresh() }
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: root.line }
                    RowLayout {
                        Layout.fillWidth: true
                        Repeater { model: ["01  Select a control", "02  Record a shortcut", "03  Save & verify"]
                            Text { required property string modelData; text: modelData; color: root.muted; font.pixelSize: 11; Layout.fillWidth: true }
                        }
                    }
                }
            }
            Rectangle {
                Layout.preferredWidth: 294; Layout.fillHeight: true; radius: 18; color: root.surface; border.color: root.line
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 23; spacing: 15
                    Text { text: "ASSIGNMENT"; color: root.muted; font.pixelSize: 10; font.weight: Font.Bold; font.letterSpacing: 1.6 }
                    Text { text: root.data.selectedName; color: root.ink; font.pixelSize: 19; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                    Text { text: "Currently sends"; color: root.muted; font.pixelSize: 12 }
                    Text { text: root.data.current; color: root.ink; font.pixelSize: 23; font.weight: Font.Medium; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                    Rectangle { Layout.fillWidth: true; height: 1; color: root.line }
                    Rectangle {
                        Layout.fillWidth: true; Layout.preferredHeight: 128; radius: 13
                        color: root.data.recording ? (root.dark ? "#243e68" : "#eaf0ff") : (root.dark ? "#202d40" : "#f6f8fc")
                        border.width: root.data.recording ? 2 : 1; border.color: root.data.recording ? "#5a83f4" : root.line
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: 15; spacing: 9
                            Text { text: root.data.pending ? "NEW SHORTCUT" : root.data.recording ? "LISTENING…" : "READY WHEN YOU ARE"; font.pixelSize: 9; font.weight: Font.Bold; font.letterSpacing: 1.1; color: root.muted; Layout.alignment: Qt.AlignHCenter }
                            Text { text: root.data.pending || (root.data.recording ? "Press your shortcut" : "⌘  +  …"); color: root.data.pending ? "#4476e5" : root.muted; font.pixelSize: 21; font.weight: Font.DemiBold; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap }
                            Text { text: root.data.recording ? "Normal keyboard · Esc cancels" : "One key, with optional modifiers"; color: root.muted; font.pixelSize: 10; Layout.alignment: Qt.AlignHCenter }
                        }
                    }
                    StudioButton { objectName: "recordButton"; text: root.data.recording ? "Cancel recording" : root.data.pending ? "Record again" : "Record shortcut"; dark: root.dark; Layout.fillWidth: true; enabled: root.data.connected && !root.data.busy && !root.data.calibrating && !root.data.recovery; onClicked: root.data.recording ? studio.cancel() : studio.record() }
                    Text { visible: !root.data.verified && root.data.connected; text: "This position is inferred. Verify it once so edits go to the right control."; color: root.muted; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    StudioButton { visible: !root.data.verified && root.data.connected; text: "Verify this control"; dark: root.dark; Layout.fillWidth: true; enabled: !root.data.busy && !root.data.calibrating && !root.data.recovery; onClicked: verifyDialog.open() }
                    Text { visible: !root.data.inputAvailable && root.data.connected; text: "To detect presses, enable Input Monitoring for this app or your terminal, then restart it."; color: root.muted; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Item { Layout.fillHeight: true }
                    StudioButton { objectName: "saveButton"; text: root.data.busy ? "Working…" : root.data.demo ? "Save in demo" : "Save to pad"; primary: true; dark: root.dark; Layout.fillWidth: true; enabled: root.data.canSave; onClicked: studio.save() }
                    Text { text: "Backed up first. Read back after every save."; color: root.muted; font.pixelSize: 10; Layout.alignment: Qt.AlignHCenter }
                    StudioButton { objectName: "undoButton"; text: "Undo last save"; dark: root.dark; Layout.fillWidth: true; enabled: root.data.canUndo && !root.data.busy && !root.data.calibrating && !root.data.recovery; onClicked: studio.undo() }
                }
            }
        }
        Rectangle {
            Layout.fillWidth: true; implicitHeight: Math.max(48, notice.implicitHeight+24); radius: 12
            color: root.data.error ? (root.dark ? "#422934" : "#fff0ee") : (root.dark ? "#1d2d41" : "#eaf0f8")
            RowLayout {
                anchors.fill: parent; anchors.margins: 12; spacing: 10
                Text { text: root.data.error ? "!" : root.data.calibrating ? "◎" : "●"; color: root.data.error ? "#ce5f59" : "#5880ba"; font.pixelSize: 14 }
                Text { id: notice; Layout.fillWidth: true; text: root.data.error || root.data.message; color: root.ink; font.pixelSize: 12; wrapMode: Text.WrapAnywhere; textFormat: Text.PlainText }
                StudioButton { visible: root.data.recovery || root.data.calibrating; text: "Restore test"; dark: root.dark; enabled: !root.data.busy; onClicked: studio.recover() }
                StudioButton { text: "Backups"; dark: root.dark; implicitHeight: 32; implicitWidth: 83; onClicked: studio.openBackups() }
            }
        }
    }
    Dialog {
        id: confirmDialog; parent: Overlay.overlay; anchors.centerIn: parent; width: 400; modal: true
        visible: root.data.confirm; title: "Change this control?"; closePolicy: Popup.NoAutoClose
        background: Rectangle { radius: 15; color: root.surface; border.color: root.line }
        contentItem: ColumnLayout {
            spacing: 18
            Text { text: root.data.selectedName + " sends “" + root.data.current + "”. Record a new shortcut?"; color: root.ink; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 14 }
            RowLayout { Layout.alignment: Qt.AlignRight
                StudioButton { text: "Keep it"; dark: root.dark; onClicked: studio.cancel() }
                StudioButton { text: "Record new"; primary: true; dark: root.dark; onClicked: studio.record() }
            }
        }
    }
    Dialog {
        id: verifyDialog; parent: Overlay.overlay; anchors.centerIn: parent; width: 430; modal: true; title: "Verify the physical control"
        background: Rectangle { radius: 15; color: root.surface; border.color: root.line }
        contentItem: ColumnLayout {
            spacing: 18
            Text { text: "The app will back up this assignment and temporarily give it an unused function key. Operate ONLY the selected control when prompted. Its original assignment will then be restored. If nothing arrives, the test restores it after 90 seconds. Keep the pad connected."; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: root.ink; font.pixelSize: 13 }
            RowLayout { Layout.alignment: Qt.AlignRight
                StudioButton { text: "Cancel"; dark: root.dark; onClicked: verifyDialog.close() }
                StudioButton { text: "Start control test"; primary: true; dark: root.dark; onClicked: { verifyDialog.close(); studio.verifyControl() } }
            }
        }
    }
    Dialog {
        id: closeDialog; parent: Overlay.overlay; anchors.centerIn: parent; width: 390; modal: true; title: "Finish the device operation"
        contentItem: Text { text: "Wait for saving to finish, or use Restore test to finish the control check before closing."; wrapMode: Text.WordWrap; color: root.ink }
        standardButtons: Dialog.Ok
        background: Rectangle { radius: 15; color: root.surface; border.color: root.line }
    }
}

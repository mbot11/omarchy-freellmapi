import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "io.github.mbot11.freellmapi"
  ipcTarget: "io.github.mbot11.freellmapi"
  manageIpc: false

  readonly property int refreshIntervalSec: setting("refreshIntervalSec", 60)
  readonly property string statePath: Quickshell.env("XDG_STATE_HOME")
                    ? Quickshell.env("XDG_STATE_HOME") + "/omarchy/io.github.mbot11.freellmapi/state.json"
                    : Quickshell.env("HOME") + "/.local/state/omarchy/io.github.mbot11.freellmapi/state.json"
  readonly property string collectorPath: root.fromFileUrl(Qt.resolvedUrl("bin/collect"))

  property var snap: ({})

  readonly property var gateway: (root.snap && root.snap.gateway) ? root.snap.gateway : ({})
  readonly property bool gatewayLive: root.gateway.live === true
  readonly property bool gatewayReady: root.gateway.ready === true
  readonly property bool gatewayDown: !root.gatewayLive || !root.gatewayReady
  readonly property bool degraded: {
    if (root.gatewayDown) return false
    var s = root.snap
    if (s && s.error) return true
    var list = s && s.providers
    if (!list || !list.length) return false
    for (var i = 0; i < list.length; i++) {
      if (list[i] && list[i].status === "rate_limited") return true
    }
    return false
  }
  readonly property color statusColor: {
    if (root.gatewayDown) return Color.urgent
    if (root.degraded) return Color.accent
    return Color.foreground
  }
  readonly property string statusLabel: {
    if (root.gatewayDown) return "Down"
    if (root.degraded) return "Degraded"
    return "Ready"
  }
  readonly property string pillCount: {
    var list = root.snap && root.snap.providers
    if (!list || !list.length) return "?"
    var n = root.gateway.ready_upstreams
    if (n === undefined || n === null) return "?"
    return String(n)
  }
  readonly property string pillText: "FLA · " + root.pillCount

  function fromFileUrl(u) {
    var s = String(u || "").replace(/^file:\/\//, "")
    try { return decodeURIComponent(s) } catch (e) { return s }
  }

  function parseSnap(raw) {
    try {
      var parsed = JSON.parse(String(raw || ""))
      if (parsed && typeof parsed === "object") root.snap = parsed
    } catch (e) { /* keep last good */ }
  }

  function refresh() {
    if (collectProc.running) return
    collectProc.command = ["python3", root.collectorPath]
    collectProc.running = true
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Component.onCompleted: refresh()
  onOpenedChanged: if (opened) {
    refresh()
    Qt.callLater(function() { if (keyCatcher) keyCatcher.forceActiveFocus() })
  }

  FileView {
    id: stateFile
    path: root.statePath
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.parseSnap(text())
  }

  Process {
    id: collectProc
    onExited: stateFile.reload()
  }

  Timer {
    interval: Math.max(30, root.refreshIntervalSec) * 1000
    running: true
    repeat: true
    triggeredOnStart: false
    onTriggered: root.refresh()
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.pillText
    labelVisible: false
    hasVisualContent: true
    foreground: Color.foreground
    tooltipText: root.pillText + " · " + root.statusLabel
    implicitWidth: pillRow.implicitWidth + Style.space(16)
    implicitHeight: bar && bar.barSize ? bar.barSize : Style.bar.sizeHorizontal

    onPressed: function(buttonCode) { root.toggle() }

    Row {
      id: pillRow
      anchors.centerIn: parent
      spacing: Style.space(6)

      Item {
        width: statusDot.width
        height: pillLabel.implicitHeight

        Rectangle {
          id: statusDot
          width: Style.space(6)
          height: Style.space(6)
          radius: width / 2
          color: root.statusColor
          anchors.centerIn: parent
        }
      }

      Text {
        id: pillLabel
        text: root.pillText
        textFormat: Text.PlainText
        color: Color.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.body
      }
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(360))
    contentHeight: panel.fittedContentHeight(column.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) {
        if (t === "r" || t === "R") root.refresh()
      }

      Column {
        id: column
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: Style.space(14)

        Text {
          text: "FLA"
          textFormat: Text.PlainText
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.title
          font.bold: true
        }

        Text {
          text: root.statusLabel
          textFormat: Text.PlainText
          color: root.statusColor
          font.family: Style.font.family
          font.pixelSize: Style.font.body
          font.bold: true
        }

        Text {
          width: parent.width
          visible: !!(root.snap && root.snap.error)
          text: root.snap && root.snap.error ? String(root.snap.error) : ""
          textFormat: Text.PlainText
          wrapMode: Text.WordWrap
          color: Color.muted
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
        }
      }
    }
  }
}

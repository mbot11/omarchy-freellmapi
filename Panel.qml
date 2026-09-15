import QtQuick
import QtQuick.Controls
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
  readonly property var tabNames: ["Overview", "Providers", "Chat", "Fusion", "Media", "Quota"]

  property var snap: ({})
  property int tabIndex: 0
  property string chatQuery: ""
  property var sortedProviders: []
  property var filteredChatModels: []

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
  readonly property var chatSnap: (root.snap && root.snap.chat) ? root.snap.chat : ({})
  readonly property var fusionSnap: (root.snap && root.snap.fusion) ? root.snap.fusion : ({})
  readonly property var mediaSnap: (root.snap && root.snap.media) ? root.snap.media : ({})
  readonly property var quotaSnap: (root.snap && root.snap.quota) ? root.snap.quota : ({})
  readonly property var mediaInferred: root.mediaSnap.inferred || []
  readonly property var quotaPools: root.quotaSnap.pools || []
  readonly property bool missingUnifiedKey: {
    var err = root.snap && root.snap.error ? String(root.snap.error) : ""
    return err.indexOf("FREELLMAPI_UNIFIED_KEY") >= 0
  }

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

  function formatDuration(sec) {
    var n = Number(sec)
    if (!isFinite(n) || n < 0) n = 0
    n = Math.floor(n)
    if (n < 60) return n + "s"
    if (n < 3600) return Math.floor(n / 60) + "m"
    if (n < 86400) {
      var h = Math.floor(n / 3600)
      var m = Math.floor((n % 3600) / 60)
      return m ? (h + "h " + m + "m") : (h + "h")
    }
    var d = Math.floor(n / 86400)
    var rh = Math.floor((n % 86400) / 3600)
    return rh ? (d + "d " + rh + "h") : (d + "d")
  }

  function pollAge() {
    var iso = root.snap && root.snap.fetched_at
    if (!iso) return "never"
    var t = Date.parse(iso)
    if (!isFinite(t)) return String(iso)
    var sec = Math.max(0, Math.floor((Date.now() - t) / 1000))
    return root.formatDuration(sec) + " ago"
  }

  function providerRank(row) {
    var s = row && row.status
    if (s === "healthy") return 2
    if (s === "rate_limited") return 1
    return 0
  }

  function providerStatusLabel(row) {
    var s = row && row.status
    if (s === "healthy") return "healthy"
    if (s === "rate_limited") return "cooling"
    return "down"
  }

  function providerStatusColor(row) {
    var s = row && row.status
    if (s === "healthy") return Color.foreground
    if (s === "rate_limited") return Color.accent
    return Color.urgent
  }

  function chatRank(row) {
    var id = row && row.id
    if (id === "auto") return 0
    if (id === "fusion") return 1
    if (row && row.available) return 2
    return 3
  }

  function rebuildLists() {
    var plist = (root.snap && root.snap.providers) ? root.snap.providers.slice() : []
    plist.sort(function(a, b) {
      var ra = root.providerRank(a)
      var rb = root.providerRank(b)
      if (ra !== rb) return ra - rb
      return String((a && a.name) || (a && a.platform) || "").localeCompare(String((b && b.name) || (b && b.platform) || ""))
    })
    root.sortedProviders = plist

    var models = (root.chatSnap && root.chatSnap.models) ? root.chatSnap.models.slice() : []
    var q = String(root.chatQuery || "").toLowerCase()
    if (q.length) {
      models = models.filter(function(m) {
        var id = String((m && m.id) || "").toLowerCase()
        var name = String((m && m.name) || "").toLowerCase()
        return id.indexOf(q) >= 0 || name.indexOf(q) >= 0
      })
    }
    models.sort(function(a, b) {
      var ra = root.chatRank(a)
      var rb = root.chatRank(b)
      if (ra !== rb) return ra - rb
      return String((a && a.id) || "").localeCompare(String((b && b.id) || ""))
    })
    root.filteredChatModels = models
  }

  function selectTab(index) {
    if (index < 0 || index > 5) return
    root.tabIndex = index
    if (index !== 2 && chatFilter.activeFocus)
      Qt.callLater(function() { if (keyCatcher) keyCatcher.forceActiveFocus() })
  }

  function focusChatFilter() {
    if (root.tabIndex !== 2) return
    chatFilter.forceActiveFocus()
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Component.onCompleted: {
    root.rebuildLists()
    refresh()
  }
  onSnapChanged: root.rebuildLists()
  onChatQueryChanged: root.rebuildLists()
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

  IpcHandler {
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): void { root.refresh() }
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
    contentWidth: panel.fittedContentWidth(Style.space(620))
    contentHeight: panel.fittedContentHeight(column.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      blocked: chatFilter.activeFocus
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) {
        if (t === "r" || t === "R") root.refresh()
        else if (t === "/") root.focusChatFilter()
        else if (t === "1") root.selectTab(0)
        else if (t === "2") root.selectTab(1)
        else if (t === "3") root.selectTab(2)
        else if (t === "4") root.selectTab(3)
        else if (t === "5") root.selectTab(4)
        else if (t === "6") root.selectTab(5)
      }

      Column {
        id: column
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: Style.space(14)

        Row {
          id: tabRow
          spacing: Style.space(6)

          Repeater {
            model: root.tabNames
            Rectangle {
              required property int index
              required property var modelData
              implicitWidth: tabLabel.implicitWidth + Style.space(16)
              implicitHeight: tabLabel.implicitHeight + Style.space(8)
              radius: Style.cornerRadius
              color: root.tabIndex === index ? Color.accent : (tabMouse.containsMouse ? Style.hoverFillFor(Color.foreground, Color.accent) : "transparent")

              Text {
                id: tabLabel
                anchors.centerIn: parent
                text: modelData
                textFormat: Text.PlainText
                color: root.tabIndex === index ? Color.background : Color.muted
                font.family: Style.font.family
                font.pixelSize: Style.font.body
                font.bold: root.tabIndex === index
              }

              MouseArea {
                id: tabMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.selectTab(index)
              }
            }
          }
        }

        Flickable {
          id: bodyScroll
          width: parent.width
          implicitHeight: Math.min(bodyColumn.implicitHeight, Style.space(420))
          height: implicitHeight
          contentWidth: width
          contentHeight: bodyColumn.implicitHeight
          clip: true
          boundsBehavior: Flickable.StopAtBounds
          interactive: contentHeight > height

          Column {
            id: bodyColumn
            width: bodyScroll.width
            spacing: Style.space(12)

            // ---- Overview ----
            Column {
              width: parent.width
              spacing: Style.space(10)
              visible: root.tabIndex === 0

              Text {
                text: root.statusLabel
                textFormat: Text.PlainText
                color: root.statusColor
                font.family: Style.font.family
                font.pixelSize: Style.font.heading
                font.bold: true
              }

              Text {
                width: parent.width
                text: "version " + (root.gateway.version ? String(root.gateway.version) : "—")
                      + " · up " + root.formatDuration(root.gateway.uptime_s)
                      + " · polled " + root.pollAge()
                      + (root.snap && root.snap.stale ? " · stale" : "")
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: Color.muted
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
              }

              Grid {
                width: parent.width
                columns: 2
                columnSpacing: Style.space(12)
                rowSpacing: Style.space(8)

                Column {
                  spacing: Style.space(2)
                  Text { text: "Upstreams"; textFormat: Text.PlainText; color: Color.muted; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                  Text { text: root.pillCount; textFormat: Text.PlainText; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.title; font.bold: true }
                }
                Column {
                  spacing: Style.space(2)
                  Text { text: "Chat"; textFormat: Text.PlainText; color: Color.muted; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                  Text { text: String(root.chatSnap.available || 0) + "/" + String(root.chatSnap.total || 0); textFormat: Text.PlainText; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.title; font.bold: true }
                }
                Column {
                  spacing: Style.space(2)
                  Text { text: "Fusion"; textFormat: Text.PlainText; color: Color.muted; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                  Text { text: root.fusionSnap.available ? "available" : "unavailable"; textFormat: Text.PlainText; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.title; font.bold: true }
                }
                Column {
                  spacing: Style.space(2)
                  Text { text: "Quota"; textFormat: Text.PlainText; color: Color.muted; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                  Text { text: root.quotaPools.length ? (String(root.quotaPools.length) + " pools") : "none"; textFormat: Text.PlainText; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.title; font.bold: true }
                }
              }

              Text {
                width: parent.width
                visible: !root.gatewayLive
                text: "No process on 127.0.0.1:3001"
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: Color.urgent
                font.family: Style.font.family
                font.pixelSize: Style.font.body
              }

              Text {
                width: parent.width
                visible: root.missingUnifiedKey
                text: "Set FREELLMAPI_UNIFIED_KEY in ~/.env (mode 0600)."
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: Color.accent
                font.family: Style.font.family
                font.pixelSize: Style.font.body
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

            // ---- Providers ----
            Column {
              width: parent.width
              spacing: Style.space(8)
              visible: root.tabIndex === 1

              Text {
                width: parent.width
                visible: root.sortedProviders.length === 0
                text: "No enabled upstreams."
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: Color.muted
                font.family: Style.font.family
                font.pixelSize: Style.font.body
              }

              Repeater {
                model: root.sortedProviders
                Column {
                  required property var modelData
                  width: bodyColumn.width
                  spacing: Style.space(4)

                  Text {
                    width: parent.width
                    text: String((modelData && modelData.name) || (modelData && modelData.platform) || "unknown")
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                    color: Color.foreground
                    font.family: Style.font.family
                    font.pixelSize: Style.font.body
                    font.bold: true
                  }

                  Flow {
                    width: parent.width
                    spacing: Style.space(6)

                    Rectangle {
                      implicitWidth: statusChipLabel.implicitWidth + Style.space(10)
                      implicitHeight: statusChipLabel.implicitHeight + Style.space(4)
                      radius: Style.cornerRadius
                      color: Style.normalFillFor(Color.foreground, Color.accent)

                      Text {
                        id: statusChipLabel
                        anchors.centerIn: parent
                        text: root.providerStatusLabel(modelData)
                        textFormat: Text.PlainText
                        color: root.providerStatusColor(modelData)
                        font.family: Style.font.family
                        font.pixelSize: Style.font.caption
                      }
                    }

                    Text {
                      text: "keys " + String((modelData && modelData.keys) != null ? modelData.keys : "—")
                      textFormat: Text.PlainText
                      color: Color.muted
                      font.family: Style.font.family
                      font.pixelSize: Style.font.caption
                    }

                    Text {
                      visible: !!(modelData && modelData.status === "rate_limited" && modelData.resume_at)
                      text: "resume " + String(modelData && modelData.resume_at ? modelData.resume_at : "")
                      textFormat: Text.PlainText
                      color: Color.accent
                      font.family: Style.font.family
                      font.pixelSize: Style.font.caption
                    }

                    Text {
                      visible: modelData && modelData.requests_remaining_pct != null
                      text: String(modelData && modelData.requests_remaining_pct != null ? modelData.requests_remaining_pct : "") + "% remaining"
                      textFormat: Text.PlainText
                      color: Color.muted
                      font.family: Style.font.family
                      font.pixelSize: Style.font.caption
                    }
                  }

                  Text {
                    width: parent.width
                    visible: !!(modelData && modelData.last_error)
                    text: modelData && modelData.last_error ? String(modelData.last_error) : ""
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                    color: Color.muted
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                  }
                }
              }
            }

            // ---- Chat ----
            Column {
              width: parent.width
              spacing: Style.space(8)
              visible: root.tabIndex === 2

              TextField {
                id: chatFilter
                width: parent.width
                placeholderText: "Filter models"
                foreground: Color.foreground
                onTextChanged: if (root.chatQuery !== text) root.chatQuery = text
                Keys.onPressed: function(event) {
                  if (event.key === Qt.Key_Escape) {
                    root.close()
                    event.accepted = true
                  }
                }
              }

              Text {
                width: parent.width
                text: String(root.chatSnap.available || 0) + " available · "
                      + String(root.chatSnap.unavailable || 0) + " unavailable · "
                      + String(root.chatSnap.total || 0) + " total"
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: Color.muted
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
              }

              Text {
                width: parent.width
                visible: root.filteredChatModels.length === 0
                text: (root.chatSnap.total || 0) > 0
                      ? "No models match the filter."
                      : "Catalog empty."
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: Color.muted
                font.family: Style.font.family
                font.pixelSize: Style.font.body
              }

              Repeater {
                model: root.filteredChatModels
                Column {
                  required property var modelData
                  width: bodyColumn.width
                  spacing: Style.space(2)

                  Text {
                    width: parent.width
                    text: String((modelData && modelData.id) || "")
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                    color: (modelData && modelData.available) ? Color.foreground : Color.muted
                    font.family: Style.font.family
                    font.pixelSize: Style.font.body
                    font.bold: modelData && (modelData.id === "auto" || modelData.id === "fusion")

                    HoverHandler { id: chatHover }
                    ToolTip.visible: chatHover.hovered && !!(modelData && modelData.unavailable_reason)
                    ToolTip.text: modelData && modelData.unavailable_reason ? String(modelData.unavailable_reason) : ""
                    ToolTip.delay: 250
                  }

                  Text {
                    width: parent.width
                    visible: !!(modelData && modelData.name)
                    text: modelData && modelData.name ? String(modelData.name) : ""
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                    color: Color.muted
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                  }
                }
              }
            }

            // ---- Fusion ----
            Column {
              width: parent.width
              spacing: Style.space(8)
              visible: root.tabIndex === 3

              Text {
                width: parent.width
                text: root.fusionSnap.name ? String(root.fusionSnap.name) : "fusion"
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: Color.foreground
                font.family: Style.font.family
                font.pixelSize: Style.font.body
                font.bold: true
              }

              Text {
                text: root.fusionSnap.available ? "available" : "unavailable"
                textFormat: Text.PlainText
                color: root.fusionSnap.available ? Color.foreground : Color.urgent
                font.family: Style.font.family
                font.pixelSize: Style.font.body
              }

              Text {
                width: parent.width
                visible: !!(root.fusionSnap.unavailable_reason)
                text: root.fusionSnap.unavailable_reason ? String(root.fusionSnap.unavailable_reason) : ""
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: Color.muted
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
              }

              Text {
                width: parent.width
                text: "Saved panel k/judge is dashboard-session and out of scope."
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: Color.muted
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
              }
            }

            // ---- Media ----
            Column {
              width: parent.width
              spacing: Style.space(8)
              visible: root.tabIndex === 4

              Text {
                width: parent.width
                text: "counts unknown"
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: Color.muted
                font.family: Style.font.family
                font.pixelSize: Style.font.body
              }

              Flow {
                width: parent.width
                spacing: Style.space(8)

                Repeater {
                  model: root.mediaInferred
                  Rectangle {
                    required property var modelData
                    implicitWidth: mediaChipCol.implicitWidth + Style.space(12)
                    implicitHeight: mediaChipCol.implicitHeight + Style.space(8)
                    radius: Style.cornerRadius
                    color: Style.normalFillFor(Color.foreground, Color.accent)

                    Column {
                      id: mediaChipCol
                      anchors.centerIn: parent
                      spacing: Style.space(2)

                      Text {
                        text: String((modelData && modelData.modality) || "")
                        textFormat: Text.PlainText
                        color: Color.foreground
                        font.family: Style.font.family
                        font.pixelSize: Style.font.body
                        font.bold: true
                      }

                      Text {
                        text: {
                          var from = modelData && modelData.from
                          if (modelData && modelData.modality === "embeddings") return "not in /v1/models"
                          if (!from || !from.length) return "counts unknown"
                          return from.join(", ")
                        }
                        textFormat: Text.PlainText
                        color: Color.muted
                        font.family: Style.font.family
                        font.pixelSize: Style.font.caption
                      }
                    }
                  }
                }
              }
            }

            // ---- Quota ----
            Column {
              width: parent.width
              spacing: Style.space(8)
              visible: root.tabIndex === 5

              Text {
                width: parent.width
                visible: root.quotaPools.length === 0
                text: "No numeric quotas reported yet"
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: Color.muted
                font.family: Style.font.family
                font.pixelSize: Style.font.body
              }

              Text {
                width: parent.width
                visible: root.quotaPools.length > 0 && !!(root.quotaSnap.generated_at)
                text: "generated " + String(root.quotaSnap.generated_at || "")
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: Color.muted
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
              }

              Repeater {
                model: root.quotaPools
                Column {
                  required property var modelData
                  width: bodyColumn.width
                  spacing: Style.space(2)

                  Text {
                    width: parent.width
                    text: String((modelData && (modelData.pool || modelData.platform)) || "pool")
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                    color: Color.foreground
                    font.family: Style.font.family
                    font.pixelSize: Style.font.body
                    font.bold: true
                  }

                  Text {
                    width: parent.width
                    text: {
                      var used = modelData && modelData.used
                      var remaining = modelData && modelData.remaining
                      var limit = modelData && modelData.limit
                      var pct = modelData && modelData.remaining_pct
                      var parts = []
                      if (remaining != null && limit != null) parts.push(String(remaining) + "/" + String(limit) + " remaining")
                      else if (remaining != null) parts.push(String(remaining) + " remaining")
                      if (pct != null) parts.push(String(pct) + "%")
                      if (modelData && modelData.reset_at) parts.push("reset " + String(modelData.reset_at))
                      if (modelData && modelData.low_balance) parts.push("low")
                      return parts.join(" · ")
                    }
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                    color: (modelData && modelData.low_balance) ? Color.accent : Color.muted
                    font.family: Style.font.family
                    font.pixelSize: Style.font.caption
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}

/*
 * WEL Video — plugin de fondo de Plasma para Wallpaper Engine Linux.
 *
 * Reproduce vídeos (MP4/WebM, vía QtMultimedia), GIF (AnimatedImage),
 * páginas web (WebEngineView) e imágenes dentro del escritorio de Plasma,
 * detrás de los iconos y ventanas.
 *
 * Configuración (grupo [Wallpaper][wel.video][General]):
 *   source : URL del archivo (file:///...)
 *   fill   : crop | fit | stretch
 *
 * Nota: la configuración puede llegar DESPUÉS de crear el componente
 * (carrera de recarga de Plasma); por eso `source` no es un binding directo:
 * se lee en onCompleted, en onConfigurationChanged y con un temporizador de
 * respaldo que se auto-repara hasta que la fuente está cargada.
 */
import QtQuick
import QtMultimedia
import QtWebEngine
import org.kde.plasma.plasmoid

WallpaperItem {
    id: root

    property url source: ""
    property string fill: "crop"

    readonly property bool isGif: String(root.source).toLowerCase().endsWith(".gif")
    readonly property bool isWeb: {
        var s = String(root.source).toLowerCase();
        return s.endsWith(".html") || s.endsWith(".htm");
    }
    readonly property bool isVideo: {
        var s = String(root.source).toLowerCase();
        return s.endsWith(".mp4") || s.endsWith(".webm") || s.endsWith(".mkv") ||
               s.endsWith(".mov") || s.endsWith(".avi") || s.endsWith(".ogv") ||
               s.endsWith(".m4v");
    }

    function refreshSource() {
        var s = root.configuration.source;
        if (s !== undefined && String(s) !== "") {
            root.source = s;
        }
        var f = root.configuration.fill;
        if (f !== undefined && String(f) !== "") {
            root.fill = String(f);
        }
    }

    Component.onCompleted: {
        refreshSource();
    }

    onConfigurationChanged: {
        refreshSource();
    }

    // auto-reparación: mientras no haya fuente, reintentar cada 600 ms
    Timer {
        interval: 600
        running: true
        repeat: true
        onTriggered: {
            if (!root.source) {
                refreshSource();
            }
        }
    }

    MediaPlayer {
        id: player
        autoPlay: true
        loops: MediaPlayer.Infinite
        source: (!root.isGif && !root.isWeb && root.source != "") ? root.source : ""
        videoOutput: videoOutput
        audioOutput: AudioOutput {
            muted: true
        }
    }

    VideoOutput {
        id: videoOutput
        anchors.fill: parent
        fillMode: root.fill === "stretch" ? VideoOutput.Stretch :
                  root.fill === "fit" ? VideoOutput.PreserveAspectFit :
                  VideoOutput.PreserveAspectCrop
    }

    AnimatedImage {
        id: gifImage
        anchors.fill: parent
        source: root.isGif ? root.source : ""
        fillMode: root.fill === "stretch" ? Image.Stretch :
                  root.fill === "fit" ? Image.PreserveAspectFit :
                  Image.PreserveAspectCrop
        visible: root.isGif && root.source != ""
        playing: visible
        cache: false
    }

    WebEngineView {
        id: webView
        anchors.fill: parent
        url: root.isWeb ? root.source : ""
        visible: root.isWeb && root.source != ""
        audioMuted: true
    }

    Image {
        id: fallback
        anchors.fill: parent
        source: (!root.isGif && !root.isWeb && !root.isVideo) ? root.source : ""
        fillMode: root.fill === "stretch" ? Image.Stretch :
                  root.fill === "fit" ? Image.PreserveAspectFit :
                  Image.PreserveAspectCrop
        visible: root.source != "" && !root.isGif && !root.isWeb && !root.isVideo
    }
}

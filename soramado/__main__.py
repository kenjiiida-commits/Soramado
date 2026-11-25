"""起動: python3 -m soramado"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication, QMessageBox


def main() -> int:
    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setDepthBufferSize(24)
    fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(fmt)
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

    app = QApplication(sys.argv)
    app.setApplicationName("Soramado")
    app.setApplicationDisplayName("そらみ窓")
    app.setDesktopFileName("soramado")

    from .app import make_window
    try:
        w = make_window()
        w.show()
    except Exception as exc:  # noqa: BLE001
        QMessageBox.critical(None, "そらみ窓", f"起動できませんでした。\n\n{exc}")
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

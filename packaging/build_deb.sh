#!/bin/bash
# DEB パッケージを作る: bash packaging/build_deb.sh
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(python3 -c "import re;print(re.search(r'__version__ = \"(.+?)\"', open('soramado/__init__.py').read()).group(1))")
PKG=soramado
BUILD=$(mktemp -d)
ROOT="$BUILD/${PKG}_${VERSION}_all"

mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/bin" "$ROOT/usr/lib/$PKG" \
         "$ROOT/usr/share/applications" "$ROOT/usr/share/icons/hicolor/scalable/apps" \
         "$ROOT/usr/share/doc/$PKG"

cp -r soramado "$ROOT/usr/lib/$PKG/"
find "$ROOT/usr/lib/$PKG" -name "__pycache__" -type d -prune -exec rm -r {} +
cp packaging/soramado.desktop "$ROOT/usr/share/applications/"
cp soramado/soramado.svg "$ROOT/usr/share/icons/hicolor/scalable/apps/"
cp LICENSE README.md "$ROOT/usr/share/doc/$PKG/"

cat > "$ROOT/usr/bin/soramado" <<'SH'
#!/bin/sh
export PYTHONPATH="/usr/lib/soramado${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m soramado "$@"
SH
chmod 755 "$ROOT/usr/bin/soramado"

cat > "$ROOT/DEBIAN/control" <<CTRL
Package: $PKG
Version: $VERSION
Section: science
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-numpy, python3-pyside6.qtcore, python3-pyside6.qtgui, python3-pyside6.qtwidgets, python3-pyside6.qtopengl, python3-pyside6.qtopenglwidgets
Maintainer: Kenji Iida <kenjiiida-commits@users.noreply.github.com>
Homepage: https://github.com/kenjiiida-commits/Soramado
Description: Space simulator for Ubuntu (Soramado)
 そらみ窓は、太陽系を3Dで自由に旅できる宇宙シミュレーターです。
 惑星は実際の日付どおりの位置で公転し、時間の早送りや逆再生もできます。
CTRL

cat > "$ROOT/DEBIAN/postinst" <<'SH'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q /usr/share/icons/hicolor || true
SH
chmod 755 "$ROOT/DEBIAN/postinst"

mkdir -p dist
dpkg-deb --root-owner-group --build "$ROOT" "dist/${PKG}_${VERSION}_all.deb"
rm -r "$BUILD"
echo "できました: dist/${PKG}_${VERSION}_all.deb"

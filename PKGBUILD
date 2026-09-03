# Maintainer: TheRealGhost007
pkgname=resmon
pkgver=0.1.0
pkgrel=1
pkgdesc="A clean system resource monitor: full app + desktop overlay widget, built for Hyprland/Omarchy"
arch=('any')
url="https://github.com/TheRealGhost007/resmon"
license=('MIT')
depends=('python' 'python-gobject' 'python-psutil' 'gtk4' 'libadwaita')
optdepends=(
    'gtk4-layer-shell: dock the overlay widget to a screen corner (falls back to a floating window without it)'
    'hyprland: the Processes tab Apps/System split and the Omarchy bar widget'
)
options=('!debug')

# Builds directly from this checkout rather than a downloaded/verified
# tarball — this PKGBUILD is meant for local `makepkg -si` use, not AUR
# submission, so an empty source array (nothing to fetch) is intentional.
# NOTE: if this ever moves to a real downloaded source (for AUR), makepkg
# extracts into ./src, which collides with this project's own src/ directory
# — that'll need a subdir or a renamed source layout at that point.
source=()
sha256sums=()

package() {
    cd "$startdir"

    site_packages="usr/lib/python$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')/site-packages"
    install -d "$pkgdir/$site_packages"
    cp -r src/resmon "$pkgdir/$site_packages/"
    find "$pkgdir/$site_packages/resmon" -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

    install -Dm755 packaging/resmon "$pkgdir/usr/bin/resmon"

    install -Dm644 data/icons/dev.local.Resmon.svg \
        "$pkgdir/usr/share/icons/hicolor/scalable/apps/dev.local.Resmon.svg"

    install -Dm644 packaging/dev.local.Resmon.desktop \
        "$pkgdir/usr/share/applications/dev.local.Resmon.desktop"
    install -Dm644 packaging/dev.local.Resmon.Overlay.desktop \
        "$pkgdir/usr/share/applications/dev.local.Resmon.Overlay.desktop"

    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}

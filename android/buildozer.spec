[app]
title = AliJ-Ichimoku
package.name = alijichimoku
package.domain = org.alij
source.dir = .
source.include_exts = py,png,jpg,ttf
source.exclude_dirs = __pycache__,.git,bin,.buildozer
version = 0.1.0
requirements = python3,kivy,charset-normalizer==3.3.2
orientation = portrait
fullscreen = 0
icon.filename = branding/AliJ.png
android.api = 35
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1

[app]
title = UCDM Legends
package.name = ucdmlegends
package.domain = org.ucdm
source.dir = .
source.include_exts = py,png,json,ttf,otf,ogg,wav,mp3,mcmeta,txt
source.include_patterns = assets/*,version.json
source.exclude_dirs = dist,build,docs,installer,tests,tools,.github,.git,__pycache__,bin,.buildozer
# (a versão é ajustada pelo CI a partir de version.json)
version = 0.0.0
requirements = python3,pygame
orientation = landscape
fullscreen = 1
icon.filename = %(source.dir)s/assets/sprites/ui/icon.png
android.permissions = INTERNET
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True
android.logcat_filters = *:S python:D

[buildozer]
log_level = 2
warn_on_root = 1

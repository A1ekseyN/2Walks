[app]
title = 2Walks
package.name = walks2
package.domain = org.test
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.0.5b
requirements = python3,kivy,colorama,gspread,oauth2client,json,csv
orientation = portrait

[buildozer]
log_level = 2
warn_on_root = 1

[android]
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.archs = arm64-v8a,armeabi-v7a
android.allow_backup = True
android.api = 31
android.minapi = 21
android.python_version = 3

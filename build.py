from conan.packager import ConanMultiPackager
from conans.tools import os_info
import platform

if __name__ == "__main__":
    builder = ConanMultiPackager(username="bilke", channel="testing")
    builder.add_common_builds()
    builder.add({}, {"Qt:xmlpatterns": "True"})
    filtered_builds = []
    for settings, options in builder.builds:
        if os_info.is_macos and settings["build_type"] != "Debug":
            filtered_builds.append([settings, options])
    builder.builds = filtered_builds
    builder.run()

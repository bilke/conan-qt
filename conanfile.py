import os
from distutils.spawn import find_executable
from conans import AutoToolsBuildEnvironment, ConanFile, tools, VisualStudioBuildEnvironment
from conans.tools import cpu_count, os_info, SystemPackageTool
from distutils.util import strtobool

def which(program):
    """
    Locate a command.
    """
    def is_exe(fpath):
        """
        Check if a path is executable.
        """
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, _ = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

class QtConan(ConanFile):
    """ Qt Conan package """

    name = "Qt"
    version = "5.9.2"
    description = "Conan.io package for Qt library."
    source_dir = "qt5"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "opengl": ["desktop", "dynamic"],
        "canvas3d": [True, False],
        "gamepad": [True, False],
        "graphicaleffects": [True, False],
        "imageformats": [True, False],
        "location": [True, False],
        "serialport": [True, False],
        "svg": [True, False],
        "tools": [True, False],
        "webengine": [True, False],
        "websockets": [True, False],
        "xmlpatterns": [True, False],
        "x11extras": [True, False],
        "openssl": ["no", "yes", "linked"]
    }
    default_options = ("shared=True", "opengl=desktop", "canvas3d=False", "gamepad=False",
        "graphicaleffects=False", "imageformats=False", "location=False",
        "serialport=False", "svg=False", "tools=False", "webengine=False",
        "websockets=False", "xmlpatterns=False", "x11extras=True", "openssl=no")
    url = "http://github.com/osechet/conan-qt"
    license = "http://doc.qt.io/qt-5/lgpl.html"
    short_paths = True

    def system_requirements(self):
        pack_names = None
        if os_info.linux_distro == "ubuntu":
            pack_names = ["libgl1-mesa-dev", "libxcb1", "libxcb1-dev",
                          "libx11-xcb1", "libx11-xcb-dev", "libxcb-keysyms1",
                          "libxcb-keysyms1-dev", "libxcb-image0", "libxcb-image0-dev",
                          "libxcb-shm0", "libxcb-shm0-dev", "libxcb-icccm4",
                          "libxcb-icccm4-dev", "libxcb-sync1", "libxcb-sync-dev",
                          "libxcb-xfixes0-dev", "libxrender-dev", "libxcb-shape0-dev",
                          "libxcb-randr0-dev", "libxcb-render-util0", "libxcb-render-util0-dev",
                          "libxcb-glx0-dev", "libxcb-xinerama0", "libxcb-xinerama0-dev"]

            if self.settings.arch == "x86":
                full_pack_names = []
                for pack_name in pack_names:
                    full_pack_names += [pack_name + ":i386"]
                pack_names = full_pack_names

        if os_info.linux_distro == "debian":
            pack_names = ["libx11-dev", "libxext-dev", "libglu-dev"]

        if pack_names:
            installer = SystemPackageTool()
            installer.update() # Update the package database
            installer.install(" ".join(pack_names)) # Install the package

    def config_options(self):
        if not os_info.is_windows:
            del self.options.opengl
            del self.options.openssl
        if not os_info.is_linux:
            del self.options.x11extras

    def requirements(self):
        if os_info.is_windows:
            if self.options.openssl == "yes":
                self.requires("OpenSSL/1.0.2l@conan/stable", dev=True)
            elif self.options.openssl == "linked":
                self.requires("OpenSSL/1.0.2l@conan/stable")

    def source(self):
        submodules = ["qtbase"]

        for key, value in self.options.items():
            if key in ["shared"]:
                continue
            if (value == "False" or value == "True") and strtobool(value) == True:
                submodules.append('qt' + key)

        major = ".".join(self.version.split(".")[:2])
        self.run("git clone http://code.qt.io/qt/qt5.git")
        self.run("cd %s && git checkout %s" % (self.source_dir, major))
        self.run("cd %s && perl init-repository --no-update --module-subset=%s"
                 % (self.source_dir, ",".join(submodules)))
        self.run("cd %s && git checkout v%s && git submodule update"
                 % (self.source_dir, self.version))

        if not os_info.is_windows:
            self.run("chmod +x ./%s/configure" % self.source_dir)
        else:
            # Fix issue with sh.exe and cmake on Windows
            # This solution isn't good at all but I cannot find anything else
            sh_path = which("sh.exe")
            if sh_path:
                fpath, _ = os.path.split(sh_path)
                self.run("ren \"%s\" _sh.exe" % os.path.join(fpath, "sh.exe"))

    def build(self):
        """ Define your project building. You decide the way of building it
            to reuse it later in any other project.
        """
        args = ["-opensource", "-confirm-license", "-nomake examples", "-nomake tests",
                "-qt-zlib", "-prefix %s" % self.package_folder]
        if not self.options.shared:
            args.insert(0, "-static")
        if self.settings.build_type == "Debug":
            args.append("-debug")
        else:
            args.append("-release")

        if os_info.is_windows:
            if self.settings.compiler == "Visual Studio":
                self._build_msvc(args)
            else:
                self._build_mingw(args)
        else:
            self._build_unix(args)

    def _build_msvc(self, args):
        build_command = find_executable("jom.exe")
        if build_command:
            build_args = ["-j", str(cpu_count())]
        else:
            build_command = "nmake.exe"
            build_args = []
        self.output.info("Using '%s %s' to build" % (build_command, " ".join(build_args)))

        env = {}
        env.update({'PATH': ['%s/qtbase/bin' % self.source_folder,
                             '%s/gnuwin32/bin' % self.source_folder,
                             '%s/qtrepotools/bin' % self.source_folder]})
        # it seems not enough to set the vcvars for older versions
        if self.settings.compiler == "Visual Studio":
            if self.settings.compiler.version == "14":
                env.update({'QMAKESPEC': 'win32-msvc2015'})
                args += ["-platform win32-msvc2015"]
            if self.settings.compiler.version == "12":
                env.update({'QMAKESPEC': 'win32-msvc2013'})
                args += ["-platform win32-msvc2013"]
            if self.settings.compiler.version == "11":
                env.update({'QMAKESPEC': 'win32-msvc2012'})
                args += ["-platform win32-msvc2012"]
            if self.settings.compiler.version == "10":
                env.update({'QMAKESPEC': 'win32-msvc2010'})
                args += ["-platform win32-msvc2010"]

        env_build = VisualStudioBuildEnvironment(self)
        env.update(env_build.vars)
        vcvars = tools.vcvars_command(self.settings)

        args += ["-opengl %s" % self.options.opengl]
        if self.options.openssl == "no":
            args += ["-no-openssl"]
        elif self.options.openssl == "yes":
            args += ["-openssl"]
        else:
            args += ["-openssl-linked"]

        self.run("%s && cd %s && set" % (vcvars, self.source_dir))
        self.run("%s && cd %s && configure %s"
                 % (vcvars, self.source_dir, " ".join(args)))
        self.run("%s && cd %s && %s %s"
                 % (vcvars, self.source_dir, build_command, " ".join(build_args)))
        self.run("%s && cd %s && %s install" % (vcvars, self.source_dir, build_command))

    def _build_mingw(self, args):
        env_build = AutoToolsBuildEnvironment(self)
        env = {'PATH': ['%s/bin' % self.source_folder,
                        '%s/qtbase/bin' % self.source_folder,
                        '%s/gnuwin32/bin' % self.source_folder,
                        '%s/qtrepotools/bin' % self.source_folder],
               'QMAKESPEC': 'win32-g++'}
        env.update(env_build.vars)
        with tools.environment_append(env):
            # Workaround for configure using clang first if in the path
            new_path = []
            for item in os.environ['PATH'].split(';'):
                if item != 'C:\\Program Files\\LLVM\\bin':
                    new_path.append(item)
            os.environ['PATH'] = ';'.join(new_path)
            # end workaround
            args += ["-developer-build",
                     "-opengl %s" % self.options.opengl,
                     "-platform win32-g++"]

            self.output.info("Using '%s' threads" % str(cpu_count()))
            self.run("cd %s && configure.bat %s"
                     % (self.source_dir, " ".join(args)))
            self.run("cd %s && mingw32-make -j %s"
                     % (self.source_dir, str(cpu_count())))
            self.run("cd %s && mingw32-make install" % (self.source_dir))

    def _build_unix(self, args):
        if os_info.is_linux:
            args += ["-silent", "-xcb"]
            if self.settings.arch == "x86":
                args += ["-platform linux-g++-32"]
        else:
            args += ["-silent", "-no-framework"]
            if self.settings.arch == "x86":
                args += ["-platform macx-clang-32"]

        self.output.info("Using '%s' threads" % str(cpu_count()))
        self.run("cd %s && ./configure %s" % (self.source_dir, " ".join(args)))
        self.run("cd %s && make -j %s" % (self.source_dir, str(cpu_count())))
        self.run("cd %s && make install" % (self.source_dir))

    def package_info(self):
        libs = ['Concurrent', 'Core', 'DBus',
                'Gui', 'Network', 'OpenGL',
                'Sql', 'Test', 'Widgets', 'Xml']
        if 'x11extras' in self.options and self.options.x11extras == True:
            libs += ['X11Extras']

        self.cpp_info.libs = []
        self.cpp_info.includedirs = ["include"]
        for lib in libs:
            if os_info.is_windows and self.settings.build_type == "Debug":
                suffix = "d"
            elif os_info.is_macos and self.settings.build_type == "Debug":
                suffix = "_debug"
            else:
                suffix = ""
            self.cpp_info.libs += ["Qt5%s%s" % (lib, suffix)]
            self.cpp_info.includedirs += ["include/Qt%s" % lib]

        if os_info.is_windows:
            # Some missing shared libs inside QML and others, but for the test it works
            self.env_info.path.append(os.path.join(self.package_folder, "bin"))

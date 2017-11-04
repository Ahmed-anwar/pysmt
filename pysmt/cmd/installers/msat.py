# Copyright 2014 Andrea Micheli and Marco Gario
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import glob

from pysmt.cmd.installers.base import SolverInstaller

# A patched version of setup.py for the Windows platform
WIN_PATCHED_SETUP_PY = """#!/usr/bin/env python
import os, sys
from setuptools import setup, Extension

MATHSAT_DIR = '..'

libraries = ['mathsat', 'psapi', 'mpir']

setup(name='mathsat', version='0.1',
      description='MathSAT API',
      ext_modules=[Extension('_mathsat', ['mathsat_python_wrap.c'],
                             define_macros=[('SWIG','1')],
                             include_dirs=[os.path.join(MATHSAT_DIR,
                                                        'include')],
                             library_dirs=[os.path.join(MATHSAT_DIR, 'lib')],
                             extra_compile_args=[],
                             extra_link_args=[],
                             libraries=libraries,
                             language='c++',
                             )]
      )
"""


class MSatInstaller(SolverInstaller):

    SOLVER = "msat"

    def __init__(self, install_dir, bindings_dir, solver_version,
                 mirror_link=None):

        # Getting the right archive name
        os_name = self.os_name
        arch = self.architecture
        ext = "tar.gz"
        if os_name == "windows":
            ext = "zip"
            arch = "msvc"
            if self.architecture == "x86_64":
                os_name = "win64"
            else:
                os_name = "win32"
        elif os_name == "darwin":
            os_name = "darwin-libcxx"

        archive_name = "mathsat-%s-%s-%s.%s" % (solver_version, os_name,
                                                arch, ext)

        native_link = "http://mathsat.fbk.eu/download.php?file={archive_name}"

        SolverInstaller.__init__(self, install_dir=install_dir,
                                 bindings_dir=bindings_dir,
                                 solver_version=solver_version,
                                 archive_name=archive_name,
                                 native_link = native_link,
                                 mirror_link=mirror_link)

        self.python_bindings_dir = os.path.join(self.extract_path, "python")


    def compile(self):
        # Patching the swig wrapper
        # This hardcoded patch fixes a problem in the msat wrapper
        # that can cause segfaults (especially under windows). An
        # array that is malloc'd is freed with a call to msat_free
        # instead of a plain free(). This issue has been fixed
        # upstream, and this patching can be removed when we will
        # upgrade the version of MathSAT to be greater (but not equal) to
        # 5.4.1.
        key = "if (arg2) msat_free(arg2);"
        subst = "if (arg2) free(arg2);"
        c_body = None
        with open(os.path.join(self.python_bindings_dir, "mathsat_python_wrap.c"), "r") as f:
            c_body = f.read()
        c_body = c_body.replace(key, subst)
        with open(os.path.join(self.python_bindings_dir, "mathsat_python_wrap.c"), "w") as f:
            f.write(c_body)

        if self.os_name == "windows":
            libdir = os.path.join(self.python_bindings_dir, "../lib")
            incdir = os.path.join(self.python_bindings_dir, "../include")
            gmp_h_url = "https://raw.githubusercontent.com/mikand/tamer-windows-deps/master/gmp/include/gmp.h"
            mpir_dll_url = "https://github.com/Legrandin/mpir-windows-builds/blob/master/mpir-2.6.0_VS2015_%s/mpir.dll?raw=true" % self.bits
            mpir_lib_url = "https://github.com/Legrandin/mpir-windows-builds/blob/master/mpir-2.6.0_VS2015_%s/mpir.lib?raw=true" % self.bits

            SolverInstaller.do_download(gmp_h_url, os.path.join(incdir, "gmp.h"))
            SolverInstaller.do_download(mpir_dll_url, os.path.join(libdir, "mpir.dll"))
            SolverInstaller.do_download(mpir_lib_url, os.path.join(libdir, "mpir.lib"))

            # Overwrite setup.py with the patched version
            with open(os.path.join(self.python_bindings_dir, "setup.py"), "w") as f:
                f.write(WIN_PATCHED_SETUP_PY)

        # Run setup.py to compile the bindings
        SolverInstaller.run_python("./setup.py build", self.python_bindings_dir)


    def move(self):
        pdir = self.python_bindings_dir
        bdir = os.path.join(pdir, "build")
        sodir = glob.glob(bdir + "/lib.*")[0]

        for f in os.listdir(sodir):
            if f.endswith(".so") or f.endswith(".pyd"):
                SolverInstaller.mv(os.path.join(sodir, f), self.bindings_dir)
        SolverInstaller.mv(os.path.join(pdir, "mathsat.py"), self.bindings_dir)

        # Under windows we also need the DLLs of mathsat and mpir in the PATH
        if self.os_name == "windows":
            libdir = os.path.join(self.python_bindings_dir, "../lib")
            SolverInstaller.mv(os.path.join(libdir, "mathsat.dll"), self.bindings_dir)
            SolverInstaller.mv(os.path.join(libdir, "mpir.dll"), self.bindings_dir)


    def get_installed_version(self):
        return self.get_installed_version_script(self.bindings_dir, "msat")

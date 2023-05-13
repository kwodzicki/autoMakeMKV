#!/usr/bin/env python
from distutils.util import convert_path
from setuptools import setup, find_packages

NAME  = "automakemkv"
DESC  = "Package for automagically ripping media with MakeMKV"
URL   = "https://github.com/kwodzicki/mediaID"
AUTH  = "Kyle R. Wodzicki"
EMAIL = "krwodzicki@gmail.com"

main_ns  = {}
ver_path = convert_path( "{}/version.py".format(NAME) )
with open(ver_path) as ver_file:
    exec(ver_file.read(), main_ns)

if __name__ == "__main__":
    setup(
        name                 = NAME,
        description          = DESC,
        url                  = URL,
        author               = AUTH,
        author_email         = EMAIL,
        version              = main_ns['__version__'],
        packages             = find_packages(),
        include_package_data = True,
        install_requires     = [ 'PyQt5', 'pyudev' ],
        scripts              = ['bin/autoMakeMKV', 'bin/autoMakeMKV_gui'],
        zip_safe             = False
    )

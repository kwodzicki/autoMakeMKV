#!/usr/bin/env python
from setuptools import setup, find_packages, convert_path

NAME = "automakemkv"
DESC = "Package for automagically ripping media with MakeMKV"

main_ns  = {}
ver_path = convert_path( "{}/version.py".format(NAME) )
with open(ver_path) as ver_file:
  exec(ver_file.read(), main_ns)

setup(
  name                 = NAME,
  description          = DESC,
  url                  = "https://github.com/kwodzicki/mediaID",
  author               = "Kyle R. Wodzicki",
  author_email         = "krwodzicki@gmail.com",
  version              = main_ns['__version__'],
  packages             = find_packages(),
  include_package_data = True,
  install_requires     = [ 'PyQt5', 'pyudev' ],
  scripts              = ['bin/autoMakeMKV'],
  zip_safe             = False
)

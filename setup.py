#!/usr/bin/env python3
"""
Python LEEM image module

"""

from setuptools import setup
from codecs import open
from os import path

current_path = path.abspath(path.dirname(__file__))
with open(path.join(current_path, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='LEEMImg',
    version='0.9.0',
    description='LEEM Image module to import and operate LEEM images',
    long_description=long_description,
    #url=TODO
    author='Jon-Olaf Krisponeit, Jan Höcker',
    author_email='Jon-Olaf Krisponeit <krisponeit@ifp.uni-bremen.de>,'+\
        'Jan Höcker <jhoecker@ifp.uni-bremen.de>',
    license='LGPLv3+',
    classifiers=[
        'Development Status :: 4',
        'Intended Audience :: Science',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)'
        'License :: OSI Approved :: LGPL License',
        'Progamming Language :: Python :: 3'
        ],
    keywords='LEEM Science Images',
    py_modules=['LEEMImg'],
    )

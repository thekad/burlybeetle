#!/usr/bin/env python

import os
import setuptools

import turtletoss


base = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(base, 'README.rst')) as f:
    readme = f.read()

setuptools.setup(
    name='turtletoss',
    author='Jorge Gallegos',
    author_email='kad@close.io',
    description=turtletoss.__desc__,
    url='https://github.com/thekad/turtletoss',
    long_description=readme,
    install_requires=[
        'Fabric==1.10.2',
    ],
    packages=setuptools.find_packages(),
    zip_safe=False,
    license='MIT',
    entry_points={
        'console_scripts': [
            'turtletoss=turtletoss.cli:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Database :: Database Engines/Servers',
    ],
)

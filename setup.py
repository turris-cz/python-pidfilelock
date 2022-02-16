#!/usr/bin/env python3
from setuptools import setup

setup(
    name="pidfilelock",
    version="0.1.0",
    description="The implementation of lock file with PID",
    url="https://gitlab.nic.cz/turris/python-pidfilelock",
    author="CZ.NIC, z. s. p. o.",
    author_email="packaging@turris.cz",
    license="GPL-3.0-or-later",
    python_requires=">=3.6",
    packages=["pidfilelock"],
)

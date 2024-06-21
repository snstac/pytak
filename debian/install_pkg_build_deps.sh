#!/bin/bash

echo "Installing Debian package build dependencies"

apt-get update -qq

apt-get install -y \
  python3 python3-dev python3-pip python3-venv python3-all \
  dh-python debhelper devscripts dput software-properties-common \
  python3-distutils python3-setuptools python3-wheel python3-stdeb

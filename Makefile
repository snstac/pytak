# Makefile from https://github.com/snstac/pytak
# PyTAK Makefile
#
# Copyright Sensors & Signals LLC https://www.snstac.com/
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

REPO_NAME ?= $(shell echo $(wildcard src/*/__init__.py) | awk -F'/' '{print $$2}')
SHELL := /bin/bash
.DEFAULT_GOAL := editable
# postinst = $(wildcard debian/*.postinst.sh)
# service = $(wildcard debian/*.service)

prepare:
	mkdir -p build/

develop:
	python3 setup.py develop

editable:
	python3 -m pip install -e .

install_test_requirements:
	python3 -m pip install -r requirements_test.txt 

install:
	python3 setup.py install

uninstall:
	python3 -m pip uninstall -y $(REPO_NAME)

reinstall: uninstall install

publish:
	python3 setup.py publish

clean:
	@rm -rf *.egg* build dist *.py[oc] */*.py[co] cover doctest_pypi.cfg \
		nosetests.xml pylint.log output.xml flake8.log tests.log \
		test-result.xml htmlcov fab.log .coverage __pycache__ \
		*/__pycache__ deb_dist .mypy_cache .pytest_cache

pep8:
	flake8 --max-line-length=88 --extend-ignore=E203 --exit-zero $(REPO_NAME)/*.py

flake8: pep8

lint:
	pylint --msg-template="{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}" \
		--max-line-length=88 -r n $(REPO_NAME)/*.py || exit 0

pylint: lint

checkmetadata:
	python3 setup.py check -s --restructuredtext

mypy:
	mypy --strict .

pytest:
	python3 -m pytest

test: editable install_test_requirements pytest

test_cov:
	python3 -m pytest --cov=$(REPO_NAME) --cov-report term-missing

black:
	black .

mkdocs:
	pip install -r docs/requirements.txt
	mkdocs serve

deb_dist: 
	python3 setup.py --command-packages=stdeb.command sdist_dsc

deb_custom:
	cp debian/$(REPO_NAME).conf $(wildcard deb_dist/*/debian)/$(REPO_NAME).default
	cp debian/$(REPO_NAME).postinst $(wildcard deb_dist/*/debian)/$(REPO_NAME).postinst
	cp debian/$(REPO_NAME).service $(wildcard deb_dist/*/debian)/$(REPO_NAME).service

bdist_deb: deb_dist deb_custom
	cd deb_dist/$(REPO_NAME)-*/ && dpkg-buildpackage -rfakeroot -uc -us
	
faux_latest:
	cp deb_dist/$(REPO_NAME)_*-1_all.deb deb_dist/$(REPO_NAME)_latest_all.deb
	cp deb_dist/$(REPO_NAME)_*-1_all.deb deb_dist/python3-$(REPO_NAME)_latest_all.deb

package: bdist_deb faux_latest

extract: 
	dpkg-deb -e $(wildcard deb_dist/*latest_all.deb) deb_dist/extract
	dpkg-deb -x $(wildcard deb_dist/*latest_all.deb) deb_dist/extract

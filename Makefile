#
# Copyright 2023 Greg Albrecht <oss@undef.net>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Author:: Greg Albrecht W2GMD <oss@undef.net>
# Copyright:: Copyright 2023 Greg Albrecht
# License:: Apache License, Version 2.0
#

this_app = pytak
.DEFAULT_GOAL := all

all: editable

develop:
	python3 setup.py develop

editable:
	python3 -m pip install -e .

install_test_requirements:
	python3 -m pip install -r requirements_test.txt

install:
	python3 setup.py install

uninstall:
	python3 -m pip uninstall -y $(this_app)

reinstall: uninstall install

publish:
	python3 setup.py publish

clean:
	@rm -rf *.egg* build dist *.py[oc] */*.py[co] cover doctest_pypi.cfg \
		nosetests.xml pylint.log output.xml flake8.log tests.log \
		test-result.xml htmlcov fab.log .coverage __pycache__ \
		*/__pycache__

pep8:
	flake8 --max-line-length=88 --extend-ignore=E203,E231 --exit-zero $(this_app)/*.py

flake8: pep8

lint:
	pylint --msg-template="{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}" \
		--max-line-length=88 -r n $(this_app)/*.py || exit 0

pylint: lint

checkmetadata:
	python3 setup.py check -s --restructuredtext

mypy:
	mypy --strict .

pytest:
	pytest

test: editable install_test_requirements pytest

test_cov:
	pytest --cov=$(this_app) --cov-report term-missing

black:
	black .

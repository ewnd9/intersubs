.PHONY: format
format:
	autopep8  --in-place --aggressive --aggressive *.py

.PHONY: lint
lint:
	pylint --rcfile=./standard.rc --extension-pkg-whitelist=PyQt5 *.py
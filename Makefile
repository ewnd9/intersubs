.PHONY: deps-pip
deps-pip:
	python3 -m pip install -r requirements.txt

.PHONY: deps-brew
deps-brew:
	brew cask install xquartz
	brew install xdotool

.PHONY: format
format:
	autopep8  --in-place --aggressive --aggressive **/*.py

.PHONY: lint
lint:
	pylint --rcfile=./standard.rc **/*.py

.PHONY: dev
dev:
	python3 intersubs/intersubs.py whatever /tmp/intersubs-test.txt testing

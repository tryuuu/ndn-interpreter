S ?= examples/hello.ndn

.PHONY: run install

install:
	pip install -e .

run:
	python -m ndnc.cli run $(S)
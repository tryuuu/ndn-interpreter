S ?= examples/hello.ndn

.PHONY: run install

install:
	python -m pip install -e .

run:
	python -m ndnc.cli run $(S)
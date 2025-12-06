S ?= examples/hello.ndn

.PHONY: run install serve

install:
	python -m pip install -e .

run:
	python -m ndnc.cli run $(S)

serve:
	python -m ndnc.cli serve
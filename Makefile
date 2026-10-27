.PHONY: test ingest build check all

# Unit tests run on a 10-row fixture and need no downloaded data.
test:
	python3 -m unittest discover -s tests -t . -v

# CSV to Parquet, then register the raw view.
ingest:
	python3 -m lakehouse.runner ingest

# Materialise staging, fact and mart models in dependency order.
build:
	python3 -m lakehouse.runner build

# Run the SQL data tests against the built warehouse.
check:
	python3 -m lakehouse.runner test

all: ingest build check

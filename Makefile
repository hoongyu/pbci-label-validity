.PHONY: all download download-check verify-raw extract inventory preprocess baseline cells manipulation divergence variance clean

all: baseline cells manipulation divergence variance

# Raw data acquisition. Deliberately NOT a prerequisite of `all`: data/raw is
# read-only source, not a regenerable artifact (dataset.md 1).
download-check:               # preflight only, downloads nothing
	python -m src.io.download --check

download:                     # ~29.5 GB from Zenodo, resumable
	python -m src.io.download

verify-raw:                   # md5 every local file against the Zenodo API
	python -m src.io.download --verify

extract:                      # unzip sub-*.zip in place
	python -m src.io.download --extract

inventory:
	python -m src.io.inventory

preprocess: inventory
	python -m src.preprocess.run

baseline: preprocess          # G0.4
	python -m analyses.P0_baseline.reproduce

cells: preprocess             # G1.1
	python -m analyses.P1_divergence.build_cells

manipulation: cells           # G1.2
	python -m analyses.P1_divergence.manipulation_checks

divergence: cells             # G1.3
	python -m analyses.P1_divergence.metrics

variance: cells               # G1.4
	python -m analyses.P1_divergence.variance_components

test:
	pytest -q

clean:
	rm -rf data/derived outputs/figures outputs/tables

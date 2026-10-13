.PHONY: all download download-check verify-raw extract inventory preprocess
.PHONY: preprocess-descriptive baseline cells manipulation anomaly confound
.PHONY: divergence variance test clean

all: baseline cells manipulation anomaly divergence variance

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

manipulation: cells           # G1.2 Part A
	python -m analyses.P1_divergence.manipulation_checks

preprocess-descriptive:       # second preprocessing variant, 0.5 s epochs
	python -m src.preprocess.descriptive

anomaly: preprocess-descriptive   # G1.2 Part B, the verdict in attempt 4
	python -m analyses.P1_divergence.descriptive_partb

confound: preprocess-descriptive  # presentation-order control for G1.2
	python -m analyses.P1_divergence.order_confound

divergence: cells             # G1.3
	python -m analyses.P1_divergence.divergence

variance: cells               # G1.4
	python -m analyses.P1_divergence.variance

test:
	pytest -q

clean:
	rm -rf data/derived outputs/figures outputs/tables

.PHONY: all inventory preprocess baseline cells manipulation divergence variance clean

all: baseline cells manipulation divergence variance

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

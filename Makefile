PYTHON ?= python

.PHONY: validate-source resolve discover materialize validate-resolved media crop freeze build test all clean-generated

validate-source:
	$(PYTHON) scripts/validate_source.py

resolve: validate-source
	$(PYTHON) scripts/resolve_cards_tcgdex.py

discover: resolve
	$(PYTHON) scripts/discover_printings_tcgdex.py

materialize: discover
	$(PYTHON) scripts/materialize_mechanical_pool.py

validate-resolved: materialize
	$(PYTHON) scripts/validate_resolved_pool.py

media: validate-resolved
	$(PYTHON) scripts/download_media.py

crop: media
	$(PYTHON) scripts/crop_artwork.py

freeze: validate-resolved
	$(PYTHON) scripts/freeze_natural_keys.py

build: crop
	$(PYTHON) scripts/build_anki.py

test:
	$(PYTHON) -m pytest

all: test build

clean-generated:
	rm -f generated/*.jsonl generated/*resolved*.csv generated/media_manifest.json
	rm -f media/*.png media/*.jpg media/*.webp dist/*.apkg

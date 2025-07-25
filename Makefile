PROJECT_DIRS = src tests 

export DATA_DIR = asper_bench
export ASSETS_DIR = assets
export GENERATED_DATA_DIR = data

# Get current timestamp for archive naming
TIMESTAMP := $(shell date +%Y-%m-%d-%H%M)

create_assets_dirs:
	mkdir -p $(ASSETS_DIR)
	mkdir -p $(DATA_DIR)
	mkdir -p $(GENERATED_DATA_DIR)

compress:
	tar -czf $(ASSETS_DIR)/asper_bench_$(TIMESTAMP).tgz -C $(DATA_DIR) .

restore_assets: create_assets_dirs
	@echo "Running restore_assets target"; \
	LATEST_ARCHIVE=$$(find $(ASSETS_DIR) -name "*.tgz" -type f -print0 | xargs -0 -r ls -t | head -n 1); \
	echo "Found archive: $$LATEST_ARCHIVE"; \
	if [ -z "$$LATEST_ARCHIVE" ]; then \
		echo "Failed to restore $$LATEST_ARCHIVE."; \
	else \
		echo "Restoring from archive: $$LATEST_ARCHIVE"; \
		echo "Data dir $$DATA_DIR"; \
		tar -xzf $$LATEST_ARCHIVE -C $$DATA_DIR; \
	fi

install_deps:
	pipenv install -e '.[testing]'

install: install_deps restore_assets

test:
	pytest

black:
	black $(PROJECT_DIRS)

mypy:
	mypy $(PROJECT_DIRS)

isort:
	isort $(PROJECT_DIRS)

format: black isort

check: black test

.PHONY: compress restore_assets create_assets_dirs

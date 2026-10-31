UVX ?= uvx
PYTHON_CMD = $(UVX) --with playwright --with python-dotenv --with loguru --with xlrd --with openpyxl --with jsonschema --with requests --with boto3 -- python

.PHONY: help test lint buygoods buygoods-api buygoods-lake pagamerican pagamerican-api pagamerican-lake diff painel

help:
	@printf '%s\n' 'Targets:' '  make test           Run unit tests' '  make lint           Ruff lint/format check and prettier check' '  make buygoods       Run browser-based BuyGoods export for yesterday' '  make buygoods-api   Build yesterday'"'"'s BuyGoods JSON from the API' '  make buygoods-lake  Build yesterday'"'"'s BuyGoods JSON from the Athena lake' '  make pagamerican    Download yesterday'"'"'s PagAmerican Excel report (HEADED=1 for first login)' '  make pagamerican-api Build yesterday'"'"'s PagAmerican JSON from the Data API' '  make pagamerican-lake Build yesterday'"'"'s PagAmerican JSON from the Athena lake' '  make diff GATEWAY=buygoods|pagamerican  Compare api/lake JSONs against web (AI + dashboard)' '  make painel         Build the panel mockup data (latest diff per gateway) and print the file to open'

test:
	PYTHONPATH=. $(PYTHON_CMD) -m unittest discover -s tests -v

lint:
	$(UVX) ruff check src tests
	$(UVX) ruff format --check src tests
	npx prettier --check .

buygoods:
	PYTHONPATH=. $(PYTHON_CMD) src/scripts/extracao_diaria_buygoods_web.py $(if $(filter 1,$(DEBUG)),--debug) $(if $(OUTPUT_ROOT),--output-root "$(OUTPUT_ROOT)") $(if $(DATE),--date $(DATE))

buygoods-api:
	PYTHONPATH=. $(PYTHON_CMD) src/scripts/extracao_diaria_buygoods_api.py $(if $(filter 1,$(DEBUG)),--debug) $(if $(OUTPUT_ROOT),--output-root "$(OUTPUT_ROOT)") $(if $(DATE),--date $(DATE))

buygoods-lake:
	PYTHONPATH=. $(PYTHON_CMD) src/scripts/extracao_diaria_buygoods_lake.py $(if $(filter 1,$(DEBUG)),--debug) $(if $(OUTPUT_ROOT),--output-root "$(OUTPUT_ROOT)") $(if $(DATE),--date $(DATE))

pagamerican:
	PYTHONPATH=. $(PYTHON_CMD) src/scripts/extracao_diaria_pagamerican_web.py $(if $(filter 1,$(DEBUG)),--debug) $(if $(filter 1,$(HEADED)),--headed) $(if $(OUTPUT_ROOT),--output-root "$(OUTPUT_ROOT)") $(if $(DATE),--date $(DATE))

pagamerican-api:
	PYTHONPATH=. $(PYTHON_CMD) src/scripts/extracao_diaria_pagamerican_api.py $(if $(filter 1,$(DEBUG)),--debug) $(if $(OUTPUT_ROOT),--output-root "$(OUTPUT_ROOT)") $(if $(DATE),--date $(DATE))

pagamerican-lake:
	PYTHONPATH=. $(PYTHON_CMD) src/scripts/extracao_diaria_pagamerican_lake.py $(if $(filter 1,$(DEBUG)),--debug) $(if $(OUTPUT_ROOT),--output-root "$(OUTPUT_ROOT)") $(if $(DATE),--date $(DATE))

diff:
	PYTHONPATH=. $(PYTHON_CMD) src/scripts/diff_fontes.py $(GATEWAY) $(if $(DATE),--date $(DATE)) $(if $(OUTPUT_ROOT),--output-root "$(OUTPUT_ROOT)")

painel:
	PYTHONPATH=. $(PYTHON_CMD) src/scripts/dados_painel.py $(if $(BUYGOODS_DATE),--buygoods-date $(BUYGOODS_DATE)) $(if $(PAGAMERICAN_DATE),--pagamerican-date $(PAGAMERICAN_DATE)) $(if $(OUTPUT_ROOT),--output-root "$(OUTPUT_ROOT)")
	@printf 'Open: file://%s/mockups/painel.html\n' "$(CURDIR)"

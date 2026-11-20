PY := .venv/bin/python
DBT := ../.venv/bin/dbt

.PHONY: setup data dbt build test validate evals api ui docker clean

setup:            ## create virtualenv and install dependencies
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

data:             ## generate FOCUS-format billing data
	$(PY) data/generate_focus.py --out data/raw/focus_billing.csv

dbt:              ## build models and run data tests
	cd dbt && $(DBT) build --profiles-dir .

build: data dbt   ## data + warehouse

test:             ## unit + integration tests (no API key needed)
	$(PY) -m pytest -q

validate:         ## check every gold answer in the benchmark
	$(PY) evals/run_evals.py --validate-gold

evals:            ## run the agent on the benchmark (needs GEMINI_API_KEY)
	$(PY) evals/run_evals.py

api:              ## REST API on :8000
	.venv/bin/uvicorn api.main:app --reload --port 8000

ui:               ## Streamlit UI on :8501
	.venv/bin/streamlit run app/streamlit_app.py

docker:
	docker build -t finops-agent .

clean:
	rm -rf warehouse/*.duckdb* dbt/target dbt/logs data/raw

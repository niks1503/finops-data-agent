FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Build the warehouse at image build time so the container starts ready to answer.
RUN python data/generate_focus.py --out data/raw/focus_billing.csv \
 && cd dbt && dbt build --profiles-dir .

EXPOSE 8501 8000
# Default: Streamlit UI. Override with: docker run ... uvicorn api.main:app --host 0.0.0.0 --port 8000
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]

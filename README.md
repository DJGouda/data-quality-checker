# Data Quality Checker API

A lightweight FastAPI project that analyzes uploaded CSV files for common data quality issues such as missing values, duplicate rows, and invalid numeric values.

## Features
- Upload CSV files from a browser
- REST API for analysis
- Interactive API docs at `/docs`
- Missing value detection
- Duplicate row detection
- Numeric summary statistics
- Simple rule-based checks

## Tech Stack
- Python
- FastAPI
- Pandas
- HTML / JavaScript

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
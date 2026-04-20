from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
import pandas as pd
from io import StringIO

app = FastAPI(title="Data Quality Checker API")

latest_report = None

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
        <head>
            <title>Data Quality Checker</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 900px;
                    margin: 40px auto;
                    padding: 20px;
                    line-height: 1.6;
                }
                h1 {
                    color: #222;
                }
                .box {
                    border: 1px solid #ddd;
                    border-radius: 10px;
                    padding: 20px;
                    margin-top: 20px;
                    background: #fafafa;
                }
                button {
                    background: #0066cc;
                    color: white;
                    border: none;
                    padding: 10px 16px;
                    border-radius: 6px;
                    cursor: pointer;
                }
                button:hover {
                    background: #004d99;
                }
                input[type=file] {
                    margin-bottom: 10px;
                }
                pre {
                    background: #111;
                    color: #eee;
                    padding: 15px;
                    border-radius: 8px;
                    overflow-x: auto;
                    white-space: pre-wrap;
                }
            </style>
        </head>
        <body>
            <h1>Data Quality Checker</h1>
            <p>Upload a CSV file to analyze missing values, duplicates, and numeric statistics.</p>

            <div class="box">
                <form id="uploadForm">
                    <input type="file" id="fileInput" accept=".csv" required />
                    <br />
                    <button type="submit">Upload and Analyze</button>
                </form>
            </div>

            <div class="box">
                <h2>Latest Report</h2>
                <pre id="result">No report yet.</pre>
            </div>

            <script>
                const form = document.getElementById("uploadForm");
                const fileInput = document.getElementById("fileInput");
                const result = document.getElementById("result");

                form.addEventListener("submit", async (e) => {
                    e.preventDefault();

                    const file = fileInput.files[0];
                    if (!file) {
                        alert("Please select a CSV file.");
                        return;
                    }

                    const formData = new FormData();
                    formData.append("file", file);

                    result.textContent = "Analyzing...";

                    try {
                        const response = await fetch("/upload", {
                            method: "POST",
                            body: formData
                        });

                        const data = await response.json();
                        result.textContent = JSON.stringify(data, null, 2);
                    } catch (error) {
                        result.textContent = "Error: " + error;
                    }
                });
            </script>
        </body>
    </html>
    """

@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    global latest_report

    if not file.filename.endswith(".csv"):
        return {"error": "Only CSV files are allowed."}

    contents = await file.read()

    try:
        decoded = contents.decode("utf-8")
        df = pd.read_csv(StringIO(decoded))
    except Exception as e:
        return {"error": f"Could not read CSV file: {str(e)}"}

    total_rows = len(df)
    total_columns = len(df.columns)
    duplicate_rows = int(df.duplicated().sum())
    missing_values = df.isnull().sum().to_dict()

    numeric_stats = {}
    numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()

    invalid_rules = {}

    if "age" in df.columns:
        invalid_age_count = int((df["age"].fillna(0) < 0).sum())
        invalid_rules["age_less_than_zero"] = invalid_age_count

    if "salary" in df.columns:
        invalid_salary_count = int((df["salary"].fillna(0) < 0).sum())
        invalid_rules["salary_less_than_zero"] = invalid_salary_count

    for col in numeric_columns:
        numeric_stats[col] = {
            "min": None if pd.isna(df[col].min()) else float(df[col].min()),
            "max": None if pd.isna(df[col].max()) else float(df[col].max()),
            "mean": None if pd.isna(df[col].mean()) else float(df[col].mean())
        }

    columns_with_missing = [col for col, count in missing_values.items() if count > 0]

    latest_report = {
        "file_name": file.filename,
        "total_rows": total_rows,
        "total_columns": total_columns,
        "duplicate_rows": duplicate_rows,
        "columns": list(df.columns),
        "missing_values_by_column": missing_values,
        "columns_with_missing_values": columns_with_missing,
        "numeric_column_stats": numeric_stats,
        "custom_validation_rules": invalid_rules
    }

    return latest_report

@app.get("/report")
def get_latest_report():
    if latest_report is None:
        return {"message": "No report generated yet. Upload a CSV first."}
    return latest_report
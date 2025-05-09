import os.path
import shutil
import subprocess
import tempfile
import zipfile
from os import listdir
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

app = FastAPI()

class TestResultsResponse(BaseModel):
    project_name: str
    results: list[str]

@app.post("/run-tests")
async def run_tests(project: UploadFile = File(...)) -> TestResultsResponse:
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_file_path = os.path.join(temp_dir, project.filename)
            with open(zip_file_path, "wb") as buffer:
                shutil.copyfileobj(project.file, buffer)

            with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            extracted_dir = Path(temp_dir) / Path(project.filename).stem

            print(listdir(extracted_dir))

            pom_file_path = extracted_dir / "pom.xml"
            print(f"Extracted dir: {extracted_dir.resolve()}")
            if not pom_file_path.exists():
                print("[Error] - pom.xml file not found")
                raise HTTPException(status_code=400, detail="Invalid maven project, pom.xml not found")

            print("[In Progress] - Running maven tests")
            process = subprocess.Popen(
                ["mvn", "surefire-report:report"],
                cwd=extracted_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True
            )

            stdout, stderr = process.communicate()
            print(f"Process finished with code: {process.returncode}")
            if process.returncode != 0:
                print(f"[Error] - Test execution failed: {stderr}")
                raise HTTPException(status_code=500, detail=f"Test execution failed: {stderr}")

            surefire_reports_dir = extracted_dir / "target" / "surefire-reports"
            if not surefire_reports_dir.exists():
                print("[Error] - Test reports not generated")
                raise HTTPException(status_code=500, detail="Test reports not generated")

            response_list = []
            for file_name in listdir(surefire_reports_dir):
                if file_name.endswith(".txt"):
                    report = open(surefire_reports_dir / file_name, "r")
                    response_list.append(report.read())
                    report.close()

            return TestResultsResponse(project_name=Path(project.filename).stem, results=response_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
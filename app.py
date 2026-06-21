from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import csv
import json
import os
import subprocess
import sys
from datetime import datetime

app = Flask(__name__)
CORS(app)

PATH = 'all excels/'
CONFIG_JSON_PATH = 'config/user_config.json'
RESUMES_FOLDER = 'all resumes/'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_user_config() -> dict:
    '''Load user_config.json, return empty dict on failure.'''
    try:
        with open(CONFIG_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        return {"_error": f"JSON parse error: {e}"}


def save_user_config(data: dict) -> None:
    '''Write data to user_config.json.'''
    os.makedirs(os.path.dirname(CONFIG_JSON_PATH), exist_ok=True)
    with open(CONFIG_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_questions_db() -> dict:
    '''Load questions_db.json'''
    try:
        with open('config/questions_db.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return {"mappings": [], "_error": str(e)}


def save_questions_db(data: dict) -> None:
    with open('config/questions_db.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route('/')
def home():
    """Displays the home page of the application."""
    return render_template('index.html')

# ---------------------------------------------------------------------------
# Applied Jobs CRUD
# ---------------------------------------------------------------------------

@app.route('/applied-jobs', methods=['GET'])
def get_applied_jobs():
    '''
    Retrieves a list of applied jobs from the applications history CSV file.
    '''
    try:
        jobs = []
        with open(PATH + 'all_applied_applications_history.csv', 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                jobs.append({
                    'Job_ID': row['Job ID'],
                    'Title': row['Title'],
                    'Company': row['Company'],
                    'HR_Name': row['HR Name'],
                    'HR_Link': row['HR Link'],
                    'Job_Link': row['Job Link'],
                    'External_Job_link': row['External Job link'],
                    'Date_Applied': row['Date Applied']
                })
        return jsonify(jobs)
    except FileNotFoundError:
        return jsonify({"error": "No applications history found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/applied-jobs/<job_id>', methods=['PUT'])
def update_applied_date(job_id):
    """Updates the 'Date Applied' field of a job in the applications history CSV file."""
    try:
        data = []
        csvPath = PATH + 'all_applied_applications_history.csv'

        if not os.path.exists(csvPath):
            return jsonify({"error": f"CSV file not found at {csvPath}"}), 404

        with open(csvPath, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            fieldNames = reader.fieldnames
            found = False
            for row in reader:
                if row['Job ID'] == job_id:
                    row['Date Applied'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    found = True
                data.append(row)

        if not found:
            return jsonify({"error": f"Job ID {job_id} not found"}), 404

        with open(csvPath, 'w', encoding='utf-8', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldNames)
            writer.writeheader()
            writer.writerows(data)

        return jsonify({"message": "Date Applied updated successfully"}), 200
    except Exception as e:
        print(f"Error updating applied date: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
# Configuration API
# ---------------------------------------------------------------------------

@app.route('/config', methods=['GET'])
def get_config():
    '''Return full user config as JSON.'''
    config = load_user_config()
    if "_error" in config:
        return jsonify(config), 500
    return jsonify(config)


@app.route('/config', methods=['POST'])
def save_config():
    '''Save full user config JSON sent from the UI.'''
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "No data received"}), 400

        # Preserve comment field
        existing = load_user_config()
        if "_comment" in existing:
            data["_comment"] = existing["_comment"]

        save_user_config(data)
        return jsonify({"message": "Configuration saved successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/config/resumes', methods=['GET'])
def get_resumes():
    '''List all PDF files available in the resumes folder.'''
    try:
        os.makedirs(RESUMES_FOLDER, exist_ok=True)
        files = [f for f in os.listdir(RESUMES_FOLDER) if f.lower().endswith('.pdf')]
        return jsonify({"resumes": files, "folder": RESUMES_FOLDER})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/config/validate', methods=['GET'])
def validate_config_endpoint():
    '''
    Run the validator on all config files and return any errors found.
    Returns {"valid": true} or {"valid": false, "errors": [...]}
    '''
    errors = []
    config = load_user_config()

    # --- Personals ---
    p = config.get("personals", {})
    if not p.get("first_name", "").strip():
        errors.append({"section": "Perfil", "field": "first_name", "message": "El nombre es obligatorio."})
    if not p.get("last_name", "").strip():
        errors.append({"section": "Perfil", "field": "last_name", "message": "El apellido es obligatorio."})
    if len(p.get("phone_number", "")) < 10:
        errors.append({"section": "Perfil", "field": "phone_number", "message": "El teléfono debe tener al menos 10 dígitos."})

    # --- Questions ---
    q = config.get("questions", {})
    resume = q.get("default_resume_path", "")
    if resume and not os.path.exists(resume):
        errors.append({"section": "Aplicaciones", "field": "default_resume_path", "message": f"El archivo de CV '{resume}' no existe."})
    if not q.get("years_of_experience", ""):
        errors.append({"section": "Aplicaciones", "field": "years_of_experience", "message": "Los años de experiencia son obligatorios."})
    salary = q.get("desired_salary", 0)
    if not isinstance(salary, (int, float)) or salary <= 0:
        errors.append({"section": "Aplicaciones", "field": "desired_salary", "message": "El salario deseado debe ser un número mayor a 0."})
    if not q.get("linkedIn", ""):
        errors.append({"section": "Aplicaciones", "field": "linkedIn", "message": "La URL de LinkedIn es recomendada."})

    # --- Search ---
    s = config.get("search", {})
    if not s.get("search_terms") or len(s["search_terms"]) == 0:
        errors.append({"section": "Búsqueda", "field": "search_terms", "message": "Debes ingresar al menos un término de búsqueda."})
    if not s.get("search_location", "").strip():
        errors.append({"section": "Búsqueda", "field": "search_location", "message": "La ubicación de búsqueda es recomendada."})

    # --- Secrets ---
    sec = config.get("secrets", {})
    if sec.get("use_AI") and not sec.get("llm_model"):
        errors.append({"section": "IA", "field": "llm_model", "message": "Si usas IA debes especificar el modelo."})

    if errors:
        return jsonify({"valid": False, "errors": errors})
    return jsonify({"valid": True, "errors": []})


@app.route('/config/questions-db', methods=['GET'])
def get_questions_db():
    '''Return the questions_db.json contents.'''
    return jsonify(load_questions_db())


@app.route('/config/questions-db', methods=['POST'])
def save_questions_db_endpoint():
    '''Save new questions_db.json contents from UI.'''
    try:
        data = request.get_json(force=True)
        if not data or "mappings" not in data:
            return jsonify({"error": "Invalid format. Expected {mappings: [...]}"}), 400
        save_questions_db(data)
        return jsonify({"message": "Questions DB saved successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, jsonify, render_template
from flask_cors import CORS
import csv
import os
from datetime import datetime

# The dashboard is a READ-ONLY viewer of application results.
# All bot configuration lives in the Tkinter settings window (modules/bot_ui.py),
# which edits the config/*.py files directly.

app = Flask(__name__)
CORS(app)

PATH = 'all excels/'
NOTES_FILE = PATH + 'application_notes.csv'


def _application_notes() -> dict:
    """Why each application went out, keyed by job id (sidecar CSV).

    Kept apart from the history CSV so an installation from 1.0.0 keeps its old
    header and still opens here; a missing sidecar simply means no notes yet.
    """
    notas = {}
    try:
        with open(NOTES_FILE, 'r', encoding='utf-8') as file:
            for row in csv.DictReader(file):
                if row.get('Job ID'):
                    notas[row['Job ID']] = row
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Could not read application notes: {e}")
    return notas

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
        notas = _application_notes()
        with open(PATH + 'all_applied_applications_history.csv', 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                nota = notas.get(row['Job ID'], {})
                jobs.append({
                    'Job_ID': row['Job ID'],
                    'Title': row['Title'],
                    'Company': row['Company'],
                    'HR_Name': row['HR Name'],
                    'HR_Link': row['HR Link'],
                    'Job_Link': row['Job Link'],
                    'External_Job_link': row['External Job link'],
                    'Date_Applied': row['Date Applied'],
                    'AI_Score': nota.get('AI Score', ''),
                    'AI_Reason': nota.get('AI Reason', ''),
                    'Applied_Despite': nota.get('Applied Despite', ''),
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

if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, request, render_template, session, redirect, url_for
from markupsafe import Markup
import google.generativeai as genai
import os, json
import re
import sqlite3

app = Flask(__name__)
app.secret_key = "1623"

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def ask_gemini(prompt):
    model = genai.GenerativeModel("gemini-2.0-flash")
    result = model.generate_content(prompt)
    return result.text

def format_explanation(text):
    return Markup(text.replace("\n", "<br>"))

def extract_json(text):  #had to chatgpt this function as went through 5+ iterations but all had problems, fixed when ast.literal introduced.
    """
    Extracts JSON-like content from AI output and converts it to valid JSON.
    """
    import ast

    # Remove ```json blocks if present
    cleaned = re.sub(r"```(?:json)?", "", text).strip()

    # Find {...} block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError("No JSON found in AI output")

    extracted = match.group(0)

    try:
        # Convert to Python dict safely
        data = ast.literal_eval(extracted)
    except Exception as e:
        raise ValueError(f"Failed to parse AI output: {e}")

    # Now convert Python dict to valid JSON
    return json.loads(json.dumps(data))

def init_db():
    conn = sqlite3.connect("tmua.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            options TEXT,          
            correct_answer TEXT,
            topic TEXT,
            explanation TEXT,
            raw_output TEXT,       
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS users (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       username TEXT,
                       email TEXT UNIQUE,
                       password TEXT
                   )
                   """)

    conn.commit()
    conn.close()

@app.before_request
def clear_session_on_restart():
    if not hasattr(app, "has_cleared"):
        session.clear()
        app.has_cleared = True

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("tmua.db")
        cursor = conn.cursor()

        try:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                           (username, email, password))
            conn.commit()
            conn.close()
            return redirect("/login")
        except:
            conn.close()
            return "Account already linked to email."

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_input = request.form["login"]
        password = request.form["password"]

        conn = sqlite3.connect("tmua.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM users 
            WHERE (username = ? OR email = ?) AND password = ?
        """, (login_input, login_input, password))
        row = cursor.fetchone()
        conn.close()

        if row:
            session["user_id"] = row[0]
            return redirect("/")
        else:
            return "Incorrect login details."

    return render_template("login.html")



@app.route("/", methods=["GET", "POST"])

def home():
    if "user_id" not in session:
        return redirect("/login")
    #initialising these variables as when flask runs using GET method, the POST block never runs so these variables dont exist and the return function breaks
    question = ""
    options = []
    answer = ""
    topic = ""
    explanation = ""
    Mark = ''
    question_id = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "generate":
            ai_output = ask_gemini("Generate a simple TMUA-style math question with multiple-choice options, "
                "(A–H). Return your response as valid JSON in this format: "
                "{'question': '...', 'options': ['A) ...', 'B) ...'], 'correct_answer': '...', 'topic': '...', 'explanation': '...'}"
            )
            print("RAW GEMINI OUTPUT:\n", ai_output)
            data = extract_json(ai_output)
            question = data.get("question", "")
            options = data.get("options", [])
            answer = data.get("correct_answer", "")
            topic = data.get("topic", "")
            explanation = format_explanation(data.get("explanation", ""))
            response = Markup(ai_output.replace("\n", "<br>"))

            conn = sqlite3.connect("tmua.db")
            cursor = conn.cursor()
            cursor.execute("""
                           INSERT INTO questions (question, options, correct_answer, topic, explanation, raw_output)
                           VALUES (?, ?, ?, ?, ?, ?)
                           """, (
                               question,
                               json.dumps(options),  # as sql has no list data type, so convert to json to store
                               answer,
                               topic,
                               data.get("explanation", ""),
                               ai_output
                           ))
            conn.commit()
            question_id = cursor.lastrowid
            conn.close()


        elif action == "submit_answer":
            user_answer = request.form.get("user_input", "").strip()
            question_id = request.form.get("question_id")

            conn = sqlite3.connect("tmua.db")
            cursor = conn.cursor()
            cursor.execute("""
            SELECT question, options, correct_answer, topic, explanation
            FROM questions WHERE id = ?
            """, (question_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                question = row[0]
                options = json.loads(row[1])
                correct_answer = row[2]
                topic = row[3]
                explanation = format_explanation(row[4])

                if user_answer.lower() == correct_answer.lower():
                    Mark = "Correct!"
                else:
                    Mark = f"Incorrect. Correct answer was: {correct_answer}"


    return render_template("index_original.html", question=question, options=options,answer=answer, topic=topic, explanation=explanation, response=Mark, question_id = question_id)

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)

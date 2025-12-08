from flask import Flask, request, render_template, session, redirect, url_for
from markupsafe import Markup
import google.generativeai as genai
import os, json, re, sqlite3, ast
from datetime import datetime

app = Flask(__name__)
app.secret_key = "1623"

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def ask_gemini(prompt):
    model = genai.GenerativeModel("gemini-2.5-flash")
    result = model.generate_content(prompt)
    return result.text


def format_explanation(text):
    return Markup(text.replace("\n", "<br>"))


def extract_json(text):
    """Extracts JSON-like content from AI output and converts to valid JSON."""
    cleaned = re.sub(r"```(?:json)?", "", text).strip()

    match = re.search(r"{.*}", cleaned, re.DOTALL)
    if not match:
        raise ValueError("No JSON found in AI output")

    extracted = match.group(0)

    try:
        data = ast.literal_eval(extracted)  # safe Python structure
    except Exception as e:
        raise ValueError(f"Failed to parse AI output: {e}")

    return json.loads(json.dumps(data))  # ensure valid JSON


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
            difficulty INTEGER,
            explanation TEXT,
            raw_output TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS question_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER,
            option_text TEXT,
            is_correct INTEGER DEFAULT 0,
            FOREIGN KEY(question_id) REFERENCES questions(id)
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

    cursor.execute("""
    
    CREATE TABLE IF NOT EXISTS History (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER,
        user_id INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        user_answer TEXT,
        correct_answer TEXT,
        time_taken FLOAT,
        FOREIGN KEY(question_id) REFERENCES questions(id)
        FOREIGN KEY(user_id) REFERENCES users(id)
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
    #initialising variables as errors occur when running the request functions if not declared.
    question = ""
    options = []
    answer = ""
    topic = ""
    explanation = ""
    Mark = ""
    question_id = None
    time_taken = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "generate":

            ai_output = ask_gemini(
                "Generate a simple TMUA-style math question with multiple-choice options (A–H).Give the question a difficulty rating of 1-9, which links to the type of TMUA grade question it would be. Return EXACT JSON:\n"
                "{'question': '...', 'options': ['A) ...','B) ...','C) ...','D) ...','E) ...','F) ...','G) ...','H) ...'], 'correct_answer': 'C', 'topic': '...', 'explanation': '...', 'difficulty': '...'}"
            )

            print("RAW GEMINI OUTPUT:\n", ai_output)

            data = extract_json(ai_output)

            question = data.get("question", "")
            options = data.get("options", [])
            correct_letter = data.get("correct_answer", "").upper().strip()
            topic = data.get("topic", "")
            explanation_raw = data.get("explanation", "")
            explanation = format_explanation(explanation_raw)
            difficulty = data.get("difficulty", "")

            # Convert A-H to option text
            index = ord(correct_letter) - ord("A")
            if 0 <= index < len(options):
                correct_option_text = options[index]

            conn = sqlite3.connect("tmua.db")
            cursor = conn.cursor()

            # insert into questions table
            cursor.execute("""
                INSERT INTO questions (question, options, correct_answer, topic, difficulty, explanation, raw_output)
                VALUES (?, ?, ?, ?, ?, ?,?)
            """, (
                question,
                json.dumps(options),
                correct_option_text,
                topic,
                difficulty,
                explanation_raw,
                ai_output
            ))

            question_id = cursor.lastrowid

            # insert each option into question options
            for i, opt in enumerate(options):
                is_correct = 1 if i == index else 0
                cursor.execute("""
                    INSERT INTO question_options (question_id, option_text, is_correct)
                    VALUES (?, ?, ?)
                """, (question_id, opt, is_correct))

            conn.commit()
            conn.close()
            session["start_time"] = datetime.now().timestamp()

        elif action == "submit_answer":

            start = session.get("start_time")
            if start is not None:
                end = datetime.now().timestamp()
                time_taken = end - start  # in seconds
            else:
                time_taken = None
            print(time_taken)

            user_answer = request.form.get("user_input", "").strip()
            question_id = request.form.get("question_id")

            conn = sqlite3.connect("tmua.db")
            cursor = conn.cursor()

            cursor.execute("""
                SELECT question, topic, explanation
                FROM questions
                WHERE id = ?
            """, (question_id,))
            row = cursor.fetchone()

            cursor.execute("""
                SELECT option_text, is_correct
                FROM question_options
                WHERE question_id = ?
            """, (question_id,))
            option_rows = cursor.fetchall()

            conn.close()

            if row:
                question = row[0]
                topic = row[1]
                explanation = format_explanation(row[2])

                options = [i[0] for i in option_rows]
                correct_answer = next(i[0] for i in option_rows if i[1] == 1)

                if user_answer.lower().strip() == correct_answer.lower().strip():
                    Mark = "Correct!"
                else:
                    Mark = f"Incorrect. Correct answer was: {correct_answer}"

            conn = sqlite3.connect("tmua.db")
            cursor = conn.cursor()

            cursor.execute("""
                           INSERT INTO history (question_id, user_id, user_answer, correct_answer, time_taken)
                           VALUES (?, ?, ?, ?, ?)
                           """, (
                               question_id,
                               session["user_id"],
                               user_answer,
                               correct_answer,
                               time_taken
                           ))

            conn.commit()
            conn.close()

    return render_template("index_original.html",
                           question=question,
                           options=options,
                           answer=answer,
                           topic=topic,
                           explanation=explanation,
                           response=Mark,
                           question_id=question_id)

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)


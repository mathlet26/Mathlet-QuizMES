import os
import time
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'free_college_quiz_secret_2026')

# Host കൺട്രോൾ ചെയ്യാനുള്ള PIN (നിങ്ങൾക്ക് മാറ്റാം)
HOST_PIN = os.environ.get('HOST_PIN', '4321')

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ക്വിസ് ചോദ്യങ്ങൾ ഇവിടെ ചേർക്കുക
QUESTIONS = [
    {
        "id": 1,
        "question": "ഇന്ത്യയുടെ ആദ്യത്തെ കൃത്രിമ ഉപഗ്രഹം ഏതാണ്?",
        "options": ["ഭാസ്കര", "ആര്യഭട്ട", "രോഹിണി", "ഇൻസാറ്റ്"],
        "answer": "ആര്യഭട്ട",
        "time_limit": 20
    },
    {
        "id": 2,
        "question": "HTTP-ൽ 'S' എന്നത് എന്തിനെ സൂചിപ്പിക്കുന്നു?",
        "options": ["Server", "Secure", "System", "Speed"],
        "answer": "Secure",
        "time_limit": 20
    },
    {
        "id": 3,
        "question": "കമ്പ്യൂട്ടറിന്റെ തലച്ചോറ് എന്നറിയപ്പെടുന്നത് ഏതാണ്?",
        "options": ["RAM", "Hard Disk", "CPU", "Monitor"],
        "answer": "CPU",
        "time_limit": 15
    }
]

state = {
    "current_q_index": -1,
    "question_start_time": 0.0,
    "players": {}  # {name: {"score": 0.0, "total_time": 0.0, "last_time": None, "answered_current": False}}
}

def get_sorted_leaderboard():
    # ഉയർന്ന സ്കോർ ഉള്ളവർ മുകളിൽ; സ്കോർ തുല്യമാണെങ്കിൽ കുറഞ്ഞ സമയം എടുത്തവർ മുകളിൽ
    rows = []
    for name, data in state["players"].items():
        rows.append({
            "name": name,
            "score": round(data["score"]),
            "last_time": data["last_time"],
            "total_time": round(data["total_time"], 2)
        })
    rows.sort(key=lambda x: (-x["score"], x["total_time"]))
    return rows

@app.route('/')
def player_view():
    return render_template('player.html')

@app.route('/projector')
def projector_view():
    return render_template('projector.html')

@socketio.on('join_quiz')
def handle_join(data):
    name = str((data or {}).get('name', '')).strip()[:40]
    if not name:
        return
    if name not in state["players"]:
        state["players"][name] = {
            "score": 0.0,
            "total_time": 0.0,
            "last_time": None,
            "answered_current": False
        }
    emit('update_leaderboard', get_sorted_leaderboard(), broadcast=True)

@socketio.on('next_question')
def handle_next_question(data):
    pin = str((data or {}).get('pin', '')).strip()
    if pin != HOST_PIN:
        emit('host_error', {"message": "തെറ്റായ Host PIN! ശരിയായ PIN നൽകുക."})
        return

    state["current_q_index"] += 1
    if state["current_q_index"] < len(QUESTIONS):
        q = QUESTIONS[state["current_q_index"]]
        state["question_start_time"] = time.time()

        for p in state["players"].values():
            p["answered_current"] = False
            p["last_time"] = None

        q_payload = {
            "index": state["current_q_index"] + 1,
            "total": len(QUESTIONS),
            "question": q["question"],
            "options": q["options"],
            "time_limit": q["time_limit"]
        }
        emit('new_question', q_payload, broadcast=True)
        emit('update_leaderboard', get_sorted_leaderboard(), broadcast=True)
    else:
        emit('quiz_over', get_sorted_leaderboard(), broadcast=True)

@socketio.on('submit_answer')
def handle_answer(data):
    name = str((data or {}).get('name', '')).strip()
    selected = (data or {}).get('answer')
    idx = state["current_q_index"]

    if idx < 0 or idx >= len(QUESTIONS) or name not in state["players"]:
        return

    player = state["players"][name]
    if player["answered_current"]:
        return  # ഒരു ചോദ്യത്തിന് ഒരു തവണ മാത്രമേ ഉത്തരം നൽകാൻ കഴിയൂ

    player["answered_current"] = True
    time_taken = round(time.time() - state["question_start_time"], 2)
    q = QUESTIONS[idx]

    if selected == q["answer"] and time_taken <= q["time_limit"]:
        # Base 500 + വേഗതയ്ക്ക് അനുസരിച്ച് 500 വരെ ബോണസ്
        bonus = max(0.0, (q["time_limit"] - time_taken) / q["time_limit"]) * 500.0
        player["score"] += (500.0 + bonus)
        player["total_time"] += time_taken
        player["last_time"] = f"{time_taken}s ✓"
    else:
        player["last_time"] = f"{time_taken}s ✗"

    emit('update_leaderboard', get_sorted_leaderboard(), broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)

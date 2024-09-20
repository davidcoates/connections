from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from service import Service, color_to_symbol, Color
from datetime import datetime
import json
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a random secret key
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

service = Service()
USER_DATA_FILE = "user_data.json"

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.username = username

@login_manager.user_loader
def load_user(username):
    user_data = load_user_data()
    if username in user_data:
        return User(username)
    return None

def serialize_item(item):
    text, color = item
    return [text, color.name if color else None]

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    else:
        # Create the file with empty data if it doesn't exist
        empty_data = {}
        save_user_data(empty_data)
        return empty_data

def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f)

@app.route('/')
def index():
    puzzles = service.get_puzzles()
    puzzle_dates = [puzzle.date.isoformat() for puzzle in puzzles]
    user_data = load_user_data()
    completed_puzzles = user_data.get(current_user.username, {}).get("completed_puzzles", 0) if current_user.is_authenticated else 0
    return render_template('index.html', puzzle_dates=puzzle_dates, completed_puzzles=completed_puzzles)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_data = load_user_data()
        if username in user_data and check_password_hash(user_data[username]['password'], password):
            user = User(username)
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_data = load_user_data()
        if username in user_data:
            flash('Username already exists')
        else:
            user_data[username] = {
                'password': generate_password_hash(password),
                'completed_puzzles': 0,
                'puzzle_attempts': {}
            }
            save_user_data(user_data)
            user = User(username)
            login_user(user)
            return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/new_game', methods=['POST'])
@login_required
def new_game():
    date = request.json.get('date')
    try:
        puzzle = next((p for p in service.get_puzzles() if p.date.isoformat() == date), None)
        if not puzzle:
            raise Exception("Invalid date")
        
        user_data = load_user_data()
        user_puzzles = user_data[current_user.username]['puzzle_attempts']
        if str(puzzle.id) in user_puzzles:
            if user_puzzles[str(puzzle.id)]["completed"]:
                return jsonify({'error': "You've already completed this puzzle."}), 400
            elif user_puzzles[str(puzzle.id)]["failed"]:
                return jsonify({'error': "You've already failed this puzzle and cannot reattempt it."}), 400
        
        game = service.new_game(puzzle.id)
        user_puzzles[str(puzzle.id)] = {"completed": False, "failed": False}
        save_user_data(user_data)
        return jsonify({'game_id': game.id, 'items': [serialize_item(item) for item in game.items]}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/game_state/<game_id>', methods=['GET'])
@login_required
def game_state(game_id):
    try:
        game = service.get_game(game_id)
        return jsonify({
            'items': [serialize_item(item) for item in game.items],
            'solved_colors': [color.name for color in game.solved_colors],
            'attempts_remaining': game.attempts_remaining,
            'solved': game.solved
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/guess/<game_id>', methods=['POST'])
@login_required
def guess(game_id):
    items = request.json.get('items', [])
    try:
        game = service.get_game(game_id)
        result = game.guess(items)
        user_data = load_user_data()
        user_puzzles = user_data[current_user.username]['puzzle_attempts']
        
        response_data = {
            'result': result.name,
            'items': [serialize_item(item) for item in game.items],
            'solved_colors': [color.name for color in game.solved_colors],
            'attempts_remaining': game.attempts_remaining,
            'solved': game.solved
        }
        
        if game.solved:
            user_data[current_user.username]['completed_puzzles'] += 1
            user_puzzles[str(game.puzzle.id)]["completed"] = True
            save_user_data(user_data)
            response_data['completed_puzzles'] = user_data[current_user.username]['completed_puzzles']
        elif game.attempts_remaining == 0:
            user_puzzles[str(game.puzzle.id)]["failed"] = True
            save_user_data(user_data)
        
        return jsonify(response_data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
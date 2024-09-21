from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from service import Service, color_to_symbol, Color
from datetime import datetime
import json
import os
import atexit

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
    user_data = load_user_data()
    completed_puzzles = user_data.get(current_user.username, {}).get("completed_puzzles", 0) if current_user.is_authenticated else 0
    return render_template('index.html', puzzles=puzzles, completed_puzzles=completed_puzzles)

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

def serialize_group(group):
    return { 'color': group.color.name, 'category': group.category, 'items': group.items }

@app.route('/game/<puzzle_id>', methods=['POST'])
@login_required
def new_game(puzzle_id):
    try:
        puzzle = service.get_puzzle(puzzle_id)
        user_data = load_user_data()
        user_puzzles = user_data[current_user.username]['puzzle_attempts']
        if str(puzzle.id) in user_puzzles:
            game_id = user_puzzles[puzzle.id]
            game = service.get_game(game_id)
        else:
            game = service.new_game(puzzle.id)
            service.save_games()
            user_puzzles[puzzle.id] = game.id
            save_user_data(user_data)
        return jsonify({
            'game_id': game.id,
            'unsolved_items': game.unsolved_items,
            'solved_groups': [ serialize_group(group) for group in game.solved_groups ],
            'attempts_remaining': game.attempts_remaining,
            'solved': game.solved,
            'guess_report': game.guess_report if game.solved or game.attempts_remaining == 0 else []
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
        service.save_games()
        # Remove the service.save_games() call from here
        user_data = load_user_data()
        response_data = {
            'result': result.name,
            'unsolved_items': game.unsolved_items,
            'solved_groups': [ serialize_group(group) for group in game.solved_groups ],
            'attempts_remaining': game.attempts_remaining,
            'solved': game.solved,
            'guess_report': game.guess_report
        }
        if game.solved:
            user_data[current_user.username]['completed_puzzles'] += 1
            save_user_data(user_data)
            response_data['completed_puzzles'] = user_data[current_user.username]['completed_puzzles']
        return jsonify(response_data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/save_current_puzzle', methods=['POST'])
@login_required
def save_current_puzzle():
    puzzle_id = request.json.get('puzzle_id')
    service.save_current_puzzle(current_user.id, puzzle_id)
    return jsonify({"success": True}), 200

@app.route('/get_current_puzzle', methods=['GET'])
@login_required
def get_current_puzzle():
    puzzle_id = service.get_current_puzzle(current_user.id)
    return jsonify({"puzzle_id": puzzle_id}), 200

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
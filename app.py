from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from service import Service, color_to_symbol, Color
from user import *
from datetime import datetime
import json
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a random secret key
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.anonymous_user = AnonymousUser

service = Service()

@app.before_request
def make_session_permanent():
    session.permanent = True

@login_manager.user_loader
def load_user(username):
    return try_fetch_user(username)

@app.route('/')
def index():
    puzzles = service.get_puzzles()
    completed_puzzles = current_user.data['completed_puzzles']
    return render_template('index.html', puzzles=puzzles, completed_puzzles=completed_puzzles)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = try_fetch_user(username, password)
        if user is None:
            flash('Invalid username or password')
        else:
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = try_create_user(username, password)
        if user is None:
            flash('Username already exists')
        else:
            login_user(user)
            return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

def serialize_group(group):
    return { 'color': group.color.name, 'category': group.category, 'items': group.items }

@app.route('/game/<puzzle_id>', methods=['POST'])
def game(puzzle_id):
    try:
        game = None
        puzzle_attempts = current_user.data['puzzle_attempts']
        if puzzle_id in puzzle_attempts:
            game_id = puzzle_attempts[puzzle_id]
            game = service.get_game(game_id)
        if game is None:
            puzzle = service.get_puzzle(puzzle_id)
            if puzzle is None:
                raise Exception("invalid puzzle_id")
            game = service.new_game(puzzle)
            puzzle_attempts[puzzle_id] = game.id
            current_user.save()
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
def guess(game_id):
    items = request.json.get('items', [])
    try:
        game = service.get_game(game_id)
        result = game.guess(items)
        # Remove the service.save_games() call from here
        response_data = {
            'result': result.name,
            'unsolved_items': game.unsolved_items,
            'solved_groups': [ serialize_group(group) for group in game.solved_groups ],
            'attempts_remaining': game.attempts_remaining,
            'solved': game.solved,
            'guess_report': game.guess_report
        }
        if game.solved:
            current_user.data['completed_puzzles'] += 1
            current_user.save()
            response_data['completed_puzzles'] = current_user.data['completed_puzzles']
        return jsonify(response_data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/save_current_puzzle', methods=['POST'])
def save_current_puzzle():
    puzzle_id = request.json.get('puzzle_id')
    current_user.data['current_puzzle'] = puzzle_id
    current_user.save()
    return jsonify({"success": True}), 200

@app.route('/get_current_puzzle', methods=['GET'])
def get_current_puzzle():
    puzzle_id = current_user.data.get('current_puzzle')
    return jsonify({"puzzle_id": puzzle_id}), 200

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
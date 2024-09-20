from flask import Flask, render_template, request, jsonify
from service import Service, color_to_symbol, Color
from datetime import datetime

app = Flask(__name__)
service = Service()

def serialize_item(item):
    text, color = item
    return [text, color.name if color else None]

@app.route('/')
def index():
    puzzles = service.get_puzzles()
    puzzle_dates = [puzzle.date.isoformat() for puzzle in puzzles]
    return render_template('index.html', puzzle_dates=puzzle_dates)

@app.route('/new_game', methods=['POST'])
def new_game():
    date = request.json.get('date')
    try:
        puzzle = next((p for p in service.get_puzzles() if p.date.isoformat() == date), None)
        if not puzzle:
            raise Exception("Invalid date")
        game = service.new_game(puzzle.id)
        return jsonify({'game_id': game.id, 'items': [serialize_item(item) for item in game.items]}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/game_state/<game_id>', methods=['GET'])
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
def guess(game_id):
    items = request.json.get('items', [])
    try:
        game = service.get_game(game_id)
        result = game.guess(items)
        return jsonify({
            'result': result.name,
            'items': [serialize_item(item) for item in game.items],
            'solved_colors': [color.name for color in game.solved_colors],
            'attempts_remaining': game.attempts_remaining,
            'solved': game.solved
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
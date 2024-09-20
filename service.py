from dataclasses import dataclass
from collections import defaultdict
import datetime
from enum import Enum, auto
import json
import uuid
import random


class Color(Enum):
    YELLOW = auto()
    GREEN = auto()
    BLUE = auto()
    PURPLE = auto()

def color_to_symbol(color: Color):
    match color:
        case Color.YELLOW:
            return '🟨'
        case Color.GREEN:
            return '🟩'
        case Color.BLUE:
            return '🟦'
        case Color.PURPLE:
            return '🟪'
        case _:
            assert False

type Item = str
type Items = list[str]
type Category = str

ITEMS_PER_GROUP = 4

@dataclass
class Group:
    category: Category
    items: Items

    def __post_init__(self):
        assert len(self.items) == ITEMS_PER_GROUP


type Solution = dict[Color, Group]

@dataclass
class Puzzle:
    id: int
    date: datetime.date
    author: str
    solution: Solution


    @staticmethod
    def from_JSON(id, data):
        date = datetime.date.fromisoformat(data['date'])
        author = data['author']
        solution = { Color[color] : Group(**group) for color, group in data['solution'].items() }
        return Puzzle(id, date, author, solution)

    def item_to_color(self, item: Item) -> Color | None:
        for color, group in self.solution.items():
            if item in group.items:
                return color
        return None


class Guess(Enum):
    ALREADY_GUESSED = auto()
    INCORRECT = auto()
    INCORRECT_ONE_AWAY = auto()
    CORRECT = auto()

class Game:

    MAX_INCORRECT_GUESSES = 4

    def __init__(self, puzzle: Puzzle):
        self.id = str(uuid.uuid4())
        self.puzzle = puzzle
        self.incorrect_guesses = set()
        self.correct_guesses = set()
        self.solved_colors = []
        self.shuffled_items = [item for color in Color for item in self.puzzle.solution[color].items]
        random.shuffle(self.shuffled_items)

    @property
    def items(self) -> list[Item, Color | None]:
        """The state of the items grid to be displayed to the user"""
        items = []
        for color in self.solved_colors:
            for item in self.puzzle.solution[color].items:
                items.append((item, color))
        for item in self.shuffled_items:
            color = self.puzzle.item_to_color(item)
            assert color is not None
            if color in self.solved_colors:
                continue
            items.append((item, None))
        return items

    @property
    def attempts_remaining(self) -> int:
        return self.MAX_INCORRECT_GUESSES - len(self.incorrect_guesses)

    @property
    def solved(self) -> bool:
        return len(self.solved_colors) == len(Color)

    def guess(self, items: Items) -> Guess:
        if self.solved:
            raise Exception("already solved")
        if self.attempts_remaining == 0:
            raise Exception("out of attempts")
        if len(items) != ITEMS_PER_GROUP:
            raise Exception("invalid items")
        guess = frozenset(items)
        if guess in self.incorrect_guesses or guess in self.correct_guesses:
            return Guess.ALREADY_GUESSED
        for item in items:
            color = self.puzzle.item_to_color(item)
            if color is None or color in self.solved_colors:
                raise Exception("invalid items")

        counts_by_color = defaultdict(int)
        for item in items:
            color = self.puzzle.item_to_color(item)
            counts_by_color[color] += 1
        counts = sorted(list(counts_by_color.values()))
        if counts == [4]:
            self.correct_guesses.add(guess)
            color = next(iter(counts_by_color.keys()))
            self.solved_colors.append(color)
            return Guess.CORRECT
        elif counts == [1,3]:
            self.incorrect_guesses.add(guess)
            return Guess.INCORRECT_ONE_AWAY
        else:
            self.incorrect_guesses.add(guess)
            return Guess.INCORRECT


class Service:

    PUZZLES_FILENAME = "puzzles.json"

    def __init__(self):
        self.games_by_id = {}
        with open(self.PUZZLES_FILENAME) as f:
            self.puzzles = [ Puzzle.from_JSON(id, puzzle) for id, puzzle in enumerate(json.load(f)) ]

    def get_puzzles(self) -> list[Puzzle]:
        return self.puzzles
    
    def new_game(self, puzzle_id: int) -> Game:
        if puzzle_id < 0 or puzzle_id >= len(self.puzzles):
            raise Exception("invalid puzzle_id")
        puzzle = self.puzzles[puzzle_id]
        game = Game(puzzle)
        self.games_by_id[game.id] = game
        return game

    def get_game(self, game_id: str) -> Game:
        if game_id not in self.games_by_id:
            raise Exception("invalid game_id")
        return self.games_by_id[game_id]

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

@dataclass(frozen=True)
class Group:
    color: Color
    category: Category
    items: Items

    def __post_init__(self):
        assert len(self.items) == ITEMS_PER_GROUP

    @staticmethod
    def from_JSON(data):
        color = Color[data['color']]
        category = data['category']
        items = data['items']
        return Group(color, category, items)

    def __hash__(self):
        return hash(self.color)

    def __eq__(self, other):
        return self.color == other.color


@dataclass(frozen=True)
class Puzzle:
    id: int
    date: datetime.date
    author: str
    groups: list[Group]

    def __post_init__(self):
        assert { group.color for group in self.groups } == set(Color)

    @staticmethod
    def from_JSON(id, data):
        date = datetime.date.fromisoformat(data['date'])
        author = data['author']
        groups = [ Group.from_JSON(group) for group in data['groups'] ]
        return Puzzle(id, date, author, groups)

    def item_to_group(self, item: Item) -> Group | None:
        for group in self.groups:
            if item in group.items:
                return group
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
        self.solved_groups = []
        self.guess_report = []
        self.shuffled_items = [item for group in self.puzzle.groups for item in group.items]
        random.shuffle(self.shuffled_items)

    @property
    def unsolved_items(self) -> list[Item]:
        return [ item for item in self.shuffled_items if self.puzzle.item_to_group(item) not in self.solved_groups ]

    @property
    def attempts_remaining(self) -> int:
        return self.MAX_INCORRECT_GUESSES - len(self.incorrect_guesses)

    @property
    def solved(self) -> bool:
        return len(self.solved_groups) == len(Color)

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
            group = self.puzzle.item_to_group(item)
            if group is None or group in self.solved_groups:
                raise Exception("invalid items")
        self.guess_report.append([color_to_symbol(self.puzzle.item_to_group(item).color) for item in items])
        counts_by_group = defaultdict(int)
        for item in items:
            group = self.puzzle.item_to_group(item)
            counts_by_group[group] += 1
        counts = sorted(list(counts_by_group.values()))
        if counts == [4]:
            self.correct_guesses.add(guess)
            group = next(iter(counts_by_group.keys()))
            self.solved_groups.append(group)
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

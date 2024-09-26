from dataclasses import dataclass
from collections import defaultdict
import datetime
from enum import Enum, auto
import json
import uuid
import random
from json import JSONEncoder, JSONDecoder


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
    id: str
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

    def try_get_group_by_item(self, item: Item) -> Group | None:
        for group in self.groups:
            if item in group.items:
                return group
        return None

    def get_group_by_item(self, item: Item) -> Group:
        group = self.try_get_group_by_item(item)
        assert group is not None
        return group

    def get_group_by_color(self, color: Color) -> Group:
        for group in self.groups:
            if group.color == color:
                return group
        assert False


class Guess(Enum):
    ALREADY_GUESSED = auto()
    INCORRECT = auto()
    INCORRECT_ONE_AWAY = auto()
    CORRECT = auto()

class GameEncoder(JSONEncoder):

    def default(self, obj):
        if isinstance(obj, Game):
            return {
                '_id': obj._id,
                '_puzzle': obj._puzzle.id,  # Store only the puzzle ID
                '_solved_groups': [group.color.name for group in obj._solved_groups],
                '_guess_report': obj._guess_report,
                '_incorrect_guesses': list(obj._incorrect_guesses),
                '_correct_guesses': list(obj._correct_guesses),
                '_shuffled_items': obj._shuffled_items
            }
        elif isinstance(obj, frozenset):
            return list(obj)
        return super().default(obj)


class GameDecoder(JSONDecoder):

    def __init__(self, *args, **kwargs):
        self.service = kwargs.pop('service')
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, data):
        if all(key in data for key in ('_id', '_puzzle', '_solved_groups', '_guess_report', '_incorrect_guesses', '_correct_guesses', '_shuffled_items')):
            puzzle = self.service.get_puzzle(data['_puzzle'])
            game = Game(self.service, puzzle)
            game._id = data['_id']
            game._solved_groups = [game._puzzle.get_group_by_color(Color[color]) for color in data['_solved_groups']]
            game._guess_report = data['_guess_report']
            game._incorrect_guesses = set(frozenset(guess) for guess in data['_incorrect_guesses'])
            game._correct_guesses = set(frozenset(guess) for guess in data['_correct_guesses'])
            game._shuffled_items = data['_shuffled_items']
            return game
        return data


class Game:

    MAX_INCORRECT_GUESSES = 4

    def __init__(self, service, puzzle: Puzzle):
        self._service = service
        self._id = str(uuid.uuid4())
        self._puzzle = puzzle
        self._solved_groups = []
        self._guess_report = []
        self._incorrect_guesses = set()
        self._correct_guesses = set()
        self._shuffled_items = [item for group in self._puzzle.groups for item in group.items]
        random.shuffle(self._shuffled_items)

    @property
    def id(self) -> str:
        return self._id

    @property
    def puzzle(self) -> Puzzle:
        return self._puzzle

    @property
    def solved_groups(self) -> list[Group]:
        """ List of groups solved, in the order they were solved """
        return self._solved_groups

    @property
    def unsolved_items(self) -> list[Item]:
        """ List of unsolved items, in the order they should be displayed """
        return [ item for item in self._shuffled_items if self._puzzle.get_group_by_item(item) not in self._solved_groups ]

    @property
    def guess_report(self) -> list[str]:
        return self._guess_report

    @property
    def attempts_remaining(self) -> int:
        return self.MAX_INCORRECT_GUESSES - len(self._incorrect_guesses)

    @property
    def solved(self) -> bool:
        return len(self.solved_groups) == len(Color)

    def guess(self, items: Items) -> Guess:
        result = self._guess(items)
        if result != Guess.ALREADY_GUESSED:
            self._service._on_game_updated(self)
        return result

    def _guess(self, items: Items) -> Guess:
        if self.solved:
            raise Exception("already solved")
        if self.attempts_remaining == 0:
            raise Exception("out of attempts")
        if len(items) != ITEMS_PER_GROUP:
            raise Exception("invalid items")
        guess = frozenset(items)
        if guess in self._incorrect_guesses or guess in self._correct_guesses:
            return Guess.ALREADY_GUESSED
        for item in items:
            group = self._puzzle.try_get_group_by_item(item)
            if group is None or group in self._solved_groups:
                raise Exception("invalid items")
        self.guess_report.append(''.join([color_to_symbol(self._puzzle.get_group_by_item(item).color) for item in items]))
        counts_by_group = defaultdict(int)
        for item in items:
            group = self._puzzle.get_group_by_item(item)
            counts_by_group[group] += 1
        counts = sorted(list(counts_by_group.values()))
        if counts == [4]:
            self._correct_guesses.add(guess)
            group = next(iter(counts_by_group.keys()))
            self._solved_groups.append(group)
            return Guess.CORRECT
        elif counts == [1,3]:
            self._incorrect_guesses.add(guess)
            return Guess.INCORRECT_ONE_AWAY
        else:
            self._incorrect_guesses.add(guess)
            return Guess.INCORRECT

    def to_json(self):
        return json.dumps(self, cls=GameEncoder)

    @classmethod
    def from_json(cls, json_str, service):
        return json.loads(json_str, cls=GameDecoder, service=service)


class Service:

    PUZZLES_FILENAME = "puzzles.json"
    GAMES_FILENAME = "games.json"

    def __init__(self):
        self._puzzles_by_id = self._load_puzzles()
        self._games_by_id = self._load_games()

    def get_puzzles(self) -> list[Puzzle]:
        return list(self._puzzles_by_id.values())

    def get_puzzle(self, puzzle_id: str) -> Puzzle | None:
        return self._puzzles_by_id.get(puzzle_id)

    def new_game(self, puzzle: Puzzle) -> Game:
        game = Game(self, puzzle)
        self._games_by_id[game.id] = game
        self._save_games()
        return game

    def get_game(self, game_id: str) -> Game | None:
        return self._games_by_id.get(game_id)

    def _on_game_updated(self, game):
        self._save_games()

    def _save_games(self):
        games_data = {game_id: game.to_json() for game_id, game in self._games_by_id.items()}
        with open(self.GAMES_FILENAME, 'w') as f:
            json.dump(games_data, f)

    def _load_games(self):
        try:
            with open(self.GAMES_FILENAME, 'r') as f:
                games_data = json.load(f)
            return {game_id: Game.from_json(game_json, self) for game_id, game_json in games_data.items()}
        except FileNotFoundError:
            return {}

    def _load_puzzles(self):
        try:
            with open(self.PUZZLES_FILENAME, 'r') as f:
                puzzle_data = json.load(f)
            puzzles = [ Puzzle.from_JSON(str(id + 1), data) for id, data in enumerate(puzzle_data) ]
            today = datetime.date.today()
            return { puzzle.id : puzzle for puzzle in puzzles if puzzle.date <= today }
        except FileNotFoundError:
            return {}

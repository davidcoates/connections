from flask import session
from flask_login import AnonymousUserMixin, UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
import os
import json


USER_DATA_FILENAME = "user_data.json"

class User(UserMixin):

    def __init__(self, name, data):
        self.id = name
        self.username = name
        self._data = data

    @staticmethod
    def from_JSON(name, data):
        return User(name, data)

    def to_JSON(self):
        return self._data

    @property
    def data(self):
        return self._data

    def save(self):
        save_user_data()


def load_user_data():
    if os.path.exists(USER_DATA_FILENAME):
        with open(USER_DATA_FILENAME, 'r') as f:
            user_data = json.load(f)
            return { name : User.from_JSON(name, data) for name, data in user_data.items() }
    else:
        return {}

def save_user_data():
    user_data = { name : user.to_JSON() for name, user in users_by_name.items() }
    with open(USER_DATA_FILENAME, 'w') as f:
        json.dump(user_data, f)

users_by_name = load_user_data()

def try_fetch_user(name, password = None) -> User | None:
    if name not in users_by_name:
        return None
    user = users_by_name[name]
    if password is not None and not check_password_hash(user.data['password'], password):
        return None
    return user

    if name not in user_data:
        return None
    return User(name)

    def set_password(self, password):
        self.data['password'] = generate_password_hash(password)
        self.save()

    def check_password(self, password) -> bool:
        return check_password_hash(self.data['password'], password)


def try_create_user(name, password) -> User | None:
    if name in users_by_name:
        return None
    data = {
        'password': generate_password_hash(password),
        'completed_puzzles': 0,
        'puzzle_attempts': {}
    }
    user = User(name, data)
    users_by_name[name] = user
    save_user_data()
    return None


class AnonymousUser(AnonymousUserMixin):

    def __init__(self):
        self._session = session
        if 'data' not in self._session:
            session['data'] = {
                'completed_puzzles': 0,
                'puzzle_attempts': {}
            }

    @property
    def data(self):
        return self._session['data']

    def save(self):
        self._session.modified = True


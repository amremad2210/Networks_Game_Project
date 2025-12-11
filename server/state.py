import json
import random
from player import Player
from logging_utils import log_message

class State:
    DIRECTION_MAP = {
        "UP": [-1, 0],
        "LEFT": [0, -1],
        "DOWN": [1, 0],
        "RIGHT": [0, 1]
    }

    def __init__(self):
        self.dimensions = [20, 20]
        self.food = self.get_random_position()
        self.players = {}

    def to_json(self):
        # Convert players dict from {username: player_obj} to {player_id: player_dict}
        players_with_ids = {}
        for player_id, (username, player_obj) in enumerate(self.players.items()):
            player_dict = player_obj.to_dict()
            player_dict["player_id"] = player_id  # Add the player_id field
            player_dict["segments"] = [
                {"x": seg[1], "y": seg[0]} for seg in player_dict.get("segments", [])
            ]
            players_with_ids[str(player_id)] = player_dict  # Use player_id as key
            
        
        return json.dumps({
            "dimensions": self.dimensions,
            "food": {"x": self.food[1], "y": self.food[0]}, #changed to match UI format
            "players": players_with_ids  # ← Now keys are "0", "1", "2", etc.
        })

    def get_random_position(self, buffer=0):
        return [random.randint(1+buffer, self.dimensions[0]-2-buffer),
                random.randint(1+buffer, self.dimensions[1]-2-buffer)]

    def add_player(self, username):
        start_pos = [self.get_random_position(buffer=3)]
        direction = random.choice(list(State.DIRECTION_MAP.values()))
        colour = random.randint(1, 7)
        self.players[username] = Player(start_pos, direction, colour, username)
        log_message("INFO", "State", f"Added {username}")

    def remove_player(self, username):
        if username in self.players:
            self.players[username].kill_player()
            del self.players[username]
            log_message("INFO", "State", f"{username} is dead")

    def update_player_direction(self, username, key):
        if username in self.players and key in State.DIRECTION_MAP:
            new_dir = State.DIRECTION_MAP[key]
            player = self.players[username]
            if not self.is_opposite(new_dir, player.direction):
                player.direction = new_dir

    def update_state(self):
        occupied = [pos for p in self.players.values() for pos in p.segments]
        dead = []
        eater = None

        for username, player in self.players.items():
            if not player.alive:
                continue

            player.add_new_head()
            if not player.check_alive(occupied, self.dimensions):
                dead.append(username)
                continue
            if player.get_head() == self.food:
                eater = username
            else:
                player.pop_tail()

        if eater:
            self.regenerate_food(eater)
        for d in dead:
            self.remove_player(d)

    def regenerate_food(self, eater):
        self.food = self.get_random_position()
        while self.food in [pos for p in self.players.values() for pos in p.segments]:
            self.food = self.get_random_position()
        self.players[eater].score += 1

    def is_opposite(self, d1, d2):
        return d1[0] + d2[0] == 0 and d1[1] + d2[1] == 0

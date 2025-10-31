import socket
import threading
import packet

class Client():
    def __init__(self):
        self.snapshot_id = 0
        # used when sending a msg to server
        self.client_seq_num = 0
        # used to track msgs recieved from the server
        self.server_seq_num = 0
        self.game_state

    def join_game(self, username):
        # send request to server to join the game
        # server assigns a player id
        pass

    def make_move(self, move):
        #sends move packet to the server
        pass

    def sync_game(self):
        # recieves periodic snapshots from the server and updates the game UI
        pass

    def log_msg(self):
        # logs all messages in a csv file for later
        pass

if __name__ == "__main__":
    player= Client()

import socket
import threading
import packet

PORT=9999
SERVER= socket.gethostbyname(socket.gethostname()) # gets the ip of my laptop
ADDR= (SERVER, PORT)
FREQUENCY = 30 #frequency of sending snapshots to all clients

class Server:
    def __init__(self):
        # create the UDP socket 
        self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server.bind(ADDR)
        #number of players in the game used to assign new player ids
        self.players_num = 0
        #is the game over?
        self.game_in_progress= False
        # list of clients should store for each client the player id, username, address, sequence number counter
        self.clients = []
        #stores the current game state (player positions, scores, leaderboard, ...etc)
        self.game_state
        
    def sync_game(self):
        #this function should be called every (10-60hz)
        #should loop on all clients and send the current game_state
        pass

    def handle_clients(self):
        # should recive UDP packets, call decode function
        # then process the message
        pass

    def start_game(self):
        # handle client request to start a new game
        pass

    def add_player(self):
        # handle client request to join a game
        # assigns a player id
        # stores the client info in self.clients
        pass

    def handle_move(self):
        # handle a move made by the client
        # updates the game state
        pass

    def game_over(self):
        # called at the end of the game
        # updates all scores and ends the game (disconnect clients)
        pass

    def log_msg(self):
        # logs all messages in a csv file for later
        pass


if __name__ == "__main___":
    server = Server()
class Player:
    def __init__(self, segments, direction, colour, username ="Unknown Player"):
        self.segments = segments
        self.direction = direction
        self.score = 0
        self.colour = colour
        self.username = username
        self.alive = True  

    def to_dict(self): #changed to match UI format
        return {
            "username": self.username,
            "direction": self.direction_to_str(),
            "colour": self.colour,
            "score": self.score,
            "segments": self.segments,
            "alive": self.alive  # Added for UI
        }

    def kill_player(self):
        """Mark player as dead and clear their snake body"""
        self.alive = False
        self.segments = []

    def direction_to_str(self):
        if self.direction == [0, -1]:
            return "LEFT"
        elif self.direction == [0, 1]:
            return "RIGHT"
        elif self.direction == [-1, 0]:
            return "UP"
        elif self.direction == [1, 0]:
            return "DOWN"
        
    def get_head(self):
        return self.segments[0]

    def add_new_head(self):
        new_head = [self.get_head()[0] + self.direction[0],
                    self.get_head()[1] + self.direction[1]]
        self.segments.insert(0, new_head)

    def pop_tail(self):
        self.segments.pop()

    def check_alive(self, occupied, dimensions):
        x, y = self.get_head()
        if x <= 0 or x >= dimensions[0]-1 or y <= 0 or y >= dimensions[1]-1:
            return False
        if self.get_head() in occupied[1:]:  # ignore own head
            return False
        return True
    def stop(self):
        """Clean up client resources"""
        self.connected = False
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=1)
        self.sock.close()

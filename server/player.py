class Player:
    def __init__(self, segments, direction, colour):
        self.segments = segments
        self.direction = direction
        self.score = 0
        self.colour = colour

    def to_dict(self):
        return {
            "segments": self.segments,
            "direction": self.direction,
            "score": self.score,
            "colour": self.colour
        }

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

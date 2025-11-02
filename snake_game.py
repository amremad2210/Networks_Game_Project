import pygame
import json
import threading
import time
import random
from enum import Enum
from client import Client
#from login_class import LoginScreen
# screen dimensions
WIN_WIDTH = 1000
WIN_HEIGHT= 700

# grid config (20 x 20)
GRID_WIDTH = 20
GRID_HEIGHT = 20
CELL_SIZE = 30 # in pixels

# colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (50, 50, 50)
GRID_COLOR = (100, 100, 100)
FOOD_COLOR = (255, 0, 0)
PLAYERS_COLOR = [
    (0, 255, 0),    # Player 0 -> Green
    (0, 0, 255),    # Player 1 -> Blue
    (255, 255, 0),  # Player 2 -> Yellow
    (255, 0, 255),  # Player 3 -> Magenta
]

# UI Layout
GRID_START_X = 20
GRID_START_Y = 20
SCOREBOARD_START_X = GRID_START_X + (GRID_WIDTH * CELL_SIZE) + 30

# Frame rate
FPS = 60

# GameGrid class : responsible for rendering the grid
class GameGrid:
    def __init__(self, surface):
        """
        Initialize the grid.
        
        Args:
            surface: Pygame surface to draw on
        """
        # Store reference to the drawing surface to use later
        self.surface = surface
        
        # Calculate pixel dimensions of the grid
        # Total width = number of cells × pixel size per cell
        self.pixel_width = GRID_WIDTH * CELL_SIZE
        self.pixel_height = GRID_HEIGHT * CELL_SIZE
    
    def draw(self):
        """Draw the game grid background and grid lines."""
        
        # Draw grid background (filled rectangle)
        pygame.draw.rect(
            self.surface,
            GRAY,
            (GRID_START_X, GRID_START_Y, self.pixel_width, self.pixel_height)
        )
        
        # Draw vertical grid lines
        # For each column, draw a line from top to bottom
        for x in range(GRID_WIDTH + 1):
            # Convert grid coordinate to pixel coordinate
            pixel_x = GRID_START_X + (x * CELL_SIZE)
            
            pygame.draw.line(
                self.surface,
                GRID_COLOR,
                # From top of grid to bottom
                (pixel_x, GRID_START_Y),
                (pixel_x, GRID_START_Y + self.pixel_height),
                width=1
            )
        
        # Draw horizontal grid lines
        # For each row, draw a line from left to right
        for y in range(GRID_HEIGHT + 1):
            pixel_y = GRID_START_Y + (y * CELL_SIZE)
            pygame.draw.line(
                self.surface,
                GRID_COLOR,
                (GRID_START_X, pixel_y),
                (GRID_START_X + self.pixel_width, pixel_y),
                width=1
            )

    def grid_to_pixels(self, grid_x, grid_y):
        """
        Convert grid coordinates to pixel coordinates.
        Used when rendering objects at specific grid positions.
        
        Args:
            grid_x: X position in grid (0 to GRID_WIDTH-1)
            grid_y: Y position in grid (0 to GRID_HEIGHT-1)
        
        Returns:
            Tuple of (pixel_x, pixel_y) for top-left corner of that cell
        """
        pixel_x = GRID_START_X + (grid_x * CELL_SIZE)
        pixel_y = GRID_START_Y + (grid_y * CELL_SIZE)
        return pixel_x, pixel_y

class SnakeRender:
    """
    Renders snake segments for a specific player.
    Each player's snake is rendered with their assigned color.
    """
    
    def __init__(self, surface, grid):
        """
        Initialize snake renderer.
        
        Args:
            surface: Pygame surface to draw on
            grid: GameGrid instance for coordinate conversion
        """
        self.surface = surface
        self.grid = grid

    def draw_snake(self, snake_segments, player_id):
        """
        Draw a snake as a series of filled rectangles.
        
        Args:
            snake_segments: List of dicts [{"x": int, "y": int}, ...]
            player_id: ID of the player (0-3) for color selection (assigned by the server)
        """
        # Get color for current player
        color = PLAYERS_COLOR[player_id % len(PLAYERS_COLOR)]
        
        # Draw each segment of the snake
        for segment in snake_segments:
            # Extract x, y coordinates from segment dict
            grid_x = segment["x"]
            grid_y = segment["y"]
            
            # Convert to pixel coordinates
            pixel_x, pixel_y = self.grid.grid_to_pixels(grid_x, grid_y)
            
            # Draw filled rectangle for this segment
            # Leave 2 pixel border for visual separation between cells
            pygame.draw.rect(
                self.surface,
                color,
                (pixel_x + 2, pixel_y + 2, CELL_SIZE - 4, CELL_SIZE - 4)
            )

    def draw_direction_indicator(self, head_x, head_y, direction, player_id):
        """
        Draw a small triangle pointing in the direction the snake is moving.
        Helps visualize which direction the snake will go next.
        
        Args:
            head_x, head_y: Grid position of snake head
            direction: "UP", "DOWN", "LEFT", "RIGHT"
            player_id: Player ID for color
        """
        pixel_x, pixel_y = self.grid.grid_to_pixels(head_x, head_y)
        center_x = pixel_x + CELL_SIZE // 2
        center_y = pixel_y + CELL_SIZE // 2
        
        color = PLAYERS_COLOR[player_id % len(PLAYERS_COLOR)]
        offset = CELL_SIZE // 3
        # Define triangle points based on direction
        # Triangle points are offset from center by 8 pixels
        if direction == "UP":
            points = [
                (center_x, center_y - offset),      # Top point
                (center_x - offset, center_y + offset),  # Bottom left
                (center_x + offset, center_y + offset),  # Bottom right
            ]
        elif direction == "DOWN":
            points = [
                (center_x, center_y + offset),
                (center_x - offset, center_y - offset),
                (center_x + offset, center_y - offset),
            ]
        elif direction == "LEFT":
            points = [
                (center_x - offset, center_y),
                (center_x + offset, center_y - offset),
                (center_x + offset, center_y + offset),
            ]
        else:  # RIGHT
            points = [
                (center_x + offset, center_y),
                (center_x - offset, center_y - offset),
                (center_x - offset, center_y + offset),
            ]
        # draw triangle
        pygame.draw.polygon(self.surface, color, points)

class FoodRender:
    """Renders food items on the grid."""
    
    def __init__(self, surface, grid):
        self.surface = surface
        self.grid = grid    
    
    def draw_food(self, food_x, food_y):
        """
        Draw a food item as a circle.
        
        Args:
            food_x, food_y: Grid coordinates of food
        """
        # Convert to pixel coordinates
        pixel_x, pixel_y = self.grid.grid_to_pixels(food_x, food_y)
        
        # Calculate circle center (middle of the cell)
        center_x = pixel_x + CELL_SIZE // 2
        center_y = pixel_y + CELL_SIZE // 2
        
        pygame.draw.circle(
            self.surface,
            FOOD_COLOR,
            (center_x, center_y),
            radius=CELL_SIZE // 3
        )

class ScoreBoard:
    """Renders player scores and game status."""
    
    def __init__(self, surface):
        self.surface = surface
        
        # Create font for text rendering
        # pygame.font.SysFont(name, size)
        # Use None for default system font
        self.font_title = pygame.font.SysFont(None, 28, bold=True)
        self.font_player = pygame.font.SysFont(None, 20)  

    def draw_scoreboard(self, game_state):
        """
        Draw scoreboard showing all players, scores, and status.
        
        Args:
            game_state: Dictionary with "players" dict and other game info
        """
        # Draw title
        title = self.font_title.render("SCOREBOARD", True, WHITE)
        self.surface.blit(title, (SCOREBOARD_START_X, GRID_START_Y))
        
        # Draw horizontal separator line
        pygame.draw.line(
            self.surface,
            WHITE,
            (SCOREBOARD_START_X, GRID_START_Y + 35),
            (SCOREBOARD_START_X + 150, GRID_START_Y + 35),
            width=1
        )
        
        # Draw each player's info
        y_offset = GRID_START_Y + 50
        
        # Extract players from game state
        players = game_state.get("players", {})
        
        for player_id, player_data in sorted(players.items()):
            # Get player info
            print(f"[DEBUG] Player {player_id}: {player_data}")
        
            username = player_data.get("username", f"Player {player_id}")
            score = player_data.get("score", 0)
            alive = player_data.get("alive", True)
            pid = int(player_id)
            # Format status string
            status = "ALIVE" if alive else "DEAD"
            
            # Create player info text
            # f-string to format data into readable string
            player_text = f"{username}: {score} ({status})"
            
            # get player's color
            color = PLAYERS_COLOR[pid % len(PLAYERS_COLOR)]
        
            # Render text as surface (True = anti-aliased, COLOR_PLAYERS[...] = color)
            text_surface = self.font_player.render(player_text, True, color)
            
            # Draw text on main surface at position
            self.surface.blit(text_surface, (SCOREBOARD_START_X, y_offset))
            
            # Move down for next player
            y_offset += 30

    def draw_info_text(self, text, x, y):
        """
        Draw arbitrary text on screen.
        
        Args:
            text: String to display
            x, y: Pixel coordinates
        """
        text_surface = self.font_player.render(text, True, WHITE)
        self.surface.blit(text_surface, (x, y))

class GameUI:
    """
    Main Pygame window and event loop.
    Organizes all UI components and handles user input.
    """
    
    def __init__(self, client=None):
        """
        Initialize game screen.
        
        Args:
            client: Client instance for networking 
        """
        # Initialize Pygame
        pygame.init()
        
        # Create game window (surface to draw all components on)
        self.screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
        
        # Set window title
        pygame.display.set_caption("Multiplayer Snake Game")
        
        # Create clock for frame rate control
        self.clock = pygame.time.Clock()
        
        # Reference to client (for sending moves)
        self.client = client
        
        # UI component instances
        self.grid = GameGrid(self.screen)
        self.snake_renderer = SnakeRender(self.screen, self.grid)
        self.food_renderer = FoodRender(self.screen, self.grid)
        self.scoreboard = ScoreBoard(self.screen)
        
        
        # Current game state (updated from server)
        self.game_state = self.client.game_state
        
        # Current player's direction (set by keyboard input)
        self.player_direction = "RIGHT"
        
        # Running flag
        self.running = True
    
    def handle_input(self):
        """
        Handle keyboard input and window events.
        """
        # pygame.event.get() returns list of all events since last call
        for event in pygame.event.get():
            # Handle window close button
            if event.type == pygame.QUIT:
                self.running = False
            
            # Handle key presses
            if event.type == pygame.KEYDOWN:
                # Arrow keys for movement
                if event.key == pygame.K_UP:
                    self.player_direction = "UP"
                    if self.client is not None:
                        self.send_move_to_server()
                
                elif event.key == pygame.K_DOWN:
                    self.player_direction = "DOWN"
                    if self.client is not None:
                        self.send_move_to_server()
                
                elif event.key == pygame.K_LEFT:
                    self.player_direction = "LEFT"
                    if self.client is not None:
                        self.send_move_to_server()
                
                elif event.key == pygame.K_RIGHT:
                    self.player_direction = "RIGHT"
                    if self.client is not None:
                        self.send_move_to_server()
                
                # Quit game with Q key
                elif event.key == pygame.K_q:
                    self.running = False
    
    def send_move_to_server(self):
        """
        Send current direction to server via client.
        Called when user presses arrow key.
        """
        if self.client:
            self.client.make_move(self.player_direction)
    
    def update(self):
        """
        Update game state (received from server).
        Called once per frame before rendering.
        """
        if self.client is not None:
            if self.client.game_state:
                self.game_state = self.client.game_state

    def render(self):
        """
        Draw all game elements on screen.
        Called once per frame.
        """
        # Clear screen with black background
        self.screen.fill(BLACK)
        
        # Draw game grid
        self.grid.draw()
        
        # Draw food
        food = self.game_state.get("food", {})
        self.food_renderer.draw_food(food.get("x", 0), food.get("y", 0))
        
        # Draw all player snakes
        players = self.game_state.get("players", {})
        for player_id, player_data in players.items():
            # Get snake segments from player data
            segments = player_data.get("segments", [])
            
            player_id = int(player_id)
            # Draw snake
            self.snake_renderer.draw_snake(segments[1:], player_id)
            
            # Draw direction indicator on head
            if segments:
                head = segments[0]
                self.snake_renderer.draw_direction_indicator(
                    head["x"], head["y"],
                    player_data.get("direction", "RIGHT"),
                    player_id
                )
        
        # Draw scoreboard
        self.scoreboard.draw_scoreboard(self.game_state)
        
        # Draw help text at bottom
        help_text = "Controls: ARROW KEYS to move | Q to quit"
        self.scoreboard.draw_info_text(help_text, GRID_START_X, WIN_HEIGHT - 30)
        
        # Update display (updates entire screen)
        pygame.display.flip()
    
    def run(self):
        """
        Main game loop.
        Handles events, updates, and rendering each frame.
        """
        while self.running:
            # Handle user input
            self.handle_input()
            
            # Update game state
            self.update()
            
            # Draw everything
            self.render()
            
            # Control frame rate
            # clock.tick(FPS) sleeps as needed to maintain constant frame rate
            self.clock.tick(FPS)
        
        # Cleanup
        pygame.quit()
    
    def close(self):
        """Stop the game loop."""
        self.running = False

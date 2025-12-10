import pygame
import threading
import time
from client import Client
from snake_game import WHITE, BLACK, GRAY, WIN_HEIGHT, WIN_WIDTH, FPS, GameUI

LIGHT_GRAY = (200, 200, 200)
DARK_GRAY = (80, 80, 80)

class LoginScreen:
    """
    Login screen where users enter username and join the game.
    This screen appears before the game starts.
    """
    
    def __init__(self):
        """Initialize login screen."""
        # Initialize Pygame
        pygame.init()
        
        # Create window
        self.screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
        pygame.display.set_caption("Multiplayer Snake Game - Login")
        
        # Clock for frame rate
        self.clock = pygame.time.Clock()
        
        # Fonts for rendering text
        self.font_title = pygame.font.SysFont(None, 48, bold=True)
        self.font_label = pygame.font.SysFont(None, 28)
        self.font_button = pygame.font.SysFont(None, 24)
        self.font_error = pygame.font.SysFont(None, 20)
        
        # Input field for username
        self.username = ""
        
        # Button rectangle for join button
        # pygame.Rect(x, y, width, height)
        button_width = 200
        button_height = 50
        self.join_button = pygame.Rect(
            WIN_WIDTH // 2 - button_width // 2,  # Centered X
            WIN_HEIGHT // 2 + 100,                # Below input field
            button_width,
            button_height
        )
        
        # Status message (for errors, connecting, etc.)
        self.status_message = ""
        self.status_color = WHITE
        
        # Track if user clicked join button
        self.joining = False
        
        # Client reference (will be set after joining)
        self.client = None
        
        # Flag to know when to exit login screen
        self.login_complete = False
        
        # Running flag
        self.running = True
    
    def handle_events(self):
        """
        Handle mouse clicks and keyboard input on login screen.
        """
        for event in pygame.event.get():
            # Handle window close
            if event.type == pygame.QUIT:
                self.running = False
                self.login_complete = False  # Signal failure to exit
            
            # Handle key presses
            elif event.type == pygame.KEYDOWN:
                # Backspace: delete last character from username
                if event.key == pygame.K_BACKSPACE:
                    # Remove last character: self.username[:-1] means "all but last"
                    self.username = self.username[:-1]
                
                # Enter key: same as clicking join button
                elif event.key == pygame.K_RETURN:
                    self.try_join()
                
                # Regular characters: add to username
                elif event.unicode.isprintable():
                    # Limit username to 20 characters
                    if len(self.username) < 20:
                        self.username += event.unicode
            
            # Handle mouse clicks
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Check if user clicked the join button
                # rect.collidepoint(x, y) returns True if point is inside rectangle
                if self.join_button.collidepoint(event.pos):
                    self.try_join()
    
    def try_join(self):
        """
        Attempt to join the game with entered username.
        Validates input and connects to server.
        """
        # Validate username
        if not self.username.strip():
            # Username is empty
            self.status_message = "Please enter a username"
            self.status_color = (255, 100, 100)  # Red
            return
        
        # Check if already trying to join (prevent double-click)
        if self.joining:
            return
        
        # Mark as joining (prevent multiple attempts)
        self.joining = True
        self.status_message = "Connecting to server..."
        self.status_color = WHITE
        
        # Start connection in a separate thread
        # This way the UI doesn't freeze while waiting for server response
        connect_thread = threading.Thread(
            target=self.connect_to_server,
            daemon=True
        )
        connect_thread.start()
    
    def connect_to_server(self):
        """
        Connect to server and join game.
        Runs in background thread to keep UI responsive.
        """
        try:
            # Create client instance
            # Default server is localhost (127.0.0.1) on port 9999
            self.client = Client(server_host='127.0.0.1', server_port=9999)
            
            # Send join request to server with username
            # join_game() sends INIT packet and waits for ACK
            success = self.client.join_game(self.username)
            
            if success:
                # Successfully joined!
                self.status_message = f"Welcome, {self.username}!"
                self.status_color = (100, 255, 100)  # Green
                
                # Small delay so user sees the success message
                time.sleep(0.5)
                
                # Signal that login is complete and we can move to game
                self.login_complete = True
            else:
                # Server connection failed
                self.status_message = "Failed to connect to server"
                self.status_color = (255, 100, 100)  # Red
                self.joining = False
        
        except Exception as e:
            # Any error during connection
            self.status_message = f"Error: {str(e)[:30]}"  # Truncate long errors
            self.status_color = (255, 100, 100)
            self.joining = False
    
    def render(self):
        """Draw login screen elements."""
        # Clear screen with black background
        self.screen.fill(BLACK)
        
        # Draw title
        title = self.font_title.render("MULTIPLAYER SNAKE", True, WHITE)
        # Calculate position to center horizontally
        title_rect = title.get_rect(center=(WIN_WIDTH // 2, 100))
        self.screen.blit(title, title_rect)
        
        # Draw username label
        label = self.font_label.render("Enter Username:", True, WHITE)
        self.screen.blit(label, (WIN_WIDTH // 2 - 150, 200))
        
        # Draw username input field (rectangle background)
        input_rect = pygame.Rect(
            WIN_WIDTH // 2 - 150,   # X position
            250,                    # Y position
            300,                    # Width
            40                      # Height
        )
        
        # Draw rectangle border
        pygame.draw.rect(self.screen, LIGHT_GRAY, input_rect)
        
        # Draw username text in the input field
        username_text = self.font_label.render(self.username, True, BLACK)
        self.screen.blit(username_text, (input_rect.x + 10, input_rect.y + 5))
        
        # Draw cursor (blinking line) if input field is active
        # Use time.time() % 1 to create blinking effect (flashes every second)
        if int(time.time() * 2) % 2 == 0:  # Blink every 0.5 seconds
            cursor_x = input_rect.x + 10 + username_text.get_width()
            pygame.draw.line(
                self.screen,
                BLACK,
                (cursor_x, input_rect.y + 5),
                (cursor_x, input_rect.y + 35),
                width=2
            )
        
        # Draw join button
        button_color = DARK_GRAY if self.joining else GRAY
        pygame.draw.rect(self.screen, button_color, self.join_button)
        
        # Draw button border
        pygame.draw.rect(self.screen, WHITE, self.join_button, width=2)
        
        # Draw button text
        button_text = "JOINING..." if self.joining else "JOIN GAME"
        button_label = self.font_button.render(button_text, True, WHITE)
        button_label_rect = button_label.get_rect(center=self.join_button.center)
        self.screen.blit(button_label, button_label_rect)
        
        # Draw status message (error/success message)
        if self.status_message:
            status_text = self.font_error.render(self.status_message, True, self.status_color)
            status_rect = status_text.get_rect(center=(WIN_WIDTH // 2, WIN_HEIGHT - 100))
            self.screen.blit(status_text, status_rect)
        
        # Draw instructions at bottom
        instructions = self.font_error.render("Press ENTER or click JOIN to connect", True, LIGHT_GRAY)
        self.screen.blit(instructions, (WIN_WIDTH // 2 - 200, WIN_HEIGHT - 50))
        
        # Update display
        pygame.display.flip()
    
    def run(self):
        """
        Main login loop - keep displaying until user joins successfully.
        """
        while self.running and not self.login_complete:
            # Handle user input (typing, clicking)
            self.handle_events()
            
            # Draw the screen
            self.render()
            
            # Control frame rate
            self.clock.tick(FPS)
        
        # Return client if login successful, None if closed window
        if self.login_complete:
            return self.client
        else:
            return None


def stop(self):
    self.running = False


def automated_play(game, duration=15):
    """
    Simulate automated gameplay for network test automation.
    Moves RIGHT every second.
    """
    start_time = time.time()
    # Try to post pygame events; if video system isn't initialized (headless),
    # fall back to calling the client's API directly (safer for automation).
    try:
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
    except Exception:
        # ignore if event system not ready
        pass

    while time.time() - start_time < duration:
        try:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
        except pygame.error:
            # Headless or video system not initialized; call client move directly.
            try:
                if hasattr(game, 'client') and game.client:
                    game.client.make_move('UP')
            except Exception:
                pass
        except Exception:
            # Other exceptions from pygame.event.post - ignore and fallback
            try:
                if hasattr(game, 'client') and game.client:
                    game.client.make_move('UP')
            except Exception:
                pass

        time.sleep(1)

        try:
            pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_RIGHT))
        except pygame.error:
            try:
                if hasattr(game, 'client') and game.client:
                    # No direct UP/RIGHT mapping needed for KEYUP; send a no-op or alternate move
                    pass
            except Exception:
                pass
        except Exception:
            pass

        time.sleep(1)
    print("[Automated] Finished automated gameplay.")

def auto_login():
    login = LoginScreen()
    auto_user = os.getenv('AUTO_USERNAME')
    if auto_user:
        login.username = auto_user
        login.try_join()
        timeout = 10
        start_time = time.time()
        while not login.login_complete and time.time() - start_time < timeout:
            login.handle_events()
            login.render()
            login.clock.tick(FPS)
        if not login.login_complete:
            print("Auto-login failed or timeout")
            pygame.quit()
            return None
        return login.client
    else:
        return login.run()

if __name__ == "__main__":
    import os
    import time

    client = auto_login()
    if client is None:
        print("Login failed or cancelled")
        pygame.quit()
        exit()

    game = GameUI(client)

    if os.getenv("AUTOMATE") == "1":
        import threading

        # Start ONLY the automation in a background thread
        t = threading.Thread(target=automated_play, args=(game, 5), daemon=True)
        t.start()

        # Run the game loop on the MAIN thread (same one that created the window)
        game.run()

        # Wait for automation to finish (it likely finished already)
        t.join()

        # game.run() calls pygame.quit() on exit; if not, you can still call:
        # pygame.quit()
    else:
        game.run()
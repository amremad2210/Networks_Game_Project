import socket
import sys
import os

# --- Add this block at the very top ---
# It lets Python find packet.py from the repo root
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import threading
import time
import json
import pygame
from packet import Packet, MSG_INIT, MSG_EVENT, MSG_SNAPSHOT, MSG_END, MSG_ACK
from state import State
from logging_utils import log_message

SERVER_IP = "127.0.0.1"
PORT = 9999
STATE_TICK_RATE = 1  # updates per second
SNAPSHOT_RATE = 20  # snapshots per second

class Server:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((SERVER_IP, PORT))

        self.state = State()
        self.clients = {}  # username -> (ip, port)
        self.snapshot_id = 0
        self.running = True

        self.clock = pygame.time.Clock()
        
        self._state_interval = 1.0 / STATE_TICK_RATE if STATE_TICK_RATE else 0
        self._snapshot_interval = 1.0 / SNAPSHOT_RATE if SNAPSHOT_RATE else 0

        self.state_lock = threading.Lock() # used for safe threading
        self.clients_lock = threading.Lock() # used for safe threading

        log_message("INFO", "Server", f"Listening on {SERVER_IP}:{PORT}")

    def listen(self):
        """Listens for UDP messages from clients"""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)
                packet = Packet.decode_packet(data)
                if not packet:
                    continue
                
                # handle threading safely
                with self.state_lock:
                    self.process_packet(packet, addr)
            except Exception as e:
                log_message("ERROR", "Server", str(e))

    def process_packet(self, packet, addr):
        """Handles messages from clients"""
        if packet.msg_type == MSG_INIT:
            # Decode username (can be JSON or raw string)
            try:
                payload = packet.payload.decode()
                data = json.loads(payload)
                username = data.get("username", payload)
            except Exception:
                username = packet.payload.decode()

            # Register player
            with self.clients_lock:
                self.clients[username] = addr
            self.state.add_player(username)
            log_message("INFO", "Server", f"{username} joined from {addr}")

            # --- NEW: Send ACK packet back ---
            ack_payload = json.dumps({"player_id": username}).encode("utf-8")
            ack_packet = Packet.encode_packet(
                MSG_ACK,
                0,  # snapshot_id (unused here)
                0,  # seq_num (unused here)
                int(time.time() * 1000),
                len(ack_payload),
                ack_payload
            )
            self.sock.sendto(ack_packet, addr)
            log_message("INFO", "Server", f"Sent ACK to {username}")

        elif packet.msg_type == MSG_EVENT:
            data = json.loads(packet.payload.decode())
            username = data.get("player_id") or data.get("username")
            direction = data["direction"]
            self.state.update_player_direction(username, direction)

        elif packet.msg_type == MSG_END:
            username = packet.payload.decode()
            self.state.remove_player(username)
            with self.clients_lock:
                if username in self.clients:
                    del self.clients[username]
            log_message("INFO", "Server", f"{username} disconnected")


    def broadcast_snapshot(self):
        """Sends the current game state to all clients"""
        with self.state_lock:
            state_json = self.state.to_json().encode()
        self.snapshot_id += 1
        packet_bytes = Packet.encode_packet(
            MSG_SNAPSHOT, self.snapshot_id, 0, int(time.time()*1000),
            len(state_json), state_json
        )
        with self.clients_lock:
            for addr in self.clients.values():
                self.sock.sendto(packet_bytes, addr)
                # DEBUG: Print what server is sending
                #print("[SERVER] Sending snapshot")
                print(f"[Sending State] {json.dumps(json.loads(state_json), indent=2)[:500]}")  # Print first 500 chars

    def run(self):
        """Main loop"""
        threading.Thread(target=self.listen, daemon=True).start() #reciever thread
        last_state_update = time.monotonic()
        last_snapshot_broadcast = time.monotonic()
        max_loop_rate = max(STATE_TICK_RATE, SNAPSHOT_RATE, 60)  # at least 60Hz for smooth pygame
        
        while self.running:

            now = time.monotonic()

            if self._state_interval:
                while now - last_state_update >= self._state_interval:
                    with self.state_lock:
                        self.state.update_state()
                    last_state_update += self._state_interval
            else:
                with self.state_lock:
                    self.state.update_state()

            if self._snapshot_interval:
                while now - last_snapshot_broadcast >= self._snapshot_interval:
                    self.broadcast_snapshot()
                    last_snapshot_broadcast += self._snapshot_interval
            else:
                self.broadcast_snapshot()

            self.clock.tick(max_loop_rate)

        pygame.quit()
        log_message("INFO", "Server", "Shutting down...")

if __name__ == "__main__":
    Server().run()

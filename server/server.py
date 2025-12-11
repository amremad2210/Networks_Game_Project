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
import csv
import importlib
from common.packet import Packet, MSG_INIT, MSG_EVENT, MSG_SNAPSHOT, MSG_END, MSG_ACK
from state import State
from logging_utils import log_message

psutil_spec = importlib.util.find_spec("psutil")
psutil = importlib.import_module('psutil') if psutil_spec else None

SERVER_IP = "127.0.0.1"
PORT = 9999
STATE_TICK_RATE = 3  # updates per second
SNAPSHOT_RATE = 20  # snapshots per second

class Server:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((SERVER_IP, PORT))

        self.state = State()
        # username -> { addr: (ip,port), expected_seq: int, ready: bool, last_ack_seq: int }
        self.clients = {}
        self.snapshot_id = 0
        self.running = True

        self.clock = pygame.time.Clock()
        
        self._state_interval = 1.0 / STATE_TICK_RATE if STATE_TICK_RATE else 0
        self._snapshot_interval = 1.0 / SNAPSHOT_RATE if SNAPSHOT_RATE else 0

        self.state_lock = threading.Lock() # used for safe threading
        self.clients_lock = threading.Lock() # used for safe threading

        log_message("INFO", "Server", f"Listening on {SERVER_IP}:{PORT}")
        self.log_file = None
        self.csv_writer = None
        self.setup_metrics_logging()

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

            # Register client record but do NOT add to game state until client sends READY ack
            with self.clients_lock:
                self.clients[username] = {
                    "addr": addr,
                    "expected_seq": 1,
                    "ready": False,
                    "last_ack_seq": -1
                }
            log_message("INFO", "Server", f"Registered {username} from {addr} (awaiting READY)")

            # Send INIT ACK back with ack_for field
            server_timestamp = int(time.time() * 1000)
            ack_payload = json.dumps({
                "ack_for": "init",
                "player_id": username,
                "server_snapshot_id": self.snapshot_id,
                "server_time": server_timestamp
            }).encode("utf-8")
            ack_packet = Packet.encode_packet(
                MSG_ACK,
                self.snapshot_id,
                0,
                server_timestamp,
                len(ack_payload),
                ack_payload
            )
            self.sock.sendto(ack_packet, addr)
            log_message("INFO", "Server", f"Sent INIT ACK to {username}")

        elif packet.msg_type == MSG_ACK:
            # Handle ACK messages from clients (READY or event-level ACKs)
            try:
                payload_text = packet.payload.decode('utf-8') if packet.payload_len else ""
                info = json.loads(payload_text) if payload_text.startswith('{') else {}
            except Exception:
                info = {}

            ack_for = info.get('ack_for')
            if ack_for == 'ready':
                player_id = info.get('player_id')
                if not player_id:
                    return
                with self.clients_lock:
                    client = self.clients.get(player_id)
                    if client:
                        client['ready'] = True
                        client['addr'] = addr
                        log_message("INFO", "Server", f"{player_id} marked READY from {addr}")
                        # Now add player to game state
                        self.state.add_player(player_id)
            else:
                # Other ACK types (e.g., event ACKs) can be logged; server is authoritative so no-op
                pass

        elif packet.msg_type == MSG_EVENT:
            try:
                data = json.loads(packet.payload.decode())
            except Exception:
                log_message("ERROR", "Server", "Malformed EVENT payload")
                return

            username = data.get("player_id") or data.get("username")
            direction = data.get("direction")

            if not username:
                log_message("WARNING", "Server", "EVENT without username")
                return

            with self.clients_lock:
                client = self.clients.get(username)

            if not client:
                log_message("WARNING", "Server", f"Unknown client {username} sent EVENT")
                return

            if not client.get('ready'):
                log_message("WARNING", "Server", f"Received EVENT from {username} before READY; ignoring")
                return

            seq = packet.seq_num
            expected = client.get('expected_seq', 0)

            server_timestamp = int(time.time() * 1000)

            if seq == expected:
                # Accept and process
                self.state.update_player_direction(username, direction)
                client['expected_seq'] = expected + 1
                client['last_ack_seq'] = seq
                # send ACK for this event
                ack_payload = json.dumps({"ack_for": "event", "player_id": username, "seq_num": seq}).encode('utf-8')
                ack_packet = Packet.encode_packet(MSG_ACK, self.snapshot_id, seq, server_timestamp, len(ack_payload), ack_payload)
                self.sock.sendto(ack_packet, client['addr'])
                log_message("INFO", "Server", f"Processed EVENT from {username} seq={seq}; sent ACK")

            elif seq < expected:
                # Duplicate — re-ACK
                ack_payload = json.dumps({"ack_for": "event", "player_id": username, "seq_num": seq}).encode('utf-8')
                ack_packet = Packet.encode_packet(MSG_ACK, self.snapshot_id, seq, server_timestamp, len(ack_payload), ack_payload)
                self.sock.sendto(ack_packet, client['addr'])
                log_message("INFO", "Server", f"Duplicate EVENT from {username} seq={seq}; re-ACKed")

        elif packet.msg_type == MSG_END:
            # Handle client disconnect - support both JSON and plain text
            try:
                payload_text = packet.payload.decode('utf-8') if packet.payload_len else ""
                
                # Try JSON first (new format)
                if payload_text.strip().startswith('{'):
                    data = json.loads(payload_text)
                    username = data.get('username') or data.get('player_id')
                else:
                    # Fall back to plain text (old format)
                    username = payload_text
            
            except Exception as e:
                # Last resort: just decode
                username = packet.payload.decode() if packet.payload else None
                log_message("ERROR", "Server", f"Error parsing MSG_END: {e}")
    
            if username:
                log_message("INFO", "Server", f"{username} sent disconnect message")
                self.state.remove_player(username)
                with self.clients_lock:
                    if username in self.clients:
                        del self.clients[username]
                log_message("INFO", "Server", f"{username} disconnected and removed")


    def send_end_message(self, username):
        """Send END message to a dead player and remove from clients list"""
        with self.clients_lock:
            client = self.clients.pop(username, None)
        
        if not client:
            return
        
        try:
            server_timestamp = int(time.time() * 1000)
            end_payload = json.dumps({
                "game_over": True,
                "winner": False,
                "message": "You are dead!"
            }).encode('utf-8')
            
            end_packet = Packet.encode_packet(
                MSG_END, 0, 0, server_timestamp,
                len(end_payload), end_payload
            )
            self.sock.sendto(end_packet, client['addr'])
            log_message("INFO", "Server", f"Sent END message to {username}")
        except Exception as e:
            log_message("ERROR", "Server", f"Failed to send END to {username}: {e}")

    def broadcast_snapshot(self):
        """Sends the current game state to all clients"""
        with self.state_lock:
            state_json = self.state.to_json().encode()
        self.snapshot_id += 1
        server_timestamp = int(time.time()*1000)
        packet_bytes = Packet.encode_packet(
            MSG_SNAPSHOT, self.snapshot_id, 0, server_timestamp,
            len(state_json), state_json
        )
        self.log_metrics(self.snapshot_id, 0, server_timestamp)
            
        with self.clients_lock:
            for client in self.clients.values():
                if client.get('ready'):
                    self.sock.sendto(packet_bytes, client['addr'])
                # DEBUG: Print what server is sending
                #print("[SERVER] Sending snapshot")
                #print(f"[Sending State] {json.dumps(json.loads(state_json), indent=2)[:500]}")  # Print first 500 chars

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
                        # Get list of dead players before update
                        players_before = set(self.state.players.keys())
                        self.state.update_state()
                        players_after = set(self.state.players.keys())
                        # Find newly dead players
                        newly_dead = players_before - players_after
                        for dead_player in newly_dead:
                            self.send_end_message(dead_player)
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

    # for tests and logging
    def _get_cpu_percent(self):
        if not self._process:
            return 0.0

        try:
            return round(self._process.cpu_percent(interval=None), 2)
        except Exception:
            return 0.0
        
    def _extract_player_positions(self):
        """Extract all player positions from current state"""
        positions = {}
        with self.state_lock:
            for username, player in self.state.players.items():
                if player.alive and player.segments:
                    head = player.segments[0]
                    # Convert [y, x] to {x, y} format
                    positions[username] = {"x": head[1], "y": head[0]}
        return json.dumps(positions)
    
    def setup_metrics_logging(self):
        os.makedirs('logs/server_logs', exist_ok=True)
        self.metrics_file = open('logs/server_logs/server_metrics.csv', 'w', newline='')
        self.metrics_writer = csv.writer(self.metrics_file)
        self.metrics_writer.writerow([
            'snapshot_id', 'seq_num', 'server_timestamp_ms',
            'cpu_percent', 'players_pos'
        ])
        
        self._process = None
        if psutil is not None:
            try:
                self._process = psutil.Process()
                # Prime cpu_percent so that subsequent calls return deltas
                self._process.cpu_percent(interval=None)
            except Exception:
                self._process = None

    def log_metrics(self, snapshot_id, seq_num, server_timestamp):
        cpu_percent = self._get_cpu_percent()
        players_position = self._extract_player_positions()

        self.metrics_writer.writerow([
            snapshot_id,
            seq_num,
            server_timestamp,
            cpu_percent,
            players_position
            
        ])
        self.metrics_file.flush()
    # ---------------------------------------------------

if __name__ == "__main__":
    Server().run()

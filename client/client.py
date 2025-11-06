import socket
import threading
import time
import json
import csv
import sys
import os
import math
import copy
import importlib
from datetime import datetime

psutil_spec = importlib.util.find_spec("psutil")
psutil = importlib.import_module('psutil') if psutil_spec else None

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from common.packet import Packet, MSG_INIT, MSG_EVENT, MSG_SNAPSHOT, MSG_ACK, MSG_END

class Client():
    def __init__(self, server_host='127.0.0.1', server_port=9999):
        self.server_host = server_host
        self.server_port = server_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(5.0)

        self.client_seq_num = 0
        self.player_id = None
        self.username = None
        self.connected = False
        self.server_address = None

        # Game state for snapshots
        self.game_state = {
            'players': {},
            'food': {},
            'grid_size': 20,
            'game_over': False,
            'winner': None
        }
        self.snapshot_id = 0

        # Logging
        self.log_file = None
        self.csv_writer = None
        self.setup_logging()
        self.setup_metrics_logging()

    def setup_logging(self):
        """Setup CSV logging for messages"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = open(f'client_log_{timestamp}.csv', 'w', newline='')
        self.csv_writer = csv.writer(self.log_file)
        self.csv_writer.writerow([
            'timestamp', 'client_id', 'msg_type', 'seq_num', 'snapshot_id',
            'server_timestamp', 'payload_size', 'direction'
        ])

    # ----------- Metrics Logging Additions ------------
    def setup_metrics_logging(self):
        self.metrics_file = open('metrics.csv', 'w', newline='')
        self.metrics_writer = csv.writer(self.metrics_file)
        self.metrics_writer.writerow([
            'client_id', 'snapshot_id', 'seq_num', 'server_timestamp_ms',
            'recv_time_ms', 'latency_ms', 'jitter_ms',
            'perceived_position_error', 'cpu_percent', 'bandwidth_per_client_kbps'
        ])
        self.metrics_last_latency = None
        self._last_snapshot_state = None
        self._last_snapshot_recv_time = None
        self._direction_vectors = {
            'UP': (0, -1),
            'DOWN': (0, 1),
            'LEFT': (-1, 0),
            'RIGHT': (1, 0)
        }
        self._process = None
        if psutil is not None:
            try:
                self._process = psutil.Process()
                # Prime cpu_percent so that subsequent calls return deltas
                self._process.cpu_percent(interval=None)
            except Exception:
                self._process = None



    def log_metrics(
        self, packet,
        perceived_position_error=0.0,
        cpu_percent=0.0,
        bandwidth_kbps=0.0
    ):
        recv_time_ms = int(time.time() * 1000)
        server_timestamp_ms = getattr(packet, "timestamp", 0)
        latency_ms = recv_time_ms - server_timestamp_ms
        if self.metrics_last_latency is None:
            jitter_ms = 0
        else:
            jitter_ms = abs(latency_ms - self.metrics_last_latency)
        self.metrics_last_latency = latency_ms
        self.metrics_writer.writerow([
            self.player_id,
            getattr(packet, "snapshot_id", 0),
            getattr(packet, "seq_num", 0),
            server_timestamp_ms,
            recv_time_ms,
            latency_ms,
            jitter_ms,
            perceived_position_error,
            cpu_percent,
            bandwidth_kbps
        ])
        self.metrics_file.flush()
    # ---------------------------------------------------

    def _find_player_state(self, state):
        if not isinstance(state, dict):
            return None, None

        players = state.get('players') or {}
        for player in players.values():
            if player.get('username') == self.username:
                segments = player.get('segments') or []
                head = segments[0] if segments else None
                direction = player.get('direction')
                return head, direction
        return None, None

    def _calculate_perceived_position_error(self, previous_state, current_state):
        if not previous_state or not current_state or not self.username:
            return 0.0

        prev_head, prev_direction = self._find_player_state(previous_state)
        current_head, _ = self._find_player_state(current_state)

        if not prev_head or not current_head or not prev_direction:
            return 0.0

        movement = self._direction_vectors.get(prev_direction.upper())
        if not movement:
            return 0.0

        predicted_x = prev_head.get('x', 0) + movement[0]
        predicted_y = prev_head.get('y', 0) + movement[1]
        actual_x = current_head.get('x', 0)
        actual_y = current_head.get('y', 0)

        return round(math.hypot(actual_x - predicted_x, actual_y - predicted_y), 4)

    def _get_cpu_percent(self):
        if not self._process:
            return 0.0

        try:
            return round(self._process.cpu_percent(interval=None), 2)
        except Exception:
            return 0.0

    def _calculate_bandwidth(self, raw_size):
        now = time.time()
        if self._last_snapshot_recv_time is None:
            self._last_snapshot_recv_time = now
            return 0.0

        elapsed = now - self._last_snapshot_recv_time
        self._last_snapshot_recv_time = now

        if elapsed <= 0 or not raw_size:
            return 0.0

        # Convert bytes per second to kilobits per second
        kbps = (raw_size * 8) / (elapsed * 1000.0)
        return round(kbps, 3)




    def log_msg(self, packet, direction=None):
        """Log all messages to CSV file"""
        if self.csv_writer and packet:
            self.csv_writer.writerow([
                datetime.now().isoformat(),
                self.player_id,
                packet.msg_type,
                packet.seq_num,
                packet.snapshot_id,
                packet.timestamp,
                packet.payload_len,
                direction
            ])
            self.log_file.flush()

    def join_game(self, username):
        """Send INIT message to server and wait for ACK"""
        self.username = username

        payload_data = json.dumps({'username': username}).encode('utf-8')
        payload_len = len(payload_data)

        timestamp = int(time.time() * 1000)
        packet_data = Packet.encode_packet(
            MSG_INIT, 0, self.client_seq_num, timestamp, payload_len, payload_data
        )

        server_addr = (self.server_host, self.server_port)
        self.sock.sendto(packet_data, server_addr)
        self.client_seq_num += 1

        try:
            data, addr = self.sock.recvfrom(4096)
            packet = Packet.decode_packet(data)

            if packet and packet.msg_type == MSG_ACK:
                ack_data = json.loads(packet.payload.decode('utf-8'))
                self.player_id = ack_data.get('player_id')
                self.connected = True

                #start background receive thread
                self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
                self.receive_thread.start()
                return True

        except socket.timeout:
            print("Timeout: No response from server")
        except Exception as e:
            print(f"Error: {e}")

        return False

    def make_move(self, direction):
        """Send EVENT message to server"""
        if not self.connected:
            return False
       
        move_data = {
            # server expects 'username' in current server implementation
            'username': self.username,
            'direction': direction,
            'timestamp': int(time.time() * 1000)
        }

        payload_data = json.dumps(move_data).encode('utf-8')
        payload_len = len(payload_data)

        timestamp = int(time.time() * 1000)
        packet_data = Packet.encode_packet(
            MSG_EVENT, 0, self.client_seq_num, timestamp, payload_len, payload_data
        )

        self.sock.sendto(packet_data, (self.server_host, self.server_port))

        # Log EVENT message
        event_packet = Packet(MSG_EVENT, 0, self.client_seq_num, timestamp, payload_len, payload_data)
        self.log_msg(event_packet, "SENT")

        self.client_seq_num += 1
        return True

    def handle_snapshot(self, packet, raw_size):
        """
        Handles incoming SNAPSHOT packets from the server.
        Decodes the JSON payload and updates the client's game state.
        Older snapshots (by snapshot_id) are ignored.
        """
        try:
            payload = json.loads(packet.payload.decode('utf-8'))
            snapshot_id = packet.snapshot_id
            server_timestamp = packet.timestamp
            previous_state = copy.deepcopy(self._last_snapshot_state) if self._last_snapshot_state else None


            if hasattr(self, 'last_snapshot_id') and snapshot_id <= self.last_snapshot_id:
                print(f"[Client] Ignored outdated snapshot {snapshot_id}")
                return

            self.last_snapshot_id = snapshot_id
            self.game_state = payload
            self.last_server_timestamp = server_timestamp

           # print(f"[Client] Updated game state from snapshot {snapshot_id} "
            #      f"({len(payload)} keys, timestamp={server_timestamp})")

            self.log_msg(packet, "RECEIVED")

            # LOG METRICS HERE (add real error/cpu/bw if available)
            perceived_error = self._calculate_perceived_position_error(previous_state, payload)
            cpu_percent = self._get_cpu_percent()
            bandwidth_kbps = self._calculate_bandwidth(raw_size)
            self.log_metrics(
                packet,
                perceived_position_error=perceived_error,
                cpu_percent=cpu_percent,
                bandwidth_kbps=bandwidth_kbps
            )

            self._last_snapshot_state = copy.deepcopy(payload)

        except json.JSONDecodeError:
            print("[Client] Failed to decode SNAPSHOT payload (invalid JSON).")
        except Exception as e:
            print(f"[Client] Error handling SNAPSHOT: {e}")

        pass

    def receive_messages(self):
        """Background receive loop"""
        self.sock.settimeout(0.25)
        self._rx_running = True
        print("[Client] Starting receive loop...")

        while self._rx_running:
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as e:
                print(f"[Client] Receive error: {e}")
                continue

            packet = Packet.decode_packet(data)
            if not packet:
                continue

            if self.server_address is None:
                self.server_address = addr

            if packet.msg_type == MSG_SNAPSHOT:
                self.handle_snapshot(packet, len(data))
            elif packet.msg_type == MSG_ACK:
                try:
                    _ = packet.payload.decode('utf-8') if packet.payload_len else ""
                except Exception:
                    pass
                self.log_msg(packet, "RECEIVED")
            elif packet.msg_type == MSG_END:
                try:
                    payload_text = packet.payload.decode('utf-8') if packet.payload_len else ""
                    if payload_text.strip().startswith('{'):
                        info = json.loads(payload_text)
                        self.game_state['game_over'] = bool(info.get('game_over', True))
                        self.game_state['winner'] = info.get('winner')
                    else:
                        self.game_state['game_over'] = True
                except Exception:
                    self.game_state['game_over'] = True

                print("[Client] Received END message from server. Game over.")
                self.log_msg(packet, "RECEIVED")
            else:
                print(f"[Client] Received unknown packet type: {packet.msg_type}")
                self.log_msg(packet, "RECEIVED")
        print("[Client] Receive loop terminated.")
        pass

    def stop(self):
        """Gracefully stop receiving and close resources."""
        try:
            self._rx_running = False
        except AttributeError:
            pass
        try:
            self.sock.close()
        finally:
            if self.log_file:
                self.log_file.close()
            try:
                self.metrics_file.close()
            except Exception:
                pass

    def sync_game(self):
        pass

if __name__ == "__main__":
    player= Client()
    # player.join_game("Jana")
    # player.stop()

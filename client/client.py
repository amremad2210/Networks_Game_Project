import socket
import threading
import time
import json
import csv
import sys
import os
import math
import copy
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from common.packet import Packet, MSG_INIT, MSG_EVENT, MSG_SNAPSHOT, MSG_ACK, MSG_END

class Client():
    # Retry/timeouts (configurable)
    INIT_RETRIES = 3
    INIT_RETRY_INTERVAL = 1.0
    
    # Event ACK retry (configurable)
    EVENT_ACK_TIMEOUT = 1      # seconds to wait for ACK before retrying
    MAX_EVENT_RETRIES = 5         # max retransmit attempts per event

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

        # Pending events: seq_num -> {packet_bytes, last_sent_time, retries, server_addr}
        # Lightweight tracking for retry-on-timeout
        self.pending_events = {}
        self.pending_lock = threading.Lock()

        # Event send times (seq_num -> send_time_ms) to compute delivery delays
        self.event_send_times = {}

        # Event logging (seq send/ack/delay)
        self.event_log_file = None
        self.event_csv_writer = None
        self.setup_event_logging()

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
        os.makedirs('logs/client_logs', exist_ok=True)
        self.metrics_file = open(f'logs/client_logs/client_metrics_{os.getpid()}.csv', 'w', newline='')
        self.metrics_writer = csv.writer(self.metrics_file)
        self.metrics_writer.writerow([
            'client_id', 'snapshot_id', 'seq_num',
            'recv_time_ms', 'player_position', 'bandwidth_per_client_kbps'
        ])
        self._last_snapshot_recv_time = None   

    def setup_event_logging(self):
        """Create a CSV to record event send times and ACK receipts."""
        try:
            pid = os.getpid()
            self.event_log_file = open(f'client_events_{pid}.csv', 'w', newline='')
            self.event_csv_writer = csv.writer(self.event_log_file)
            # Columns: client_id, seq_num, send_time_ms, ack_recv_time_ms, ack_delay_ms, delivered
            self.event_csv_writer.writerow(['client_id', 'seq_num', 'send_time_ms', 'ack_recv_time_ms', 'ack_delay_ms', 'delivered'])
            self.event_log_file.flush()
        except Exception:
            self.event_log_file = None
            self.event_csv_writer = None

    def log_metrics(self, packet,raw_size):
        recv_time_ms = int(time.time() * 1000)
        player_position = self._get_player_position(self.game_state)
        bandwidth_kbps = self._calculate_bandwidth(raw_size)
        
        self.metrics_writer.writerow([
            self.player_id,
            getattr(packet, "snapshot_id", 0),
            getattr(packet, "seq_num", 0),
            recv_time_ms,
            json.dumps(player_position) if player_position else "{}",
            bandwidth_kbps
        ])
        self.metrics_file.flush()
    # ---------------------------------------------------

    def _get_player_position(self, state):
        """Extract this client's player position from game state"""
        if not isinstance(state, dict):
            return None
        
        players = state.get('players') or {}
        for player in players.values():
            if player.get('username') == self.username:
                segments = player.get('segments') or []
                if segments:
                    head = segments[0]
                    return {"x": head.get('x'), "y": head.get('y')}
        return None

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
        """Send INIT message to server and wait for INIT ACK with retries.

        This method will only perform the initial handshake (INIT -> INIT ACK).
        The client must call `send_ready_ack()` after the game UI is loaded to
        complete the handshake and be marked READY on the server.
        """
        self.username = username

        payload_data = json.dumps({'username': username}).encode('utf-8')
        payload_len = len(payload_data)

        server_addr = (self.server_host, self.server_port)

        for attempt in range(self.INIT_RETRIES):
            timestamp = int(time.time() * 1000)
            packet_data = Packet.encode_packet(
                MSG_INIT, 0, self.client_seq_num, timestamp, payload_len, payload_data
            )

            try:
                # send INIT
                self.sock.sendto(packet_data, server_addr)
                self.client_seq_num += 1

                # wait for INIT ACK (short timeout per attempt)
                self.sock.settimeout(self.INIT_RETRY_INTERVAL)
                data, addr = self.sock.recvfrom(4096)
                packet = Packet.decode_packet(data)

                if packet and packet.msg_type == MSG_ACK:
                    try:
                        ack_data = json.loads(packet.payload.decode('utf-8')) if packet.payload_len else {}
                    except Exception:
                        ack_data = {}

                    if ack_data.get('ack_for') == 'init' or ack_data.get('player_id'):
                        self.player_id = ack_data.get('player_id') or self.username
                        self.server_address = addr
                        print(f"[Client] Received INIT ACK from server: player_id={self.player_id}")
                        # Do NOT mark connected or start receive thread yet — wait for READY ack
                        return True

            except socket.timeout:
                print(f"[Client] INIT attempt {attempt+1} timed out, retrying...")
                continue
            except Exception as e:
                print(f"[Client] Error during INIT: {e}")
                continue

        print("[Client] Failed to receive INIT ACK after retries")
        return False

    def make_move(self, direction):
        """Send EVENT to server and buffer for retransmit if no ACK received."""
        if not self.connected:
            return False
       
        move_data = {
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

        # Buffer for retry: {seq_num: {bytes, last_sent_time, retries}}
        with self.pending_lock:
            self.pending_events[self.client_seq_num] = {
                "bytes": packet_data,
                "last_sent_time": time.time(),
                "retries": 0
            }

        # Record send time for event delivery stats
        send_time_ms = int(time.time() * 1000)
        self.event_send_times[self.client_seq_num] = send_time_ms

        self.client_seq_num += 1
        return True

    def send_ready_ack(self):
        """Send READY ACK to server after UI has loaded and start receive loop."""
        if not self.player_id:
            print("[Client] Cannot send READY without a player_id")
            return False

        payload = json.dumps({
            'ack_for': 'ready',
            'player_id': self.player_id,
            'client_time': int(time.time() * 1000)
        }).encode('utf-8')

        timestamp = int(time.time() * 1000)
        packet_data = Packet.encode_packet(MSG_ACK, 0, 0, timestamp, len(payload), payload)

        try:
            server_addr = self.server_address or (self.server_host, self.server_port)
            self.sock.sendto(packet_data, server_addr)
            # Mark connected and start background receive thread
            self.connected = True
            if not hasattr(self, 'receive_thread') or not self.receive_thread.is_alive():
                self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
                self.receive_thread.start()
            print(f"[Client] Sent READY ACK to server for player_id={self.player_id}")
            return True
        except Exception as e:
            print(f"[Client] Failed to send READY ACK: {e}")
            return False

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

            if hasattr(self, 'last_snapshot_id') and snapshot_id <= self.last_snapshot_id:
                print(f"[Client] Ignored outdated snapshot {snapshot_id}")
                return

            self.last_snapshot_id = snapshot_id
            self.game_state = payload
            self.last_server_timestamp = server_timestamp

           # print(f"[Client] Updated game state from snapshot {snapshot_id} "
            #      f"({len(payload)} keys, timestamp={server_timestamp})")

            self.log_msg(packet, "RECEIVED")

            # LOG METRICS HERE
            self.log_metrics(packet,raw_size)

        except json.JSONDecodeError:
            print("[Client] Failed to decode SNAPSHOT payload (invalid JSON).")
        except Exception as e:
            print(f"[Client] Error handling SNAPSHOT: {e}")

        pass

    def receive_messages(self):
        """Background receive loop: handle snapshots, ACKs, END. Also check for stale events to retry."""
        self.sock.settimeout(0.25)
        self._rx_running = True
        print("[Client] Starting receive loop...")

        while self._rx_running:
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                # On timeout, check pending events for retransmit
                self._check_and_retry_events()
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
                    payload_text = packet.payload.decode('utf-8') if packet.payload_len else ""
                    info = json.loads(payload_text) if payload_text.startswith('{') else {}
                except Exception:
                    info = {}

                # If this is an EVENT ACK, remove from pending
                if info.get('ack_for') == 'event':
                    seq_num = info.get('seq_num')
                    with self.pending_lock:
                        if seq_num in self.pending_events:
                            del self.pending_events[seq_num]
                            print(f"[Client] EVENT seq={seq_num} ACKed")

                    # Log event delivery (send_time -> ack_recv_time)
                    try:
                        ack_recv_time = int(time.time() * 1000)
                        send_time = None
                        if seq_num in self.event_send_times:
                            send_time = self.event_send_times.pop(seq_num)

                        ack_delay = None
                        if send_time is not None:
                            ack_delay = ack_recv_time - send_time

                        if self.event_csv_writer:
                            client_id = self.player_id or self.username or os.getpid()
                            self.event_csv_writer.writerow([
                                client_id,
                                seq_num,
                                send_time or "",
                                ack_recv_time,
                                ack_delay if ack_delay is not None else "",
                                True
                            ])
                            self.event_log_file.flush()
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
                # Stop receive loop immediately
                self._rx_running = False
            else:
                print(f"[Client] Received unknown packet type: {packet.msg_type}")
                self.log_msg(packet, "RECEIVED")

            # Check for stale events to retry
            self._check_and_retry_events()

        print("[Client] Receive loop terminated.")

    def _check_and_retry_events(self):
        """Check pending events and retry any that have timed out."""
        now = time.time()
        with self.pending_lock:
            pending_list = list(self.pending_events.items())

        for seq_num, entry in pending_list:
            elapsed = now - entry["last_sent_time"]
            if elapsed > self.EVENT_ACK_TIMEOUT:
                if entry["retries"] >= self.MAX_EVENT_RETRIES:
                    # Max retries exceeded
                    print(f"[Client] EVENT seq={seq_num} max retries exceeded")
                    with self.pending_lock:
                        if seq_num in self.pending_events:
                            del self.pending_events[seq_num]
                    # Log failed delivery
                    try:
                        send_time = None
                        if seq_num in self.event_send_times:
                            send_time = self.event_send_times.pop(seq_num)
                        if self.event_csv_writer:
                            client_id = self.player_id or self.username or os.getpid()
                            self.event_csv_writer.writerow([
                                client_id,
                                seq_num,
                                send_time or "",
                                "",
                                "",
                                False
                            ])
                            self.event_log_file.flush()
                    except Exception:
                        pass
                else:
                    # Resend
                    self.sock.sendto(entry["bytes"], (self.server_host, self.server_port))
                    entry["retries"] += 1
                    entry["last_sent_time"] = now
                    print(f"[Client] Retry EVENT seq={seq_num} (attempt {entry['retries']})")

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
            try:
                if self.event_log_file:
                    self.event_log_file.close()
            except Exception:
                pass

    def sync_game(self):
        pass

if __name__ == "__main__":
    player = Client()
    # player.join_game("Jana")
    # player.stop()

import socket
import threading
import time
import json
import csv
from datetime import datetime
from packet import Packet, MSG_INIT, MSG_EVENT, MSG_SNAPSHOT, MSG_ACK, MSG_END


class Client():
    def __init__(self, server_host='localhost', server_port=9999):
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
            'food': [],
            'grid_size': 20,
            'game_over': False,
            'winner': None
        }
        self.snapshot_id = 0

        # Logging
        self.log_file = None
        self.csv_writer = None
        self.setup_logging()

    def setup_logging(self):
        """Setup CSV logging for messages"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = open(f'client_log_{timestamp}.csv', 'w', newline='')
        self.csv_writer = csv.writer(self.log_file)
        self.csv_writer.writerow([
            'timestamp', 'client_id', 'msg_type', 'seq_num', 'snapshot_id',
            'server_timestamp', 'payload_size', 'direction'
        ])

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
            'player_id': self.player_id,
            'direction': direction.upper(),
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
        self.log_msg(event_packet, direction.upper())

        self.client_seq_num += 1
        return True

    def handle_snapshot(self, packet):
        """
        Handles incoming SNAPSHOT packets from the server.
        Decodes the JSON payload and updates the client's game state.
        Older snapshots (by snapshot_id) are ignored.
        """
        try:
            #Decode the JSON payload
            payload = json.loads(packet.payload.decode('utf-8'))
            snapshot_id = packet.snapshot_id
            server_timestamp = packet.timestamp

            # Ignore older snapshots
            if hasattr(self, 'last_snapshot_id') and snapshot_id <= self.last_snapshot_id:
                print(f"[Client] Ignored outdated snapshot {snapshot_id}")
                return
            
            # Update game state
            self.last_snapshot_id = snapshot_id

            #Update local cached game state
            self.game_state = payload
            self.last_server_timestamp = server_timestamp

            print(f"[Client] Updated game state from snapshot {snapshot_id} "
              f"({len(payload)} keys, timestamp={server_timestamp})")
            
            # Log SNAPSHOT message
            self.log_msg(packet)
            
        except json.JSONDecodeError:
            print("[Client] Failed to decode SNAPSHOT payload (invalid JSON).")
        except Exception as e:
            print(f"[Client] Error handling SNAPSHOT: {e}")

        pass

    def receive_messages(self):
        """  
        Background receive loop:
            - Decodes incoming packets
            - Dispatches to handlers (SNAPSHOT/ACK/END)
            - Logs everything
        Run this in a thread: threading.Thread(target=self.receive_messages, daemon=True).start() 
        """

        self.sock.settimeout(0.25)  # Set timeout for recvfrom
        self._rx_running = True
        print("[Client] Starting receive loop...")

        while self._rx_running:
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue  # No data received, loop again
            except OSError:
                break  # Socket closed, exit loop
            except Exception as e:
                print(f"[Client] Receive error: {e}")
                continue

            packet = Packet.decode_packet(data)
            if not packet:
                continue  # Corrupt or failed CRC etc

            if self.server_address is None: # First packet received, store server address
                self.server_address = addr 

            if packet.msg_type == MSG_SNAPSHOT: #Dispatch by msg_type
                self.handle_snapshot(packet)

            #Generic ACKs and logging for completeness
            elif packet.msg_type == MSG_ACK:
                try:
                    _ = packet.payload.decode('utf-8') if packet.payload_len else ""    # Process ACK payload if needed
                except Exception:
                    pass
                self.log_msg(packet)

            elif packet.msg_type == MSG_END:
                #server indicated game over or disconnection
                try:
                    payload_text = packet.payload.decode('utf-8') if packet.payload_len else ""
                    # if server sends JSON payload, we can parse it here
                    if payload_text.strip().startswith('{'):
                        info = json.loads(payload_text)
                        self.game_state['game_over'] = bool(info.get('game_over', True))
                        self.game_state['winner'] = info.get('winner')
                    else:
                        self.game_state['game_over'] = True
                except Exception:
                    self.game_state['game_over'] = True

                print("[Client] Received END message from server. Game over.")
                self.log_msg(packet)
            else:
                print(f"[Client] Received unknown packet type: {packet.msg_type}")
                self.log_msg(packet)
        
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




    def sync_game(self):
        # recieves periodic snapshots from the server and updates the game UI
        # phase 2
        pass

   
if __name__ == "__main__":
    player= Client()

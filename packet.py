import struct
import zlib     # for crc32
import time     # for timestamps

# message types
MSG_INIT = 0      # Client requests to join game
MSG_EVENT = 1     # Client sends a move/action
MSG_SNAPSHOT = 2  # Server sends game state update
MSG_ACK = 3       # Server acknowledges client connection
MSG_END = 4       # Server signals game over

""" 
format for struct packing and unpacking
 4s = 4-byte string (protocol_id "SNAK")
 B = 1-byte unsigned char (version)
 B = 1-byte unsigned char (msg_type)
 I = 4-byte unsigned int (snapshot_id)
 I = 4-byte unsigned int (seq_num)
 Q = 8-byte unsigned long long (timestamp in milliseconds)
 H = 2-byte unsigned short (payload_len)
 I = 4-byte unsigned int (crc32)
"""
FORMAT = "4s B B I I Q H I"  # 28 bytes for header
PROTOCOL = b"SNAK"  # Must be bytes, not string
VER = 1
"""
Packet structure:
Field	        Size (Bytes)	Description
protocol_id	        4	        ASCII ID (“SNAK”)
version	            1	        Protocol Version
msg_type	        1	        Message Type Code (SNAPSHOT, EVENT, ACK, INIT, END)
snapshot_id     	4	        Monotonic Counter
seq_num         	4	        Packet Sequence Number
server_timestamp	8	        ms since epoch / monotonic clock
payload_len	        2	        Length of Payload
check_sum       	4	        CRC32 Recommended 
"""
class Packet:
    def __init__(self, msg_type, snapshot_id, seq_num, timestamp, payload_len, payload):
        self.protocol_id = PROTOCOL     # 4-byte identifier, must be bytes
        self.version = VER              # Protocol version number
        self.msg_type = msg_type        # Message type code
        self.snapshot_id = snapshot_id  # Game state counter
        self.seq_num = seq_num          # Sequence number
        self.timestamp = timestamp      # Timestamp in ms
        self.payload_len = payload_len  # Length of payload
        self.payload = payload          # Actual payload data (bytes)
        self.crc32 = 0                  # Will be calculated during encoding
        pass

    @staticmethod
    def calc_crc32(data):
        # calculate the crc from the message
        # zlib.crc32 computes CRC32 and returns signed int
        # We need unsigned, so mask with 0xFFFFFFFF
        return zlib.crc32(data) & 0xFFFFFFFF

    def verify_crc32(self, received_crc):
        # uses calc_crc32 to verify that the crc received is correct
         # Recalculate CRC for the header + payload
        header = struct.pack(
            "4s B B I I Q H",  # Everything except CRC
            self.protocol_id,
            self.version,
            self.msg_type,
            self.snapshot_id,
            self.seq_num,
            self.timestamp,
            self.payload_len
        )
        # Combine header and payload for CRC calculation
        data_to_check = header + self.payload
        calculated_crc = self.calc_crc32(data_to_check)
        
        return calculated_crc == received_crc

    @staticmethod
    def encode_packet(msg_type, snapshot_id, seq_num, timestamp, payload_len, payload):
        # encodes the packet into a byte stream for sending over udp
        
        # First, pack header WITHOUT CRC (we need header+payload to calculate CRC)
        header_without_crc = struct.pack(
            "4s B B I I Q H",
            PROTOCOL,
            VER,
            msg_type,
            snapshot_id,
            seq_num,
            timestamp,
            payload_len
        )
        
        # Calculate CRC32 over header (without CRC field) + payload
        data_for_crc = header_without_crc + payload
        crc32 = Packet.calc_crc32(data_for_crc)
        
        # Now pack the complete header including CRC
        header = struct.pack(
            FORMAT,
            PROTOCOL,
            VER,
            msg_type,
            snapshot_id,
            seq_num,
            timestamp,
            payload_len,
            crc32
        )
        
        # Return complete packet: header + payload
        return header + payload

    @staticmethod
    def decode_packet(msg : struct):
        # decode the struct
        # create a packet object to return

        # first check if we have at least enough bytes for the header
        header_size = struct.calcsize(FORMAT)  # Should be 28 bytes
        
        if len(msg) < header_size:
            print(f"[ERROR] Packet too small: {len(msg)} bytes, expected at least {header_size}")
            return None
        
        # Unpack the header
        try:
            header_data = struct.unpack(FORMAT, msg[:header_size])
        except struct.error as e:
            print(f"[ERROR] Failed to unpack header: {e}")
            return None
        
        # Extract fields from unpacked header
        protocol_id = header_data[0]    # Should be b"SNAK"
        version = header_data[1]        # Should be 1
        msg_type = header_data[2]
        snapshot_id = header_data[3]
        seq_num = header_data[4]
        timestamp = header_data[5]
        payload_len = header_data[6]
        received_crc = header_data[7]
        
        # Verify protocol ID
        if protocol_id != PROTOCOL:
            print(f"[ERROR] Invalid protocol ID: {protocol_id}")
            return None
        
        # Extract payload (everything after header)
        payload = msg[header_size:]
        
        # Verify payload length matches what header says
        if len(payload) != payload_len:
            print(f"[ERROR] Payload length mismatch: expected {payload_len}, got {len(payload)}")
            return None
        
        # Create packet object
        packet = Packet(msg_type, snapshot_id, seq_num, timestamp, payload_len, payload)
        
        # Verify CRC32
        if not packet.verify_crc32(received_crc):
            print(f"[ERROR] CRC32 verification failed")
            return None
        
        # All checks passed, return valid packet
        return packet
    
    def __str__(self):
        # to string function for debugging
        msg_types = {0: "INIT", 1: "EVENT", 2: "SNAPSHOT", 3: "ACK", 4: "END"}
        return (f"Packet(type={msg_types.get(self.msg_type, 'UNKNOWN')}, "
                f"snapshot={self.snapshot_id}, seq={self.seq_num}, "
                f"timestamp={self.timestamp}, payload_len={self.payload_len})")



import struct

FORMAT = ""

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
        self.protocol_id = ""
        self.version = 1
        self.msg_type = msg_type
        self.snapshot_id = snapshot_id
        self.seq_num = seq_num
        self.timestamp = timestamp
        self.payload_len = payload_len
        self.payload = payload
        self.crc32 = self.calc_crc32()
        pass

    def calc_crc32(self):
        # calculate the crc from the message
        pass

    def verify_crc32(self):
        # uses calc_crc32 to verify that the crc recievd is correct
        pass

    @staticmethod
    def encode_packet(msg_type, snapshot_id, seq_num, timestamp, payload_len, payload):
        # encodes the packet into a byte stream for sending over udp
        pass

    @staticmethod
    def decode_packet(struct):
        # decode the struct
        # create a packet object to return
        pass

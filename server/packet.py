import struct

MSG_INIT = 1
MSG_EVENT = 2
MSG_SNAPSHOT = 3
MSG_END = 4

class Packet:
    HEADER_FORMAT = "!B I I Q H"  # msg_type, seq, ack, timestamp, payload_len
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    def __init__(self, msg_type, seq, ack, timestamp, payload):
        self.msg_type = msg_type
        self.seq = seq
        self.ack = ack
        self.timestamp = timestamp
        self.payload = payload

    @staticmethod
    def encode_packet(msg_type, seq, ack, timestamp, payload_len, payload):
        header = struct.pack(Packet.HEADER_FORMAT, msg_type, seq, ack, timestamp, payload_len)
        return header + payload

    @staticmethod
    def decode_packet(data):
        try:
            header = data[:Packet.HEADER_SIZE]
            msg_type, seq, ack, timestamp, payload_len = struct.unpack(Packet.HEADER_FORMAT, header)
            payload = data[Packet.HEADER_SIZE:Packet.HEADER_SIZE + payload_len]
            return Packet(msg_type, seq, ack, timestamp, payload)
        except Exception:
            return None

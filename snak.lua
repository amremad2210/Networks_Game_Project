-- snak.lua - Wireshark dissector for SNAK protocol (save in Wireshark plugins folder)
-- Protocol: SNAK (4s B B I I Q H I) - 28 byte header + payload
-- Replace 9999 with your actual UDP port number!

do
    local snak_proto = Proto("snak", "SNAK Game Protocol v1.0")

    -- Message type names (from your packet.py)
    local msg_types = {
        [0] = "MSG_INIT (Client join)",
        [1] = "MSG_EVENT (Client move/action)", 
        [2] = "MSG_SNAPSHOT (Server state)",
        [3] = "MSG_ACK (Server ack)",
        [4] = "MSG_END (Game over)"
    }

    -- Define all 8 header fields exactly matching your FORMAT = "4s B B I I Q H I"
    local fields = {
        protoid   = ProtoField.string("snak.protoid", "Protocol ID", base.NONE),
        version   = ProtoField.uint8("snak.version", "Version", base.DEC),
        msgtype   = ProtoField.uint8("snak.msgtype", "Msg Type", base.DEC),
        snapshotid= ProtoField.uint32("snak.snapshotid", "Snapshot ID", base.DEC),
        seqnum    = ProtoField.uint32("snak.seqnum", "Seq Num", base.DEC),
        timestamp = ProtoField.uint64("snak.timestamp", "Timestamp (ms)", base.DEC),
        payloadlen= ProtoField.uint16("snak.payloadlen", "Payload Len", base.DEC),
        crc32     = ProtoField.uint32("snak.crc32", "CRC32 Checksum", base.HEX),
    }
    snak_proto.fields = fields

    -- Main dissector function
    function snak_proto.dissector(buffer, pinfo, tree)
        length = buffer:len()
        if length == 0 then return end

        -- Header is exactly 28 bytes (struct.calcsize("4s B B I I Q H I"))
        local header_len = 28
        if length < header_len then return end

        pinfo.cols.protocol = snak_proto.name
        local subtree = tree:add(snak_proto, buffer(0, header_len), "SNAK Protocol")

        -- Parse fields byte-by-byte matching your exact struct layout
        -- 0-3: protocol_id (4s)  
        subtree:add(fields.protoid, buffer(0,4))
        -- 4: version (B)
        subtree:add(fields.version, buffer(4,1))
        -- 5: msgtype (B)  
        subtree:add(fields.msgtype, buffer(5,1))
        -- 6-9: snapshot_id (I)
        subtree:add(fields.snapshotid, buffer(6,4))
        -- 10-13: seq_num (I)
        subtree:add(fields.seqnum, buffer(10,4))
        -- 14-21: timestamp (Q)
        subtree:add(fields.timestamp, buffer(14,8))
        -- 22-23: payload_len (H)
        subtree:add(fields.payloadlen, buffer(22,2))
        -- 24-27: crc32 (I)
        subtree:add(fields.crc32, buffer(24,4))

        -- Show human-readable message type
        local msgtype_val = buffer(5,1):uint()
        if msg_types[msgtype_val] then
            subtree:append_text(", " .. msg_types[msgtype_val])
            pinfo.cols.info = msg_types[msgtype_val]
        end

        -- Payload subtree (after 28-byte header)
        local payload_len = buffer(22,2):uint()
        if payload_len > 0 and length > header_len then
            local payload_end = header_len + payload_len
            if payload_end <= length then
                local payload_tree = subtree:add(buffer(header_len, payload_len), "Payload (" .. payload_len .. " bytes)")
                payload_tree:set_text("Payload Data")
            end
        end
    end

    -- Register for UDP port - CHANGE 9999 TO YOUR ACTUAL PORT!
    local udp_port = DissectorTable.get("udp.port")
    udp_port:add(9999, snak_proto)  -- ⚠️ REPLACE 9999 with your UDP port!
end

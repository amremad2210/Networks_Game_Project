local snak_proto = Proto("snak", "SNAK Protocol")

local msg_types = {[0]="MSG_INIT",[1]="MSG_EVENT",[2]="MSG_SNAPSHOT",[3]="MSG_ACK",[4]="MSG_END"}

local pf = {
    protocol_id = ProtoField.string("snak.protocol_id","Protocol ID"),
    version = ProtoField.uint8("snak.version","Version"),
    msg_type = ProtoField.uint8("snak.msg_type","Message Type",base.DEC,msg_types),
    snapshot_id = ProtoField.uint32("snak.snapshot_id","Snapshot ID"),
    seq_num = ProtoField.uint32("snak.seq_num","Sequence Number"),
    payload_len = ProtoField.uint16("snak.payload_len","Payload Length"),
}
snak_proto.fields = pf

function snak_proto.dissector(buffer,pinfo,tree)
    local len = buffer:len()
    if len < 28 then return end
    
    pinfo.cols.protocol = snak_proto.name
    local subtree = tree:add(snak_proto,buffer(),"SNAK")

    -- ORIGINAL BIG-ENDIAN NUMBERS (NO CONVERSION)
    local snapshot_id = buffer(6,4):uint()
    local seq_num = buffer(10,4):uint()
    --local payload_len = buffer(22,2):uint()
    local payload_len = buffer(22,1):uint() + buffer(23,1):uint() * 256  -- Manual LE

    -- ADD FIELDS
    subtree:add(pf.protocol_id,buffer(0,4))
    subtree:add(pf.version,buffer(4,1))
    subtree:add(pf.msg_type,buffer(5,1))
    subtree:add(pf.snapshot_id,buffer(6,4),snapshot_id)
    subtree:add(pf.seq_num,buffer(10,4),seq_num)
    subtree:add(pf.payload_len,buffer(22,2),payload_len)
    
    -- INFO LINE WITH ORIGINAL NUMBERS
    pinfo.cols.info:append(string.format(" %s Sn:%d Seq:%d",msg_types[buffer(5,1):uint()] or "?",snapshot_id,seq_num))
    
end

local udp_port = DissectorTable.get("udp.port")
udp_port:add(9999,snak_proto)

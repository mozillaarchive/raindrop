function(doc) {
    if (doc.rd_schema_id=='rd.msg.seen') {
        if (doc.seen === undefined)
            ;
        else {
            var val = {seen: doc.seen, _rev: doc._rev, outgoing_state: doc.outgoing_state};
            if (doc.outgoing_state) {
                val['outgoing_state'] = doc['outgoing_state']
            }
            emit(doc.rd_key, val);
        }
    }
}

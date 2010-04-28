function(doc) {
    if (doc.rd_schema_id && doc.outgoing_state) {
        emit(doc.outgoing_state, {'_rev': doc._rev});
    }
}

function(doc) {
    if (doc.rd_schema_id=="rd.identity.contacts") {
        for each (var cid in doc.contacts) {
            emit(cid, {rd_key: doc.rd_key, _rev: doc._rev});
        }
    }
}

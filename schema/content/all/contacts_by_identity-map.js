function(doc) {
    if (doc.rd_schema_id=="rd.identity.contacts") {
        for each (var cid in doc.contacts) {
            emit(doc.rd_key, cid);
        }
    }
}

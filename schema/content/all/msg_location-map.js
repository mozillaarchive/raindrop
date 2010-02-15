function(doc) {
    if (doc.rd_schema_id=='rd.msg.location') {
        emit(doc.location, {rd_key: doc.rd_key, _rev: doc._rev});
    }
}

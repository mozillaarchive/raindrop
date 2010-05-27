function(doc) {
    if (doc.rd_schema_id == 'rd.contact' && doc.displayName)
        emit(doc.displayName, {rd_key: doc.rd_key, _rev: doc._rev});
}

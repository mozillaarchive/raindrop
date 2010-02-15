function(doc) {
    if (doc.rd_schema_id == 'rd.contact' && doc.name)
        emit(doc.name, {rd_key: doc.rd_key, _rev: doc._rev});
}

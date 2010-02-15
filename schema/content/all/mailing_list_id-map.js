function(doc) {
    if (doc.rd_schema_id == 'rd.mailing-list' && doc.id)
        emit(doc.id, {rd_key: doc.rd_key, _rev: doc._rev});
}

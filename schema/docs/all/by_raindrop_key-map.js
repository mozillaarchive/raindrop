function(doc) {
    if (doc.rd_key)
        emit([doc.rd_key, doc.rd_schema_id || null, doc.rd_ext_id], doc._rev);
}

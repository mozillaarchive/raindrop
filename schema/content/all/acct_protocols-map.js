function(doc) {
    if (doc.rd_schema_id=='rd.account')
        emit(doc.proto, {rd_key: doc.rd_key});
}

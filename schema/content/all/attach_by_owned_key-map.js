function(doc) {
    if (doc.rd_key && doc.rd_key[0]=="attach") {
        var owned_key = doc.rd_key[1][0];
        emit(owned_key, {rd_schema_id: doc.rd_schema_id,
                         rd_key: doc.rd_key});
    }
}

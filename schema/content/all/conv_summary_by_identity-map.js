function(doc) {
    if (doc.rd_schema_id=='rd.conv.summary') {
        for each (var idid in doc.identities) {
            emit(idid, null);
        }
    }
}

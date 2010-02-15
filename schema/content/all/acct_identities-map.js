function(doc) {
    if (doc.rd_schema_id=="rd.account") {
        for each (var idty in doc.identities)
            emit(idty, null);
    }
}

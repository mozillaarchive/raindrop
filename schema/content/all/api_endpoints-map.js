function(doc) {
    if (doc.rd_schema_id=='rd.ext.api' && doc.endpoints) {
        for each (var ep in doc.endpoints) {
            emit(ep, null);
        }
    }
}

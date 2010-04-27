function(doc) {
    if (doc.rd_schema_id=='rd.grouping.info') {
        emit(doc.title, null);
    }
}

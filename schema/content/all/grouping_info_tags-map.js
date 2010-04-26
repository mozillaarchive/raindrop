function(doc) {
    if (doc.rd_schema_id=='rd.grouping.info') {
        for each (var gt in doc.grouping_tags) {
            emit(gt, doc.rd_key);
        }
    }
}

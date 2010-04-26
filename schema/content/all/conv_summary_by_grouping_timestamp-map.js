function(doc) {
    if (doc.rd_schema_id=='rd.conv.summary') {
        for each (var gt in doc['grouping-timestamp']) {
            emit(gt, null);
        }
    }
}

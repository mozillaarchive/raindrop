function(doc) {
    if (doc.rd_schema_id=='rd.conv.summary') {
        for each (var grouptag in doc.unread_grouping_tags) {
            emit(grouptag, doc.rd_key);
        }
    }
}

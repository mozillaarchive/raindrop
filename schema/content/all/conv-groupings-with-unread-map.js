function(doc) {
    if (doc.rd_schema_id=='rd.conv.summary') {
        for each (var grouptag in doc.groups_with_unread) {
            emit(grouptag, doc.rd_key);
        }
    }
}

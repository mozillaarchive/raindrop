function(doc) {
    if (doc.rd_schema_id=='rd.msg.imap-location') {
        for each (var location in doc.locations) {
            emit(location.folder_name, {rd_key: doc.rd_key, _rev: doc._rev});
        }
    }
}

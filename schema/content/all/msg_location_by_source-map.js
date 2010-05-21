function(doc) {
    if (doc.rd_schema_id=='rd.msg.imap-locations') {
        for each (var location in doc.locations) {
            var key = [location.account, location.folder_name]
            var val = {rd_key: doc.rd_key, _rev: doc._rev,
                       location: location};
            emit(key, val);
        }
    }
}

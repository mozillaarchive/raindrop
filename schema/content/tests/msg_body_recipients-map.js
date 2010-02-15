function(doc) {
    if (doc.rd_schema_id=="rd.msg.body") {
        val = {rd_key: doc.rd_key, _rev: doc._rev}
        if (doc.from)
            emit(["from", doc.from], val);
        if (doc.from_display)
            emit(["from_display", doc.from_display], val);
        for each (var recip in doc.to || [])
            emit(["to", recip], val);
        for each (var recip in doc.to_display || [])
            emit(["to_display", recip], val);
        for each (var recip in doc.cc || [])
            emit(["cc", recip], val);
        for each (var recip in doc.cc_display || [])
            emit(["cc_display", recip], val);
    }
}

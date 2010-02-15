function(doc) {
    if (doc.rd_schema_id == "rd.msg.conversation") {
        emit(doc.conversation_id, {rd_key: doc.rd_key, _rev: doc._rev});
    }
}

function(doc) {
    if (doc.rd_schema_id == "rd.msg.email.mailing-list" && doc.list_id)
        emit(doc.list_id, {rd_key: doc.rd_key, _rev: doc._rev});
}

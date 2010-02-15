function(doc) {
    if (doc.rd_schema_id == "rd.msg.email.mailing-list" && doc.listid)
        emit(doc.listid, {rd_key: doc.rd_key, _rev: doc._rev});
}

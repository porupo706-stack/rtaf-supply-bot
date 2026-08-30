NOTEBOOKS = {

    "จัดซื้อ":
    "53c42aa4-91a9-46b0-9094-2b480d0f0c5f",

    "คลัง":
    "xxxxxxxxxxxxxxxx",

    "การเงิน":
    "xxxxxxxxxxxxxxxx",

    "ส่งกำลัง":
    "xxxxxxxxxxxxxxxx"
}


def route_notebook(question):

    q = question.lower()

    if any(
        word in q
        for word in [
            "คลัง",
            "เบิก",
            "จ่ายพัสดุ",
            "รับพัสดุ"
        ]
    ):
        return NOTEBOOKS["คลัง"]

    if any(
        word in q
        for word in [
            "จัดซื้อ",
            "จัดจ้าง",
            "e-gp",
            "เฉพาะเจาะจง"
        ]
    ):
        return NOTEBOOKS["จัดซื้อ"]

    if any(
        word in q
        for word in [
            "การเงิน",
            "เบิกจ่าย",
            "งบประมาณ"
        ]
    ):
        return NOTEBOOKS["การเงิน"]

    return NOTEBOOKS["จัดซื้อ"]
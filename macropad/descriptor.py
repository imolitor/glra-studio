# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 GLRA Studio contributors

"""Parse HID short items and report lengths; never infer vendor semantics."""


def parse(data: bytes) -> dict:
    i = 0
    state = {"size": 0, "count": 0, "id": 0, "usage_page": 0}
    stack, items, reports = [], [], {}
    depth = 0
    while i < len(data):
        offset = i
        prefix = data[i]
        i += 1
        if prefix == 0xFE:
            if i + 2 > len(data):
                raise ValueError("Truncated long item")
            size, tag = data[i : i + 2]
            i += 2
            if i + size > len(data):
                raise ValueError("Truncated long-item payload")
            items.append({"offset": offset, "long_tag": tag, "hex": data[i : i + size].hex()})
            i += size
            continue
        size = (0, 1, 2, 4)[prefix & 3]
        if i + size > len(data):
            raise ValueError("Truncated short item")
        value = int.from_bytes(data[i : i + size], "little")
        i += size
        kind, tag = (prefix >> 2) & 3, prefix >> 4
        items.append({"offset": offset, "type": kind, "tag": tag, "value": value})
        if kind == 1:
            field = {0: "usage_page", 7: "size", 8: "id", 9: "count"}.get(tag)
            if field:
                if field == "id" and not 1 <= value <= 255:
                    raise ValueError("Invalid report ID")
                state[field] = value
            elif tag == 10:
                stack.append(state.copy())
            elif tag == 11:
                if not stack:
                    raise ValueError("Global POP without PUSH")
                state = stack.pop()
        elif kind == 0:
            if tag == 10:
                depth += 1
            elif tag == 12:
                depth -= 1
                if depth < 0:
                    raise ValueError("END_COLLECTION without COLLECTION")
            report_type = {8: "input", 9: "output", 11: "feature"}.get(tag)
            if report_type:
                bits = state["size"] * state["count"]
                if bits > 65536:
                    raise ValueError("Unreasonably large report")
                key = (report_type, state["id"])
                reports[key] = reports.get(key, 0) + bits
    if depth or stack:
        raise ValueError("Unbalanced descriptor")
    result = []
    for (kind, rid), bits in sorted(reports.items()):
        payload = (bits + 7) // 8
        result.append(
            {
                "type": kind,
                "id": rid,
                "bits": bits,
                "payload_bytes": payload,
                "interrupt_bytes": payload + bool(rid),
                "hidapi_control_buffer_bytes": payload + 1,
            }
        )
    return {"reports": result, "items": items}

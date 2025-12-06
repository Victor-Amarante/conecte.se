def extract_user_number(message_key: dict):
    possible_ids = [
        message_key.get("remoteJid"),
        message_key.get("senderPn"),
        message_key.get("senderLid"),
    ]

    for identifier in possible_ids:
        if not identifier:
            continue

        if "@s.whatsapp.net" in identifier:
            return identifier.replace("@s.whatsapp.net", "")

        if "@lid" in identifier:
            continue

    return None

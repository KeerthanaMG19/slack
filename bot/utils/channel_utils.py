def parse_channel_name(text):
    if not text:
        return None
    text = text.strip()
    if text.startswith('#'):
        channel_name = text[1:].strip()
    else:
        channel_name = text.strip()
    return channel_name if channel_name else None

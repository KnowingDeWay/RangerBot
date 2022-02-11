def is_null_or_whitespace(text: str):
    if text is None:
        return True
    elif text.isspace():
        return True
    else:
        return False

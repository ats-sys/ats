def snake_to_camel(input_string):
    words = input_string.split('_')
    camel_case_words = [word.capitalize() for word in words]
    return ''.join(camel_case_words)

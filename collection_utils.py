
def dict_grouping(unique_key_generator, values):
    dict = {}
    for value in values:
        key = unique_key_generator(value)

        if key in dict:
            raise ValueError(f'Duplicated key {key} (for values {dict[key]}, {value}.')

        dict[key] = value

    return dict


def first(predicate, iterable):
    for element in iterable:
        if predicate(element):
            return element

    return None

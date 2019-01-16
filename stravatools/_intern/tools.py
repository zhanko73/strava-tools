# -*- coding: utf-8 -*-
# Higher-order functions

def find(predicate, iterable):
    for i in filter(predicate, iterable):
        return i
    return None

def first(xs, mapper=lambda x:x):
    if len(xs) > 0: return mapper(xs[0])

def each(xs, mapper=lambda x:x):
    for x in xs:
        yield mapper(x)
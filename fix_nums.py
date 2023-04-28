#!/usr/bin/env python3

data = input("Which issue numbers to skip?"
             " Use x-y to select all numbers between (and including) x and y, or x,y to select x and y but not any number in between: ")
numbers = []
comma_sep = filter(lambda x: x, data.split(","))
for group in comma_sep:
    list(filter(lambda char: char not in "1234567890,-", group))
    num1, sep, num2 = group.partition("-")
    assert num1, "No negative numbers allowed"
    if not sep:  # sole number
        numbers.append(int(num1))
    else:
        numbers.extend(range(int(num1), int(num2) + 1))
print(", ".join("Fix #%s" % num for num in numbers))

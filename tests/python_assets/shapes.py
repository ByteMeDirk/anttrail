SIDES = 4


class Shape:
    name = "shape"

    def area(self):
        return 0

    class Style:
        def color(self):
            return "red"


def describe(shape):
    return shape.name

from demo_macros import macros, customliterals, log, value

class Point2D(tuple):
    
    def distance(self, other):
        return ((other[0] - self[0])**2 + (other[1] - self[1])**2)**.5

class Meters(float):

    _units = { 'km': 0.001, 'm': 1, 'dm': 10, 'cm': 100, 'mm': 1000 }

    def __getattr__(self, unit):
        return self * self._units[unit]

def working_with_distances():
    with customliterals:
        tuple = Point2D
        print('Is (0, 0) a Point2D?')
        log[(0, 0).__class__]
        log[(0, 0).distance((1,1))]

    print('Is (0, 0) a Point2D this time?')
    log[(0, 0).__class__]
    log[hasattr((0,0), 'distance')]

def working_with_units():
    with customliterals:
        num = Meters
        log[1780 .km]
    
def a_singleton_example():
    @value
    class the_one:
        realname = 'Thomas A. Anderson'
        alias = 'Neo'

        def quote(): return 'It ends tonight.\n―' + alias

    log[the_one]
    log[the_one.realname]
    print(the_one.quote())

working_with_distances()
working_with_units()
a_singleton_example()

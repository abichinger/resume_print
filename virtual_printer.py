from typing import Callable, Dict, List, Tuple


class Parameter():

    def __init__(self, char: str, type: type):
        self.char = char
        self.type = type


class GCodeInstruction():

    def __init__(self, cmd, required_params: Dict[str, Parameter], optional_params: Dict[str, Parameter], func: Callable, ignore_unknown=True):
        self.cmd = cmd
        self.required_params = required_params
        self.optional_params = optional_params
        self.func = func
        self.ignore_unknown = ignore_unknown

    @property
    def params(self):
        params = self.required_params.copy()
        params.update(self.optional_params)
        return params

    @params.setter
    def params(self, value):
        raise RuntimeError('params is read only')

    def parse(self, gcode):
        [cmd, *args] = gcode.split(" ")

        d = {}
        required = set()
        for arg in args:

            if arg[0] not in self.params:
                if self.ignore_unknown:
                    continue
                else:
                    raise RuntimeError(f'{cmd} has no parameter {arg[0]}')

            if arg[0] in self.required_params:
                required.add(p.char)

            p = self.params[arg[0]]
            d[p.char] = p.type(arg[1:])

        missing = set(self.required_params.keys()) - required
        if len(missing) != 0:
            raise RuntimeError(
                f'required arguments missing for {cmd}: {missing}')

        return d


class VirtualPrinter():

    def __init__(self, x=None, y=None, z=None, e=None, bed_temp=None, hotend_temp=None, fan_speed=None, feed_rate=None, ignore_unknown=True, abs_mode=True):

        self.x = x
        self.y = y
        self.z = z
        self.e = e
        self.feed_rate = feed_rate

        self.bed_temp = bed_temp
        self.hotend_temp = hotend_temp
        self.fan_speed = fan_speed

        self.ignore_unknown = ignore_unknown
        self.abs_mode = True
        self.abs_e_mode = True

        self.instruction_set = {}  # type: Dict[str, GCodeInstruction]

    def register_gcode(self, cmd: str, required_params: List[Tuple[str, type]], optional_params: List[Tuple[str, type]], func, ignore_unknown=True):
        required = {p[0]: Parameter(p[0], p[1]) for p in required_params}
        optional = {p[0]: Parameter(p[0], p[1]) for p in optional_params}
        self.instruction_set[cmd] = GCodeInstruction(
            cmd, required, optional, func, ignore_unknown)

    def process_line(self, gcode: str):
        if gcode.startswith(';'):
            return

        gcode = gcode.split(';')[0].strip()

        [cmd, *_] = gcode.split(" ")
        if cmd not in self.instruction_set:
            if self.ignore_unknown:
                return
            else:
                raise RuntimeError(f'unknown instruction {cmd}')

        instr = self.instruction_set[cmd]
        args = instr.parse(gcode)

        instr.func(self, args)

    def print_status(self):
        print(f'X:{self.x}, Y:{self.y}, Z:{self.z}, E:{self.e}, Bed:{self.bed_temp}°C, Hotend:{self.hotend_temp}°C, Fan-Speed:{self.fan_speed}')


def g28(printer: VirtualPrinter, args: dict):
    printer.x = 0
    printer.y = 0
    printer.z = 0


def g0(printer: VirtualPrinter, args: dict):
    if printer.abs_mode:
        printer.x = args.get('X', printer.x)
        printer.y = args.get('Y', printer.y)
        printer.z = args.get('Z', printer.z)

    else:
        printer.x += args.get('X', 0)
        printer.y += args.get('Y', 0)
        printer.z += args.get('Z', 0)

    if printer.abs_e_mode:
        printer.e = args.get('E', printer.e)
    else:
        printer.e += args.get('E', 0)

    printer.feed_rate = args.get('F', printer.feed_rate)


def m104(printer: VirtualPrinter, args: dict):
    printer.hotend_temp = args.get('S', printer.hotend_temp)


def m140(printer: VirtualPrinter, args: dict):
    printer.bed_temp = args.get('S', printer.bed_temp)


def g90(printer: VirtualPrinter, args: dict):
    printer.abs_mode = True
    printer.abs_e_mode = True


def g91(printer: VirtualPrinter, args: dict):
    printer.abs_mode = False
    printer.abs_e_mode = False


def g92(printer: VirtualPrinter, args: dict):
    printer.x = args.get('X', printer.x)
    printer.y = args.get('Y', printer.y)
    printer.z = args.get('Z', printer.z)
    printer.e = args.get('E', printer.e)


def m82(printer: VirtualPrinter, args: dict):
    printer.abs_e_mode = True


def m83(printer: VirtualPrinter, args: dict):
    printer.abs_e_mode = False


def m106(printer: VirtualPrinter, args: dict):
    printer.fan_speed = args.get('S', printer.fan_speed)


def create_printer():

    p = VirtualPrinter()

    p.register_gcode('G28', [], [], g28)
    p.register_gcode('G0', [], [('X', float), ('Y', float),
                     ('Z', float), ('E', float), ('F', float)], g0)
    p.register_gcode('G1', [], [('X', float), ('Y', float),
                     ('Z', float), ('E', float)], g0)
    p.register_gcode('M104', [], [('S', float)], m104)
    p.register_gcode('M109', [], [('S', float)], m104)
    p.register_gcode('M140', [], [('S', float)], m140)
    p.register_gcode('M190', [], [('S', float)], m140)
    p.register_gcode('M106', [], [('S', float)], m106)
    p.register_gcode('G90', [], [], g90)
    p.register_gcode('G91', [], [], g91)
    p.register_gcode('M82', [], [], m82)
    p.register_gcode('M83', [], [], m83)
    p.register_gcode('G92', [], [('X', float), ('Y', float),
                     ('Z', float), ('E', float)], g92)

    return p

import argparse
import pathlib
import re
from os import path
from typing import List

from virtual_printer import VirtualPrinter, create_printer

parser = argparse.ArgumentParser(
    prog="resume_print",
    description="Resume a 3D print based on your OctoPrint Terminal output.",
)

parser.add_argument("gcode", type=pathlib.Path)
parser.add_argument(
    "-l", "--log", type=pathlib.Path, help="OctoPrint log file", required=True
)
parser.add_argument("-o", "--out", type=pathlib.Path, help="output file", default=None)
parser.add_argument("--home", action="store_true", default=False)
parser.add_argument("--heat", action="store_true", default=False)
parser.add_argument("--keep", type=int, default=0)
parser.add_argument("--prime", action="store_true", default=False)
parser.add_argument("--fan", action="store_true", default=False)
parser.add_argument("--prime-start", type=str, default="0.1,20,0.3")
parser.add_argument("--prime-end", type=str, default="0.1,180,0.3")
parser.add_argument(
    "--lines",
    type=int,
    help="use the last n lines of sent gcode to find the failure position",
    default=5,
)


def linenr_of(file_path: str, search_str: str) -> int:
    with open(file_path, "r") as f:
        content = f.read()
        index = content.index(search_str)
        if index == -1:
            return -1
        return len(content[0:index].split("\n"))


gcode_pattern = re.compile(r"G\d+.*\*")


def gcode_in_log(file_path: str) -> List[str]:
    gcode = []
    with open(file_path, "r") as f:
        for line in f:
            if line.startswith("Send"):
                m = gcode_pattern.search(line)
                gcode.append(line[m.start() : m.end() - 1])
                continue
            if line.startswith("Recv"):
                continue
            break
    return gcode


def run_gcode(printer: VirtualPrinter, gcode: List[str]):
    for line in gcode:
        printer.process_line(line)


def read_lines(file_path: pathlib.Path, start: int = 0, end: int = None) -> List[str]:
    lines = []
    with open(file_path, "r") as f:
        for line_number, line in enumerate(f):
            if end != None and end <= line_number:
                break
            if start <= line_number:
                lines.append(line.strip())

    return lines


def parse_pos(pos: str) -> List[int]:
    return list(map(float, pos.split(",")))


def gen_start_gcode(args, printer: VirtualPrinter) -> List[str]:
    gcode = ["; start gcode"]
    if args.keep > 0:
        gcode += read_lines(args.gcode, end=args.keep)

    if args.home:
        gcode.append("G28")

    if args.heat:
        gcode.append(f"M190 S{printer.bed_temp}")
        gcode.append(f"M109 S{printer.hotend_temp}")

    if args.fan:
        gcode.append(f"M106 S{printer.fan_speed}")

    if args.prime:
        p_start = parse_pos(args.prime_start)
        p_end = parse_pos(args.prime_end)

        gcode += [
            ";Prime",
            "G92 E0 ;Reset Extruder",
            "G1 Z6.0 F3000 ;Move Z Axis up little to prevent scratching of Heat Bed",
            f"G1 X{p_start[0]} Y{p_start[1]} F5000.0 ;Move to start position",
            f"G1 X{p_start[0]} Y{p_start[1]} Z{p_start[2]} F5000.0",
            f"G1 X{p_end[0]} Y{p_end[1]} Z{p_end[2]} F1500.0 E15 ;Draw the first line",
            f"G1 X{p_end[0]+0.3} Y{p_end[1]} Z{p_end[2]} F5000.0 ;Move to side a little",
            f"G1 X{p_start[0]+0.3} Y{p_start[1]} Z{p_start[2]} F1500.0 E30 ;Draw the second line",
            "G92 E0 ;Reset Extruder",
        ]

    gcode.append("; end of start gcode")
    return gcode


if __name__ == "__main__":
    args = parser.parse_args()
    last_gcode = gcode_in_log(args.log)

    search_str = "\n".join(last_gcode[-args.lines :])
    print("Using the following gcode to locate the position of failure:")
    print(search_str + "\n")

    linenr = linenr_of(args.gcode, search_str) + args.lines - 1
    print(f"resuming at line number: {linenr}\n")

    printer = create_printer()
    run_gcode(printer, read_lines(args.gcode, end=linenr))
    print("Lastest printer state:")
    printer.print_status()

    gcode = gen_start_gcode(args, printer)

    # resume print
    gcode += [
        "; resume print",
        f"G0 Z{printer.z+2} F{printer.feed_rate} ;Move up",
        f"G92 E{printer.e} ;Set extruder",
        f"G0 X{printer.x} Y{printer.y} Z{printer.z} ;Move to start position",
    ]

    gcode.append("; Remaining gcode")
    gcode += read_lines(args.gcode, start=linenr)

    output_path = args.out
    if output_path is None:
        output_path = path.join(
            path.dirname(args.gcode), pathlib.Path(args.gcode).stem + "_resume.gcode"
        )

    with open(output_path, "w") as f:
        f.write("\n".join(gcode))

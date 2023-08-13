#!/usr/bin/python2.4
import sys

try:
    out_filename = sys.argv[-1]

    all_lines = []
    for csv_filename in sys.argv[1:-1]:
        lines = []
        with open(csv_filename) as fi:
            for line in fi:
                lines.append(line)

        if len(lines) > 0:
            first_line = lines[0]
            all_lines.extend(lines[1:])

    with open(out_filename, "w") as fo:
        fo.write(first_line)
        if len(all_lines) > 1:
            for line in all_lines:
                fo.write(line)

except OSError:
    print("Can't open file for reading/writing.", sys.argv)
    sys.exit(1)

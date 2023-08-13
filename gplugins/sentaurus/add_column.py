#!/usr/bin/python2.4
import sys

try:
    csv_filename = sys.argv[1]
    extra_label = sys.argv[2]
    extra_value = sys.argv[3]
    lines = []

    with open(csv_filename) as fi:
        for line in fi:
            lines.append(line)

    with open(csv_filename, "w") as fo:
        fo.write(lines[0].strip() + "," + extra_label + "\n")
        # Skip second line!
        for line in lines[2:]:
            if line.strip() != "":
                fo.write(line.strip() + "," + extra_value + "\n")

except OSError:
    print("Can't open file for reading/writing.")
    sys.exit(1)

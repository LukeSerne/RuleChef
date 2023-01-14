import sys

import parser

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"python {sys.argv[0]} infile [outfile]")
        print("    infile   the path to the file containing the rule description")
        print("    outfile  (optional) the path to the file where the code will be output")
        print("             if not specified, the output is printed to standard out")
        return

    rule_file_name = sys.argv[1]
    out_file_name = sys.argv[2] if len(sys.argv) > 2 else None

    rule = parser.parse_description(rule_file_name)
    code = rule.emit_c_code()

    if out_file_name is None:
        print(code)
        return

    with open(out_file_name, "w", encoding="utf-8") as f:
        f.write(code)

if __name__ == "__main__":
    main()

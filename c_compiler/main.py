import io
import pcpp
import pycparser
import sys
from compiler import *

argc = len(sys.argv)
argv = sys.argv

flags = []
allowed_flags = ("-o0", "-o1", "-o2", "-o3", "--nosoftware", "--showir")
if argc < 2:
    print("iris-c: no input files\ncompilation terminated.")
    sys.exit(1)

argv.pop(0)
out_flag_index = -1
non_flags = []

for index, arg in enumerate(argv):
    if arg.lower() == "-o":
        out_flag_index = index
        continue
    if arg.lower() in allowed_flags or arg.startswith("--"):
        flags.append(arg.lower())
        continue

    non_flags.append(arg)

input_file_name = non_flags[0]
output_file_name = "a.urcl"

if len(argv) - 1 >= out_flag_index + 1:
    output_file_name = argv[out_flag_index + 1]
    if not output_file_name.endswith(".urcl"):
        output_file_name += ".urcl"
try:
    with open(input_file_name, "r") as input_file:
        parser = pycparser.c_parser.CParser()
        preprocessor = pcpp.Preprocessor()

        preprocessor.add_path(".")

        preprocessor.parse(input_file.read())
        output = io.StringIO()
        preprocessor.write(output)
        source = output.getvalue()
        ast = parser.parse(source)
        # ast.show()
        compiler_class = IRIS_IR_C(ast, flags, preprocessor)
        compiler_class.compile(output_file_name)


except FileNotFoundError:
    print(
        f"iris-c: cannot find {input_file_name}: No such file or directory\ncompilation terminated."
    )
    sys.exit(1)

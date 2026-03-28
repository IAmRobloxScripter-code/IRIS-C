import io
import pcpp
import pycparser
import sys


argc = len(sys.argv)
argv = sys.argv

flags = []
allowed_flags = ("-O0", "-O1", "-O2", "-O3", "--nosoftware")
if argc < 2:
    print("iris-c: no input files\ncompilation terminated.")
    sys.exit(1)

argv.pop(0)
out_flag_index = -1
non_flags = []

for index, arg in enumerate(argv):
    if arg == "-o":
        out_flag_index = index
        continue
    if arg in allowed_flags or arg.startswith("--"):
        flags.append(arg)
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
    
        preprocessor.add_path('.')  

        preprocessor.parse(input_file)

        output = io.StringIO()
        preprocessor.write(output)
        source = output.getvalue()
        ast = parser.parse(source)
        ast.show()

except FileNotFoundError:
    print(
        f"iris-c: cannot find {input_file_name}: No such file or directory\ncompilation terminated."
    )
    sys.exit(1)

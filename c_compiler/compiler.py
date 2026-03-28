from pycparser import c_ast
from iris_ir.urcl_ir import ir


def get_flag_value(flags: list[str], flag: str):
    for option in flags:
        if option.startswith(flag) and "=" in option:
            value = option.split("=")
            if len(value) >= 2:
                return value[1]
    return None


class C_COMPILER:
    def __init__(self, ast: c_ast.FileAST, flags: list[str]):
        self.ast = ast
        self.flags = flags
        bits = get_flag_value(self.flags, "--bits") or 16
        minheap = get_flag_value(self.flags, "--heapmem") or 64
        minstack = get_flag_value(self.flags, "--stackmem") or 16

        self.module = ir.create_module()
        self.module.set_header(
            "ROM", ("==", bits), min_heap=int(minheap), min_stack=int(minstack)
        )
        

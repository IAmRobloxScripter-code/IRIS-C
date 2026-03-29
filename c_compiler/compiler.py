from pycparser import c_ast
import sys
import os
from typing import TypedDict, Any

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)
from iris_ir.urcl_ir import ir, __BLOCK_CLASS__, __MODULE_CLASS__


class STACK_FRAME(TypedDict):
    builder: Any
    variables: dict[str, Any]
    return_type: object


def get_flag_value(flags: list[str], flag: str):
    for option in flags:
        if option.startswith(flag) and "=" in option:
            value = option.split("=")
            if len(value) >= 2:
                return value[1]
    return None


class IRIS_IR_C:
    def __init__(self, ast: c_ast.FileAST, flags: list[str]):
        self.ast = ast
        self.flags = flags
        self.bits = get_flag_value(self.flags, "--bits") or 16
        minheap = get_flag_value(self.flags, "--heapmem") or 64
        minstack = get_flag_value(self.flags, "--stackmem") or 16

        self.module = ir.create_module()
        self.module.set_header(
            "ROM", ("==", self.bits), min_heap=int(minheap), min_stack=int(minstack)
        )

        self.stack_frames = []
        self.global_frame: STACK_FRAME = {
            "variables": {},
            "builder": self.module,
            "return_type": ir.types.IntType(0)
        }

        self.types = {
            "char": ir.types.IntType(8, True),
            "int": ir.types.IntType(int(self.bits) // 2, False),
            "half": ir.types.HalfType(),
            "float": ir.types.FloatType(),
            "double": ir.types.DoubleType(),
        }

        self.userdef = {}

        for node in ast:
            self.process(node)

        if "--showir" in flags:
            print(self.module)

    def compile(self, outfile: str):
        compiled = self.module.compile(self.flags)
        with open(outfile, "w") as out:
            out.write(compiled)
            out.close()

    def get_stack_frame(self) -> STACK_FRAME:
        if len(self.stack_frames) == 0:
            return self.global_frame
        else:
            return self.stack_frames[len(self.stack_frames) - 1]

    def get_c_int_type(self, types: list[str]):
        signed = True
        size = int(self.bits) // 2

        if "unsigned" in types:
            signed = False
        if "signed" in types:
            signed = True

        long_count = types.count("long")

        if "char" in types:
            size = 8
        elif "short" in types:
            size = min(16, int(self.bits))
        elif long_count == 2:
            size = min(64, int(self.bits))
        elif long_count == 1:
            size = min(32, int(self.bits))
        elif "int" in types or long_count == 0:
            size = int(self.bits) // 2
        else:
            raise ValueError(f"Invalid type: {' '.join(types)}")

        return ir.types.IntType(size, not signed)

    def process(self, node: c_ast.Node):
        if isinstance(node, c_ast.FuncDef):
            return self.create_function(node)
        elif isinstance(node, c_ast.Decl):
            return self.create_decl(node)
        elif isinstance(node, c_ast.Return):
            return self.create_return(node)
        elif isinstance(node, c_ast.Constant):
            return self.create_constant(node)
        elif isinstance(node, c_ast.Typedef):
            return self.process_typedef(node)
        elif isinstance(node, c_ast.BinaryOp):
            return self.create_binary_op(node)
        elif isinstance(node, c_ast.ID):
            return self.get_identifier(node)
        else:
            raise NotImplementedError(
                f"Node type not implemented: {type(node).__name__}"
            )

    def process_type(self, node: c_ast.Node):
        if isinstance(node, c_ast.TypeDecl):
            names = node.type.names
            int_types = ("long", "short", "char", "unsigned", "signed", "int")

            if any(name in names for name in int_types):
                return self.get_c_int_type(node.type.names)
            else:
                return self.types[node.type.names[0]]
        elif isinstance(node, c_ast.PtrDecl):
            return self.process_type(node.type).as_pointer()
        elif isinstance(node, c_ast.ArrayDecl):
            if not node.dim:
                return self.process_type(node.type).as_pointer()
            return ir.types.ArrayType(self.process_type(node.type), int(node.dim.value))
        elif isinstance(node, c_ast.Struct):
            members = []
            for decl in node.decls:
                members.append(self.process_type(decl.type))
            return ir.types.StructType(members)
        elif isinstance(node, c_ast.FuncDecl):
            args = []
            if node.args:
                for decl in node.args:
                    args.append(self.process_type(decl.type)) 

            return ir.types.FunctionType(self.process_type(node.type), args)
        
        if isinstance(node, str) and self.types[node]:
            return self.types[node]
        
        if isinstance(node, str) and self.userdef[node]:
            return self.userdef[node]
                
        raise TypeError("Type does not exist!")
    
    def process_typedef(self, node: c_ast.Typedef):
        self.userdef[node.name] = self.process_type(node.type)

    def get_identifier(self, node: c_ast.ID):
        stack_frame = self.get_stack_frame()

        if node.name in stack_frame["variables"]:
            return stack_frame["variables"][node.name]["memory"]
        elif node.name in self.global_frame["variables"]:
                return self.global_frame["variables"][node.name]["memory"]
        else:
            raise ValueError(f"{node.name} does not exist!")

    def create_binary_op(self, node: c_ast.BinaryOp):
        stack_frame = self.get_stack_frame()
        operator = node.op
        left = self.process(node.left)
        right = self.process(node.right)

        match operator:
            case "+":
                return stack_frame["builder"].add(left, right)
            case "-":
                return stack_frame["builder"].sub(left, right)
            case "*":
                return stack_frame["builder"].mul(left, right)
            case "/":
                return stack_frame["builder"].div(left, right)


    def create_variable(self, node: c_ast.Decl):
        stack_frame = self.get_stack_frame()
        variable_type = self.process_type(node.type)
        memory = stack_frame["builder"].alloc(variable_type)
        stack_frame["variables"][node.name] = {
            "type": variable_type,
            "memory": memory,
        }
        if node.init:
            value = self.process(node.init)
            stack_frame["builder"].store(value, memory)
        
    def create_decl(self, node: c_ast.Decl):
        base_type = self.process_type(node.type)
        if ir.typeof(base_type) != "FunctionType":
            self.create_variable(node)
            return {}

        return {
            "name": node.name,
            "type": base_type,
            "initializer": node.init,
            "storage": node.storage,
            "qualifiers": node.quals,
        }
    
    def create_constant(self, node: c_ast.Constant):
        return ir.constant(self.process_type(node.type), node.value)
    
    def create_return(self, node: c_ast.Return):
        stack_frame = self.get_stack_frame()
        value = self.process(node.expr)
        stack_frame["builder"].ret(stack_frame["return_type"], value)

    def create_function(self, node: c_ast.FuncDef):
        decl = self.create_decl(node.decl)
        func_type = decl["type"]
        func_builder = self.module.create_block()
        func = self.module.create_function(
            func_builder,
            func_type,
            decl["name"],
            decl["type"]["args"],
            inline="inline" in node.decl.funcspec,
        )

        stack_frame = {
            "variables": {},
            "builder": func_builder,
            "return_type": func_type["return_type"]
        }

        self.stack_frames.append(stack_frame)
        has_return = False
        for ast_node in node.body:
            self.process(ast_node)
            if isinstance(ast_node, c_ast.Return):
                has_return = True
                break

        if not has_return:
            func_builder.ret(func_type["return_type"], ir.constant(func_type["return_type"], 0)) 
        
        self.stack_frames.pop()
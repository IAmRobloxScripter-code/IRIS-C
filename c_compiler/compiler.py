from pycparser import c_ast
import sys
import os
from typing import TypedDict, Any

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)
from iris_ir.urcl_ir import ir, __ADDRESS__, __BLOCK_CLASS__, __MODULE_CLASS__
from iris_ir.ir_types import BINARY_OPERATORS, __ARRAY_TYPE__, __POINTER_TYPE__


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
    def __init__(self, ast: c_ast.FileAST, flags: list[str], preprocessor):
        self.ast = ast
        self.flags = flags
        self.macros = preprocessor.macros
        self.bits = get_flag_value(self.flags, "--bits") or 16
        minheap = get_flag_value(self.flags, "--heapmem") or 64
        minstack = get_flag_value(self.flags, "--stackmem") or 16

        if "MINHEAP" in self.macros:
            minheap = int(self.macros["MINHEAP"].value[0].value)
        if "MINSTACK" in self.macros:
            minstack = int(self.macros["MINSTACK"].value[0].value)
        if "BITS" in self.macros:
            self.bits = int(self.macros["BITS"].value[0].value)
        self.module = ir.create_module()
        self.module.set_header(
            "ROM", ("==", self.bits), min_heap=int(minheap), min_stack=int(minstack)
        )

        self.stack_frames = []
        self.global_frame: STACK_FRAME = {
            "variables": {},
            "builder": self.module,
            "return_type": ir.types.IntType(0),
        }

        self.types = {
            "char": ir.types.IntType(8, True),
            "int": ir.types.IntType(int(self.bits) // 2, False),
            "half": ir.types.HalfType(),
            "float": ir.types.FloatType(),
            "double": ir.types.DoubleType(),
        }

        self.possible_casts = {
            "IntType": ["HalfType", "FloatHalf", "DoubleHalf"],
        }

        self.userdef = {}
        self.type_cast_stack = []
        self.if_count = 0
        self.defined_functions = {}

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
        builder: __BLOCK_CLASS__ = self.get_stack_frame()["builder"]
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
            return builder.load(self.get_identifier(node))
        elif isinstance(node, c_ast.If):
            return self.create_if(node)
        elif isinstance(node, c_ast.UnaryOp):
            return self.create_unary_op(node)
        elif isinstance(node, c_ast.While):
            return self.create_while(node)
        elif isinstance(node, c_ast.Assignment):
            return self.create_assignment(node)
        elif isinstance(node, c_ast.ArrayRef):
            return builder.load(self.create_array_index(node))
        elif isinstance(node, c_ast.FuncCall):
            return self.create_call(node)
        else:
            raise NotImplementedError(
                f"Node type not implemented: {type(node).__name__}"
            )

    def process_lvalue(self, node: c_ast.Node):
        if isinstance(node, c_ast.ID):
            return self.get_identifier(node)
        elif isinstance(node, c_ast.ArrayRef):
            return self.create_array_index(node)
        elif isinstance(node, c_ast.UnaryOp):
            return self.create_unary_op(node)
        else:
            return self.process(node)

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

        if node.name in self.defined_functions:
            return self.defined_functions[node.name]["memory"]

        if node.name in stack_frame["variables"]:
            return stack_frame["variables"][node.name]["memory"]
        else:
            for index in range(len(self.stack_frames) - 1, -1, -1):
                frame = self.stack_frames[index]
                if node.name in frame["variables"]:
                    return frame["variables"][node.name]["memory"]

        if node.name in self.global_frame["variables"]:
            return self.global_frame["variables"][node.name]["memory"]
        else:
            raise ValueError(f"{node.name} does not exist!")

    def create_unary_op(self, node: c_ast.UnaryOp):
        stack_frame = self.get_stack_frame()
        operator = node.op

        match operator:
            case "~":
                return stack_frame["builder"].NOT(self.process(node.expr))
            case "*":
                deref_value = stack_frame["builder"].load(self.process(node.expr))
                return deref_value
                # return self.process(node.expr)
            case "&":
                value = self.process_lvalue(node.expr)
                if value:
                    return stack_frame["builder"].as_pointer(
                        value, value["name"], propagate=False
                    )

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
            case ">>":
                return stack_frame["builder"].RS(left, right)
            case "<<":
                return stack_frame["builder"].LS(left, right)
            case "&":
                return stack_frame["builder"].AND(left, right)
            case "|":
                return stack_frame["builder"].OR(left, right)
            case "^":
                return stack_frame["builder"].XOR(left, right)
            case "==" | "!=" | ">=" | "<=" | ">" | "<":
                return stack_frame["builder"].compare(operator, left, right)

    def create_array(self, array_type, node: c_ast.InitList):
        size = None
        if isinstance(array_type, __ARRAY_TYPE__):
            size = array_type.size

        array = []
        elements = 0
        for element in node.exprs:
            if isinstance(element, c_ast.InitList):
                array.append(self.create_array(array_type.of, element))
            else:
                array.append(self.process(element))
            elements += 1

        if size and elements < size:
            for _ in range(size - elements):
                if isinstance(array_type, __ARRAY_TYPE__):
                    array.append(ir.constant(array_type.of, 0))

        if isinstance(array_type, __ARRAY_TYPE__):
            array_type = ir.types.ArrayType(array_type.of, len(array))
            value = ir.constant(ir.types.ArrayType(array_type.of, len(array)), array)
        elif isinstance(array_type, __POINTER_TYPE__):
            array_type = ir.types.ArrayType(array_type.to, len(array))
            value = ir.constant(ir.types.ArrayType(array_type.of, len(array)), array)
        return value

    def create_variable(self, node: c_ast.Decl):
        stack_frame = self.get_stack_frame()
        variable_type = self.process_type(node.type)
        value = None
        if node.init:
            if isinstance(node.init, c_ast.InitList):
                size = None
                if isinstance(variable_type, __ARRAY_TYPE__):
                    size = variable_type.size

                array = []
                elements = 0
                for element in node.init.exprs:
                    if isinstance(element, c_ast.InitList):
                        if isinstance(variable_type, __ARRAY_TYPE__):
                            array.append(self.create_array(variable_type.of, element))
                        elif isinstance(variable_type, __POINTER_TYPE__):
                            array.append(self.create_array(variable_type.to, element))
                    else:
                        array.append(self.process(element))
                    elements += 1

                if size and elements < size:
                    for _ in range(size - elements):
                        if isinstance(variable_type, __ARRAY_TYPE__):
                            array.append(ir.constant(variable_type.of, 0))

                if isinstance(variable_type, __ARRAY_TYPE__):
                    variable_type = ir.types.ArrayType(variable_type.of, len(array))
                    value = ir.constant(
                        ir.types.ArrayType(variable_type.of, len(array)), array
                    )
                elif isinstance(variable_type, __POINTER_TYPE__):
                    variable_type = ir.types.ArrayType(variable_type.to, len(array))
                    value = ir.constant(
                        ir.types.ArrayType(variable_type.of, len(array)), array
                    )
            else:
                self.type_cast_stack.append(variable_type)
                value = self.process(node.init)
        memory = stack_frame["builder"].alloc(
            variable_type,
            name=node.name,
            volatile=("volatile" in node.quals),
        )
        stack_frame["variables"][node.name] = {
            "type": variable_type,
            "memory": memory,
        }
        if value:
            # value = stack_frame["builder"].load(value)
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

    def get_type_cast(self, default):
        if len(self.type_cast_stack) == 0:
            return default
        else:
            return self.type_cast_stack.pop()

    def create_constant(self, node: c_ast.Constant):
        normal_type = self.process_type(node.type)
        constant_type = self.get_type_cast(normal_type)
        if (
            constant_type["kind"] not in self.possible_casts
            or normal_type["kind"] not in self.possible_casts[constant_type["kind"]]
        ):
            constant_type = normal_type
        return ir.constant(constant_type, node.value)

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

        self.defined_functions[decl["name"]] = {
            "memory": func_builder.as_pointer(func),
            "type": decl["type"],
        }

        stack_frame = {
            "variables": {},
            "builder": func_builder,
            "return_type": func_type["return_type"],
        }
        args = node.decl.type.args
        if args and args.params:
            for index, arg in enumerate(args.params):
                arg_type = self.process_type(arg.type)
                memory = func_builder.alloc(arg_type)
                func_builder.store(func["args"][index], memory)
                stack_frame["variables"][arg.name] = {
                    "memory": memory,
                    "type": arg_type,
                }

        self.stack_frames.append(stack_frame)
        has_return = False
        for ast_node in node.body:
            self.process(ast_node)
            if isinstance(ast_node, c_ast.Return):
                has_return = True
                break
        if not has_return:
            func_builder.ret(
                func_type["return_type"], ir.constant(func_type["return_type"], 0)
            )

        self.stack_frames.pop()

    def create_if(self, node: c_ast.If):
        self.if_count += 1
        stack_frame = self.get_stack_frame()
        builder: __BLOCK_CLASS__ = stack_frame["builder"]

        condition_block = builder.create_block()
        builder.label(condition_block, f"if_cond_{self.if_count}", eliminate=False)

        then_block = builder.create_block()
        then_label = builder.label(then_block, f"if_then_{self.if_count}")

        else_block = builder.create_block()
        else_label = builder.label(else_block, f"if_else_{self.if_count}")

        current_frame = self.get_stack_frame()
        self.stack_frames.append(
            {
                "variables": current_frame["variables"],
                "builder": condition_block,
                "return_type": None,
            }
        )
        condition = self.process(node.cond)
        condition_block.branch(condition, then_label, else_label)
        self.stack_frames.pop()

        self.stack_frames.append(
            {
                "variables": {},
                "builder": then_block,
                "return_type": None,
            }
        )

        for ast_node in node.iftrue:
            self.process(ast_node)
            if isinstance(ast_node, c_ast.Return):
                break

        self.stack_frames.pop()

        if node.iffalse:
            self.stack_frames.append(
                {
                    "variables": {},
                    "builder": else_block,
                    "return_type": None,
                }
            )

            for ast_node in node.iffalse:
                self.process(ast_node)
                if isinstance(ast_node, c_ast.Return):
                    break

            self.stack_frames.pop()

    def create_while(self, node: c_ast.While):
        self.if_count += 1
        stack_frame = self.get_stack_frame()
        builder: __BLOCK_CLASS__ = stack_frame["builder"]
        condition_block = builder.create_block()
        condition_label = builder.label(
            condition_block, f"loop_cond_{self.if_count}", eliminate=False
        )

        start_block: __BLOCK_CLASS__ = builder.create_block()
        start_label = builder.label(start_block, f"loop_start_{self.if_count}")

        end_label = builder.label(None, f"loop_end_{self.if_count}", eliminate=False)

        condition = self.process(node.cond)
        condition_block.branch(condition, start_label, end_label)

        self.stack_frames.append(
            {
                "variables": {},
                "builder": start_block,
                "return_type": None,
            }
        )

        for ast_node in node.stmt:
            self.process(ast_node)
            if isinstance(ast_node, c_ast.Return):
                break
        start_block.jump(condition_label)

        self.stack_frames.pop()

    def create_assignment(self, node: c_ast.Assignment):
        stack_frame = self.get_stack_frame()
        operator = node.op
        lvalue = self.process_lvalue(node.lvalue)
        rvalue = self.process(node.rvalue)

        match operator:
            case "=":
                stack_frame["builder"].store(rvalue, lvalue)
            case "+=" | "-=" | "*=" | "/=" | ">>=" | "<<=" | "&=" | "|=" | "^=":
                symbol = operator[0]
                stack_frame["builder"].store(
                    stack_frame["builder"][BINARY_OPERATORS[symbol]](
                        lvalue,
                        rvalue,
                    ),
                    lvalue,
                )

    def create_array_index(self, node: c_ast.ArrayRef):
        stack_frame = self.get_stack_frame()
        lvalue = self.process(node.name)
        lvalue_type = None
        if lvalue["kind"] == "GetElementPointerBlock":
            lvalue_type = lvalue["element_type"]
        else:
            lvalue_type = lvalue["type"]["to"]
        index = self.process(node.subscript)

        return stack_frame["builder"].get_element_pointer(
            lvalue, lvalue_type["of"], index
        )

    def create_call(self, node: c_ast.FuncCall):
        stack_frame = self.get_stack_frame()
        func = self.process(node.name)
        args = []

        for arg in node.args:
            args.append(self.process(arg))

        return stack_frame["builder"].call(func["pointer"], args)

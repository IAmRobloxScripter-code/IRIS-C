# URCL_TYPES = {
#     "IntType": def(bits: int):
#         pass
# }
from typing import Union

MAX_BITS = 16
REPR_MODULE_INDENTATION = 2


class __POINTER_TYPE__:
    def __init__(self, type: object):
        self.kind = "PointerType"
        self.to = type
        self.size_in_bits = MAX_BITS

    def __getitem__(self, key):
        return getattr(self, key)

    def as_pointer(self):
        return __POINTER_TYPE__(self)

    def as_string(self):
        return f"{self.to.as_string()}*"  # type: ignore


class __INT_TYPE__:
    def __init__(self, size: int):
        self.kind = "IntType"
        self.size = size
        self.size_in_bits = size

    def __getitem__(self, key):
        return getattr(self, key)

    def as_pointer(self):
        return __POINTER_TYPE__(self)

    def as_string(self):
        return f"i{self.size}"


class __HALF_TYPE__:
    def __init__(self):
        self.kind = "HalfType"
        self.size_in_bits = 16

    def __getitem__(self, key):
        return getattr(self, key)

    def as_pointer(self):
        return __POINTER_TYPE__(self)

    def as_string(self):
        return "half"


class __FLOAT_TYPE__:
    def __init__(self):
        self.kind = "FloatType"
        self.size_in_bits = 32

    def __getitem__(self, key):
        return getattr(self, key)

    def as_pointer(self):
        return __POINTER_TYPE__(self)

    def as_string(self):
        return "float"


class __DOUBLE_TYPE__:
    def __init__(self):
        self.kind = "DoubleType"
        self.size_in_bits = 64

    def __getitem__(self, key):
        return getattr(self, key)

    def as_pointer(self):
        return __POINTER_TYPE__(self)

    def as_string(self):
        return "double"

class __ARRAY_TYPE__:
    def __init__(self, of, size: int):
        self.kind = "ArrayType"
        self.of = of
        self.size = size
        self.size_in_bits = of.size_in_bits * size

    def __getitem__(self, key):
        return getattr(self, key)

    def as_pointer(self):
        return __POINTER_TYPE__(self)

    def as_string(self):
        return f"[{self.size} x {self.of.as_string()}]"

class __STRING_TYPE__:
    def __init__(self, size: int = 0):
        self.kind = "StringType"
        self.size_in_bits = MAX_BITS
        self.representation = __ARRAY_TYPE__(__INT_TYPE__(8), size);

    def __getitem__(self, key):
        return getattr(self, key)

    def as_pointer(self):
        return __POINTER_TYPE__(self)

    def as_string(self):
        return self.representation.as_string()

class __FUNCTION_TYPE__:
    def __init__(self, return_type: object, args: list[object]):
        self.kind = "FunctionType"
        self.return_type = return_type
        self.args = args
        self.size = MAX_BITS

    def __getitem__(self, key):
        return getattr(self, key)

    def as_pointer(self):
        return __POINTER_TYPE__(self)

    def as_string(self):
        representation = f"{self.return_type.as_string()} ("  # type: ignore
        for index, arg in enumerate(self.args):
            representation += f"{arg.as_string()}{", " if index + 1 != len(self.args) else ""}"  # type: ignore
        representation += ")"
        return representation


class __URCL_TYPES_CLASS__:
    def IntType(self, size: int):
        return __INT_TYPE__(size)

    def HalfType(self):
        return __HALF_TYPE__()

    def FloatType(self):
        return __FLOAT_TYPE__()

    def DoubleType(self):
        return __DOUBLE_TYPE__()

    def StringType(self, size: int = 0):
        return __STRING_TYPE__(size)

    def ArrayType(self, of: object, size: int):
        return __ARRAY_TYPE__(of, size)

    def PointerType(self, of: object):
        return __POINTER_TYPE__(of)

    def FunctionType(self, return_type: object, args: list[object]):
        return __FUNCTION_TYPE__(return_type, args)


class __VALUE__:
    def __init__(self, type, name):
        self.kind = "ValueBlock"
        self.type = type
        self.name = name

    def __getitem__(self, key):
        return getattr(self, key)


class __CONSTANT__:
    def __init__(self, type, value):
        self.kind = "ConstantBlock"
        self.type = type
        self.value = value

    def __getitem__(self, key):
        return getattr(self, key)

    def as_int_str(self):
        return str(self.value)

    def as_float_str(self):
        return str(float(self.value))

    def as_array_str(self):
        representation = "["
        for index, element in enumerate(self.value):
            representation += (
                f"{element.as_string()}{", " if index + 1 != len(self.value) else ""}"
            )
        representation += "]"
        return representation

    def as_string_str(self):
        return rf'c"{self.value}\00"'

    def as_string(self):
        if self.type["kind"] == "IntType":
            return self.as_int_str()
        elif self.type["kind"] in ("HalfType", "FloatType", "DoubleType"):
            return self.as_float_str()
        elif self.type["kind"] == "ArrayType":
            return self.as_array_str()
        elif self.type["kind"] == "StringType":
            return self.as_string_str()


class __IR_CLASS__:
    def __init__(self):
        self.urcl_types = __URCL_TYPES_CLASS__()

    def create_module(self) -> "__MODULE_CLASS__": ...

    def constant(self, type: object, value):
        return __CONSTANT__(type, value)


ir = __IR_CLASS__()


class __BLOCK_CLASS__:
    def __init__(self, parent):
        self.kind = "BlockClass"
        self.parent = parent
        self.blocks = []
        self.stack = {}
        self.temporary_count = 0

    def __getitem__(self, key):
        return getattr(self, key)

    def create_block(self):
        return __BLOCK_CLASS__(self)

    def temporary(self):
        self.temporary_count += 1
        return str(self.temporary_count)

    def alloc(self, type, name=None):
        identifier = name or self.temporary()
        value = __VALUE__(type, identifier)
        self.blocks.append({"kind": "AllocBlock", "type": type, "result": value})
        self.stack[identifier] = {
            "kind": "AllocatedMemoryBlock",
            "type": type,
            "value": value,
        }
        return value

    def store(self, value, memory):
        self.blocks.append({"kind": "StoreBlock", "memory": memory, "value": value})

    def ret(self, value):
        self.blocks.append({"kind": "ReturnBlock", "value": value})

    def add(self, left, right, name=None):
        identifier = name or self.temporary()
        block = {"kind": "AddBlock", "left": left, "right": right, "result": identifier}

        return block

    def sub(self, left, right, name=None):
        identifier = name or self.temporary()
        block = {"kind": "SubBlock", "left": left, "right": right, "result": identifier}

        return block


class __MODULE_IR__:
    def __init__(self, blocks: list, data: dict):
        self.module = ""
        self.blocks = (blocks,)
        self.data = data
        self.indentation = 0
        self.stack_frame = []

        for block in blocks:
            self.ir(block)

    def enter_stack_frame(self):
        self.stack_frame.append({"kind": "FunctionFrame", "data": {}})

    def exit_stack_frame(self):
        self.stack_frame.pop()

    def get_stack_frame(self):
        if len(self.stack_frame) != 0:
            return self.stack_frame[len(self.stack_frame) - 1]
        else:
            return {}

    def ir(self, block):
        match block["kind"]:
            case "GlobalMemoryBlock":
                return self.global_memory_block(block)
            case "FunctionBlock":
                return self.function_ir(block)
            case "HeaderBlock":
                return self.header_ir(block)
            case "AllocBlock":
                return self.alloc_ir(block)
            case "StoreBlock":
                return self.store_ir(block)
            case "ReturnBlock":
                return self.ret_ir(block)
            case "ConstantBlock":
                return self.constant_ir(block)
            case "ValueBlock":
                return self.value_ir(block)
            case "AddBlock" | "SubBlock":
                return self.operator_ir(block)

    def write(self, text: str):
        self.module += f"{" "*(self.indentation * REPR_MODULE_INDENTATION)}{text}"

    def writeln(self, text: str):
        self.module += f"{" "*(self.indentation * REPR_MODULE_INDENTATION)}{text}\n"

    def inc_indentation(self, amount: int = 1):
        self.indentation += amount

    def dec_indentation(self, amount: int = 1):
        self.indentation -= amount

    def header_ir(self, block):
        if type(block["value"]) == tuple:
            self.writeln(
                f"#{block["header_kind"]} {block["value"][0]} {block["value"][1]}"
            )
        else:
            self.writeln(f"#{block["header_kind"]} == {block["value"]}")

    def global_memory_block(self, block):
        self.writeln(
            f"global {block["name"]} = {block["type"].as_string()}, {block["initializer"].as_string()}"
        )
        return f"@{block["name"]}"

    def alloc_ir(self, block):
        frame = self.get_stack_frame()
        frame["data"][block["result"].name] = {
            "kind": "LocalVariable",
            "type": block["result"].type,
            "initialized": False,
        }
        return block["result"].name

    def constant_ir(self, block):
        return block.as_string(), block.type.as_string()

    def value_ir(self, block):
        return f"%{block.name}", block.type.as_string()

    def store_ir(self, block):
        frame = self.get_stack_frame()
        if block["memory"].name in frame["data"]:
            if not frame["data"][block["memory"].name]["initialized"]:
                self.writeln(
                    f"%{block["memory"].name} = alloc {block["memory"].type.as_string()}"
                )
            frame["data"][block["memory"].name]["initialized"] = True
            value, type = self.ir(block["value"])  # type: ignore

            self.writeln(
                f"store {type} {value}, {block["memory"].type.as_pointer().as_string()} %{block["memory"].name}"
            )

    def function_ir(self, block):
        self.write(f"func {block["name"]} {block["type"].as_string()}")
        if block["block"] == None:
            return
        self.writeln(" {")
        self.inc_indentation()
        self.enter_stack_frame()
        for nested_block in block["block"].blocks:
            self.ir(nested_block)
        self.exit_stack_frame()
        self.dec_indentation()
        self.writeln("}")

    def ret_ir(self, block):
        value, type = self.ir(block["value"])  # type: ignore
        self.writeln(f"ret {type} {value}")

    def operator_ir(self, block):
        left_value, left_type = self.ir(block["left"])  # type: ignore
        right_value, right_type = self.ir(block["right"])  # type: ignore

        match block["kind"]:
            case "AddBlock":
                self.writeln(
                    f"%{block["result"]} = add {left_type} {left_value}, {right_value}"
                )
            case "SubBlock":
                self.writeln(
                    f"%{block["result"]} = sub {left_type} {left_value}, {right_value}"
                )
        return block["result"], left_type


class __MODULE_CLASS__:
    def __init__(self):
        self.blocks = []
        self.data = {}
        self.temporary_count = 0

    def __getitem__(self, key):
        return getattr(self, key)

    @property
    def module(self):
        return __MODULE_IR__(self.blocks, self.data).module

    def create_function(
        self,
        block: Union[__BLOCK_CLASS__, None],
        type: __FUNCTION_TYPE__,
        name: str,
        args: list[object],
    ):
        function_block = {
            "kind": "FunctionBlock",
            "block": block,
            "type": type,
            "name": name,
            "args": [],
        }

        for index in range(len(args)):
            function_block["args"][index] = {"arg": args[index], "name": ""}

        self.blocks.append(function_block)
        return function_block

    def add(self, left, right, name=None):
        identifier = name or self.temporary()
        self.blocks.append(
            {"kind": "AddBlock", "left": left, "right": right, "result": identifier}
        )

    def sub(self, left, right, name=None):
        identifier = name or self.temporary()
        block = {"kind": "SubBlock", "left": left, "right": right, "result": identifier}

        return block
    
    def get_element_pointer(self, ):
        

    def global_variable(self, name, type: object, initializer: __CONSTANT__):
        identifier = name or self.temporary()
        block = {
            "kind": "GlobalMemoryBlock",
            "name": identifier,
            "type": type,
            "initializer": initializer,
        }
        self.blocks.append(block)
        self.data[identifier] = block
        return block
    
    def create_global_string(self, value, name = None):
        return self.global_variable(
            name,
            ir.urcl_types.StringType(len(value) + 1),
            ir.constant(ir.urcl_types.StringType(len(value) + 1), value),
        )

    def create_block(self):
        return __BLOCK_CLASS__(self)

    def temporary(self):
        self.temporary_count += 1
        return str(self.temporary_count)

    def set_header(
        self,
        run="ROM",
        bits=("==", 16),
        min_reg=16,
        min_heap=64,
        min_stack=16,
    ):
        self.blocks.append(
            {
                "kind": "HeaderBlock",
                "value": run,
                "header_kind": "run",
            }
        )
        self.blocks.append(
            {
                "kind": "HeaderBlock",
                "value": bits,
                "header_kind": "bits",
            }
        )
        self.blocks.append(
            {
                "kind": "HeaderBlock",
                "value": min_heap,
                "header_kind": "minheap",
            }
        )
        self.blocks.append(
            {
                "kind": "HeaderBlock",
                "value": min_reg,
                "header_kind": "minreg",
            }
        )
        self.blocks.append(
            {
                "kind": "HeaderBlock",
                "value": min_stack,
                "header_kind": "minstack",
            }
        )

    def set_constants(
        self,
        umax=None,
        smax=None,
        msb=None,
        smsb=None,
        uhalf=None,
        lhalf=None,
        heap=None,
    ):
        if umax:
            self.blocks.append(
                {
                    "kind": "HeaderBlock",
                    "value": umax,
                    "header_kind": "umax",
                }
            )

        if smax:
            self.blocks.append(
                {
                    "kind": "HeaderBlock",
                    "value": smax,
                    "header_kind": "smax",
                }
            )

        if msb:
            self.blocks.append(
                {
                    "kind": "HeaderBlock",
                    "value": msb,
                    "header_kind": "msb",
                }
            )

        if smsb:
            self.blocks.append(
                {
                    "kind": "HeaderBlock",
                    "value": smsb,
                    "header_kind": "smsb",
                }
            )

        if uhalf:
            self.blocks.append(
                {
                    "kind": "HeaderBlock",
                    "value": uhalf,
                    "header_kind": "uhalf",
                }
            )

        if lhalf:
            self.blocks.append(
                {
                    "kind": "HeaderBlock",
                    "value": lhalf,
                    "header_kind": "lhalf",
                }
            )

        if heap:
            self.blocks.append(
                {
                    "kind": "HeaderBlock",
                    "value": heap,
                    "header_kind": "heap",
                }
            )


def __create_module__(self):
    return __MODULE_CLASS__()


__IR_CLASS__.create_module = __create_module__

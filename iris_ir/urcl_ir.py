# types = {
#     "IntType": def(bits: int):
#         pass
# }
from typing import Union
from .ir_types import __ADDRESS__, __TEMPORARY_VALUE__, __types_CLASS__, __CONSTANT__, __VALUE__, REPR_MODULE_INDENTATION, __FUNCTION_TYPE__, TYPEDEF_FUNCTION_ARGUMENT
from .urcl_ir_compiler import __COMPILER__, __format_urcl__
from typing import TypedDict

class __IR_CLASS__:
    def __init__(self):
        self.types = __types_CLASS__()

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
        address = __ADDRESS__(type, identifier, value)
        self.blocks.append({"kind": "AllocBlock", "type": type, "result": value})
        self.stack[identifier] = {
            "kind": "AllocatedMemoryBlock",
            "type": type,
            "value": value,
        }
        return address

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

    def mul(self, left, right, name=None):
        identifier = name or self.temporary()
        block = {"kind": "MulBlock", "left": left, "right": right, "result": identifier}

        return block

    def div(self, left, right, name=None):
        identifier = name or self.temporary()
        block = {"kind": "DivBlock", "left": left, "right": right, "result": identifier}

        return block

    def get_element_pointer(
        self, pointer, element_type, index: __CONSTANT__, name=None
    ):
        return {
            "kind": "GetElementPointerBlock",
            "element_type": element_type,
            "pointer": pointer,
            "index": index,
            "name": name or self.temporary(),
        }
    
    def call(self, func, arguments: list, name=None):
        identifier = name or self.temporary()
        block = {"kind": "CallBlock", "func": func, "args": arguments, "result": identifier}
        self.blocks.append(block)

        return __TEMPORARY_VALUE__(func["type"].return_type, identifier)
    
    def load(self, pointer):
        return {
            "kind": "LoadValueBlock",
            "pointer": pointer
        }

class __MODULE_IR__:
    def __init__(self, blocks: list, data: dict):
        self.module = ""
        self.blocks = blocks
        self.data = data
        self.indentation = 0
        self.stack_frames = []
        self.globals = []
        self.ssa = []

        for block in blocks:
            self.ir(block)

    def enter_stack_frame(self):
        self.stack_frames.append({"kind": "FunctionFrame", "data": {}, "ssa": []})

    def exit_stack_frame(self):
        self.stack_frames.pop()

    def get_stack_frame(self):
        if len(self.stack_frames) != 0:
            return self.stack_frames[len(self.stack_frames) - 1]
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
            case "AddBlock" | "SubBlock" | "MulBlock" | "DivBlock":
                return self.operator_ir(block)
            case "GetElementPointerBlock":
                return self.gep_ir(block)
            case "CallBlock":
                return self.call_ir(block)
            case "ArgumentBlock":
                return f"%{block["name"]}", block["arg"]
            case "TemporaryBlock":
                return self.temp_ir(block)
            case "AddressBlock":
                return self.address_ir(block)
            case "LoadValueBlock":
                return self.load_ir(block)

    def write(self, text: str, respect_indentation: bool = False):
        self.module += f"{" "*REPR_MODULE_INDENTATION if respect_indentation else ""}{text}"

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
        if len(self.stack_frames) != 0:
            return f"@{block["name"]}", block["type"]
        if block["name"] in self.globals:
            return f"@{block["name"]}", block["type"]
        self.writeln(
            f"global @{block["name"]} = {block["type"].as_string()}, {block["initializer"].as_string()}"
        )
        self.globals.append(block["name"])
        return f"@{block["name"]}", block["type"]

    def alloc_ir(self, block):
        frame = self.get_stack_frame()
        if block["result"].name in frame["data"]:
            return "%" + block["result"].name, block["result"].type
        frame["data"][block["result"].name] = {
            "kind": "LocalVariable",
            "type": block["result"].type,
            "initialized": False,
        }
        return "%" + block["result"].name, block["result"].type

    def constant_ir(self, block):
        return block.as_string(), block.type

    def value_ir(self, block):
        return f"%{block.name}", block.type

    def get_symbol_from_name(self, name: str):
        return "%" if name not in self.globals else "@"

    def store_ir(self, block):
        frame = self.get_stack_frame()
        memory = block["memory"]
        if memory.name in frame["data"]:
            if not frame["data"][memory.name]["initialized"]:
                self.writeln(
                    f"%{memory.name} = alloc {memory.value.type.as_string()}"
                )
            frame["data"][memory.name]["initialized"] = True
            value, type = self.ir(block["value"])  # type: ignore
            name, alloc_type = self.ir(memory)  # type: ignore
            self.writeln(
                f"store {type.as_string()} {value}, {alloc_type.as_string()} {name}"  # type: ignore
            )

    def function_ir(self, block):
        if len(self.stack_frames) != 0:
            return block["name"], block["type"]
        if block["block"] == None:
            return block["name"], block["type"]

        self.write(f"func {block["name"]} {block["type"].return_type.as_string()} (")
        for index, arg in enumerate(block["args"]):
             self.write(f"{arg["arg"].as_string()} {arg["name"]}{", " if index + 1 != len(block["args"]) else ""}")  # type: ignore
        
        self.write(")")
        if len(block["block"].blocks) == 0:
            self.writeln("")
            return block["name"], block["type"]

        self.writeln(" {")
        self.inc_indentation()
        self.enter_stack_frame()
        for nested_block in block["block"].blocks:
            self.ir(nested_block)
        self.exit_stack_frame()
        self.dec_indentation()
        self.writeln("}")
        return block["name"], block["type"]

    def ret_ir(self, block):
        value, value_type = self.ir(block["value"])  # type: ignore
        self.writeln(f"ret {value_type.as_string()} {self.get_symbol_from_name(value) if type(block["value"]) != __CONSTANT__ else ""}{value}")  # type: ignore

    def get_symbol(self):
        return "@" if len(self.stack_frames) == 0 else "%"

    def operator_ir(self, block):
        left_value, left_type = self.ir(block["left"])  # type: ignore
        right_value, right_type = self.ir(block["right"])  # type: ignore
        symbol = self.get_symbol()
        match block["kind"]:
            case "AddBlock":
                self.writeln(
                    f"{symbol}{block["result"]} = add {left_type.as_string()} {left_value}, {right_value}"
                )
            case "SubBlock":
                self.writeln(
                    f"{symbol}{block["result"]} = sub {left_type.as_string()} {left_value}, {right_value}"
                )

            case "MulBlock":
                self.writeln(
                    f"{symbol}{block["result"]} = mul {left_type.as_string()} {left_value}, {right_value}"
                )

            case "DivBlock":
                self.writeln(
                    f"{symbol}{block["result"]} = div {left_type.as_string()} {left_value}, {right_value}"
                )

        return self.get_symbol() + block["result"], left_type

    def gep_ir(self, block):
        pointer, pointer_type = self.ir(block["pointer"])
        index, index_type = self.ir(block["index"])
        self.writeln(
            f"{self.get_symbol()}{block["name"]} = getelementptr {pointer_type.as_string()} {pointer}, {index_type.as_string()} {index}"
        )
        return (
            self.get_symbol_from_name(block["name"]) + block["name"],
            block["element_type"],
        )
    
    def call_ir(self, block):
        func_name, func_type = self.ir(block["func"])
        self.write(f"{self.get_symbol()}{block["result"]} = call {func_type["return_type"].as_string()} @{func_name}(", True)
        for index, arg in enumerate(block["args"]):
            value, value_type = self.ir(arg) # type: ignore
            self.write(f"{value_type.as_string()} {value}{", " if index + 1 != len(block["args"]) else ""}")
        self.write(")")
        self.writeln("")
        return "%" + block["result"], func_type["return_type"]
    
    def temp_ir(self, block):
        if len(self.stack_frames) != 0:
            stack_frame = self.get_stack_frame()
            if block.name in stack_frame["ssa"]:
                return "%" + block.name, block.type
            stack_frame["ssa"].append(block.name)
            return "%" + block.name, block.type
        else:
            if block.name in self.ssa:
                return "@" + block.name, block.type
            else:
                self.ssa.append(block.name)
                return "@" + block.name, block.type
    
    def address_ir(self, block):
        return "%" + block.name, block.type
    
    def load_ir(self, block):
        result, result_type = self.ir(block["pointer"])
        return result, result_type

class TYPEDEF_FUNCTION_BLOCK(TypedDict):
    name: str
    block: __BLOCK_CLASS__
    args: list[TYPEDEF_FUNCTION_ARGUMENT]

class __MODULE_CLASS__:
    def __init__(self):
        self.blocks = []
        self.data = {}
        self.temporary_count = 0

    def __getitem__(self, key):
        return getattr(self, key)

    def compile(self):
        return __format_urcl__(__COMPILER__(self.blocks).urcl)

    def __str__(self):
        return __MODULE_IR__(self.blocks, self.data).module

    def create_function(
        self,
        block: Union[__BLOCK_CLASS__, None],
        type: __FUNCTION_TYPE__,
        name: str,
        args: list[object],
    ) -> TYPEDEF_FUNCTION_BLOCK:
        function_block = {
            "kind": "FunctionBlock",
            "block": block,
            "type": type,
            "name": name,
            "args": [],
        }

        for index in range(len(args)):
            function_block["args"].append({"kind": "ArgumentBlock", "arg": args[index], "name": block.temporary()}) # type: ignore

        self.blocks.append(function_block)
        return function_block # type: ignore
    
    def call(self, func, arguments: list, name=None):
        identifier = name or self.temporary()
        block = {"kind": "CallBlock", "func": func, "args": arguments, "result": identifier}
        self.blocks.append(block)

        return __TEMPORARY_VALUE__(func["type"].return_type, identifier)

    def add(self, left, right, name=None):
        identifier = name or self.temporary()
        block = {"kind": "AddBlock", "left": left, "right": right, "result": identifier}

        return block

    def sub(self, left, right, name=None):
        identifier = name or self.temporary()
        block = {"kind": "SubBlock", "left": left, "right": right, "result": identifier}

        return block

    def mul(self, left, right, name=None):
        identifier = name or self.temporary()
        block = {"kind": "MulBlock", "left": left, "right": right, "result": identifier}

        return block

    def div(self, left, right, name=None):
        identifier = name or self.temporary()
        block = {"kind": "DivBlock", "left": left, "right": right, "result": identifier}

        return block

    def get_element_pointer(
        self, pointer, element_type, index: __CONSTANT__, name=None
    ):
        return {
            "kind": "GetElementPointerBlock",
            "element_type": element_type,
            "pointer": pointer,
            "index": index,
            "name": name or self.temporary(),
        }
    
    def load(self, pointer):
        return {
            "kind": "LoadValueBlock",
            "pointer": pointer
        }

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

    def create_global_string(self, value, name=None):
        return self.global_variable(
            name,
            ir.types.StringType(len(value) + 1).as_pointer(),
            ir.constant(ir.types.StringType(len(value) + 1), value),
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
        min_reg=26,
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

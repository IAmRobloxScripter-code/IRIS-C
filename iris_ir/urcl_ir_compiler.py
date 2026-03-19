from .ir_types import __CONSTANT__, TYPEDEF_FUNCTION_ARGUMENT

def __format_urcl__(urcl: str = ""):
    lines = urcl.strip().splitlines()
    result = ""
    in_label = False
    for index, line in enumerate(lines):
        if line.startswith("."):
            result += f"{"\n" if index != 0 else ""}{line}\n"
            in_label = True
        else:
            result += f"{"\t" if in_label else ""}{line}\n"
        if "ret" in line.lower():
            in_label = False
    return result

class __COMPILER__:
    def __init__(self, blocks):
        self.blocks = blocks
        self.stack_frame = []
        self.globals = {}
        self.ssa_registers = {}
        self.urcl = ""
        entry = False
        headers = 0
        for block in blocks:
            if block["kind"] == "HeaderBlock":
                headers += 1

        self.registers = {
            "stack_pointer": {"name": "SP", "free": False, "general_purpose": False},
            "stack_address": {"name": "R1", "free": True, "general_purpose": False},
            "return_value": {"name": "R2", "free": True, "general_purpose": False},
        }

        for index in range(3, 16):
            self.registers[f"R{index}"] = {"name": f"R{index}", "free": True, "general_purpose": True} # type: ignore

        for block in blocks:
            if headers <= 0 and entry == False:
                entry = True
                self.writeln("CAL .main")
                self.writeln("HLT")
            if block["kind"] == "HeaderBlock" and entry == False:
                headers -= 1
            self.compile(block)

    def get_register_name(self, name: str):
        return self.registers[name]["name"]

    def move_reg_into_reg(self, destination, register):
        self.writeln(
            f"MOV {self.get_register_name(destination)} {self.get_register_name(register)}"
        )
        self.registers[destination]["free"] = False

    def free_register(self, register):
        if register not in self.registers:
            return
        self.registers[register]["free"] = True

    def occupy_register(self, register):
        if register not in self.registers:
            return
        self.registers[register]["free"] = False

    def write(self, text: str):
        self.urcl += text

    def writeln(self, text: str):
        self.write(f"{text}\n")

    def get_stack_frame(self):
        if len(self.stack_frame) == 0:
            return None
        else:
            return self.stack_frame[len(self.stack_frame) - 1]

    def compile(self, block):
        match block["kind"]:
            case "HeaderBlock":
                return self.compile_header(block)
            case "GlobalMemoryBlock":
                return self.compile_global_memory_block(block)
            case "ConstantBlock":
                return self.compile_constant(block)
            case "FunctionBlock":
                return self.compile_function_block(block)
            case "ReturnBlock":
                return self.compile_return_block(block)
            case "StoreBlock":
                return self.compile_store_block(block)
            case "AddBlock" | "SubBlock" | "MulBlock" | "DivBlock":
                return self.compile_operation_block(block)
            case "ValueBlock":
                return self.compile_value_block(block)
            case "ArgumentBlock":
                return self.compile_argument_block(block)
            case "CallBlock":
                return self.compile_call_block(block)
            case "TemporaryBlock":
                return self.compile_temp_block(block)
            case "GetElementPointerBlock":
                return self.compile_gep_block(block)

    def compile_header(self, block):
        kind = block["header_kind"]
        if kind == "run":
            self.writeln(f"RUN {block["value"].upper()}")
        elif kind == "bits":
            self.writeln(f"BITS {(block["value"][0])} {block["value"][1]}")
        elif kind in ("minheap", "minreg", "minstack"):
            self.writeln(f"{kind.upper()} {block["value"]}")

    def compile_constant(self, block):
        return block.as_string(True)

    def compile_global_memory_block(self, block):
        if len(self.stack_frame) != 0:
            return f".{block["name"]}"
        self.writeln(f".{block["name"]}")
        self.writeln(f"DW {self.compile(block["initializer"])}")

        return f".{block["name"]}"

    def get_free_register(self):
        for register, data in self.registers.items():
            if data["free"] and data["general_purpose"]:
                return register
        return None

    def compile_return_block(self, block):
        self.writeln(
            f"MOV {self.get_register_name("return_value")} {self.compile(block["value"])}"
        )
        self.writeln(
            f"MOV {self.get_register_name("stack_pointer")} {self.get_register_name("stack_address")}"
        )
        self.writeln(f"POP {self.get_register_name("stack_address")}")
        self.free_register("stack_address")
        self.writeln("RET")

    def compile_function_block(self, block):
        if len(self.stack_frame) != 0:
            return f".{block["name"]}"
        sp_name = self.get_register_name("stack_pointer")
        self.writeln(f".{block["name"]}")
        self.writeln(f"PSH {self.get_register_name("stack_address")}")
        self.move_reg_into_reg("stack_address", "stack_pointer")
        old_urcl = self.urcl
        self.urcl = ""

        frame = {"kind": "FunctionFrame", "variables": {}, "params": {}, "stack_address": 0, "ssa_registers": {}}
        self.stack_frame.append(frame)
        args: list[TYPEDEF_FUNCTION_ARGUMENT] = block["args"]
        for index, arg in enumerate(args):
            offset = arg["arg"].offset # type: ignore
            frame["stack_address"] += offset
            if index < 6:
                self.writeln(f"LSTR R1 -{frame["stack_address"]} R{17 + index}")
            else:
                register = self.get_free_register()
                self.occupy_register(register)
                self.writeln(f"LLOD {register} R1 {1 + (offset * ((index - 6) + 1))}")
                self.writeln(f"LSTR R1 -{frame["stack_address"]} {register}")
                self.free_register(register)
            frame["params"][arg["name"]] = {
                "stack_offset": frame["stack_address"],
                "offset": offset,
            }

        for nested_block in block["block"].blocks:
            self.compile(nested_block)

        old_urcl += f"SUB {sp_name} {sp_name} {frame["stack_address"]}\n"
        self.urcl = old_urcl + self.urcl
        self.stack_frame.pop()
        return f".{block["name"]}"
    
    def compile_array(self, frame, value, offset_index = 0):
        offset = value.type.of.offset
        for index in range(value.type.size):
            if type(value) == __CONSTANT__ and value.value[index].type.kind == "ArrayType": # type: ignore
                self.compile_array(frame, value.value[index], offset_index + (index * offset)) # type: ignore
                continue
            alignment = offset_index + (index * offset)
            c_value = self.compile(value.value[index]) # type: ignore
            self.writeln(
                f"LSTR {self.get_register_name("stack_address")} -{frame["stack_address"] - alignment} {c_value}"
            )

    def compile_store_block(self, block):
        frame = self.get_stack_frame()
        if frame == None:
            print("Cannot allocate stack variables outside of a scope!")
            return

        value = self.compile(block["value"])
        offset = block["memory"].type.offset
        frame["stack_address"] += offset
        if block["memory"].type["kind"] == "ArrayType":
            self.compile_array(frame, block["value"])
        else:
            self.writeln(
                f"LSTR {self.get_register_name("stack_address")} -{frame["stack_address"]} {value}"
            )

        frame["variables"][block["memory"].name] = {
            "stack_offset": frame["stack_address"],
            "offset": offset,
        }

        self.free_register(value)

    def compile_operation_block(self, block):
        # {"kind": "AddBlock", "left": left, "right": right, "result": identifier}
        left = self.compile(block["left"])
        right = self.compile(block["right"])

        result_register = self.get_free_register()
        self.occupy_register(result_register)

        match block["kind"]:
            case "AddBlock":
                self.writeln(f"ADD {result_register} {left} {right}")
            case "SubBlock":
                self.writeln(f"SUB {result_register} {left} {right}")
            case "MulBlock":
                self.writeln(f"MLT {result_register} {left} {right}")

        self.free_register(left)
        self.free_register(right)
        return result_register

    def compile_value_block(self, block):
        name = block.name
        frame = self.get_stack_frame()
        if not frame:
            print("Cannot retrieve value outside of a scope!")
            return
        
        if name not in frame["variables"]:
            print(f"'{name}' is not a variable!")
            return

        data = frame["variables"][name]
        register = self.get_free_register()
        self.occupy_register(register)
        self.writeln(f"LLOD {register} {self.get_register_name("stack_address")} -{data["stack_offset"]}")
        return register
    
    def compile_argument_block(self, block):
        name = block["name"]
        frame = self.get_stack_frame()
        if not frame:
            print("Cannot access arguments outside of a scope!")
            return
        
        if name not in frame["params"]:
            print(f"'{name}' is not a parameter!")
            return
        
        data = frame["params"][name]
        register = self.get_free_register()
        self.occupy_register(register)
        self.writeln(f"LLOD {register} {self.get_register_name("stack_address")} -{data["stack_offset"]}")
        return register
    
    def compile_call_block(self, block):
        # {"kind": "CallBlock", "func": func, "args": arguments, "result": result_value}
        func = self.compile(block["func"])
        # print(block["func"])
        stack_usage = 0
        stack_args = []
        for index, arg in enumerate(block["args"]):
            value = self.compile(arg)
            if index < 6:
                self.writeln(f"MOV R{17 + index} {value}")
            else:
                stack_usage += self.get_type(arg).offset # type: ignore
                stack_args.append(f"PSH {value}")
            self.free_register(value)
        
        stack_args.reverse()
        for value in stack_args:
            self.writeln(value)
        
        self.writeln(f"CAL {func}")
        self.occupy_register("return_value")
        if stack_usage > 0:
            self.writeln(f"ADD {self.get_register_name("stack_pointer")} {self.get_register_name("stack_pointer")} {stack_usage}")
        frame = self.get_stack_frame()
        return_register_name = self.get_register_name("return_value")
        if frame:
            frame["ssa_registers"][block["result"]] = return_register_name
        else:
            self.ssa_registers[block["result"]] = return_register_name
        return self.get_register_name("return_value")

    def compile_temp_block(self, block):
        frame = self.get_stack_frame()
        if not frame:
            return self.ssa_registers[block.name]
        else:
            if block.name in frame["ssa_registers"]:
                return frame["ssa_registers"][block.name]
            else:
                return self.ssa_registers[block.name]

    def compile_gep_block(self, block):
        """
            {
                "kind": "GetElementPointerBlock",
                "element_type": element_type,
                "pointer": pointer,
                "index": index,
                "name": name or self.temporary(),
            }
        """
        pointer_value = self.compile(block["pointer"])
        index_value = self.compile(block["index"])
        index_register = self.get_free_register()
        self.occupy_register(index_register)
        self.writeln(f"MOV {index_register} {index_value}")
        offset_register = self.get_free_register()
        self.occupy_register(offset_register)
        self.writeln(f"MUL {offset_register} {index_register} {block["element_type"].offset}")
        register = self.get_free_register()
        self.writeln(f"LLOD {register} {pointer_value} {offset_register}")
        self.free_register(pointer_value)
        self.free_register(index_value)
        self.free_register(offset_register)
        self.occupy_register(register)

        return register

    def get_type(self, block):
        match block["kind"]:
            case "GlobalMemoryBlock":
                return block["type"]
            case "ConstantBlock":
                return block.type
            case "FunctionBlock":
                return block["type"]
            case "ReturnBlock":
                return self.get_type(block["value"])
            case "AddBlock" | "SubBlock" | "MulBlock" | "DivBlock":
                return self.get_type(block["left"])
            case "ValueBlock":
                return block.type
            case "ArgumentBlock":
                return block["arg"]
            case "CallBlock":
                func_type = self.get_type(block["func"])
                return func_type.return_type
            case "TemporaryBlock":
                return block.type
class __COMPILER__:
    def __init__(self, blocks):
        self.blocks = blocks
        self.stack_frame = []
        self.globals = {}
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
            "R3": {"name": "R3", "free": True, "general_purpose": True},
            "R4": {"name": "R4", "free": True, "general_purpose": True},
            "R5": {"name": "R5", "free": True, "general_purpose": True},
            "R6": {"name": "R6", "free": True, "general_purpose": True},
            "R7": {"name": "R7", "free": True, "general_purpose": True},
            "R8": {"name": "R8", "free": True, "general_purpose": True},
        }

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
            case "AddBlock" | "SubBlock":
                return self.compile_operation_block(block)
            case "ValueBlock":
                return self.compile_value_block(block)

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

        frame = {"kind": "FunctionFrame", "variables": {}, "stack_address": 0}
        self.stack_frame.append(frame)

        for nested_block in block["block"].blocks:
            self.compile(nested_block)

        old_urcl += f"SUB {sp_name} {sp_name} {frame["stack_address"]}\n"
        self.urcl = old_urcl + self.urcl
        self.stack_frame.pop()
        return f".{block["name"]}"

    def compile_store_block(self, block):
        # {
        #     "kind": "AllocatedMemoryBlock",
        #     "type": type,
        #     "value": value,
        # }

        # self.blocks.append({"kind": "StoreBlock", "memory": memory, "value": value})
        frame = self.get_stack_frame()
        if frame == None:
            print("Cannot allocate stack variables outside of a scope!")
            return

        value = self.compile(block["value"])
        offset = block["memory"].type.offset
        frame["stack_address"] += offset
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
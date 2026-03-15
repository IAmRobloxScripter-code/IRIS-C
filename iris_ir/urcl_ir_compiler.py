class __COMPILER__:
    def __init__(self, blocks):
        self.blocks = blocks
        self.stack_frame = []
        self.globals = {}
        self.urcl = ""
        self.registers = {
            "stack_pointer": {"name": "SP", "free": False},
            "stack_offset": {"name": "R1", "free": True}
        }

        for block in blocks:
            self.compile(block)

    def get_register_name(self, name: str):
        return self.registers[name]["name"]
    
    def move_reg_into_reg(self, destination, register):
        self.writeln(f"MOV {self.get_register_name(destination)} {self.get_register_name(register)}")
        self.registers[destination]["free"] = False
    
    def free_register(self, register):
        self.registers[register]["free"] = True
        
    def write(self, text: str):
        self.urcl += text
    
    def writeln(self, text: str):
        self.write(f"{text}\n")
    
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
        self.writeln(f".{block["name"]}")
        self.writeln(f"DW {self.compile(block["initializer"])}")
    
    def compile_function_block(self, block):
        self.writeln(f".{block["name"]}")
        self.writeln(f"PSH {self.get_register_name("stack_pointer")}")
        self.move_reg_into_reg("stack_offset", "stack_pointer")
        
        self.writeln(f"POP {self.get_register_name("stack_offset")}")
        self.free_register("stack_offset")
        self.writeln("ret")
        
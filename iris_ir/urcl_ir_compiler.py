from .ir_types import CMP_OPERATORS_FUNCS, __DOUBLE_TYPE__, __FLOAT_TYPE__, __HALF_TYPE__, __INT_TYPE__, FLOAT_SCALE_FACTOR, __CONSTANT__, TYPEDEF_FUNCTION_ARGUMENT
import os


def __format_urcl__(urcl: str = ""):
    lines = urcl.strip().splitlines()
    result = ""
    in_label = False
    for index, line in enumerate(lines):
        if line.startswith("."):
            result += f"{"\n" if index != 0 else ""}{line.strip()}\n"
            in_label = True
        else:
            result += f"{"\t" if in_label else ""}{line.strip()}\n"
        if "ret" in line.lower():
            in_label = False
    return result

class __COMPILER__:
    def __init__(self, blocks, flags: list[str]):
        self.blocks = blocks
        self.stack_frame = []
        self.globals = []
        self.ssa_registers = {}
        self.urcl = ""
        self.word_size = 0
        self.flags = flags
        self.urcl_software_templates = {}
        if "-o0" in flags:
            self.optimization_level = 0
        else:
            self.optimization_level = 1 # default O1
            if "-o1" in flags:
                self.optimization_level = 1
            elif "-o2" in flags:
                self.optimization_level = 2
            elif "-o3" in flags:
                self.optimization_level = 3

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

        for index in range(3, 14):
            self.registers[f"R{index}"] = {"name": f"R{index}", "free": True, "general_purpose": True}  # type: ignore

        for block in blocks:
            if headers <= 0 and entry == False:
                entry = True
                self.writeln(f"@DEFINE FLOAT_SCALE_FACTOR_BITS {FLOAT_SCALE_FACTOR}")
                self.writeln(f"@DEFINE FLOAT_SCALE_FACTOR {round(2**FLOAT_SCALE_FACTOR)}")
                self.writeln("CAL .main")
                self.writeln("HLT")
                if "--nosoftware" not in flags:
                    self.add_urcl_software()
                    self.writeln(self.urcl_software_templates["sfpurcl_out"])
            if block["kind"] == "HeaderBlock" and entry == False:
                headers -= 1
            self.compile(block)

    def add_urcl_software(self):
        urcl_software_directory = "urcl_software"
        for flag in self.flags:
            if "--softwarepath=" in flag:
                split = flag.split("=")
                urcl_software_directory = (
                    split[1] if len(split) >= 2 else "urcl_software"
                )
                break

        base_dir = os.path.dirname(os.path.abspath(__file__))
        urcl_software_directory = os.path.join(base_dir, urcl_software_directory)
        for root, _, files in os.walk(urcl_software_directory):
            for file in files:
                full_file_path = os.path.join(root, file)

                with open(full_file_path, "r") as software_file:
                    templates = software_file.read().strip().split("NOP")
                    for template in templates:
                        lines = template.strip().splitlines()
                        name = lines.pop(0)[1:]
                        template_value = "\n".join(lines)
                        self.urcl_software_templates[name] = template_value

    def compute_template(self, name, replacers):
        template = self.urcl_software_templates[name]
        for replacer, value in replacers.items():
            template = template.replace("$" + replacer, str(value))
        return template

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
            case (
                "AddBlock"
                | "SubBlock"
                | "MulBlock"
                | "DivBlock"
                | "RSBlock"
                | "LSBlock"
                | "ANDBlock"
                | "ORBlock"
                | "XORBlock"
                ):
                return self.compile_operation_block(block)
            case "NOTBlock":
                return self.compile_unary_block(block)
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
            case "AddressBlock":
                return self.compile_address_block(block)
            case "LoadValueBlock":
                return self.compile_load_block(block)
            case "LabelDefineBlock":
                return self.compile_label_define_block(block)
            case "LabelBlock":
                return f".{block["label"]}"
            case "JumpBlock":
                self.writeln(f"JMP {self.compile(block["label"])}")
            case "CompareBlock":
                return self.compile_compare_block(block)
            case "BranchBlock":
                return self.compile_branch_block(block)

    def compile_header(self, block):
        kind = block["header_kind"]
        if kind == "run":
            self.writeln(f"RUN {block["value"].upper()}")
        elif kind == "bits":
            self.word_size = int(block["value"][1])
            self.writeln(f"BITS {(block["value"][0])} {block["value"][1]}")
        elif kind in ("minheap", "minreg", "minstack"):
            self.writeln(f"{kind.upper()} {block["value"]}")

    def compile_constant(self, block):
        if block.type["kind"] in ("HalfType", "FloatType", "DoubleType"):
            return round(block.value * (2 ** FLOAT_SCALE_FACTOR))
        if block.type["kind"] == "StructType":
            return self.compile_struct(block, original_type=block["type"])
        return block.as_string(True)

    def compile_global_memory_block(self, block):
        if len(self.stack_frame) != 0:
            return f".{block["name"]}"
        if f".{block["name"]}" in self.globals:
            return f".{block["name"]}"
        self.writeln(f".{block["name"]}")
        self.writeln(f"DW {self.compile(block["initializer"])}")
        self.writeln("NOP")
        self.globals.append(f".{block["name"]}")
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
        frame = self.get_stack_frame()
        # if frame and frame["inlined"]:
        #     frame["parent"]["ssa_registers"][block["value"]["result"]] = self.get_register_name("return_value")

        if frame and not frame["inlined"]:
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

        frame = {
            "kind": "FunctionFrame",
            "variables": {},
            "params": {},
            "stack_address": 0,
            "ssa_registers": {},
            "inlined": False
        }
        self.stack_frame.append(frame)
        args: list[TYPEDEF_FUNCTION_ARGUMENT] = block["args"]
        for index, arg in enumerate(args):
            offset = arg["arg"].offset  # type: ignore
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

    def compile_array(self, frame, value, offset_index=0, stack_offset=0):
        offset = value.type.of.offset
        for index in range(value.type.size):
            if type(value) == __CONSTANT__ and value.value[index].type.kind == "ArrayType":  # type: ignore
                self.compile_array(frame, value.value[index], offset_index + (index * offset), stack_offset=stack_offset)  # type: ignore
                continue
            alignment = offset_index + (index * offset)
            c_value = self.compile(value.value[index])  # type: ignore
            self.writeln(
                f"LSTR {self.get_register_name("stack_address")} -{stack_offset - alignment} {c_value}"
            )

    def compile_struct(self, value, stack_offset=0, offset_index=0, original_type=None):
        frame = self.get_stack_frame()
        if not frame:
            representation = "["
            for index in range(len(original_type.members)):  # type: ignore
                if original_type.members[index].kind == "StructType":  # type: ignore
                    self.compile_struct(frame, value.value[index], stack_offset=stack_offset, offset_index=offset_index + (index * offset), original_type=original_type.members[index])  # type: ignore
                    continue
                c_value = self.compile(value.value[index])  # type: ignore
                representation += f"{c_value}{", " if index + 1 != len(original_type.members) else ""}"  # type: ignore
            representation += "]"
            return representation

        offset = value.type.alignment
        for index in range(len(original_type.members)):  # type: ignore
            if original_type.members[index].kind == "StructType":  # type: ignore
                self.compile_struct(frame, value.value[index], stack_offset=stack_offset, offset_index=offset_index + (index * offset), original_type=original_type.members[index])  # type: ignore
                continue

            if original_type.members[index].kind == "ArrayType":  # type: ignore
                self.compile_array(frame, value.value[index], stack_offset=stack_offset, offset_index=offset_index + (index * offset))  # type: ignore
                continue

            alignment = offset_index + (index * offset)
            c_value = self.compile(value.value[index])  # type: ignore
            self.writeln(
                f"LSTR {self.get_register_name("stack_address")} -{stack_offset - alignment} {c_value}"
            )

    def compile_store_block(self, block):
        frame = self.get_stack_frame()
        if not frame:
            print("Cannot allocate stack variables outside of a scope!")
            return

        if block["memory"]["kind"] != "AddressBlock":
            pointer = self.compile(block["memory"])
            value = self.compile(block["value"])
            self.writeln(f"STR {pointer} {value}")
            return

        value = None
        offset = None
        stack_offset = 0
        if block["memory"]["name"] not in frame["variables"]:
            offset = block["memory"]["value"].type.offset
            frame["stack_address"] += offset
            stack_offset = frame["stack_address"]
        else:
            stack_offset = frame["variables"][block["memory"]["name"]]["stack_offset"]

        if block["memory"].value.type["kind"] == "ArrayType":
            self.compile_array(frame, block["value"], stack_offset=stack_offset)
        elif block["memory"].value.type["kind"] == "StructType":
            self.compile_struct(
                block["value"],
                stack_offset=stack_offset,
                original_type=self.get_type(block["value"]),
            )
        else:
            value = self.compile(block["value"])
            self.writeln(
                f"LSTR {self.get_register_name("stack_address")} -{stack_offset} {value}"
            )
            if block["memory"].name in frame["variables"]:
                frame["variables"][block["memory"]["name"]]["value"] = block["value"]

        if block["memory"].name not in frame["variables"]:
            frame["variables"][block["memory"].name] = {
                "stack_offset": frame["stack_address"],
                "offset": offset,
                "value": block["value"],
                "used": False,
                "volatile": False,
                "restrict": False,
            }

        self.free_register(value)

    def get_number_type(self, n):
        try:
            int(n)
            return "int"
        except ValueError:
            try:
                float(n)
                return "float"
            except ValueError:
                return None
            
    def compile_unary_block(self, block):
        value = self.compile(block["value"])
        value_type = self.get_type(block["value"])
        signed = "i" if value_type.signed else "u"

        result_register = self.get_free_register()

        match block["kind"]:
            case "NOTBlock":
                self.writeln(
                    self.compute_template(
                        f"sint_{signed}not",
                        {
                            "A_REG": value,
                            "RES_REG": result_register,
                            "SIZE_CONST": hex((1 << value_type["size"]) - 1),  # type: ignore
                            "SHIFT_CONST": self.word_size - value_type["size"],  # type: ignore
                        },
                    )
                )

        self.free_register(value)
        self.occupy_register(result_register)
        return result_register

    def compile_operation_block(self, block):
        # {"kind": "AddBlock", "left": left, "right": right, "result": identifier}
        left = self.compile(block["left"])
        right = self.compile(block["right"])

        left_type = self.get_type(block["left"])
        right_type = self.get_type(block["right"])

        result_type = left_type
        operation_kind = "int"
        operation_type = result_type.kind
        if left_type.kind != "IntType" or right_type.kind != "IntType":
            if left_type.kind == "IntType":
                operation_type = right_type.kind
            elif right_type.kind == "IntType":
                operation_type = left_type.kind

        if self.optimization_level > 0 and self.get_number_type(left) and self.get_number_type(right):
            if left_type.kind in ("HalfType", "FloatType", "DoubleType"): # type: ignore
                left = float(left) # type: ignore
            else:
                left = int(left) # type: ignore
            if right_type.kind in ("HalfType", "FloatType", "DoubleType"): # type: ignore
                right = float(right) # type: ignore
            else:
                right = int(right) # type: ignore

            if left_type.kind in ("HalfType", "FloatType", "DoubleType"):
                left /= (2 ** FLOAT_SCALE_FACTOR)

            if right_type.kind in ("HalfType", "FloatType", "DoubleType"):
                right /= (2 ** FLOAT_SCALE_FACTOR)

            match block["kind"]:
                case "AddBlock":
                    if operation_type == "IntType":
                        result = self.compile(__CONSTANT__(__INT_TYPE__(left_type.size, left_type.signed), left + right))  # type: ignore
                    elif operation_type == "HalfType":
                        result = self.compile(__CONSTANT__(__HALF_TYPE__(), left + right))  # type: ignore
                    elif operation_type == "FloatType":
                        result = self.compile(__CONSTANT__(__FLOAT_TYPE__(), left + right))  # type: ignore
                    elif operation_type == "DoubleType":
                        result = self.compile(__CONSTANT__(__DOUBLE_TYPE__(), left + right))  # type: ignore
                case "SubBlock":
                    if operation_type == "IntType":
                        result = self.compile(__CONSTANT__(__INT_TYPE__(left_type.size, left_type.signed), left - right))  # type: ignore
                    elif operation_type == "HalfType":
                        result = self.compile(__CONSTANT__(__HALF_TYPE__(), left - right))  # type: ignore
                    elif operation_type == "FloatType":
                        result = self.compile(__CONSTANT__(__FLOAT_TYPE__(), left - right))  # type: ignore
                    elif operation_type == "DoubleType":
                        result = self.compile(__CONSTANT__(__DOUBLE_TYPE__(), left - right))  # type: ignore
                case "MulBlock":
                    if operation_type == "IntType":
                        result = self.compile(__CONSTANT__(__INT_TYPE__(left_type.size, left_type.signed), left * right))  # type: ignore
                    elif operation_type == "HalfType":
                        result = self.compile(__CONSTANT__(__HALF_TYPE__(), left * right))  # type: ignore
                    elif operation_type == "FloatType":
                        result = self.compile(__CONSTANT__(__FLOAT_TYPE__(), left * right))  # type: ignore
                    elif operation_type == "DoubleType":
                        result = self.compile(__CONSTANT__(__DOUBLE_TYPE__(), left * right))  # type: ignore
                case "DivBlock":
                    if operation_type == "IntType":
                        result = self.compile(__CONSTANT__(__INT_TYPE__(left_type.size, left_type.signed), left // right))  # type: ignore
                    elif operation_type == "HalfType":
                        result = self.compile(__CONSTANT__(__HALF_TYPE__(), left / right))  # type: ignore
                    elif operation_type == "FloatType":
                        result = self.compile(__CONSTANT__(__FLOAT_TYPE__(), left / right))  # type: ignore
                    elif operation_type == "DoubleType":
                        result = self.compile(__CONSTANT__(__DOUBLE_TYPE__(), left / right))  # type: ignore
                case "RSBlock":
                    result = self.compile(__CONSTANT__(__INT_TYPE__(left_type.size, left_type.signed), int(left) >> int(right)))
                case "LSBlock":
                    result = self.compile(__CONSTANT__(__INT_TYPE__(left_type.size, left_type.signed), int(left) << int(right)))
                case "ANDBlock":
                    result = self.compile(__CONSTANT__(__INT_TYPE__(left_type.size, left_type.signed), int(left) & int(right)))
                case "ORlock":
                    result = self.compile(__CONSTANT__(__INT_TYPE__(left_type.size, left_type.signed), int(left) | int(right)))
                case "XORBlock":
                    result = self.compile(__CONSTANT__(__INT_TYPE__(left_type.size, left_type.signed), int(left) ^ int(right)))
            
            self.free_register(left)
            self.free_register(right)
            return result
        
        result_register = self.get_free_register()
        self.occupy_register(result_register)

        if operation_type == "IntType":
            operation_kind = f"sint_{"u" if not result_type["signed"] else "i"}"
        elif operation_type == "HalfType":
            operation_kind = "sfp16_"
        elif operation_type == "FloatType":
            operation_kind = "sfp32_"
        elif operation_type == "DoubleType":
            operation_kind = "sfp64_"
        else:
            print("Invalid type for operation!")
            self.free_register(left)
            self.free_register(right)
            self.free_register(result_register)
            return
        
        if operation_type != "IntType":
            if left_type.kind == "IntType":
                new_left_register = self.get_free_register()
                self.writeln(f"BSL {new_left_register} {left} {FLOAT_SCALE_FACTOR}")
                self.occupy_register(new_left_register)
                self.free_register(left)
                left = new_left_register
                left_type = right_type
                result_type = right_type
            elif right_type.kind == "IntType":
                new_right_register = self.get_free_register()
                self.writeln(f"BSL {new_right_register} {right} {FLOAT_SCALE_FACTOR}")
                self.occupy_register(new_right_register)
                self.free_register(right)
                right = new_right_register
                right_type = left_type
                result_type = left_type

        match block["kind"]:
            case "AddBlock":
                self.writeln(
                    self.compute_template(
                        f"{operation_kind}add",
                        {
                            "A_REG": left,
                            "B_REG": right,
                            "RES_REG": result_register,
                            "SIZE_CONST": hex((1 << result_type["size"]) - 1),  # type: ignore
                            "SHIFT_CONST": self.word_size - result_type["size"],  # type: ignore
                        },
                    )
                )
            case "SubBlock":
                self.writeln(
                    self.compute_template(
                        f"{operation_kind}sub",
                        {
                            "A_REG": left,
                            "B_REG": right,
                            "RES_REG": result_register,
                            "SIZE_CONST": hex((1 << result_type["size"]) - 1),  # type: ignore
                            "SHIFT_CONST": self.word_size - result_type["size"],  # type: ignore
                        },
                    )
                )
            case "MulBlock":
                self.writeln(
                    self.compute_template(
                        f"{operation_kind}mul",
                        {
                            "A_REG": left,
                            "B_REG": right,
                            "RES_REG": result_register,
                            "SIZE_CONST": hex((1 << result_type["size"]) - 1),  # type: ignore
                            "SHIFT_CONST": self.word_size - result_type["size"],  # type: ignore
                        },
                    )
                )
            case "DivBlock":
                self.writeln(
                    self.compute_template(
                        f"{operation_kind}div",
                        {
                            "A_REG": left,
                            "B_REG": right,
                            "RES_REG": result_register,
                            "SIZE_CONST": hex((1 << result_type["size"]) - 1),  # type: ignore
                            "SHIFT_CONST": self.word_size - result_type["size"],  # type: ignore
                        },
                    )
                )
            case "RSBlock":
               self.writeln(
                    self.compute_template(
                        f"{operation_kind}rs",
                        {
                            "A_REG": left,
                            "B_REG": right,
                            "RES_REG": result_register,
                            "SIZE_CONST": hex((1 << result_type["size"]) - 1),  # type: ignore
                            "SHIFT_CONST": self.word_size - result_type["size"],  # type: ignore
                        },
                    )
                )
            case "LSBlock":
               self.writeln(
                    self.compute_template(
                        f"{operation_kind}ls",
                        {
                            "A_REG": left,
                            "B_REG": right,
                            "RES_REG": result_register,
                            "SIZE_CONST": hex((1 << result_type["size"]) - 1),  # type: ignore
                            "SHIFT_CONST": self.word_size - result_type["size"],  # type: ignore
                        },
                    )
                )
            case "ANDBlock":
               self.writeln(
                    self.compute_template(
                        f"{operation_kind}and",
                        {
                            "A_REG": left,
                            "B_REG": right,
                            "RES_REG": result_register,
                            "SIZE_CONST": hex((1 << result_type["size"]) - 1),  # type: ignore
                            "SHIFT_CONST": self.word_size - result_type["size"],  # type: ignore
                        },
                    )
                )
            case "ORBlock":
                self.writeln(
                    self.compute_template(
                        f"{operation_kind}or",
                        {
                            "A_REG": left,
                            "B_REG": right,
                            "RES_REG": result_register,
                            "SIZE_CONST": hex((1 << result_type["size"]) - 1),  # type: ignore
                            "SHIFT_CONST": self.word_size - result_type["size"],  # type: ignore
                        },
                    )
                )
            case "XORBlock":
                self.writeln(
                    self.compute_template(
                        f"{operation_kind}xor",
                        {
                            "A_REG": left,
                            "B_REG": right,
                            "RES_REG": result_register,
                            "SIZE_CONST": hex((1 << result_type["size"]) - 1),  # type: ignore
                            "SHIFT_CONST": self.word_size - result_type["size"],  # type: ignore
                        },
                    )
                )

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
        if not data["used"]:
            data["used"] = True
            if data["value"]["kind"] == "AddressBlock" and data["value"]["name"] in frame["variables"]:
                return self.compile_value_block(frame["variables"][data["value"]["name"]])

            if data["value"]["kind"] == "ConstantBlock" and data["value"]["type"]["kind"] in ("IntType", "HalfType", "FloatType", "DoubleType"):
                return self.compile_constant(data["value"])

        register = self.get_free_register()
        self.occupy_register(register)
        self.writeln(
            f"LLOD {register} {self.get_register_name("stack_address")} -{data["stack_offset"]}"
        )
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
        self.writeln(
            f"LLOD {register} {self.get_register_name("stack_address")} -{data["stack_offset"]}"
        )
        return register
    
    def inline_heuristics_control_flows(self, block):
        control_flows = 0

        for block_node in block.blocks:
            if block_node["kind"] in ("BranchBlock", "JumpBlock", "LabelDefineBlock"):
                if block_node["kind"] == "BanchBlock":
                    control_flows += self.inline_heuristics_control_flows(block_node["then"])
                    control_flows += self.inline_heuristics_control_flows(block_node["else"])
                elif block_node["kind"] == "LabelDefineBlock":
                    control_flows += self.inline_heuristics_control_flows(block_node["block"])
                else:
                    control_flows += 1
        return control_flows

    def compile_call_block(self, block):
        # {"kind": "CallBlock", "func": func, "args": arguments, "result": result_value}
        if block["func"]["kind"] == "FunctionBlock" and block["func"]["inline"]:
            instructions = len(block["func"]["block"].blocks)
            control_flows = self.inline_heuristics_control_flows(block["func"]["block"])
            current_frame = self.get_stack_frame()

            if instructions > control_flows and current_frame:
                frame = {
                    "kind": "FunctionFrame",
                    "variables": {},
                    "params": {},
                    "stack_address": current_frame["stack_address"],
                    "ssa_registers": {},
                    "inlined": True,
                    "parent": current_frame
                }

                args: list[TYPEDEF_FUNCTION_ARGUMENT] = block["args"]
                for index, arg in enumerate(args):
                    fn_arg = block["func"]["args"][index]
                    offset = fn_arg["arg"].offset  # type: ignore
                    frame["stack_address"] += offset
                    arg_value = self.compile(arg)
                    self.writeln(f"LSTR R1 -{frame["stack_address"]} {arg_value}")
                    self.free_register(arg_value)

                    frame["params"][fn_arg["name"]] = {
                        "stack_offset": frame["stack_address"],
                        "offset": offset,
                    }

                self.stack_frame.append(frame)
                
                for block_node in block["func"]["block"].blocks:
                    self.compile(block_node)

                self.stack_frame.pop()
                current_frame["ssa_registers"][block["result"]] = self.get_register_name("return_value")
                self.occupy_register("return_value")
                return self.get_register_name("return_value")

        func = self.compile(block["func"])
        # print(block["func"])
        stack_usage = 0
        stack_args = []
        for index, arg in enumerate(block["args"]):
            value = self.compile(arg)
            if index < 6:
                self.writeln(f"MOV R{17 + index} {value}")
            else:
                stack_usage += self.get_type(arg).offset  # type: ignore
                stack_args.append(f"PSH {value}")
            self.free_register(value)

        stack_args.reverse()
        for value in stack_args:
            self.writeln(value)

        self.writeln(f"CAL {func}")
        self.occupy_register("return_value")
        if stack_usage > 0:
            self.writeln(
                f"ADD {self.get_register_name("stack_pointer")} {self.get_register_name("stack_pointer")} {stack_usage}"
            )
        frame = self.get_stack_frame()
        return_register_name = self.get_register_name("return_value")
        if frame:
            frame["ssa_registers"][block["result"]] = return_register_name
        else:
            self.ssa_registers[block["result"]] = return_register_name
        return return_register_name

    def compile_temp_block(self, block):
        frame = self.get_stack_frame()
        if not frame:
            return self.ssa_registers[block.name]
        else:
            if block.name in frame["ssa_registers"]:
                return frame["ssa_registers"][block.name]
            else:
                return self.ssa_registers[block.name]

    def compile_address_block(self, block):
        name = block.name
        frame = self.get_stack_frame()
        if not frame:
            return None

        data = frame["variables"][name]

        if not data["used"]:
            data["used"] = True 
            if data["value"]["kind"] == "AddressBlock" and data["value"]["name"] in frame["variables"]:
                return self.compile_value_block(data["value"])
        
            if data["value"]["kind"] == "ConstantBlock" and data["value"]["type"]["kind"] in ("IntType", "HalfType", "FloatType", "DoubleType"):
                return self.compile_constant(data["value"])

        register = self.get_free_register()
        self.occupy_register(register)

        self.writeln(
            f"SUB {register} {self.get_register_name("stack_address")} {data["stack_offset"]}"
        )

        return register

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

        pointer = block["pointer"]
        if pointer["kind"] == "ValueBlock":
            base_pointer = self.compile_address_block(pointer)
        else:
            base_pointer = self.compile(pointer)

        index_value = self.compile(block["index"])
        index_register = self.get_free_register()
        self.occupy_register(index_register)
        self.writeln(f"MOV {index_register} {index_value}")
        offset_register = self.get_free_register()
        self.occupy_register(offset_register)
        element_type = self.get_type(block["pointer"])
        self.writeln(
            f"MLT {offset_register} {index_register} {element_type.offset - 1}"  # type: ignore
        )
        register = self.get_free_register()
        self.writeln(f"ADD {register} {base_pointer} {offset_register}")
        self.free_register(base_pointer)
        self.free_register(index_value)
        self.free_register(offset_register)
        self.occupy_register(register)

        return register

    def compile_load_block(self, block):
        pointer = self.compile(block["pointer"])
        register = self.get_free_register()
        self.writeln(f"LOD {register} {pointer}")
        self.occupy_register(register)
        self.free_register(pointer)
        return register

    def compile_compare_block(self, block):
        operator = block["operator"]
        left = self.compile(block["left"])
        right = self.compile(block["right"])
        result_register = self.get_free_register()

        left_type = self.get_type(block["left"])
        right_type = self.get_type(block["right"])
        
        if self.optimization_level > 0 and self.get_number_type(left) and self.get_number_type(right):
            if self.get_number_type(left) == "float":
                left = float(left) # type: ignore
            else:
                left = int(right) # type: ignore

            if self.get_number_type(right) == "float":
                right = float(right) # type: ignore
            else:
                right = int(right) # type: ignore
                    
            if left_type.kind != "IntType" or right_type.kind != "IntType":
                if left_type.kind == "IntType":
                    left <<= FLOAT_SCALE_FACTOR # type: ignore
                elif right_type.kind == "IntType":
                    right <<= FLOAT_SCALE_FACTOR # type: ignore


            result = CMP_OPERATORS_FUNCS[operator](left, right)
            
            if result == True:
                return str(True)
            else:
                return str(False)

        signedness = "i"

        if left_type.kind != "IntType" or right_type.kind != "IntType":
            if left_type.kind == "IntType":
                new_left_register = self.get_free_register()
                self.writeln(f"BSL {new_left_register} {left} {FLOAT_SCALE_FACTOR}")
                self.occupy_register(new_left_register)
                self.free_register(left)
                left = new_left_register
                left_type = right_type
            elif right_type.kind == "IntType":
                new_right_register = self.get_free_register()
                self.writeln(f"BSL {new_right_register} {right} {FLOAT_SCALE_FACTOR}")
                self.occupy_register(new_right_register)
                self.free_register(right)
                right = new_right_register
                right_type = left_type

        if left_type.kind == "IntType" and right_type.kind == "IntType":
            if left_type.kind == "IntType":
                signedness = "i" if left_type.signed else "u"

            if right_type.kind == "IntType" and signedness == "u":
                signedness = "i" if right_type.signed else "u"

        match operator:
            case "==":
                self.writeln(
                    self.compute_template(
                        f"sint_{signedness}eq",
                        {
                            "A_REG": left,
                            "B_REG": right,
                            "RES_REG": result_register,
                        },
                    )
                )
            case "!=":
                self.writeln(
                    self.compute_template(
                        f"sint_{signedness}neq",
                        {
                            "A_REG": left,
                            "B_REG": right,
                            "RES_REG": result_register,
                        },
                    )
                )
            case ">=":
                self.writeln(
                    self.compute_template(
                        f"sint_{signedness}gte",
                        {
                            "A_REG": left,
                            "B_REG": right,
                            "RES_REG": result_register,
                        },
                    )
                )
            case "<=":
                self.writeln(
                    self.compute_template(
                        f"sint_{signedness}lte",
                        {
                            "A_REG": left,
                            "B_REG": right,
                            "RES_REG": result_register,
                        },
                    )
                )
            case ">":
                self.writeln(
                    self.compute_template(
                        f"sint_{signedness}gt",
                        {
                            "A_REG": left,
                            "B_REG": right,
                            "RES_REG": result_register,
                        },
                    )
                )
            case "<":
                self.writeln(
                    self.compute_template(
                        f"sint_{signedness}lt",
                        {
                            "A_REG": left,
                            "B_REG": right,
                            "RES_REG": result_register,
                        },
                    )
                )

        self.occupy_register(result_register)
        return result_register

    def compile_label_define_block(self, block):
        self.writeln(f".{block["label"]}")
        if not block["block"]:
            return
        for nested_block in block["block"].blocks:
            self.compile(nested_block)

    def compile_branch_block(self, block):
        then_label = self.compile(block["then"])
        else_label = self.compile(block["else"])
        condition_result = self.compile(block["condition"])

        if self.optimization_level > 0:
            if condition_result == "True":
                self.writeln(f"JMP {then_label}")
                self.free_register(condition_result)
                self.free_register(then_label)
                self.free_register(else_label)
                return
            elif condition_result == "False":
                self.writeln(f"JMP {else_label}")
                self.free_register(condition_result)
                self.free_register(then_label)
                self.free_register(else_label)
                return

        self.writeln(f"BRE {then_label} {condition_result} {2 ** self.word_size - 1}")
        self.writeln(f"BRE {else_label} {condition_result} 0")
        self.free_register(condition_result)
        self.free_register(then_label)
        self.free_register(else_label)

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
            case "AddBlock" | "SubBlock" | "MulBlock" | "DivBlock" | "RSBlock" | "LSBlock" | "ANDBlock" | "NANDBlock" | "ORBlock" | "NORBlock" | "XORBlock":
                left_type = self.get_type(block["left"])
                right_type = self.get_type(block["right"])

                if left_type.kind == "IntType" and right_type.kind == "IntType":
                    return left_type
                else:
                    if left_type.kind == "IntType":
                        return right_type
                    else:
                        return left_type
            case "ValueBlock":
                return block.type
            case "ArgumentBlock":
                return block["arg"]
            case "CallBlock":
                func_type = self.get_type(block["func"])
                return func_type.return_type
            case "TemporaryBlock":
                return block.type
            case "GetElementPointerBlock":
                return block["pointer"].type
            case "StructTypeBlock":
                return block["type"]
            case "AddressBlock":
                return self.get_type(block.value)
            case "ValueBlock":
                return block.type

        return __INT_TYPE__(0, False)
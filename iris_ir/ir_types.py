from typing import TypedDict


MAX_BITS = 16
REPR_MODULE_INDENTATION = 2


class __POINTER_TYPE__:
    def __init__(self, type: object):
        self.kind = "PointerType"
        self.to = type
        self.size_in_bits = MAX_BITS
        self.offset = 1

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
        self.offset = 1

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
        self.offset = 1

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
        self.offset = 1

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
        self.offset = 1

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
        self.offset = (of.size_in_bits * size) // 8

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
        self.representation = __ARRAY_TYPE__(__INT_TYPE__(8), size)
        self.offset = 1

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
        self.size = 1
        self.offset = 1

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

class __STRUCT_TYPE__:
    def __init__(self, members: list[object]) -> None:
        self.kind = "StructType"
        self.members = members
        self.size = 0
        self.offset = 0
        for member in members:
            if member.offset > self.offset: # type: ignore
                self.offset = member.offset # type: ignore
            self.size += member.size  # type: ignore

        def __getitem__(self, key):
            return getattr(self, key)

    def as_pointer(self):
        return __POINTER_TYPE__(self)
    
    def as_string(self):
        representation = "["
        for index, member in enumerate(self.members):
            representation += f"{member.as_string()}{", " if index + 1 != len(self.members) else ""}" # type: ignore
        representation += "]"
        return representation

class __types_CLASS__:
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
    
    def StructType(self, members: list[object]):
        return __STRUCT_TYPE__(members)


class __VALUE__:
    def __init__(self, type, name):
        self.kind = "ValueBlock"
        self.type = type
        self.name = name

    def __getitem__(self, key):
        return getattr(self, key)


class __ADDRESS__:
    def __init__(self, type, name, value: __VALUE__):
        self.kind = "AddressBlock"
        self.type = type.as_pointer()
        self.name = name
        self.value = value

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

    def as_string_str(self, display_string_as_array):
        if not display_string_as_array:
            representation = '"'
            for char in self.value:
                if char in (
                    "\n",
                    "\t",
                    '"',
                    "\r",
                    "\0",
                    "\\",
                    "'",
                    "\b",
                    "\f",
                    "\v",
                    "\a",
                    "\00",
                    "\000",
                ):
                    representation += f"\\{str(ord(char))}"
                else:
                    representation += char
            representation += '\\0"'
            return representation

        representation = "["
        inquotes = False
        for char in self.value:
            if char in (
                "\n",
                "\t",
                '"',
                "\r",
                "\0",
                "\\",
                "'",
                "\b",
                "\f",
                "\v",
                "\a",
                "\00",
                "\000",
            ):
                if inquotes == True:
                    inquotes = False
                    representation += '"'
                representation += ", "
                representation += str(ord(char))
            else:
                if inquotes == False:
                    inquotes = True
                    representation += f'{", " if representation != "[" else ""}"'
                representation += char
        if inquotes == True:
            inquotes = False
            representation += '"'
        representation += ", 0]"
        return representation

    def as_string(self, display_string_as_array=False):
        if self.type["kind"] == "IntType":
            return self.as_int_str()
        elif self.type["kind"] in ("HalfType", "FloatType", "DoubleType"):
            return self.as_float_str()
        elif self.type["kind"] == "ArrayType":
            return self.as_array_str()
        elif self.type["kind"] == "StringType":
            return self.as_string_str(display_string_as_array)


class TYPEDEF_FUNCTION_ARGUMENT(TypedDict):
    kind: str
    name: str


class __TEMPORARY_VALUE__:
    def __init__(self, type, name):
        self.kind = "TemporaryBlock"
        self.name = name
        self.type = type

    def __getitem__(self, key):
        return getattr(self, key)


CMP_OPERATORS = {
    "==": "eq",
    "!=": "neq",
    ">": "gt",
    "<": "lt",
    ">=": "gte",
    "<=": "lte",
}

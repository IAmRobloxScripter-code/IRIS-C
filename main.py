from iris_ir.urcl_ir import ir

module = ir.create_module()
module.set_header(bits=("==", 16))

stdint = ir.types.IntType(8)
# char = ir.types.IntType(8)

function_type = ir.types.FunctionType(stdint, [])
builder = module.create_block()
function_data = module.create_function(builder, function_type, "main", [])

# hwstr = module.create_global_string("Hello World!")
# foo = builder.alloc(char.as_pointer())
# builder.store(builder.get_element_pointer(hwstr, char.as_pointer(), ir.constant(stdint, 0)), foo)

a = builder.alloc(stdint)
builder.store(ir.constant(stdint, 100), a)

b = builder.alloc(stdint)
builder.store(ir.constant(stdint, 200), b)

c = builder.alloc(stdint)
builder.store(ir.constant(stdint, 600), c)

d = builder.alloc(stdint)
builder.store(builder.add(builder.sub(c, a), b), d)

# 600 - 100 + 200

builder.ret(ir.constant(stdint, 0))

print(module.module)
print("-"*60)
print(module.compile())

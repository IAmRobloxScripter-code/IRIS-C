from urcl_ir import ir

module = ir.create_module()
module.set_header(bits=16)

stdint = ir.urcl_types.IntType(8)
char = ir.urcl_types.IntType(8)

function_type = ir.urcl_types.FunctionType(stdint, [])
builder = module.create_block()
function_data = module.create_function(builder, function_type, "main", [])

hwstr = module.create_global_string("Hello World!")
foo = builder.alloc(char.as_pointer())
builder.store(foo, )

builder.ret(ir.constant(stdint, 0))

print(module.module)

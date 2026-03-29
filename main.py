from iris_ir.urcl_ir import ir

module = ir.create_module()
module.set_header(bits=("==", 32))

stdint = ir.types.IntType(16, False)
stdhalf = ir.types.HalfType()

add_func_type = ir.types.FunctionType(stdint, [stdint, stdint])
add_func_builder = module.create_block()
add_func = module.create_function(add_func_builder, add_func_type, "add", [stdint, stdint], inline=True)

add_func_builder.ret(stdint, add_func_builder.add(add_func["args"][0], add_func["args"][1]))

main_function_type = ir.types.FunctionType(stdint, [])
main_builder = module.create_block()
main_function = module.create_function(main_builder, main_function_type, "main", [])

a = main_builder.alloc(stdint)
main_builder.store(main_builder.call(add_func, [ir.constant(stdint, 200), ir.constant(stdint, 400)]), a)

main_builder.ret(stdint, ir.constant(stdint, 0))
print(module)
print("-" * 60)
with open("result.urcl", "w") as result:
    result.write(module.compile())
    result.close()
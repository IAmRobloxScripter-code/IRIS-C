from iris_ir.urcl_ir import ir

module = ir.create_module()
module.set_header(bits=("==", 16))

stdint = ir.types.IntType(8)

hello_world_global = module.create_global_string("Hello World!")

main_function_type = ir.types.FunctionType(stdint, [])
main_builder = module.create_block()
main_function = module.create_function(main_builder, main_function_type, "main", [])

value = main_builder.alloc(stdint)
x = main_builder.get_element_pointer(hello_world_global, stdint, ir.constant(stdint, 0))
main_builder.store(main_builder.load(x), value)

main_builder.ret(ir.constant(stdint, 0))
print(module)
print("-" * 60)
with open("result.urcl", "w") as result:
    result.write(module.compile())
    result.close()

from iris_ir.urcl_ir import ir

module = ir.create_module()
module.set_header(bits=("==", 32))

stdint = ir.types.IntType(16, False)
stdhalf = ir.types.HalfType()

main_function_type = ir.types.FunctionType(stdint, [])
main_builder = module.create_block()
main_function = module.create_function(main_builder, main_function_type, "main", [])

a = main_builder.alloc(stdint)
main_builder.store(main_builder.add(ir.constant(stdint, 200), ir.constant(stdint, 400)), a)
b = main_builder.alloc(stdint)
main_builder.store(main_builder.add(a, ir.constant(stdint, 400)), b)

main_builder.ret(stdint, ir.constant(stdint, 0))
print(module)
print("-" * 60)
with open("result.urcl", "w") as result:
    result.write(module.compile(["-o0"]))
    result.close()
from iris_ir.urcl_ir import ir

module = ir.create_module()
module.set_header(bits=("==", 16))

stdint = ir.types.IntType(8)
struct_type = ir.types.StructType([stdint, stdint.as_pointer()])

main_function_type = ir.types.FunctionType(stdint, [])
main_builder = module.create_block()
main_function = module.create_function(main_builder, main_function_type, "main", [])

me = main_builder.alloc(struct_type)
my_name = module.create_global_string("Entity")
main_builder.store(ir.constant(struct_type, [ir.constant(stdint, 17), my_name]), me)

main_builder.ret(ir.constant(stdint, 0))
print(module)
print("-" * 60)
with open("result.urcl", "w") as result:
    result.write(module.compile())
    result.close()

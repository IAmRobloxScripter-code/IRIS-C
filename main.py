from iris_ir.urcl_ir import ir

module = ir.create_module()
module.set_header(bits=("==", 16))

stdint = ir.types.IntType(8)


main_function_type = ir.types.FunctionType(stdint, [])
main_builder = module.create_block()
main_function = module.create_function(main_builder, main_function_type, "main", [])

array_type = ir.types.ArrayType(stdint, 3)
array = main_builder.alloc(array_type)
main_builder.store(
    ir.constant(
        array_type,
        [ir.constant(stdint, 100), ir.constant(stdint, 200), ir.constant(stdint, 300)],
    ),
    array,
)

value = main_builder.alloc(stdint)
main_builder.store(main_builder.get_element_pointer(array, stdint, ir.constant(stdint, 0)), value)

main_builder.ret(ir.constant(stdint, 0))
print(module)
print("-" * 60)
with open("result.urcl", "w") as result:
    result.write(module.compile())
    result.close()

from typing import BinaryIO, Final
from pprint import PrettyPrinter

from enums import *
from infos import *
from utils import *

from faking_it import fake_classes

loaded_classes |= fake_classes


def parse_class(path: str):
    clazz = ClassFile()
    with open(path, 'rb') as f:
        magic = parse_int(f, 4)
        assert magic == 0xCAFEBABE
        clazz.minor_version = parse_int(f, 2)
        clazz.major_version = parse_int(f, 2)
        constant_count = parse_cp_index(f)
        clazz.constant_pool = []
        was_two = False
        for _ in range(constant_count):
            if was_two:
                was_two = False
                continue
            e = parse_constant_pool_info(f)
            if not isinstance(e, Nothing):
                clazz.constant_pool.append(e)
            if isinstance(e, (DoubleInfo, LongInfo)):
                was_two = True
                clazz.constant_pool.append(Nothing())
        clazz.access_flags = Access(parse_int(f, 2))
        clazz.this_class = parse_cp_index(f)
        clazz.super_class = parse_cp_index(f)
        interface_count = parse_int(f, 2)
        clazz.interfaces = [parse_cp_index(f) for _ in range(interface_count)]
        field_count = parse_int(f, 2)
        clazz.fields = [parse_field_info(f, clazz) for _ in range(field_count)]
        method_count = parse_int(f, 2)
        clazz.methods = [parse_method_info(f, clazz) for _ in range(method_count)]
        attrs_count = parse_int(f, 2)
        clazz.attributes = [parse_attribute_info(f, clazz) for _ in range(attrs_count)]
    obj = clazz.get_const(clazz.this_class, ClassInfo)
    # TODO: clazz.resolve_indices()
    name_info = clazz.get_const(obj.name_index, Utf8Info)
    loaded_classes[name_info.bytes] = clazz
    return clazz


def parse_constant_pool_info(f: BinaryIO) -> ConstantPoolInfo:
    tag = CPInfoTag(parse_int(f, 1))
    match tag:
        case CPInfoTag.Methodref | CPInfoTag.Fieldref | CPInfoTag.InterfaceMethodref:
            return ReferenceInfo(parse_cp_index(f), parse_cp_index(f))
        case CPInfoTag.Class:
            return ClassInfo(parse_cp_index(f))
        case CPInfoTag.NameAndType:
            return NameAndTypeInfo(parse_cp_index(f), parse_cp_index(f))
        case CPInfoTag.Utf8:
            length = parse_int(f, 2)
            return Utf8Info(f.read(length))
        case CPInfoTag.String:
            return StringInfo(parse_cp_index(f))
        case CPInfoTag.Integer:
            return IntegerInfo(parse_int(f, 4))
        case CPInfoTag.Long:
            return LongInfo(parse_int(f, 8))
        case CPInfoTag.Float:
            bits = parse_int(f, 4)
            s = -1 if  bits >> 31 else 1
            e = ((bits >> 23) & 0xff)
            if e != 0xff:
                m = (bits & 0x7fffff) | 0x800000 if e else (bits & 0x7fffff) << 1
                return FloatInfo(s * m * 2 ** (e - 150))
            else:
                return FloatInfo(s * float('inf'))
        case CPInfoTag.Double:
            bits = parse_int(f, 8)
            s = -1 if bits >> 63 else 1
            e = (bits >> 52) & 0x7ff
            if e != 0x7ff:
                m = (bits & 0xfffffffffffff) | 0x10000000000000 if e else (bits & 0xfffffffffffff) << 1
                return DoubleInfo(s * m * 2 ** (e - 1075))
            else:
                return DoubleInfo(s * float('inf'))
        case CPInfoTag.Nothing:
            pass
        case _:
            raise ValueError(f'unexpected tag {tag}')
    raise TypeError(f'this cannot happen')


def parse_field_info(f: BinaryIO, klass: ClassFile) -> FieldInfo:
    flags = Access(parse_int(f, 2))
    name = parse_cp_index(f)
    descriptor = parse_cp_index(f)
    attr_count = parse_int(f, 2)
    attrs = [parse_attribute_info(f, klass) for _ in range(attr_count)]
    return FieldInfo(attrs, flags, name, descriptor)


def parse_method_info(f: BinaryIO, klass: ClassFile) -> MethodInfo:
    flags = Access(parse_int(f, 2))
    name = parse_cp_index(f)
    descriptor = parse_cp_index(f)
    attr_count = parse_int(f, 2)
    attrs = [parse_attribute_info(f, klass) for _ in range(attr_count)]
    return MethodInfo(attrs, klass, flags, name, descriptor)





def parse_attribute_info(f: BinaryIO, clazz: ClassFile) -> AttributeInfo:
    name_index = parse_cp_index(f)
    # name = AttributeName(constants[name_index].bytes)
    name = AttributeName(clazz.get_const(name_index, Utf8Info).bytes)
    length = parse_int(f, 4)
    # data: dict[str, bytes | int] = {}
    sub_attrs = []
    match name:
        case AttributeName.Code:
            max_stack = parse_int(f, 2)
            max_locals = parse_int(f, 2)
            code_len = parse_int(f, 4)
            code = f.read(code_len)
            exc_table_len = parse_int(f, 2)
            exception_table = [ExceptionDescriptor(
                parse_int(f, 2),
                parse_int(f, 2),
                parse_int(f, 2),
                parse_int(f, 2),
            ) for _ in range(exc_table_len)]
            num_attributes = parse_int(f, 2)
            sub_attrs = [parse_attribute_info(f, clazz) for _ in range(num_attributes)]
            return CodeAttribute(sub_attrs, max_stack, max_locals, code, exception_table)
        case AttributeName.LineNumberTable:
            num_numbers = parse_int(f, 2)
            return LineNumbers([LineNumber(
                parse_int(f, 2),
                parse_int(f, 2)
            ) for _ in range(num_numbers)])
        case AttributeName.SourceFile:
            assert length == 2
            return SourceFile(clazz.get_const(parse_cp_index(f), Utf8Info).bytes)
        case AttributeName.Signature:
            assert length == 2
            return SignatureAttr(clazz.get_const(parse_cp_index(f), Utf8Info).bytes)
        case _:
            raise ValueError(f'unexpected attribute name {name}')


# loaded_classes[b'java/lang/System'] = ClassFile()


if __name__ == '__main__':
    pp = PrettyPrinter()
    c = parse_class('Thing.class')
    c.validate(pp)
    # print(c.constant_pool[c.methods_by_name(b'hmmm')[0].descriptor_index])
    # pp.pprint(c.methods)
    # for m in c.methods:
    #     print()
    c.initialize(pp)
    # pp.pprint(c.methods_by_name(b'<init>'))
    c.methods_by_name(b'main')[0].run(c, deque(), [[]])
    # print(c.access_flags)

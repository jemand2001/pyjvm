from contextlib import suppress
from dataclasses import dataclass, field
from collections import deque
from functools import cached_property
from io import BytesIO
from pprint import PrettyPrinter
from typing import Any, Optional, Type
from inspect import Signature

from enums import *
from utils import *

loaded_classes: dict[bytes, 'ClassFile'] = {}


class ConstantPoolInfo:
    pass
    # __tag__: CPInfoTag = CPInfoTag.Nothing
    # data: dict[str, int | bytes] = field(default_factory=dict)


@dataclass
class ReferenceInfo(ConstantPoolInfo):
    class_index: int
    name_and_type_index: int
@dataclass
class ClassInfo(ConstantPoolInfo):
    name_index: int
@dataclass
class NameAndTypeInfo(ConstantPoolInfo):
    name_index: int
    descriptor_index: int
@dataclass
class Utf8Info(ConstantPoolInfo):
    bytes: bytes
@dataclass
class StringInfo(ConstantPoolInfo):
    string_index: int
@dataclass
class IntegerInfo(ConstantPoolInfo):
    value: int
@dataclass
class LongInfo(ConstantPoolInfo):
    value: int
@dataclass
class FloatInfo(ConstantPoolInfo):
    value: float
@dataclass
class DoubleInfo(ConstantPoolInfo):
    value: float
@dataclass
class Nothing(ConstantPoolInfo):
    pass


@dataclass(slots=True)
class HasAttributes:
    attributes: list["AttributeInfo"] = field(default_factory=list)

    def attribute_by_name(self, name: AttributeName) -> "AttributeInfo":
        for attr in self.attributes:
            if attr.__attr_name__ == name:
                return attr
        raise KeyError(name)

    def has_attribute(self, name: AttributeName) -> bool:
        return any(attr.__attr_name__ == name for attr in self.attributes)


@dataclass
class ExceptionDescriptor:
    start_pc: int
    end_pc: int
    handler_pc: int
    catch_type: int


@dataclass
class LineNumber:
    start_pc: int
    line_number: int


class AttributeInfo:
    __attr_name__: AttributeName
    pass


@dataclass
class CodeAttribute(AttributeInfo, HasAttributes):
    __attr_name__ = AttributeName.Code
    max_stack: int = 0
    max_locals: int = 0
    code: bytes = b''
    exception_table: list[ExceptionDescriptor] = field(default_factory=list)


@dataclass
class LineNumbers(AttributeInfo):
    __attr_name__ = AttributeName.LineNumberTable
    table: list[LineNumber]


@dataclass
class SourceFile(AttributeInfo):
    __attr_name__ = AttributeName.SourceFile
    source: bytes


class SignatureAttr(AttributeInfo):
    def __init__(self, sig: bytes):
        self.descriptor = sig


@dataclass
class StackEntry:
    tag: StackTag
    data: object
    @classmethod
    def from_value(cls, value):
        if isinstance(value, int):
            tag = StackTag.Integer
        elif isinstance(value, float):
            tag = StackTag.Float
        else:
            tag = StackTag.Reference
        return cls(tag, value)


@dataclass(slots=True)
class FieldInfo(HasAttributes):
    access_flags: Access = Access(0)
    name_index: int = 0
    descriptor_index: int = 0


@dataclass(slots=True, repr=False)
class MethodInfo(HasAttributes):
    klass: Optional["ClassFile"] = None
    access_flags: Access = Access(0)
    name_index: int = 0
    descriptor_index: int = 0

    signature: Optional[tuple[tuple[bytes, ...], bytes]] = None

    def __post_init__(self):
        # print(self.klass)
        # print(self.descriptor_index)
        descriptor = self.klass.get_const(self.descriptor_index, Utf8Info).bytes
        args: list[bytes] = []
        ret = b'V'
        with BytesIO(descriptor) as d:
            assert d.read(1) == b'('
            while d.tell() < len(descriptor):
                match d.read(1):
                    case b'L':
                        args.append(read_until(d, b';'))
                    case  (b'B' | b'C' | b'D' | b'F' | b'I' | b'J' | b'S' | b'Z') as b:
                        args.append(b)
                    case b')':
                        ret = d.read()
        self.signature = (tuple(args), ret)

    def run(self, cls: "ClassFile", stack: deque[StackEntry], locals: list):
        code = self.attribute_by_name(AttributeName.Code)
        assert isinstance(code, CodeAttribute)
        locals.extend([None] * (code.max_locals - len(locals)))
        bytecode = code.code
        offset = 0
        with BytesIO(bytecode) as instructions:
            while instructions.tell() < len(bytecode):
                opcode = Opcode(instructions.read(1)[0])
                # print(opcode, locals)
                match opcode:
                    case Opcode.getstatic:
                        index = parse_cp_index(instructions)
                        class_name, attr_name, attr_type = cls.get_class_name_and_type(index)
                        class_file = loaded_classes[class_name]
                        # print(class_name, attr_name, attr_type)
                        class_file.initialize()
                        value = class_file.get_static_field(attr_name)
                        stack.append(StackEntry.from_value(value))
                        offset += 1
                    case Opcode.ldc:
                        index = parse_int(instructions, 1) - 1
                        const: ConstantPoolInfo = cls.constant_pool[index]
                        data: int | float | str
                        match const:
                            case StringInfo(v):
                                data = cls.get_const(v, Utf8Info).bytes.decode('utf-8')
                            case IntegerInfo(v) | LongInfo(v) | FloatInfo(v) | DoubleInfo(v):
                                data = v
                            case tag:
                                raise TypeError(f'cannot push constant of type {tag}')
                        stack.append(StackEntry.from_value(data))
                        offset += 1
                    case Opcode.invokevirtual:
                        index = parse_cp_index(instructions)
                        class_name, method_name, method_type = cls.get_class_name_and_type(index)
                        class_file = loaded_classes[class_name]
                        # print(class_name, method_name, method_type)
                        method = class_file.resolve_overload(method_name, method_type)
                        assert method.signature
                        args: list = []
                        for spot in method.signature[0]:
                            args.append(stack.pop())
                            offset -= 1
                        args.append(stack.pop())
                        offset -= 1
                        args.reverse()
                        method.run(cls, stack, args)
                    case Opcode.new:
                        index = parse_cp_index(instructions)
                        clazz = cls.get_const(index, ClassInfo)
                        name_info = cls.get_const(clazz.name_index, Utf8Info)
                        class_name = name_info.bytes
                        actual = loaded_classes[class_name]
                        stack.append(StackEntry(StackTag.Reference, actual.new_instance()))
                        offset += 1
                    case Opcode.putfield:
                        index = parse_cp_index(instructions)
                        class_name, attr_name, attr_type = cls.get_class_name_and_type(index)
                        # print(class_name, attr_name, attr_type)
                        value = stack.pop()
                        offset -= 1
                        ref = stack.pop()
                        offset -= 1
                        assert ref.tag == StackTag.Reference
                        if ref.data is None:
                            raise ValueError(f'attempting to set {attr_name!r} on None')
                        assert isinstance(ref.data, Instance)
                        ref.data.fields[attr_name] = value
                    case Opcode.getfield:
                        index = parse_cp_index(instructions)
                        class_name, attr_name, attr_type = cls.get_class_name_and_type(index)
                        # print(class_name, attr_name, attr_type)
                        ref = stack.pop()
                        # print(ref)
                        assert ref.tag == StackTag.Reference and isinstance(ref.data, Instance)
                        stack.append(ref.data.get_field(attr_name))
                    case Opcode.invokespecial:
                        index = parse_cp_index(instructions)
                        class_name, method_name, method_type = cls.get_class_name_and_type(index)
                        klass = loaded_classes[class_name]
                        # print(class_name, method_name, method_type)
                        method = klass.resolve_overload(method_name, method_type)
                        assert method.signature
                        args = []
                        for spot in method.signature[0]:
                            args.append(stack.pop())
                            offset -= 1
                        if Access.STATIC not in method.access_flags:
                            args.append(stack.pop())
                            offset -= 1
                        method.run(cls, stack, args)
                    case Opcode.ldc2_w:
                        index = parse_cp_index(instructions)
                        const = cls.get_const(index, ConstantPoolInfo)
                        # assert isinstance(const, DoubleInfo | LongInfo)
                        # stack.append(StackEntry(const.value))
                        match const:
                            case DoubleInfo(x):
                                stack.append(StackEntry(StackTag.Float, x))
                            case LongInfo(x):
                                stack.append(StackEntry(StackTag.Integer, x))
                            case x:
                                raise ValueError(f'invalid operand for {opcode}: {x}')
                        offset += 1
                    case Opcode.aload_0:
                        stack.append(locals[0])
                        offset += 1
                    case Opcode.aload_1:
                        stack.append(locals[1])
                        offset += 1
                    case Opcode.astore_1:
                        locals[1] = stack.pop()
                        offset -= 1
                    case Opcode.sipush:
                        stack.append(StackEntry.from_value(parse_int(instructions, 2)))
                        offset += 1
                    case Opcode.bipush:
                        stack.append(StackEntry.from_value(instructions.read(1)[0]))
                        offset += 1
                    case Opcode.dup:
                        stack.append(stack[-1])
                        offset += 1
                    case Opcode.iconst_1:
                        stack.append(StackEntry(StackTag.Integer, 1))
                        offset += 1
                    case Opcode.dconst_1:
                        stack.append(StackEntry(StackTag.Float, 1.0))
                        offset += 1
                    case Opcode.return_:
                        return
                    case Opcode.areturn:
                        ret = stack.pop()
                        offset -= 1
                        while offset:
                            stack.pop()
                            offset -= 1
                        stack.append(ret)
                    case i:
                        raise ValueError(f'unexpected Opcode: {i} ({hex(i.value)})')
                # print(stack)


@dataclass(repr=False)
class Instance:
    klass: "ClassFile"
    fields: dict[bytes, Any] = field(default_factory=dict)
    def get_field(self, name: bytes):
        if name in self.fields:
            return self.fields[name]
        raise AttributeError(f'{self}.{name!r}')
    def __repr__(self):
        return f'{self.klass.class_name}({self.fields})'


@dataclass(slots=True)
class ClassFile(HasAttributes):
    minor_version: int = 0
    major_version: int = 0
    constant_pool: list[ConstantPoolInfo] = field(default_factory=list)
    access_flags: Access = Access.PUBLIC
    this_class: int = 0
    super_class: int = 0
    interfaces: list[int] = field(default_factory=list)
    fields: list[FieldInfo] = field(default_factory=list)
    methods: list[MethodInfo] = field(default_factory=list)
    initialized: InitializationState = InitializationState.verified
    static_fields: dict = field(default_factory=dict)

    def get_static_field(self, name: bytes):
        if name in self.static_fields:
            return self.static_fields[name]
        else:
            raise AttributeError(f'{self.class_name}.{name.decode()}')

    def methods_by_name(self, name: bytes) -> list[MethodInfo]:
        return [mi for mi in self.methods if isinstance(c := self.constant_pool[mi.name_index], Utf8Info) and c.bytes == name]

    def field_by_name(self, name: bytes) -> FieldInfo:
        return next(fi for fi in self.fields if isinstance(c := self.constant_pool[fi.name_index], Utf8Info) and c.bytes == name)
    
    def get_const(self, idx: int, t: Type[T]) -> T:
        v = self.constant_pool[idx]
        assert isinstance(v, t)
        return v

    def resolve_overload(self, name: bytes, signature: bytes) -> MethodInfo:
        candidates = self.methods_by_name(name)
        fit = []
        for c in candidates:
            sig = self.get_const(c.descriptor_index, Utf8Info).bytes
            if (a := sig.split(b')')[0]) == (b := signature.split(b')')[0]):
                fit.append(c)
        if not fit:
            raise ValueError(f'No overload for {name!r} with signature {signature!r}')
        if len(fit) > 1:
            raise ValueError(f'Ambiguous overload for {name!r} with signature {signature!r}')
        return fit[0]

    def get_class_name_and_type(self, index: int) -> tuple[bytes, bytes, bytes]:
        attr = self.get_const(index, ReferenceInfo)
        clazz = self.get_const(attr.class_index, ClassInfo)
        name_entry = self.get_const(clazz.name_index, Utf8Info)
        class_name = name_entry.bytes
        attr_name_and_type = self.get_const(attr.name_and_type_index, NameAndTypeInfo)
        attr_name = self.get_const(attr_name_and_type.name_index, Utf8Info).bytes
        attr_type = self.get_const(attr_name_and_type.descriptor_index, Utf8Info).bytes
        return class_name, attr_name, attr_type

    def validate(self, pp: PrettyPrinter):
        for const in self.constant_pool:
            # with suppress(AttributeError):
            #     self.get_const(const.name_index, Utf8Info)
            match const:
                case NameAndTypeInfo(name, _) | ClassInfo(name):
                    self.get_const(name, Utf8Info)
                case ReferenceInfo(cls, nat):
                    self.get_const(nat, NameAndTypeInfo)
                    self.get_const(cls, ClassInfo)
                case StringInfo(idx):
                    self.get_const(idx, Utf8Info)
                case _:
                    pass

    def new_instance(self):
        res = Instance(self)
        for field in self.fields:
            if Access.STATIC not in field.access_flags:
                name = self.get_const(field.name_index, Utf8Info).bytes
                try:
                    value = field.attribute_by_name(AttributeName.ConstantValue)
                    res.fields[name] = value
                except:
                    res.fields[name] = None
        return res

    def initialize(self, pp: PrettyPrinter=None):
        if pp is None:
            pp = PrettyPrinter()
        from jvm import parse_class
        match self.initialized:
            case InitializationState.in_progress | InitializationState.done:
                return
            case InitializationState.error:
                raise ValueError(f'NoClassDefFoundError: {self.constant_pool[self.this_class]}')
        self.initialized = InitializationState.in_progress
        if Access.INTERFACE not in self.access_flags:
            sup = self.constant_pool[self.super_class]
            assert isinstance(sup, ClassInfo)
            name: bytes = self.get_const(sup.name_index, Utf8Info).bytes
            if name not in loaded_classes:
                try:
                    superclass = parse_class(name.decode())
                    superclass.validate(pp)
                except Exception:
                    self.initialized = InitializationState.error
                    raise
            else:
                superclass = loaded_classes[name]
            if superclass.initialized != InitializationState.done:
                superclass.initialize(pp)
            # [init] = self.methods_by_name(b'<init>')
            # init.run(self, deque())
            # self.initialized = InitializationState.done

    @property
    def class_name(self):
        return self.get_const(self.get_const(self.this_class, ClassInfo).name_index, Utf8Info).bytes

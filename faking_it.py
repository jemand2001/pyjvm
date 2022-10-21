

from collections import deque
from dataclasses import dataclass, field
from types import FunctionType
from typing import Callable, Generic, TypeVar
from inspect import signature

from enums import Access, CPInfoTag, InitializationState
from infos import ClassFile, ConstantPoolInfo, FieldInfo, AttributeInfo, MethodInfo, Utf8Info, ClassInfo, StackEntry


T = TypeVar('T')
fake_classes = {}


@dataclass
class ToExport:
    f: Callable
    name: str | None = None
    signatures: list[tuple[bytes, int]] = field(default_factory=list)
    def __call__(self, *args, **kwargs):
        return self.f(*args, **kwargs)


def export(signature: bytes, num_args: int, name: str=None):
    def decorator(f: Callable):
        if not isinstance(f, ToExport):
            f = ToExport(f)
        f.signatures.append((signature, num_args))
        if f.name:
            raise ValueError(f'{f} already has an export name')
        else:
            f.name = name
        return f
    return decorator


@dataclass
class StaticField(Generic[T]):
    value: T


class PrintStream:
    @export(b'(Ljava/lang/String;)V', 1)
    @export(b'(D)V', 1)
    @export(b'(F)V', 1)
    @export(b'(I)V', 1)
    def println(self, x):
        print(x)


class System:
    out = StaticField(PrintStream())


class Object:
    @export(b'()V', 0, name='<init>')
    def init(self):
        pass


@dataclass
class FakeMethod(MethodInfo):
    access_flags = Access.PUBLIC | Access.NATIVE
    original_function: Callable = lambda self: None
    arg_count: int = 0
    def run(self, cls: "ClassFile", stack: deque, args: list[StackEntry]):
        self.original_function(*(a.data for a in args))


@dataclass
class FakeField(FieldInfo):
    access_flags = Access.PUBLIC


@dataclass
class FakeClass(ClassFile):
    attributes: list[AttributeInfo] = field(default_factory=list)
    minor_version = 0
    major_version = 0
    this_class=0
    def initialize(self, *_):
        return


def build_class(cls: type, name: bytes) -> ClassFile:
    constants: list[ConstantPoolInfo] = [
        Utf8Info(name),
        Utf8Info(b'java/lang/Object'),
        ClassInfo(0)]
    methods: list[MethodInfo] = []
    attributes: list[FieldInfo] = []
    static_fields: dict[bytes, object] = {}
    count = len(constants)
    clazz = FakeClass(constant_pool=constants, this_class=2, fields=attributes, methods=methods, initialized=InitializationState.done, static_fields=static_fields)
    for k, v in cls.__dict__.items():
        if isinstance(v, ToExport):
            if v.name is not None:
                k = v.name
            constants.append(Utf8Info(k.encode('utf-8')))
            count += 1
            name_index = count-1
            for s, c in v.signatures:
                constants.append(Utf8Info(s))
                methods.append(FakeMethod(original_function=v.f, klass=clazz, name_index=name_index, descriptor_index=count, arg_count=c))
                count += 1
        elif not k.startswith('_') and not isinstance(v, FunctionType|ToExport):
            constants.append(Utf8Info(k.encode('utf-8')))
            attributes.append(FakeField(name_index=count-1, descriptor_index=1))
            if isinstance(v, StaticField):
                static_fields[k.encode()] = v.value
    return clazz


fake_classes.update({
    b'java/lang/System': build_class(System, b'java/lang/System'),
    b'java/lang/String': build_class(str, b'java/lang/String'),
    b'java/io/PrintStream': build_class(PrintStream, b'java/io/PrintStream'),
    b'java/lang/Object': build_class(Object, b'java/lang/Object'),
})

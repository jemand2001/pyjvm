from enum import Flag, Enum, auto

class Access(Flag):
    PUBLIC       = 0x0001
    PRIVATE      = 0x0002
    PROTECTED    = 0x0004
    STATIC       = 0x0008
    FINAL        = 0x0010
    SUPER        = 0x0020
    SYNCHRONIZED = 0x0020
    BRIDGE       = 0x0040
    VARARGS      = 0x0080
    NATIVE       = 0x0100
    INTERFACE    = 0x0200
    ABSTRACT     = 0x0400
    STRICT       = 0x0800
    SYNTHETIC    = 0x1000
    ANNOTATION   = 0x2000
    ENUM         = 0x4000


class CPInfoTag(Enum):
    Nothing            = 0
    Class              = 7
    Fieldref           = 9
    Methodref          = 10
    InterfaceMethodref = 11
    String             = 8
    Integer            = 3
    Float              = 4
    Long               = 5
    Double             = 6
    NameAndType        = 12
    Utf8               = 1
    MethodHandle       = 15
    MethodType         = 16
    InvokeDynamic      = 18


class AttributeName(Enum):
    ConstantValue                        = b"ConstantValue"
    Code                                 = b"Code"
    StackMapTable                        = b"StackMapTable"
    Exceptions                           = b"Exceptions"
    InnerClasses                         = b"InnerClasses"
    EnclosingMethod                      = b"EnclosingMethod"
    Synthetic                            = b"Synthetic"
    Signature                            = b"Signature"
    SourceFile                           = b"SourceFile"
    SourceDebugExtension                 = b"SourceDebugExtension"
    LineNumberTable                      = b"LineNumberTable"
    LocalVariableTable                   = b"LocalVariableTable"
    LocalVariableTypeTable               = b"LocalVariableTypeTable"
    Deprecated                           = b"Deprecated"
    RuntimeVisibleAnnotations            = b"RuntimeVisibleAnnotations"
    RuntimeInvisibleAnnotations          = b"RuntimeInvisibleAnnotations"
    RuntimeVisibleParameterAnnotations   = b"RuntimeVisibleParameterAnnotations"
    RuntimeInvisibleParameterAnnotations = b"RuntimeInvisibleParameterAnnotations"
    AnnotationDefault                    = b"AnnotationDefault"
    BootstrapMethods                     = b"BootstrapMethods"


class Opcode(Enum):
    aload_0         = 0x2a
    aload_1         = 0x2b
    getstatic       = 0xb2
    ldc             = 0x12
    invokevirtual   = 0xb6
    new             = 0xbb
    l2f             = 0x89
    dup             = 0x59
    invokespecial   = 0xb7
    astore_0        = 0x4b
    astore_1        = 0x4c
    ldc2_w          = 0x14
    dstore_2        = 0x49
    return_         = 0xb1
    sipush          = 0x11
    bipush          = 0x10
    putfield        = 0xb5
    areturn         = 0xb0
    getfield        = 0xb4
    nop             = 0
    iconst_1        = 4
    dconst_1        = 15


class InitializationState(Enum):
    verified = auto()
    in_progress = auto()
    done = auto()
    error = auto()


class StackTag(Enum):
    Return = auto()
    Reference = auto()
    Integer = auto()
    Float = auto()


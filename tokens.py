import typing

ALL_OP_NAMES = (
    "COPY", "LOAD", "STORE", "BRANCH", "CBRANCH", "BRANCHIND", "CALL", "CALLIND",
    "CALLOTHER", "RETURN", "INT_EQUAL", "INT_NOTEQUAL", "INT_SLESS",
    "INT_SLESSEQUAL", "INT_LESS", "INT_LESSEQUAL", "INT_ZEXT", "INT_SEXT",
    "INT_ADD", "INT_SUB", "INT_CARRY", "INT_SCARRY", "INT_SBORROW", "INT_2COMP",
    "INT_NEGATE", "INT_XOR", "INT_AND", "INT_OR", "INT_LEFT", "INT_RIGHT",
    "INT_SRIGHT", "INT_MULT", "INT_DIV", "INT_SDIV", "INT_REM", "INT_SREM",
    "BOOL_NEGATE", "BOOL_XOR", "BOOL_AND", "BOOL_OR", "FLOAT_EQUAL",
    "FLOAT_NOTEQUAL", "FLOAT_LESS", "FLOAT_LESSEQUAL", "FLOAT_NAN", "FLOAT_ADD",
    "FLOAT_DIV", "FLOAT_MULT", "FLOAT_SUB", "FLOAT_NEG", "FLOAT_ABS",
    "FLOAT_SQRT", "FLOAT_INT2FLOAT", "FLOAT_FLOAT2FLOAT", "FLOAT_TRUNC",
    "FLOAT_CEIL", "FLOAT_FLOOR", "FLOAT_ROUND", "MULTIEQUAL", "INDIRECT",
    "PIECE", "SUBPIECE", "CAST", "PTRADD", "PTRSUB", "SEGMENTOP", "CPOOLREF",
    "NEW", "INSERT", "EXTRACT", "POPCOUNT"
)

COMMUTATIVE_OP_NAMES = (
    "INT_EQUAL", "INT_NOTEQUAL", "INT_ADD", "INT_XOR", "INT_AND", "INT_OR",
    "INT_MULT", "BOOL_XOR", "BOOL_AND", "BOOL_OR", "FLOAT_EQUAL", "FLOAT_NOTEQUAL",
    "FLOAT_ADD", "FLOAT_MULT",
)

class Token:
    def to_c(self) -> str:
        """
        Returns a string that contains valid C code that represents this token.
        """
        raise NotImplementedError("Tokens must implement 'to_c'.")

    def get_size(self) -> typing.Optional[int]:
        """
        Return the (output) size of this token, or None if unknown.
        """
        raise NotImplementedError("Tokens must implement 'get_size'.")

    def to_pretty(self) -> str:
        """
        Returns a string that contains a pretty-printed version of an input that
        might be used to generate this token.
        """
        raise NotImplementedError("Tokens must implement 'to_pretty'.")


class TOK_VAR(Token):
    def __init__(self, name):
        self._name = name

    def __eq__(self, other: 'TOK_VAR') -> bool:
        return isinstance(other, TOK_VAR) and self._name == other._name

    def __hash__(self) -> int:
        return self._name.__hash__()

    def __repr__(self) -> str:
        return f"VAR({self._name!r})"

    def to_c(self) -> str:
        return f"{self._name}"

    def get_size(self) -> typing.Optional[int]:
        """
        The size of a variable depends on whether it's a varnode or a number.
        If it's a number, it has size 8. If it's a varnode, its size can be
        found using TOK_SIZEOF(varnode).to_c().
        """
        return None

    def to_pretty(self) -> str:
        if self._name.startswith('autovar_'):
            return self._name[len('autovar_'):]
        return self._name

    def get_variables(self):
        yield self

class TOK_SIZEOF(Token):
    def __init__(self, variable: TOK_VAR):
        self._variable = variable

    def __repr__(self) -> str:
        return f"SIZEOF({self._variable!r})"

    def get_size(self) -> int:
        return 8

    def to_c(self) -> str:
        return f"{self._variable.to_c()}->getSize()"

    def to_pretty(self) -> str:
        return f"|{self._variable.to_pretty()}|"

    def get_variables(self):
        yield self._variable

class TOK_NUMBER(Token):
    def __init__(self, val: str, size: str):
        self._val = int(val, 0)
        self._size = size
        self._val_repr = val

        if isinstance(size, str):
            self._size_val = int(size, 0)
        else:
            self._size_val = None

    def __repr__(self) -> str:
        return f"INT({self._val_repr}, {self._size!r})"

    def to_c(self) -> str:
        return self._val_repr

    def size_to_c(self) -> str:
        if isinstance(self._size, str):
            return self._size

        assert isinstance(self._size, TOK_SIZEOF)
        return self._size.to_c()

    def to_pretty(self) -> str:
        if self._size_val == 8:
            return self._val_repr

        if self._size_val is None:
            return self._val_repr + ":" + self._size.to_pretty()

        return self._val_repr + ":" + self._size

    def get_variables(self):
        if self._size_val is not None:
            return

        yield from self._size.get_variables()

class TOK_BINARY_OPERATION(Token):
    _name = "TOK_BINARY_OPERATION"
    _c_token = "?"
    _size = 8  # Ghidra's uintb type is 8 bytes wide

    def __init__(self, left: 'op', right: 'op'):
        self._left = left
        self._right = right

    def __repr__(self) -> str:
        return f"{self._name}({self._left!r}, {self._right!r})"

    def to_c(self) -> str:
        return f"({self._left.to_c()} {self._c_token} {self._right.to_c()})"

    def get_size(self) -> int:
        assert left.get_size() == right.get_size()
        return left.get_size()

    def to_pretty(self) -> str:
        # TODO: The token used for this operation in C might not be the same as
        # the token used for this operation in the rule specification grammar.
        return f"{self._left.to_pretty()} {self._c_token} {self._right.to_pretty()})"

    def get_variables(self):
        yield from self._left.get_variables()
        yield from self._right.get_variables()

class TOK_OPCODE(Token):
    def __init__(self, name: str, args: list['args']):
        self._name = name
        self._args = tuple(args)

    def __repr__(self) -> str:
        return f"TOK_OPCODE({self._name}, {self._args})"

    def get_name(self) -> str:
        return self._name

    def get_args(self) -> list['args']:
        return self._args

    def get_variables(self) -> [TOK_VAR]:
        for arg in self._args:
            yield from arg.get_variables()

    def get_size_hint(self):
        """
        Returns some sort of hint on the constraints of the sizes of the
        arguments, so that doesn't have to be specified explicitly. Not yet
        implemented.
        """
        raise NotImplementedError("TOK_OPCODE.get_size_hint has not yet been implemented.")

    def get_size(self) -> typing.Optional[int]:
        """
        Returns the size of the output varnode of this opcode. See:
        https://github.com/NationalSecurityAgency/ghidra/blob/master/GhidraDocs/languages/html/pcodedescription.html
        """
        if self._name == "PIECE":
            # Output size is the sum of the sizes of the (2) inputs
            return self._args[0].get_size() + self._args[1].get_size(),

        if self._name in {
            "COPY", "INT_ADD", "INT_SUB", "INT_2COMP", "INT_NEGATE",
            "INT_XOR", "INT_AND", "INT_OR", "INT_LEFT", "INT_RIGHT",
            "INT_SRIGHT", "INT_MULT", "INT_DIV", "INT_REM", "INT_SDIV",
            "INT_SREM", "FLOAT_ADD", "FLOAT_SUB", "FLOAT_MULT", "FLOAT_DIV",
            "FLOAT_NEG", "FLOAT_ABS", "FLOAT_SQRT", "FLOAT_CEIL",
            "FLOAT_FLOOR", "FLOAT_ROUND"
        }:
            # Output is the same size as input
            return self._args[0].get_size()

        if self._name in {
            "INT_EQUAL", "INT_NOTEQUAL", "INT_LESS", "INT_SLESS",
            "INT_LESSEQUAL", "INT_SLESSEQUAL", "INT_CARRY", "INT_SCARRY",
            "INT_SBORROW", "BOOL_NEGATE", "BOOL_XOR", "BOOL_AND", "BOOL_OR",
            "FLOAT_EQUAL", "FLOAT_NOTEQUAL", "FLOAT_LESS", "FLOAT_LESSEQUAL",
            "FLOAT_NAN"
        }:
            # Output is a boolean - output is a single byte
            return 1

        # Opcode is not in reference or output size is not related to input size
        return None

    def get_num_args(self) -> int:
        # TODO: This should probably be a name-based lookup, similar to get_size
        return len(self._args)

    def to_pretty(self) -> str:
        return f"{self._name}({', '.join([a.to_pretty() for a in self._args])})"

class TOK_CONSTRAINT(Token):
    def __init__(self, left, comparison, right):
        self._left = left
        self._comparison_op = comparison
        self._right = right
        self._or_func_name = None  # only used when the right side is a TOK_OPCODE_OR

    def to_check_c(self, emitter: "emit.Emitter", indent_level: int) -> tuple[str, int]:
        if isinstance(self._right, TOK_OPCODE_OR):
            assert self._comparison_op == "=", "Only equality constraints are supported for OPCODE_OR."

            self._or_func_name = emitter._get_free_name("or_func")
            option_name = emitter._get_free_name("option_id")
            indent_str = " " * indent_level

            assert not any([isinstance(e, TOK_VAR) for e in self._right._elements]), "Comparing two variables for equality is not supported - use as few variables as possible."

            return (
                "\n"
                f"{indent_str}auto {self._or_func_name} = [&](int4 {option_name}) -> int4 {{\n"
                f"{indent_str}  if ({option_name} == 0) {{\n" +
                emitter._emit_check_opcode(self._left, self._right._elements[0], indent_level + 4) +
                "".join([
                    f"{indent_str}  }} else if ({option_name} == {i}) {{\n" +
                    emitter._emit_check_opcode(self._left, self._right._elements[i], indent_level + 4)
                    for i in range(1, len(self._right._elements) - 1)
                ]) +
                f"{indent_str}  }} else {{\n" +
                emitter._emit_check_opcode(self._left, self._right._elements[-1], indent_level + 4) +
                f"{indent_str}  }}\n\n"
            ), indent_level + 2

        match self._comparison_op:
            case "=":
                if self._left == self._right:
                    return "", indent_level

                if isinstance(self._right, TOK_OPCODE):
                    return emitter._emit_check_opcode(self._left, self._right, indent_level), indent_level

                assert not isinstance(self._right, TOK_VAR), "Comparing two variables for equality is not supported - use as few variables as possible."

                return emitter._emit_check_constant_equal(self._left.to_c(), self._right.to_c(), indent_level), indent_level

            case "<":
                if self._left == self._right:
                    print("Warning: less-than constraint between two equal sides")
                    return f"{' ' * indent_level}return 0;", indent_level

                if isinstance(self._right, TOK_VAR):
                    # variable
                    var_name = self._right.to_c()
                    assert var_name in emitter._variables, "Cannot create new variable in constraint"

                    return (
                        emitter._emit_check_is_constant(var_name, indent_level)
                        + emitter._emit_check_constant_less(self._left.to_c(), f"{var_name}->getOffset()", indent_level)
                    ), indent_level

                if isinstance(self._right, (TOK_BINARY_OPERATION, TOK_NUMBER)):
                    # some operations that will evaluate to a constant
                    return emitter._emit_check_constant_less(self._left.to_c(), self._right.to_c(), indent_level), indent_level

            case ">":
                if self._left == self._right:
                    print("Warning: greater-than constraint between two equal sides")
                    return f"{' ' * indent_level}return 0;", indent_level

                if isinstance(self._right, TOK_VAR):
                    # variable
                    var_name = self._right.to_c()
                    assert var_name in emitter._variables, "Cannot create new variable in constraint"

                    return (
                        emitter._emit_check_is_constant(var_name, indent_level)
                        + emitter._emit_check_constant_greater(self._left.to_c(), f"{var_name}->getOffset()", indent_level)
                    ), indent_level

                if isinstance(self._right, (TOK_BINARY_OPERATION, TOK_NUMBER)):
                    # some operations that will evaluate to a constant
                    return emitter._emit_check_constant_greater(self._left.to_c(), self._right.to_c(), indent_level)

        raise ValueError(f"Unsupported type: {self._comparison_op!r} constraint with variable and {type(check_val)} in constraint.")

    def to_check_c_end(self, emitter: "emit.Emitter", indent_level: int) -> str:
        assert isinstance(self._right, TOK_OPCODE_OR)

        indent_str = " " * indent_level
        it_var = emitter._get_free_name("i")

        return (
            f"{indent_str}}}\n"
            f"\n"
            f"{indent_str}int4 {it_var};\n"
            f"{indent_str}for ({it_var} = 0; {it_var} < {len(self._right._elements)}; {it_var}++) {{;\n"
            f"{indent_str}  if ({self._or_func_name}({it_var}) != 0)\n"
            f"{indent_str}    break;\n"
            f"{indent_str}}}\n"
            f"\n"
            f"{indent_str}if ({it_var} == {len(self._right._elements)})\n"
            f"{indent_str}  return 0;\n"
            f"{indent_str}}}\n"
        )

    def __repr__(self) -> str:
        return f"TOK_CONSTRAINT({self._left!r}, {self._comparison_op!r}, {self._right!r})"

    def get_variables(self):
        yield from self._left.get_variables()
        yield from self._right.get_variables()

    def get_size(self) -> typing.Optional[int]:
        """
        A constraint has no size, so this function returns None.
        """
        return None

    def to_pretty(self) -> str:
        return f"{self._left.to_pretty()} {self._comparison_op} {self._right.to_pretty()}\n"

class TOK_OPCODE_OR(Token):
    def __init__(self, elements: tuple[TOK_OPCODE | TOK_VAR]):
        assert len(elements) > 1
        self._elements = elements

    def __repr__(self) -> str:
        return f"TOK_OPCODE_OR{self._elements!r}"

    def get_size(self) -> typing.Optional[int]:
        return None

    def to_pretty(self) -> str:
        return " | ".join((e.to_pretty() for e in self._elements))

    def get_variables(self):
        for element in self._elements:
            yield from element.get_variables()

class TOK_BINOP_ADD(TOK_BINARY_OPERATION):
    _name = "TOK_BINOP_ADD"
    _c_token = "+"

class TOK_BINOP_SUB(TOK_BINARY_OPERATION):
    _name = "TOK_BINOP_SUB"
    _c_token = "-"

class TOK_BINOP_MULT(TOK_BINARY_OPERATION):
    _name = "TOK_BINOP_MULT"
    _c_token = "*"

class TOK_BINOP_AND(TOK_BINARY_OPERATION):
    _name = "TOK_BINOP_AND"
    _c_token = "&"

class TOK_BINOP_OR(TOK_BINARY_OPERATION):
    _name = "TOK_BINOP_OR"
    _c_token = "|"

class TOK_BINOP_XOR(TOK_BINARY_OPERATION):
    _name = "TOK_BINOP_XOR"
    _c_token = "^"

class TOK_BINOP_LSHIFT(TOK_BINARY_OPERATION):
    _name = "TOK_BINOP_LSHIFT"
    _c_token = "<<"

class TOK_BINOP_RSHIFT(TOK_BINARY_OPERATION):
    _name = "TOK_BINOP_RSHIFT"
    _c_token = ">>"

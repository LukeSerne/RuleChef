import tokens

class Emitter:
    def __init__(self):
        # keep track of variables we come across
        self._variables = set()
        self._declared_vars = set()

    def emit_apply_op(self, class_name: str, match_expr: tokens.TOK_OPCODE, constraints: list[tokens.TOK_CONSTRAINT], replace_expr: tokens.TOK_OPCODE | tokens.TOK_VAR) -> str:
        out = (
            f"int4 RuleSimplify{class_name}::applyOp(PcodeOp *op, Funcdata &data)\n"
            "\n"
            "{\n"
            "\n"
            "  // Remaining checks on the match expression\n"
        )

        # First verify the other parts of the match expr
        assert isinstance(match_expr, tokens.TOK_OPCODE)

        # Declare all named variables in this scope because we might need them
        # later
        for var in replace_expr.get_variables():
            out += self._emit_declare_var(var)

        out += self._emit_check_opcode_children("op", match_expr, 2)

        # Now the extra constraints
        if constraints:
            out += (
                "\n"
                "  // Some more checks for the extra constraints\n"
            )

        indent_level = 2
        finish_constraints = []

        for constr in constraints:
            code, new_indent_level = constr.to_check_c(self, indent_level)
            out += code

            if new_indent_level != indent_level:
                finish_constraints.append((indent_level, constr))
                indent_level = new_indent_level

        for indent_level, constr in reversed(finish_constraints):
            out += constr.to_check_c_end(self, indent_level)

        out += (
            "\n"
            "  // matched this PcodeOp - replace this with the simplified structure\n"
        )

        # TODO: Add support for replacing with variables
        assert isinstance(replace_expr, tokens.TOK_OPCODE), "The replace expression must be an OPCODE"

        # TODO: Automatically detect if we need to add an INT_ZEXT opcode

        # Change this opcode and num inputs if different
        if replace_expr.get_name() != match_expr.get_name():
            out += f"  data.opSetOpcode(op, CPUI_{replace_expr.get_name()});\n"

        num_match_args = match_expr.get_num_args()
        num_replace_args = replace_expr.get_num_args()

        for i in range(num_match_args, num_replace_args):
            out += f"  op->insertInput({i});\n"
        for i in range(num_replace_args, num_match_args):
            out += f"  data.opRemoveInput(op, {i});\n"

        # Change inputs
        for i, replace_arg in enumerate(replace_expr.get_args()):
            if isinstance(replace_arg, tokens.TOK_OPCODE):
                out += self._emit_create_opcode(replace_arg, "op", i)
            elif isinstance(replace_arg, tokens.TOK_VAR):
                out += self._emit_create_var(replace_arg, "op", i)
            else:
                out += self._emit_create_const(replace_arg,- "op", i)

        out += (
            "\n"
            "  return 1;\n"
            "}\n"
        )

        return out

    def _get_free_name(self, prefix: str) -> str:
        for i in range(1000):
            name = f"{prefix}_{i}"
            if name not in self._variables:
                self._variables.add(name)
                return name

        raise ValueError("Too many variables in use!")

    def _emit_create_opcode(self, opcode: tokens.TOK_OPCODE, parent_op_name: str, input_num: int) -> str:
        new_op_name = self._get_free_name("out_op")
        new_out_varname = self._get_free_name("out_varnode")

        out  = f"  PcodeOp* {new_op_name} = data.newOp({len(opcode._args)}, {parent_op_name}->getAddr());\n"
        out += f"  data.opSetOpcode({new_op_name}, CPUI_{opcode._name});\n"
        out += f"  Varnode* {new_out_varname} = data.newUniqueOut({opcode.get_size()}, {new_op_name});\n"
        out += f"  data.opInsertBefore({new_op_name}, {parent_op_name});\n"
        out += f"  data.opSetInput({parent_op_name}, {new_out_varname}, {input_num});\n\n"

        for i, arg in enumerate(opcode._args):
            if isinstance(arg, tokens.TOK_OPCODE):
                out += self._emit_create_opcode(arg, new_op_name, i)
            elif isinstance(arg, tokens.TOK_VAR):
                out += self._emit_create_var(arg, new_op_name, i)
            else:
                out += self._emit_create_const(arg, new_op_name, i)

        return out

    def _emit_create_var(self, variable: tokens.TOK_VAR, parent_op_name: str, input_number: int) -> str:
        return f"  data.opSetInput({parent_op_name}, {variable.to_c()}, {input_number});\n"

    def _emit_create_const(self, constant: tokens.TOK_NUMBER | tokens.TOK_BINARY_OPERATION, parent_op_name: str, input_number: int):
        const_varnode_name = self._get_free_name("out_const")
        out  = f"  Varnode* {const_varnode_name} = data.newConstant({constant.size_to_c()}, {constant.to_c()});\n"
        out += f"  data.opSetInput(op, {const_varnode_name}, {input_number});\n"
        return out

    def _emit_declare_var(self, variable: tokens.TOK_VAR) -> str:
        self._declared_vars.add(variable.to_c())
        return f"  Varnode* {variable.to_c()};\n"

    def _emit_create_varnode(self, var_name: str, var_source: str, num_indent: int) -> str:
        if var_name not in self._declared_vars:
            type_name = "Varnode* "
        else:
            type_name = ""

        return f"{' ' * num_indent}{type_name}{var_name} = {var_source};\n"

    def _emit_check(self, left: str, op: str, right: str, num_indent: int) -> str:
        return f"{' ' * num_indent}if ({left} {op} {right}) return 0;\n"
    def _emit_check_equality(self, name_a: str, name_b: str, num_indent: int) -> str:
        return self._emit_check(name_a, "!=", name_b, num_indent)
    def _emit_check_inequality(self, name_a: str, name_b: str, num_indent: int) -> str:
        return self._emit_check(name_a, "==", name_b, num_indent)
    def _emit_check_greater(self, name_a: str, name_b: str, num_indent: int) -> str:
        return self._emit_check(name_a, "<=", name_b, num_indent)
    def _emit_check_greater_equal(self, name_a: str, name_b: str, num_indent: int) -> str:
        return self._emit_check(name_a, "<", name_b, num_indent)
    def _emit_check_less(self, name_a: str, name_b: str, num_indent: int) -> str:
        return self._emit_check(name_a, ">=", name_b, num_indent)
    def _emit_check_less_equal(self, name_a: str, name_b: str, num_indent: int) -> str:
        return self._emit_check(name_a, ">", name_b, num_indent)

    def _emit_check_is_constant(self, varnode_name: str, num_indent: int) -> str:
        return f"{' ' * num_indent}if ((! {varnode_name}->isConstant()) return 0;"
    def _emit_check_constant(self, varnode_name: str, op: str, const_val: tokens.TOK_NUMBER | tokens.TOK_BINARY_OPERATION, num_indent: int) -> str:
        if const_val._size == 8:
            return f"{' ' * num_indent}if ((! {varnode_name}->isConstant()) || ({varnode_name}->getOffset() {op} {const_val.to_c()})) return 0;\n"

        return (
            f"{' ' * num_indent}uintb masked_const = {const_val.to_c()} & ((((uintb) 1) << (8 * {const_val._size.to_c()})) - 1);\n"
            f"{' ' * num_indent}if ((! {varnode_name}->isConstant()) || ({varnode_name}->getOffset() {op} masked_const)) return 0;\n"
        )

    def _emit_check_constant_equal(self, varnode_name: str, const_val: tokens.TOK_NUMBER | tokens.TOK_BINARY_OPERATION, num_indent: int) -> str:
        if const_val._size == 8:
            return f"{' ' * num_indent}if (! {varnode_name}->constantMatch({const_val.to_c()})) return 0;\n"

        return (
            f"{' ' * num_indent}uintb masked_const = {const_val.to_c()} & ((((uintb) 1) << (8 * {const_val._size.to_c()})) - 1);\n"
            f"{' ' * num_indent}if (! {varnode_name}->constantMatch(masked_const)) return 0;\n"
        )

    def _emit_check_constant_not_equal(self, varnode_name: str, const_val: tokens.TOK_NUMBER | tokens.TOK_BINARY_OPERATION, num_indent: int) -> str:
        return self._emit_check_constant(varnode_name, "==", const_val, num_indent)
    def _emit_check_constant_greater(self, varnode_name: str, const_val: tokens.TOK_NUMBER | tokens.TOK_BINARY_OPERATION, num_indent: int) -> str:
        return self._emit_check_constant(varnode_name, "<=", const_val, num_indent)
    def _emit_check_constant_greater_equal(self, varnode_name: str, const_val: tokens.TOK_NUMBER | tokens.TOK_BINARY_OPERATION, num_indent: int) -> str:
        return self._emit_check_constant(varnode_name, "<", const_val, num_indent)
    def _emit_check_constant_less(self, varnode_name: str, const_val: tokens.TOK_NUMBER | tokens.TOK_BINARY_OPERATION, num_indent: int) -> str:
        return self._emit_check_constant(varnode_name, ">=", const_val, num_indent)
    def _emit_check_constant_less_equal(self, varnode_name: str, const_val: tokens.TOK_NUMBER | tokens.TOK_BINARY_OPERATION, num_indent: int) -> str:
        return self._emit_check_constant(varnode_name, ">", const_val, num_indent)

    def _emit_check_opcode(self, varnode: tokens.TOK_VAR, opcode: tokens.TOK_OPCODE, num_indent: int) -> str:
        # check that the varnode is not a constant
        indent_str = " " * num_indent
        out = f"{indent_str}if (! {varnode.to_c()}->isWritten()) return 0;\n"

        # extract the PcodeOp
        pcode_varname = self._get_free_name("temp_pcode")
        out += f"{indent_str}PcodeOp* {pcode_varname} = {varnode.to_c()}->getDef();\n"

        # check the PcodeOp's code
        out += self._emit_check_equality(f"{pcode_varname}->code()", f"CPUI_{opcode._name}", num_indent)
        # and its children
        out += self._emit_check_opcode_children(pcode_varname, opcode, num_indent)

        return out

    def _emit_check_opcode_children(self, target: str, opcode: tokens.TOK_OPCODE, indentation = 2) -> str:
        # check the number of args - we could also hardcode this
        indent_str = " " * indentation

        out = (
            "\n"
            f"{indent_str}// Checks {opcode.to_pretty()}\n"
        )

        is_commutative = opcode._name in tokens.COMMUTATIVE_OP_NAMES

        if is_commutative:
            check_lambda_name = self._get_free_name("check_" + opcode.get_name().lower().rsplit("_", 1)[-1])
            varnode_left_name = self._get_free_name("autovar_left")
            varnode_right_name = self._get_free_name("autovar_right")

            out += f"{indent_str}auto {check_lambda_name} = [&](Varnode* {varnode_left_name}, Varnode* {varnode_right_name}) -> int4 {{\n"
            indentation += 2

        for i, arg in enumerate(opcode._args):
            if is_commutative:
                target_arg = (varnode_left_name, varnode_right_name)[i]
            else:
                target_arg = f"{target}->getIn({i})"


            if isinstance(arg, tokens.TOK_VAR):
                # variable
                var_name = arg.to_c()
                if var_name in self._variables:
                    # exists already - check for equality
                    out += self._emit_check_equality(target_arg, var_name, indentation)
                else:
                    # does not yet exist - create
                    self._variables.add(var_name)
                    out += self._emit_create_varnode(var_name, target_arg, indentation)

            elif isinstance(arg, tokens.TOK_BINARY_OPERATION):
                # maths
                out += self._emit_check_constant_equal(target_arg, arg, indentation)

            elif isinstance(arg, tokens.TOK_OPCODE):
                # opcode
                if is_commutative:
                    varnode_name = target_arg
                else:
                    varnode_name = self._get_free_name("autovar")
                    out += self._emit_create_varnode(varnode_name, target_arg, indentation)

                out += self._emit_check_opcode(tokens.TOK_VAR(varnode_name), arg, indentation)

            elif isinstance(arg, tokens.TOK_NUMBER):
                # int
                out += self._emit_check_constant_equal(target_arg, arg, indentation)

            else:
                raise ValueError(f"Unsupported OPNAME argument type {type(arg)}")

            out += "\n"

        if is_commutative:
            indentation -= 2
            name_a = self._get_free_name("autovar")
            name_b = self._get_free_name("autovar")
            out += (
                f"{indent_str}  return 1;\n"
                f"{indent_str}}};\n\n" +
                self._emit_create_varnode(name_a, f"{target}->getIn(0)", indentation) +
                self._emit_create_varnode(name_b, f"{target}->getIn(1)", indentation) +
                f"{indent_str}if ((! {check_lambda_name}({name_a}, {name_b})) && (! {check_lambda_name}({name_b}, {name_a})))\n"
                f"{indent_str}  return 0;\n"
            )

        return out

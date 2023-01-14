import pyparsing as pp

import rule
import tokens

def get_grammar():
    # The name of the rule (such as: 'SignBitExtract')
    name = pp.Word("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_")

    # The name of a 'CPUI_' opcode in Ghidra (such as: 'INT_RIGHT')
    opcode = pp.Or(tokens.ALL_OP_NAMES)

    # The name of a variable in the description (such as: 'shift_amount')
    variable = pp.Word("abcdefghijklmnopqrstuvwxyz_")

    # A number in base 10 or in hexadecimal if prefixed with '0x'
    number = pp.Combine(pp.Or((
        "0",
        pp.Char("123456789") + pp.Char("0123456789")[...],
        "-" + pp.Char("123456789") + pp.Char("0123456789")[...],
        "0x0",
        "0x" + pp.Char("123456789abcdefABCDEF") + pp.Char("0123456789abcdefABCDEF")[...],
    )))

    # The size of a variable, or Varnode (such as '|shift_amount|')
    sizeof = "|" + variable + "|"

    # A number with optional size indication (such as '0:|shift_amount|')
    sized_number = number + pp.Optional(":" + pp.Or((number, sizeof)))

    # A variable with a concrete value during execution of the rule (such as 'shift_amount')
    value = pp.Or((variable, sized_number, sizeof))

    # The various expressions with values. Note that the associativity and
    # precedence is the same as in C. If in doubt, you can always use parentheses
    # to specify the order and associativity you want.
    value_expr = pp.infix_notation(
        value,
        [
            ("*", 2, pp.OpAssoc.LEFT),
            (pp.one_of("+ -"), 2, pp.OpAssoc.LEFT),
            (pp.one_of("<< >>"), 2, pp.opAssoc.LEFT),
            ("&", 2, pp.opAssoc.LEFT),
            ("^", 2, pp.opAssoc.LEFT),
            ("|", 2, pp.opAssoc.LEFT),
        ],
    )

    expr = pp.Forward()

    # An opcode with expressions as arguments (such as 'INT_RIGHT(x, |y| + 4)')
    opcode_expr = opcode + "(" + pp.delimited_list(expr) + ")"

    # Multiple opcode expressions that are alternatives (such as 'INT_RIGHT(y) | y')
    opcode_alt_expr = opcode_expr + (pp.Suppress("|") + pp.Or((variable, opcode_expr)))[...]

    # A match expression always has to be a single opcode expression
    match_expr = opcode_expr

    # A replace expression might be either an opcode expression or a variable
    replace_expr = pp.Group(pp.Or(opcode_expr, variable))

    # An expression is either an opcode or a value expression
    expr <<= pp.Or((opcode_alt_expr, value_expr))

    # A constraint is an inequality that must be satisfiable for the match to
    # succeed. The left-hand-side of the inequality can only be something with
    # a concrete value during execution, so no opcode expressions.
    constraint = value_expr + pp.one_of("< > =") + expr

    rule = name("rule_name") - ":" - match_expr("match_expr") + pp.Optional(
        pp.Literal(":-") - "{" - constraint[...]("constraints") + "}"
    ) - "=>" - replace_expr("replace_expr")

    @constraint.set_parse_action
    def parse_constraint(results: pp.ParseResults):
        return tokens.TOK_CONSTRAINT(results[0], results[1], results[2])

    @opcode_alt_expr.set_parse_action
    def parse_opcode_alt_expr(results: pp.ParseResults):
        if len(results) > 1:
            return tokens.TOK_OPCODE_OR(tuple(results))
        else:
            return results[0]

    @opcode_expr.set_parse_action
    def parse_opcode(results: pp.ParseResults):
        return tokens.TOK_OPCODE(results[0], results[2:-1])

    def parse_value_expr(results: pp.ParseResults):
        if isinstance(results, int):
            return parse_number(results)
        if not isinstance(results, pp.ParseResults):
            return results

        if len(results) == 1:
            return parse_value_expr(results[0])

        op = results[1]
        left = parse_value_expr(results[0])
        right = parse_value_expr(results[2])

        if op == "+":
            return tokens.TOK_BINOP_ADD(left, right)
        elif op == "-":
            return tokens.TOK_BINOP_SUB(left, right)
        elif op == "*":
            return tokens.TOK_BINOP_MULT(left, right)
        elif op == "&":
            return tokens.TOK_BINOP_AND(left, right)
        elif op == "|":
            return tokens.TOK_BINOP_OR(left, right)
        elif op == "^":
            return tokens.TOK_BINOP_XOR(left, right)
        elif op == "<<":
            return tokens.TOK_BINOP_LSHIFT(left, right)
        elif op == ">>":
            return tokens.TOK_BINOP_RSHIFT(left, right)

        raise ValueError(f"Unsupported operand: {op!r}")

    value_expr.set_parse_action(parse_value_expr)

    @sizeof.set_parse_action
    def parse_sizeof(results: pp.ParseResults):
        return tokens.TOK_SIZEOF(results[1])

    @sized_number.set_parse_action
    def parse_number(results: pp.ParseResults):
        if len(results) == 1:
            return tokens.TOK_NUMBER(results[0], "8")

        num, _, size = results

        return tokens.TOK_NUMBER(num, size)

    @variable.set_parse_action
    def parse_variable(results: pp.ParseResults):
        return tokens.TOK_VAR("autovar_" + results[0])

    return rule

def parse_description(file_name: str) -> rule.Rule:
    grammar = get_grammar()

    parsed_tokens = grammar.parse_file(file_name)

    # TODO: Figure out why this is needed...
    parsed_tokens['match_expr'] = tokens.TOK_OPCODE(parsed_tokens['match_expr'][0], parsed_tokens['match_expr'][2:-1])

    return rule.Rule(
        parsed_tokens['rule_name'],
        parsed_tokens['match_expr'],
        parsed_tokens.get('constraints', []),
        parsed_tokens['replace_expr'][0],
    )

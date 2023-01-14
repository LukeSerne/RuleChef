import tokens
import emit

class Rule:
    def __init__(self, name, match_expr, constraints, replace_expr):
        self._name = name
        self._match_expr = match_expr
        self._constraints = constraints
        self._replace_expr = replace_expr

    def emit_c_code(self) -> str:
        explanation_comment = self._get_explanation_docstring()
        header = self._emit_header()
        get_oplist = self._emit_get_oplist()

        emitter = emit.Emitter()
        apply_op = emitter.emit_apply_op(self._name, self._match_expr, self._constraints, self._replace_expr)

        return "\n".join((header, "", explanation_comment, get_oplist, "", apply_op))

    def _emit_header(self) -> str:
        return (
            f"class RuleSimplify{self._name} : public Rule {{\n"
            "public:\n"
            f"  RuleSimplify{self._name}(const string &g) : Rule( g, 0, \"simplify{self._name.lower()}\") {{}}	///< Constructor\n"
            "  virtual Rule *clone(const ActionGroupList &grouplist) const {\n"
            "    if (!grouplist.contains(getGroup())) return (Rule *)0;\n"
            f"    return new RuleSimplify{self._name}(getGroup());\n"
            "  }\n"
            "  virtual void getOpList(vector<uint4> &oplist) const;\n"
            "  virtual int4 applyOp(PcodeOp *op,Funcdata &data);\n"
            "};\n"
        )

    def _emit_get_oplist(self) -> str:
        return (
            f"void RuleSimplify{self._name}::getOpList(vector<uint4> &oplist) const\n"
            "{\n"
            f"  oplist.push_back(CPUI_{self._match_expr.get_name()});\n"
            "}\n"
        )

    def _get_explanation_docstring(self) -> str:
        """
        Returns a string containing a C comment that describes the rule.
        """
        pretty_rule = self._get_pretty_rule()

        return (
            f"/// \\class RuleSimplify{self._name}\n"
            "///\n"
            f"/// \\brief This rule was automatically generated rule from the expression:\n"
            "///\n"
            "/// "
        ) + "/// ".join(pretty_rule) + "///"

    def _get_pretty_rule(self) -> list[str]:
        """
        Returns a pretty-printed version of the description that was used to
        create this rule. Each line is a separate element of the returned list.
        """
        match_expr = self._match_expr.to_pretty()
        replace_expr = self._replace_expr.to_pretty()

        if not self._constraints:
            return [f"{match_expr} => {replace_expr}\n"]
        else:
            return [
                f"{match_expr} :- {{\n",
                *[f"    {constraint.to_pretty()}" for constraint in self._constraints],
                f"}} => {replace_expr}\n",
            ]

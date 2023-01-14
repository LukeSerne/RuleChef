# RuleChef
Translates a high-level declarative description of a simplification rule for [Ghidra]'s decompiler into the C++ code that is required for the decompiler to apply the rule.

## Usage

    python rulechef.py /path/to/example.txt

## Syntax
The syntax to define these simplification rules is a work in progress that has been largely inspired by the Statix language used in [Spoofax]. The syntax is designed in a way that is hopefully intuitive and clear.

### Example

    SignBitExtract:
        INT_RIGHT(x, |x| * 8 - 1) :- {
            x = INT_OR(y, INT_MULT(y, -1:|y|))
        }
        => INT_ZEXT(INT_NOTEQUAL(y, 0:|y|))

### Structure
A specification file is just a text file containing a description of a single rule. This description starts with the name of the rule, which can contain lower- and uppercase characters, as well as digits and underscores (`[A-Za-z0-9_]+`). A colon separates the rule name from the rule itself, which consists of three parts.

The first part is the matching criterion. This is the `PcodeOp` that the rule should apply to. Next, the inputs of this `PcodeOp` are listed using a syntax that resembles the function call syntax. The name of the `PcodeOp` is the one listed in [Ghidra's P-Code Operation Reference]. These inputs can be specified to be concrete numbers (both in base 10 or in base 16 with the `0x` prefix) or other `PcodeOp`s. Additionally, variables, written as a continuous string of lowercase characters and underscores (`[a-z_]+`), can be used to represent either a `PcodeOp` or a constant. In the place of a concrete value, also an expression involving constants might be used. Simple arithmetic operators are supported and can be used to combine constants and variables that represent concrete values. Furthermore, the `|<variable>|` syntax can be used to refer to the size of the specified variable.

The second part of the rule is optional and imposes further constraints on the variables introduced in the matching criterion. In addition, it can also introduce new variables. This part starts with the two tokens `:-` and `{`, with optional whitespace in-between. A number of constraints follows, and the end of the part is indicated by the `}` token.
Each constraint consists of three parts, a left-hand-side, a comparison operator and a right-hand-side. The left-hand-side is the variable that is compared. The comparison operator is either `<`, `>` or `=` to indicate less-than, greater than or equality. If a variable refers to a `PcodeOp`, only the `=` operator is supported. The right-hand-side can be either a constant, `PcodeOp`, variable or set of alternative `PcodeOp`s. The latter construct is indicated using the `|` operator. As such, the constraint `y = INT_ZEXT(z) | INT_2COMP(z)` constrains the variable `y` to either of those two `PcodeOp`s. The order in which they are attempted in the generated C++ code is the same as the order in which they are specified.

The third part contains the replacement expression. This starts with the `=>` token. After it comes the `PcodeOp` that should be constructed in place of the matched `PcodeOp`. In its specification, any variables that have been used previously can be used again. If any constants are included, it is likely that a size indication is required.

### Caveats
There are a few main caveats:
1. Barely any checking is performed on the input rule other than syntactical correctness. As such, if the input rule is not specified correctly, the output C++ code will not match the correct structures. To debug this, calls to `printf` can be added, or a debugger (such as `gdb`) can be attached to follow the execution of the generated rule.
1. Currently, no distinction is made between variables that refer to constants and variables that refer to a `PcodeOp`. Based on the context, assumptions are made on whether the variable refers to a constant or a `PcodeOp` and those assumptions are reflected in the generated C++ code. As such, care should be taken to not mix constant-variables and `PcodeOp`-variables.
1. Currently, the left-hand-side of a constraint can only be a variable. This excludes potentially useful constraints such as `c & 0xFF = 0`.
1. The order of the constraints are generated in the order that they are specified. This means that a variable should probably not appear in the left-hand-side before it has been "defined" - that is, its value has somehow been constrained. If a rule does use a variable in the left-hand-side before its value has been constrained, the generated C++ code will be broken and either not compile or the rule will not match anything.
1. Nodes in the data flow graph (whether they are `PcodeOp`s or constants) also have an associated size. As such, it may be necessary to specify the size of a constant, especially for negative constants, to ensure proper matching. The size of constants can be indicated using `<number>:<size>` syntax. `<size>` can be either a number or a "sizeof" expression. If no size is specified, a size of 8 bytes is assumed. For example, `0:|y|` means "a constant with the value 0 with the same size as the variable `y`".
1. As with nearly all automatically generated code, the code might be a little hard to understand. To reduce this problem, the automatically generated code contains a few comments that indicate what different parts of the code are doing.
1. The generated code might not be written in a way that is most efficient. For example, there might be redundant checks or needless overhead. In most cases, this is because this program is written in a way to support as many rule types as possible. Other times, opportunities for optimization exist because multiple constraints can be combined. As such, the code might benefit from a manual pass-through to further optimize the code.

## TODO
The items below are listed indicate limitations to the program in its current form that should be addressed at some point in the future.

- Allow constraints like `x + 5 = y & 8`, while disallowing `x + 5 = INT_ZEXT(y)`.
- Make a distinction between variables that are a number and an opcode.
- Hardcode input/output constraints for `PcodeOps`, so fewer size indicators are required.
- Implement code generation for `&`, `|`, `^`, `<<` and `>>` operators.


[Ghidra]: https://github.com/NationalSecurityAgency/ghidra
[Spoofax]: https://github.com/metaborg/spoofax-pie
[Ghidra's P-Code Operation Reference]: https://github.com/NationalSecurityAgency/ghidra/blob/master/GhidraDocs/languages/html/pcodedescription.html
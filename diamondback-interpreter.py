import operator
import sys
from lupa import LuaRuntime


class Interpreter:
    def __init__(self):
        self.variables = {}
        self.functions = {}
        self.imported_libraries = {}
        self.in_function_definition = False
        self.current_function_name = ""
        self.current_function_body = []
        self.allow_library_vars = False
        self.lua = LuaRuntime()

    def run_from_file(self, filename):
        with open(filename, "r") as file:
            code = file.readlines()
            self.run(code)

    def run(self, lines):
        in_python_block = False
        in_lua_block = False
        python_code = ""
        lua_code = ""
        code_to_execute = []

        for line in lines:
            stripped_line = line.strip()

            if stripped_line == "[plang python]":
                in_python_block = True
                continue

            elif stripped_line == "[plang lua]":
                in_lua_block = True
                continue

            if stripped_line == "[endplang]" and in_python_block:
                in_python_block = False
                code_to_execute.append(("python", python_code.strip()))
                python_code = ""
                continue
            
            elif stripped_line == "[endplang]" and in_lua_block:
                in_lua_block = False
                code_to_execute.append(("lua", lua_code.strip()))
                lua_code = ""
                continue

            if in_python_block:
                python_code += line + "\n"
            
            elif in_lua_block:
                lua_code += line + "\n"

            else:

                if self.in_function_definition:
                    if stripped_line == "endf":
                        self.functions[self.current_function_name] = (
                            self.current_function_body
                        )
                        self.in_function_definition = False
                        self.current_function_name = ""
                        self.current_function_body = []
                    else:
                        self.current_function_body.append(stripped_line)
                else:
                    code_to_execute.append(("diba", stripped_line))

        for code_type, code in code_to_execute:
            if code_type == "python":
                self.execute_python_code(code)
            elif code_type == "lua":
                self.execute_lua_code(code)
            elif code_type == "diba":
                self.parse_line(code)

    def execute_python_code(self, python_code):
        if not self.in_function_definition:
            local_scope = {**self.variables}
            global_scope = {"__builtins__": __builtins__, "print": self.custom_print}

            try:
                exec(python_code, global_scope, local_scope)

                self.variables.update(local_scope)

                for var in local_scope:
                    if callable(local_scope[var]):
                        self.functions[var] = local_scope[var]

            except Exception as e:
                print(f"Error executing embedded Python code: {e}")
        else:
            return

    def execute_lua_code(self, lua_code):
        try:
            result = self.lua.execute(lua_code)
            if result is not None:
                print(result)
        except Exception as e:
            print(f"Error executing Lua code: {e}")

    def custom_print(self, *args, **kwargs):
        print(*args, **kwargs)

    def parse_line(self, line):
        line = line.split("//")[0].strip()
        if not line:
            return
        if line.startswith("def ") and line.endswith("()"):
            self.handle_function_definition(line[4:-2])
            return
        if self.in_function_definition:
            if line == "endf":
                self.in_function_definition = False
                self.functions[self.current_function_name] = self.current_function_body
                self.current_function_name = ""
                self.current_function_body = []
            else:
                self.current_function_body.append(line)
            return

        if line.startswith("var "):
            var_name, var_value = line[4:].split("=")
            self.variables[var_name.strip()] = self.evaluate_expression(
                var_value.strip()
            )
        elif line.startswith("print(") and line.endswith(")"):
            self.handle_print(line[6:-1])
        elif line.startswith("import ") and line.endswith(" [varcopy]"):
            library_name = line[7:-10].strip()
            self.handle_import(library_name, True)
        elif line.startswith("import "):
            library_name = line[7:].strip()
            self.handle_import(library_name, False)
        elif "=" in line:
            self.handle_assignment(line)
        elif line.endswith("()") and not line.startswith("def "):
            func_name = line[:-2].strip()
            if func_name in self.functions:
                self.handle_function_call(func_name)
            else:
                print(f"Undefined function: {func_name}")
        elif line.startswith("[plang") and line.endswith("]"):
            # self.execute_python_code(line)
            return
        elif line.startswith("[endplang]"):
            return
        else:
            print("Invaild Syntax.")
            sys.exit(1)

    def evaluate_expression(self, expression):
        tokens = expression.split()

        if len(tokens) == 1:
            token = tokens[0]
            try:
                return int(token)
            except ValueError:
                if token.startswith('"') and token.endswith('"'):
                    return token[1:-1]
                return self.variables.get(token, token)

        while "+" in tokens or "-" in tokens or "*" in tokens or "/" in tokens:
            for i, token in enumerate(tokens):
                if token in ["+", "-", "*", "/"]:
                    lhs = self.evaluate_expression(" ".join(tokens[:i]))
                    rhs = self.evaluate_expression(" ".join(tokens[i + 1 :]))
                    op = {
                        "+": operator.add,
                        "-": operator.sub,
                        "*": operator.mul,
                        "/": operator.truediv,
                    }[token]
                    return op(lhs, rhs)

        raise ValueError(f"Invalid expression: {expression}")

    def handle_print(self, line):
        value = self.evaluate_expression(line)
        print(value)

    def handle_assignment(self, line):
        var_name, value = line.split("=")
        var_name = var_name.strip()
        value = value.strip()
        self.variables[var_name] = value

    def handle_function_definition(self, line):
        func_name, _, remainder = line.partition(" ")
        self.current_function_name = func_name.strip()
        self.in_function_definition = True

        if remainder:
            print(
                f"Error: Unexpected code after function definition on the same line: {remainder.strip()}"
            )

    def handle_function_call(self, function_name):
        if function_name in self.functions and not self.in_function_definition:
            function_body = self.functions[function_name]

            for func_line in function_body:
                self.parse_line(func_line)
        else:
            print(
                f"Attempt to execute function '{function_name}' during its definition or function is undefined."
            )

    def handle_import(self, library_name, x):
        if library_name in self.imported_libraries:
            return

        try:
            with open(f"libs/{library_name}.dbl", "r") as file:
                library_code = file.readlines()

            current_vars = self.variables.copy()
            current_funcs = self.functions.copy()
            current_in_func_def = self.in_function_definition
            current_func_name = self.current_function_name
            current_func_body = self.current_function_body.copy()

            self.run(library_code)

            if x == True:
                self.variables.update(current_vars)
            else:
                self.variables = current_vars
            self.functions.update(current_funcs)
            self.in_function_definition = current_in_func_def
            self.current_function_name = current_func_name
            self.current_function_body = current_func_body
            self.allow_library_vars = False

            self.imported_libraries[library_name] = True
        except FileNotFoundError:
            print(f"Library not found: libs/{library_name}.dbl")
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python main.py <filename.diba> or diba <filename.diba>")
        sys.exit(1)

    filename = sys.argv[1]
    if not filename.endswith(".diba"):
        print("Error: File must have a .diba extension")
        sys.exit(1)

    interpreter = Interpreter()
    interpreter.run_from_file(filename)

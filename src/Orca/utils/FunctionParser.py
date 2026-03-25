from enum import Enum

class Token(Enum):
	# Structural
	LPAREN      = 1  # (
	RPAREN      = 2  # )
	COMMA       = 3  # ,
	SEMICOLON   = 4  # ;
	COLON       = 5  # :
	BACKTICK    = 6  # `
	ARROW       = 7  # ->
	# Keywords
	ASYNC       = 10 # async
	TYPE_FLOAT  = 11 # float
	TYPE_INT    = 12 # int
	TYPE_STR    = 13 # str
	TYPE_BOOL   = 14 # bool
	BOOL_TRUE   = 15 # True
	BOOL_FALSE  = 16 # False
	# Literals
	IDENTIFIER  = 20
	STRING      = 21
	NUMBER      = 22
	# Modifiers
	SILENT      = 30 # !
	# Special
	DESCRIPTION = 40
	EOF         = 41

class Lexeme:
	def __init__(self, token: Token, value: str, col: int = -1):
		self.token = token
		self.value = value
		self.col = col

# Map identifier strings to keyword tokens
KEYWORDS = {
	"async": "ASYNC",
	"float": "TYPE_FLOAT",
	"int":   "TYPE_INT",
	"str":   "TYPE_STR",
	"bool":  "TYPE_BOOL",
	"True":  "BOOL_TRUE",
	"False": "BOOL_FALSE",
}

class Lexer:
	def __init__(self, source: str):
		self.source = source
		self.start = 0
		self.current = 0
		self.line_start = 0
		self.lexemes: list[Lexeme] = []

	def tokenise(self) -> list[Lexeme]:
		while not self._is_at_end():
			self.start = self.current
			self.scan_token()

		# Append EOF at the end
		self.lexemes.append(Lexeme(Token.EOF, "", self.start))
		return self.lexemes

	def _is_at_end(self) -> bool:
		return self.current >= len(self.source)

	def _advance(self) -> str:
		ch = self.source[self.current]
		self.current += 1
		return ch

	def _peek(self) -> str:
		if self._is_at_end():
			return "\0"
		return self.source[self.current]

	def _peek_next(self) -> str:
		if self.current + 1 >= len(self.source):
			return "\0"
		return self.source[self.current + 1]

	def _match(self, expected: str) -> bool:
		if self._is_at_end():
			return False
		if self.source[self.current] != expected:
			return False
		self.current += 1
		return True

	def _add_token(self, token: Token, value: str):
		col = self.start - self.line_start
		self.lexemes.append(Lexeme(token, value, col))

	def scan_token(self):
		c = self._advance()

		# Whitespace
		if c in (" ", "\t", "\r"):
			return
		if c == "\n":
			self.line_start = self.current
			return

		# Single-char structural tokens
		if c == "(":
			self._add_token(Token.LPAREN, c)
			return
		if c == ")":
			self._add_token(Token.RPAREN, c)
			return
		if c == ",":
			self._add_token(Token.COMMA, c)
			return
		if c == ";":
			self._add_token(Token.SEMICOLON, c)
			return
		if c == "`":
			self._add_token(Token.BACKTICK, c)
			return
		if c == "!":
			self._add_token(Token.SILENT, c)
			return

		# Arrow "->"
		if c == "-":
			if self._match(">"):
				self._add_token(Token.ARROW, "->")
			else:
				# Unknown '-' by itself for this grammar; you can error if you want
				pass
			return

		# Colon vs description start
		if c == ":":
			self._colon_or_description()
			return

		# String literal
		if c == "\"":
			self._string()
			return

		# Number literal
		if c.isdigit():
			self._number()
			return

		# Identifier / keyword
		if c.isalpha() or c == "_":
			self._identifier()
			return

		# Anything else is currently ignored; you can add error handling here if desired

	def _colon_or_description(self):
		prev = self.lexemes[-1] if self.lexemes else None

		# If we just saw a BACKTICK token and the next char is space,
		# treat this as the start of "`: " Description
		if prev is not None and prev.token == Token.BACKTICK and self._peek() == " ":
			# Consume the space after ':'
			self._advance()
			desc_start = self.current

			# Read until newline or EOF
			while not self._is_at_end() and self._peek() != "\n":
				self._advance()

			value = self.source[desc_start:self.current]
			col = desc_start - self.line_start
			self.lexemes.append(Lexeme(Token.DESCRIPTION, value, col))
		else:
			self._add_token(Token.COLON, ":")

	def _string(self):
		# We are currently after the opening quote
		while not self._is_at_end() and self._peek() != "\"":
			self._advance()

		# Unterminated string; you can decide how to handle this
		if self._is_at_end():
			value = self.source[self.start + 1:self.current]
		else:
			# Consume closing quote
			self._advance()
			value = self.source[self.start + 1:self.current - 1]

		col = self.start - self.line_start
		self.lexemes.append(Lexeme(Token.STRING, value, col))

	def _number(self):
		while not self._is_at_end():
			ch = self._peek()
			if ch.isdigit() or ch == "_" or ch == ".":
				self._advance()
			else:
				break

		value = self.source[self.start:self.current]
		self._add_token(Token.NUMBER, value)

	def _identifier(self):
		while not self._is_at_end() and (self._peek().isalnum() or self._peek() == "_"):
			self._advance()

		text = self.source[self.start:self.current]
		name = KEYWORDS.get(text)

		if name is not None:
			token_type = getattr(Token, name)
			self._add_token(token_type, text)
		else:
			self._add_token(Token.IDENTIFIER, text)

class Parser:
	def __init__(self, lexemes: list[Lexeme]):
		self.lexemes = lexemes
		self.current = 0

	def _peek(self) -> Lexeme:
		return self.lexemes[self.current]

	def _previous(self) -> Lexeme:
		return self.lexemes[self.current - 1]

	def _is_at_end(self) -> bool:
		return self._peek().token == Token.EOF

	def _advance(self) -> Lexeme:
		if not self._is_at_end():
			self.current += 1
		return self._previous()

	def _check(self, token: Token) -> bool:
		if self._is_at_end():
			return False
		return self._peek().token == token

	def _check_next(self, token: Token) -> bool:
		if self.current + 1 >= len(self.lexemes):
			return False
		return self.lexemes[self.current + 1].token == token

	def _match(self, *tokens: Token) -> bool:
		for t in tokens:
			if self._check(t):
				self._advance()
				return True
		return False

	def _consume(self, token: Token, msg: str) -> Lexeme:
		if self._check(token):
			return self._advance()
		raise ValueError(msg + f" (got {self._peek().token} at index {self.current})")

	# Calls can contain multiple function calls
	def parse_call(self) -> list[dict]:
		calls: list[dict] = []
		while not self._is_at_end():
			# Allow stray semicolons
			if self._match(Token.SEMICOLON):
				continue
			if self._check(Token.EOF):
				break
			calls.append(self._function_call())
			# Optional semicolon after each call
			self._match(Token.SEMICOLON)
		return calls

	def _function_call(self) -> dict:
		client = None

		# Optional namespace
		if self._check(Token.IDENTIFIER) and self._check_next(Token.COLON):
			client = self._advance().value
			self._consume(Token.COLON, "Expected ':' after namespace")

		# Function name
		name_lex = self._consume(Token.IDENTIFIER, "Expected function name")
		func_name = name_lex.value

		self._consume(Token.LPAREN, "Expected '(' after function name")

		args: list[str] = []
		if not self._check(Token.RPAREN):
			args.append(self._argument())
			while self._match(Token.COMMA):
				args.append(self._argument())

		self._consume(Token.RPAREN, "Expected ')' after arguments")

		return {
			"client": client,
			"function": func_name,
			"args": args,
		}

	def _argument(self):
		if self._match(Token.STRING):
			return self._previous().value
		if self._match(Token.NUMBER):
			return self._previous().value
		if self._match(Token.BOOL_TRUE):
			return self._previous().value
		if self._match(Token.BOOL_FALSE):
			return self._previous().value
		raise ValueError(f"Expected argument value, got {self._peek().token}")

	def parse_definition(self) -> dict:
		# FunctionDefinition = "`" [ Async ] [ Namespace ] Name "(" [ Parameterlist ] ")" [ SilentModifier ] [ ReturnType ] "`: " Description ;
		self._consume(Token.BACKTICK, "Expected '`' at start of function definition")

		is_async = self._match(Token.ASYNC)

		client = None
		if self._check(Token.IDENTIFIER) and self._check_next(Token.COLON):
			client = self._advance().value
			self._consume(Token.COLON, "Expected ':' after namespace")

		name_lex = self._consume(Token.IDENTIFIER, "Expected function name")
		func_name = name_lex.value

		self._consume(Token.LPAREN, "Expected '(' after function name")

		params: list = []
		if not self._check(Token.RPAREN):
			params.append(self._parameter())
			while self._match(Token.COMMA):
				params.append(self._parameter())

		self._consume(Token.RPAREN, "Expected ')' after parameters")

		is_silent = self._match(Token.SILENT)

		ret_type = None
		if self._match(Token.ARROW):
			# Return type can be a built-in type token or an identifier (UnconstrainedType)
			if self._match(Token.TYPE_FLOAT, Token.TYPE_INT, Token.TYPE_STR, Token.TYPE_BOOL, Token.IDENTIFIER):
				ret_type = self._previous().value
			else:
				raise ValueError("Expected return type after '->'")

		self._consume(Token.BACKTICK, "Expected closing '`' before description")

		description = None
		if self._match(Token.DESCRIPTION):
			description = self._previous().value

		return {
			"client": client,
			"function": func_name,
			"params": params,
			"return": ret_type,
			"silent": is_silent,
			"async": is_async,
			"description": description,
		}

	def _parameter(self):
		name_lex = self._consume(Token.IDENTIFIER, "Expected parameter name")
		self._consume(Token.COLON, "Expected ':' after parameter name")

		if self._match(Token.TYPE_FLOAT, Token.TYPE_INT, Token.TYPE_STR, Token.TYPE_BOOL, Token.IDENTIFIER):
			type_name = self._previous().value
		else:
			raise ValueError("Expected parameter type")

		return (name_lex.value, type_name)

class FunctionParser:
	def __init__(self):
		pass

	def call(self, source: str) -> list[dict]:
		# Allow omitting the final semicolon on the last call
		trimmed = source.rstrip()
		if trimmed and not trimmed.endswith(";"):
			trimmed += ";"
		lexer = Lexer(trimmed)
		parser = Parser(lexer.tokenise())
		return parser.parse_call()

	def definition(self, source: str) -> dict:
		lexer = Lexer(source)
		parser = Parser(lexer.tokenise())
		return parser.parse_definition()
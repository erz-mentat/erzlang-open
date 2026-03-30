from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from typing import Any

from ir.refs import RefPolicyError, normalize_ref_id

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")


class CompactError(ValueError):
    """Base error for compact form handling."""


class CompactParseError(CompactError):
    """Raised when syntax is invalid."""


class CompactValidationError(CompactError):
    """Raised when parsed content violates compact subset constraints."""


@dataclass(frozen=True)
class StatementSchema:
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()

    @property
    def ordered_fields(self) -> tuple[str, ...]:
        return self.required + tuple(k for k in self.optional if k not in self.required)

    @property
    def allowed_fields(self) -> set[str]:
        return set(self.required) | set(self.optional)


SCHEMA: dict[str, StatementSchema] = {
    "erz": StatementSchema(required=("v",)),
    # Sprint-1 long-form tags
    "event": StatementSchema(required=("type",), optional=("payload",)),
    "rule": StatementSchema(required=("id", "when", "then"), optional=("priority",)),
    "action": StatementSchema(required=("kind",), optional=("params",)),
    # Sprint-3 compact tags
    "ev": StatementSchema(required=("type",), optional=("payload",)),
    "rl": StatementSchema(required=("id", "when", "then"), optional=("priority",)),
    "ac": StatementSchema(required=("kind",), optional=("params",)),
    "tr": StatementSchema(
        required=("rule_id", "matched_clauses"),
        optional=("score", "calibrated_probability", "timestamp", "seed"),
    ),
    "rf": StatementSchema(required=("id", "v")),
    "pl": StatementSchema(required=(), optional=("rt",)),
}


@dataclass(frozen=True)
class Token:
    kind: str
    value: Any
    position: int


class _Tokenizer:
    def __init__(self, text: str) -> None:
        self.text = text
        self.length = len(text)
        self.index = 0

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while self.index < self.length:
            char = self.text[self.index]
            if char.isspace():
                self.index += 1
                continue

            if char in "{}[]:,":
                tokens.append(Token(kind=char, value=char, position=self.index))
                self.index += 1
                continue

            if char == '"':
                start = self.index
                try:
                    value, consumed = json.JSONDecoder().raw_decode(self.text[self.index :])
                except json.JSONDecodeError as exc:
                    raise CompactParseError(f"Invalid string at position {start}") from exc
                tokens.append(Token(kind="STRING", value=value, position=start))
                self.index += consumed
                continue

            if char.isdigit() or char == "-":
                tokens.append(self._consume_number())
                continue

            if char.isalpha() or char == "_":
                tokens.append(self._consume_identifier())
                continue

            raise CompactParseError(f"Unexpected character '{char}' at position {self.index}")

        tokens.append(Token(kind="EOF", value=None, position=self.length))
        return tokens

    def _consume_number(self) -> Token:
        start = self.index
        if self.text[self.index] == "-":
            self.index += 1
            if self.index >= self.length or not self.text[self.index].isdigit():
                raise CompactParseError(f"Invalid number at position {start}")

        while self.index < self.length and self.text[self.index].isdigit():
            self.index += 1

        has_fraction = False
        if self.index < self.length and self.text[self.index] == ".":
            has_fraction = True
            self.index += 1
            if self.index >= self.length or not self.text[self.index].isdigit():
                raise CompactParseError(f"Invalid number at position {start}")
            while self.index < self.length and self.text[self.index].isdigit():
                self.index += 1

        has_exponent = False
        if self.index < self.length and self.text[self.index] in "eE":
            has_exponent = True
            self.index += 1
            if self.index < self.length and self.text[self.index] in "+-":
                self.index += 1
            if self.index >= self.length or not self.text[self.index].isdigit():
                raise CompactParseError(f"Invalid number at position {start}")
            while self.index < self.length and self.text[self.index].isdigit():
                self.index += 1

        raw = self.text[start : self.index]
        if has_fraction or has_exponent:
            try:
                value = float(raw)
            except ValueError as exc:
                raise CompactParseError(f"Invalid number at position {start}") from exc
            return Token(kind="NUMBER", value=value, position=start)

        return Token(kind="NUMBER", value=int(raw), position=start)

    def _consume_identifier(self) -> Token:
        start = self.index
        self.index += 1
        while self.index < self.length and re.match(r"[A-Za-z0-9_-]", self.text[self.index]):
            self.index += 1

        ident = self.text[start : self.index]
        if ident == "true":
            return Token(kind="BOOL", value=True, position=start)
        if ident == "false":
            return Token(kind="BOOL", value=False, position=start)
        if ident == "null":
            return Token(kind="NULL", value=None, position=start)
        return Token(kind="IDENT", value=ident, position=start)


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.index = 0

    def parse_program(self) -> list[dict[str, Any]]:
        statements: list[dict[str, Any]] = []
        while not self._check("EOF"):
            statements.append(self._parse_statement())
        return statements

    def _parse_statement(self) -> dict[str, Any]:
        tag = self._consume("IDENT", "Expected statement tag").value
        self._consume("{", "Expected '{' after statement tag")

        fields: dict[str, Any] = {}
        if not self._check("}"):
            while True:
                key = self._consume("IDENT", "Expected field key").value
                if key in fields:
                    raise CompactValidationError(f"Duplicate field '{key}' in statement '{tag}'")
                self._consume(":", "Expected ':' after field key")
                fields[key] = self._parse_value()
                if self._match(","):
                    continue
                break

        self._consume("}", "Expected '}' to close statement")
        statement = {"tag": tag, "fields": fields}
        _validate_statement(statement)
        return statement

    def _parse_value(self) -> Any:
        token = self._peek()
        if token.kind in {"STRING", "NUMBER", "BOOL", "NULL"}:
            self.index += 1
            return token.value
        if token.kind == "[":
            return self._parse_array()
        if token.kind == "{":
            return self._parse_object()
        raise CompactParseError(
            f"Unexpected token '{token.kind}' at position {token.position} while parsing value"
        )

    def _parse_array(self) -> list[Any]:
        self._consume("[", "Expected '['")
        values: list[Any] = []
        if not self._check("]"):
            while True:
                values.append(self._parse_value())
                if self._match(","):
                    continue
                break
        self._consume("]", "Expected ']' to close array")
        return values

    def _parse_object(self) -> dict[str, Any]:
        self._consume("{", "Expected '{'")
        mapping: dict[str, Any] = {}
        if not self._check("}"):
            while True:
                key_token = self._peek()
                if key_token.kind == "IDENT":
                    key = self._advance().value
                elif key_token.kind == "STRING":
                    key = self._advance().value
                else:
                    raise CompactParseError(
                        f"Expected object key at position {key_token.position}"
                    )

                if key in mapping:
                    raise CompactValidationError(f"Duplicate object key '{key}'")

                self._consume(":", "Expected ':' after object key")
                mapping[key] = self._parse_value()
                if self._match(","):
                    continue
                break

        self._consume("}", "Expected '}' to close object")
        return mapping

    def _peek(self) -> Token:
        return self.tokens[self.index]

    def _advance(self) -> Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _check(self, kind: str) -> bool:
        return self._peek().kind == kind

    def _match(self, kind: str) -> bool:
        if self._check(kind):
            self.index += 1
            return True
        return False

    def _consume(self, kind: str, message: str) -> Token:
        token = self._peek()
        if token.kind != kind:
            raise CompactParseError(f"{message} at position {token.position}")
        self.index += 1
        return token


def parse_compact(text: str) -> list[dict[str, Any]]:
    tokenizer = _Tokenizer(text)
    tokens = tokenizer.tokenize()
    parser = _Parser(tokens)
    program = parser.parse_program()
    _validate_program(program)
    return program


def canonicalize_program(program: list[dict[str, Any]]) -> list[dict[str, Any]]:
    canonical: list[dict[str, Any]] = []
    for statement in program:
        tag = statement["tag"]
        schema = SCHEMA[tag]
        source_fields = statement["fields"]
        fields: dict[str, Any] = {}
        for key in schema.ordered_fields:
            if key in source_fields:
                fields[key] = _canonicalize_value(source_fields[key])
        canonical.append({"tag": tag, "fields": fields})
    return canonical


def format_compact(program: list[dict[str, Any]]) -> str:
    canonical = canonicalize_program(program)
    lines = []
    for statement in canonical:
        tag = statement["tag"]
        fields = statement["fields"]
        inner = ",".join(f"{key}:{_format_value(value)}" for key, value in fields.items())
        lines.append(f"{tag}{{{inner}}}")
    return "\n".join(lines) + ("\n" if lines else "")


def parse_and_format_compact(text: str) -> str:
    return format_compact(parse_compact(text))


def parse_and_dump_json(text: str) -> str:
    canonical = canonicalize_program(parse_compact(text))
    return json.dumps(canonical, indent=2, sort_keys=True, ensure_ascii=False)


def _canonicalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonicalize_value(value[key]) for key in sorted(value.keys())}
    if isinstance(value, list):
        return [_canonicalize_value(item) for item in value]
    return value


def _format_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CompactValidationError("Floating-point values must be finite")
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    if isinstance(value, list):
        return "[" + ",".join(_format_value(item) for item in value) + "]"
    if isinstance(value, dict):
        pieces = []
        for key in sorted(value.keys()):
            pieces.append(f"{_format_key(key)}:{_format_value(value[key])}")
        return "{" + ",".join(pieces) + "}"
    raise CompactValidationError(f"Unsupported value type: {type(value).__name__}")


def _format_key(key: str) -> str:
    if _IDENTIFIER_RE.fullmatch(key):
        return key
    return json.dumps(key, ensure_ascii=False)


def _validate_statement(statement: dict[str, Any]) -> None:
    tag = statement["tag"]
    if tag not in SCHEMA:
        supported = ", ".join(sorted(SCHEMA.keys()))
        raise CompactValidationError(f"Unknown statement tag '{tag}'. Supported tags: {supported}")

    fields = statement["fields"]
    schema = SCHEMA[tag]

    unknown_keys = set(fields.keys()) - schema.allowed_fields
    if unknown_keys:
        raise CompactValidationError(
            f"Unknown field(s) for '{tag}': {', '.join(sorted(unknown_keys))}"
        )

    missing_keys = set(schema.required) - set(fields.keys())
    if missing_keys:
        raise CompactValidationError(
            f"Missing required field(s) for '{tag}': {', '.join(sorted(missing_keys))}"
        )

    if tag == "erz":
        version = fields["v"]
        if not isinstance(version, int) or version <= 0:
            raise CompactValidationError("'erz.v' must be a positive integer")

    if tag in {"event", "ev"}:
        if not isinstance(fields["type"], str):
            raise CompactValidationError(f"'{tag}.type' must be a string")

    if tag in {"rule", "rl"}:
        if not isinstance(fields["id"], str):
            raise CompactValidationError(f"'{tag}.id' must be a string")
        if "priority" in fields and (
            isinstance(fields["priority"], bool) or not isinstance(fields["priority"], int)
        ):
            raise CompactValidationError(f"'{tag}.priority' must be an integer")
        when_value = fields["when"]
        if not isinstance(when_value, list) or not all(isinstance(item, str) for item in when_value):
            raise CompactValidationError(f"'{tag}.when' must be a list of strings")
        then_value = fields["then"]
        if not isinstance(then_value, list):
            raise CompactValidationError(f"'{tag}.then' must be a list of action objects")
        for index, action in enumerate(then_value):
            _validate_action_object(action, context=f"{tag}.then[{index}]")

    if tag in {"action", "ac"}:
        if not isinstance(fields["kind"], str):
            raise CompactValidationError(f"'{tag}.kind' must be a string")
        if "params" in fields and not isinstance(fields["params"], dict):
            raise CompactValidationError(f"'{tag}.params' must be an object")

    if tag == "tr":
        if not isinstance(fields["rule_id"], str):
            raise CompactValidationError("'tr.rule_id' must be a string")

        matched_clauses = fields["matched_clauses"]
        if (
            not isinstance(matched_clauses, list)
            or len(matched_clauses) == 0
            or not all(isinstance(item, str) and item for item in matched_clauses)
        ):
            raise CompactValidationError("'tr.matched_clauses' must be a non-empty list of strings")

        if "score" in fields:
            score = fields["score"]
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(float(score))
            ):
                raise CompactValidationError("'tr.score' must be a finite number")

        if "calibrated_probability" in fields:
            probability = fields["calibrated_probability"]
            if (
                isinstance(probability, bool)
                or not isinstance(probability, (int, float))
                or not math.isfinite(float(probability))
            ):
                raise CompactValidationError("'tr.calibrated_probability' must be a finite number")
            if not 0.0 <= float(probability) <= 1.0:
                raise CompactValidationError(
                    "'tr.calibrated_probability' must be within [0.0, 1.0]"
                )

        if "timestamp" in fields and (
            isinstance(fields["timestamp"], bool)
            or not isinstance(fields["timestamp"], (str, int, float))
        ):
            raise CompactValidationError("'tr.timestamp' must be a string or number")

        if "seed" in fields and (
            isinstance(fields["seed"], bool) or not isinstance(fields["seed"], (str, int))
        ):
            raise CompactValidationError("'tr.seed' must be a string or integer")

    if tag == "rf":
        if not isinstance(fields["id"], str):
            raise CompactValidationError("'rf.id' must be a string")
        try:
            normalize_ref_id(fields["id"], context="rf.id", allow_literal=False)
        except RefPolicyError as exc:
            raise CompactValidationError(str(exc)) from exc
        if not isinstance(fields["v"], str):
            raise CompactValidationError("'rf.v' must be a string")

    if tag == "pl":
        if "rt" in fields and not isinstance(fields["rt"], dict):
            raise CompactValidationError("'pl.rt' must be an object")


def _validate_program(program: list[dict[str, Any]]) -> None:
    seen_ref_ids: set[str] = set()
    for statement in program:
        if statement["tag"] != "rf":
            continue

        ref_id = statement["fields"]["id"]
        if ref_id in seen_ref_ids:
            raise CompactValidationError(f"Duplicate ref id '{ref_id}'")
        seen_ref_ids.add(ref_id)


def _validate_action_object(value: Any, context: str) -> None:
    if not isinstance(value, dict):
        raise CompactValidationError(f"'{context}' must be an object")

    allowed = {"kind", "params"}
    unknown = set(value.keys()) - allowed
    if unknown:
        raise CompactValidationError(
            f"Unknown field(s) for '{context}': {', '.join(sorted(unknown))}"
        )

    if "kind" not in value:
        raise CompactValidationError(f"Missing required field 'kind' in '{context}'")

    if not isinstance(value["kind"], str):
        raise CompactValidationError(f"'{context}.kind' must be a string")

    if "params" in value and not isinstance(value["params"], dict):
        raise CompactValidationError(f"'{context}.params' must be an object")

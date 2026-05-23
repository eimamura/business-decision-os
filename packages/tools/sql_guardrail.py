from __future__ import annotations

from dataclasses import dataclass

import sqlparse
from sqlparse.sql import Identifier, IdentifierList, Parenthesis, Statement, Token, TokenList
from sqlparse.tokens import DML, Keyword, Whitespace

from packages.tools.sql_allowlist import ALLOWED_READ_TABLES

_DISALLOWED_OPERATIONS = frozenset(
    {
        "ALTER",
        "CALL",
        "COPY",
        "CREATE",
        "DELETE",
        "DO",
        "DROP",
        "GRANT",
        "INSERT",
        "REVOKE",
        "TRUNCATE",
        "UPDATE",
    }
)
_DANGEROUS_FEATURES = frozenset(
    {
        "copy",
        "dblink",
        "lo_export",
        "lo_import",
        "pg_sleep",
        "postgres_fdw",
    }
)
_SOURCE_KEYWORDS = frozenset({"FROM", "JOIN"})
_SOURCE_END_KEYWORDS = frozenset(
    {
        "GROUP",
        "HAVING",
        "LIMIT",
        "OFFSET",
        "ON",
        "ORDER",
        "RETURNING",
        "SET",
        "UNION",
        "WHERE",
        "WINDOW",
    }
)


class SQLGuardrailError(Exception):
    pass


@dataclass(frozen=True)
class TableReference:
    table: str
    schema: str | None = None


def validate_read_sql(sql: str) -> None:
    statements = [stmt for stmt in sqlparse.parse(sql) if str(stmt).strip()]
    if not statements:
        raise SQLGuardrailError("Empty SQL statement")
    if len(statements) != 1:
        raise SQLGuardrailError("Only a single SQL statement is allowed")

    stmt = statements[0]
    _reject_disallowed_features(stmt)
    stmt_type: str = stmt.get_type()  # type: ignore[no-untyped-call]
    if stmt_type != "SELECT":
        raise SQLGuardrailError(f"Only SELECT statements are allowed, got: {stmt_type}")

    cte_names = _extract_cte_names(stmt)
    references = _extract_table_references(stmt, cte_names)
    if not references:
        raise SQLGuardrailError("SELECT must reference at least one allowlisted table")

    allowed_refs = 0
    disallowed: set[str] = set()
    for ref in references:
        display_name = f"{ref.schema}.{ref.table}" if ref.schema else ref.table
        if ref.schema not in (None, "public"):
            disallowed.add(display_name)
        elif ref.table in ALLOWED_READ_TABLES:
            allowed_refs += 1
        else:
            disallowed.add(display_name)

    if disallowed:
        tables = ", ".join(sorted(disallowed))
        raise SQLGuardrailError(f"Table(s) not allowed: {tables}")
    if allowed_refs == 0:
        raise SQLGuardrailError("SELECT must reference at least one allowlisted table")


def _reject_disallowed_features(stmt: Statement) -> None:
    for token in stmt.flatten():  # type: ignore[no-untyped-call]
        value = token.value.strip()
        if not value:
            continue
        normalized = value.lower().strip('"')
        keyword = token.normalized.upper()
        if keyword in _DISALLOWED_OPERATIONS:
            raise SQLGuardrailError(f"Operation not allowed: {keyword}")
        if normalized in _DANGEROUS_FEATURES:
            raise SQLGuardrailError(f"Function or feature not allowed: {normalized}")


def _extract_cte_names(stmt: Statement) -> set[str]:
    names: set[str] = set()
    tokens = list(stmt.tokens)
    seen_with = False
    for token in tokens:
        if token.is_whitespace:
            continue
        if not seen_with:
            if token.ttype is Keyword.CTE and token.normalized.upper() == "WITH":
                seen_with = True
            else:
                return names
            continue
        if token.ttype is DML and token.normalized.upper() == "SELECT":
            return names
        if isinstance(token, IdentifierList):
            for identifier in token.get_identifiers():  # type: ignore[no-untyped-call]
                _add_cte_name(names, identifier)
        elif isinstance(token, Identifier):
            _add_cte_name(names, token)
    return names


def _add_cte_name(names: set[str], identifier: Identifier) -> None:
    real_name = identifier.get_real_name()  # type: ignore[no-untyped-call]
    if real_name:
        names.add(_normalize_identifier(real_name))


def _extract_table_references(
    token_list: TokenList,
    cte_names: set[str],
) -> set[TableReference]:
    references: set[TableReference] = set()
    expect_source = False

    for token in token_list.tokens:
        if token.is_whitespace:
            continue
        if _is_source_keyword(token):
            expect_source = True
            continue
        if expect_source:
            if _is_source_end_keyword(token):
                expect_source = False
            else:
                references.update(_references_from_source_token(token, cte_names))
                expect_source = False
        if isinstance(token, TokenList):
            references.update(_extract_table_references(token, cte_names))

    return references


def _is_source_keyword(token: Token) -> bool:
    if token.ttype not in Keyword:
        return False
    normalized = token.normalized.upper()
    return normalized in _SOURCE_KEYWORDS or normalized.endswith(" JOIN")


def _is_source_end_keyword(token: Token) -> bool:
    if token.ttype not in Keyword:
        return False
    return token.normalized.upper().split()[0] in _SOURCE_END_KEYWORDS


def _references_from_source_token(token: Token, cte_names: set[str]) -> set[TableReference]:
    if isinstance(token, IdentifierList):
        references: set[TableReference] = set()
        for identifier in token.get_identifiers():  # type: ignore[no-untyped-call]
            references.update(_references_from_source_token(identifier, cte_names))
        return references
    if isinstance(token, Identifier):
        if _contains_select(token):
            return set()
        table = token.get_real_name()  # type: ignore[no-untyped-call]
        if not table:
            return set()
        table_name = _normalize_identifier(table)
        if table_name in cte_names:
            return set()
        parent = token.get_parent_name()  # type: ignore[no-untyped-call]
        schema_name = _normalize_identifier(parent) if parent else None
        return {TableReference(table=table_name, schema=schema_name)}
    if isinstance(token, Parenthesis):
        return set()
    if token.ttype not in (Whitespace,):
        table_name = _normalize_identifier(token.value)
        if table_name and table_name not in cte_names:
            return {TableReference(table=table_name)}
    return set()


def _contains_select(token_list: TokenList) -> bool:
    return any(
        token.ttype is DML and token.normalized.upper() == "SELECT"
        for token in token_list.flatten()  # type: ignore[no-untyped-call]
    )


def _normalize_identifier(value: str) -> str:
    return value.strip().strip('"').lower()

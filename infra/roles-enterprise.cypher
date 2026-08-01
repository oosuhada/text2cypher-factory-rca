// Enterprise Edition or a deployment supporting RBAC only.
// Pass $loader_password and $reader_password securely through cypher-shell.

CREATE USER graph_loader IF NOT EXISTS
SET PASSWORD $loader_password CHANGE NOT REQUIRED;

CREATE USER graph_reader IF NOT EXISTS
SET PASSWORD $reader_password CHANGE NOT REQUIRED;

GRANT ROLE architect TO graph_loader;
GRANT ROLE reader TO graph_reader;

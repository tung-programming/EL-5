# API reference

Owner: Member 5

The app serves the browser UI at `/` and static files under `/static/`. Start the
development server from the repository root with:

```powershell
uvicorn app:app --reload
```

All API responses are JSON. Parse and request validation errors return HTTP 400
with a `detail` message. Mathematical results outside the verifier's supported
scope return HTTP 200 with `status: "unknown"`.

## `GET /api/health`

Returns the service status and version.

```json
{"status":"ok","service":"algebra-step-checker","version":"1.0.0"}
```

## `GET /api/rules`

Returns supported operation identifiers, mistake labels, and result statuses.
The verifier owns the validity decision; operation inference does not determine
whether a step is valid. Mistake detection only runs for invalid steps.

## `POST /api/check-step`

Checks whether two equations have the same real solution set. Both equations
must be strings accepted by the project parser.

```json
{"previous_equation":"3x + 5 = 14","current_equation":"3x = 9"}
```

The request also accepts `previous` / `current` aliases. The response follows
the `CheckStepResponse` shape in [contracts.md](contracts.md): `status`,
`inference`, `mistake`, and `explanation`. `inference` or `mistake` may be
`null` when the corresponding engine cannot establish a supported result.

## `POST /api/parse-expression`

Parses an equation string and returns an `ExplorerNode` tree suitable for the
keyboard explorer.

```json
{"expression":"2(x + 3) = 12"}
```

The request also accepts `equation`, `text`, or `expression_text`. The response
is the root explorer node directly, with `id`, `type`, `role`, `value`, the
three `spoken_*` fields, and recursive `children`.

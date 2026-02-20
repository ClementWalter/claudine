---
name: effect-solutions
description: >
  Idiomatic Effect-TS patterns, solutions, and reference documentation. A field
  manual covering the full Effect ecosystem: services & layers (dependency
  injection), data modeling with Schema, error handling, config management,
  testing with @effect/vitest, HTTP clients with @effect/platform, CLIs with
  @effect/cli, observability with OpenTelemetry, and wrapping third-party
  Promise-based libraries. Use when writing or reviewing Effect-TS code, setting
  up an Effect project, choosing the right pattern for
  services/errors/config/testing, building typed HTTP clients or CLIs, or
  integrating external libraries into an Effect codebase.
---

# Effect Solutions

Field manual for idiomatic Effect-TS code. All reference files are in
`references/`.

## Reference Index

Load the relevant file(s) based on the task at hand:

| Task                                                                  | Reference File                                                |
| --------------------------------------------------------------------- | ------------------------------------------------------------- |
| Project setup (editor, language service, tsconfig)                    | `references/01-project-setup.md`, `references/02-tsconfig.md` |
| Core patterns: `Effect.gen`, `Effect.fn`, pipe, retry, timeout        | `references/03-basics.md`                                     |
| Services (`Context.Tag`) and Layers (DI, lifecycle, test layers)      | `references/04-services-and-layers.md`                        |
| Data modeling: `Schema.Class`, branded types, JSON encode/decode      | `references/05-data-modeling.md`                              |
| Error handling: `Schema.TaggedError`, `catchTag`, defects             | `references/06-error-handling.md`                             |
| Config loading: `Config`, `Schema.Config`, `Redacted`, test overrides | `references/07-config.md`                                     |
| Testing: `@effect/vitest`, `it.effect`, `TestClock`, test layers      | `references/08-testing.md`                                    |
| HTTP clients: `@effect/platform`, typed REST clients, middleware      | `references/11-http-clients.md`                               |
| Observability: OpenTelemetry, spans, OTLP export                      | `references/12-observability.md`                              |
| CLI building: `@effect/cli`, commands, args, options, subcommands     | `references/13-cli.md`                                        |
| Wrapping Promise-based libraries (Prisma, AWS SDK, etc.)              | `references/14-use-pattern.md`                                |

## Quick-Start Patterns

### Service + Layer (most common pattern)

```typescript
class MyService extends Context.Tag("@app/MyService")<
  MyService,
  { readonly doThing: (input: string) => Effect.Effect<Result, MyError> }
>() {
  static readonly layer = Layer.effect(
    MyService,
    Effect.gen(function* () {
      const dep = yield* OtherService;
      const doThing = Effect.fn("MyService.doThing")(function* (input) {
        return yield* dep.use(input);
      });
      return MyService.of({ doThing });
    }),
  );

  static readonly testLayer = Layer.succeed(MyService, {
    doThing: (_) => Effect.succeed(mockResult),
  });
}
```

### Tagged Error

```typescript
class MyError extends Schema.TaggedError<MyError>()("MyError", {
  message: Schema.String,
}) {}

// Usage: yield* new MyError({ message: "..." })
// Recovery: effect.pipe(Effect.catchTag("MyError", (e) => ...))
```

### Effect.fn (named, traced)

```typescript
const processUser = Effect.fn("processUser")(function* (userId: string) {
  const user = yield* getUser(userId);
  return yield* transform(user);
});
```

### Test with @effect/vitest

```typescript
import { it } from "@effect/vitest";

it.effect("description", () =>
  Effect.gen(function* () {
    const result = yield* myEffect;
    expect(result).toBe(expected);
  }).pipe(Effect.provide(MyService.testLayer)),
);
```

## Key Decisions

- **Service vs plain function**: Use a service when you need DI, shared state,
  or testable boundaries; plain `Effect.fn` otherwise.
- **`Layer.effect` vs `Layer.sync`**: Use `Layer.effect` when initialization
  requires effects (DB connect, config read); `Layer.sync` for pure in-memory
  setup.
- **`Schema.TaggedError` vs `Effect.orDie`**: Typed errors for recoverable
  domain failures; `orDie` for invariant violations (bugs).
- **Per-test vs suite-shared layers**: Default to per-test (clean state); use
  `it.layer` only for expensive resources.

---
title: LogUp Protocol Patterns
impact: CRITICAL
tags: logup, lookup, relations, interaction
---

# LogUp Protocol Patterns

**Impact: CRITICAL**

LogUp is the lookup argument protocol used in Stwo for verifying that values
appear in lookup tables.

## Core Concept

LogUp transforms table lookups into a fraction sum that must equal zero:

```
For each lookup of value v in table T:
  Sum of (1 / (alpha - v)) over all uses = Sum of (1 / (alpha - v)) over table entries
```

Where `alpha` is a random challenge from the verifier.

## Relation Types

### Main Relations (Dynamic)

Lookups between trace columns that vary per execution:

```rust
relations! {
    relations {
        // Memory access: any component can read/write memory
        memory_access: addr_space, addr, clk, limb_0, limb_1, limb_2, limb_3;

        // Program ROM: fetch instruction at address
        program_access: addr, value_0, value_1, value_2, value_3;

        // Register file: read/write registers
        register_access: addr, clk, limb_0, limb_1, limb_2, limb_3;
    }
}
```

### Preprocessed Relations (Static)

Constant lookup tables generated before proving:

```rust
relations! {
    preprocessed {
        // Range check: value in [0, 2^20)
        range_check_20: value;

        // Bitwise ops: a op b = result
        bitwise: a, b, result, op_id;

        // Byte range: value in [0, 256)
        range_check_8: value;
    }
}
```

## Emit vs Consume

### Emit (Positive Multiplicity)

Component **produces** a value for the relation:

```rust
// Memory component emits all valid memory entries
add_to_relation!(eval, self.relations.memory_access,
    E::F::one(),  // Positive = emit
    cols.addr_space,
    cols.addr,
    cols.clk,
    cols.limb_0,
    cols.limb_1,
    cols.limb_2,
    cols.limb_3
);
```

### Consume (Negative Multiplicity)

Component **reads** a value from the relation:

```rust
// ALU component consumes (reads) from memory
add_to_relation!(eval, self.relations.memory_access,
    -cols.enabler.clone(),  // Negative = consume
    cols.rs1_addr_space,
    cols.rs1_addr,
    cols.rs1_clk,
    cols.rs1_limb_0,
    cols.rs1_limb_1,
    cols.rs1_limb_2,
    cols.rs1_limb_3
);
```

## Balance Requirement

**The sum of all multiplicities for each relation must be zero.**

```rust
// Example: Register reads and writes must balance
//
// Register file emits all entries:
//   Sum: +N (one per valid register state)
//
// Opcodes consume for reads:
//   Sum: -R (one per register read)
//
// Opcodes emit for writes:
//   Sum: +W (one per register write)
//
// Balance: N - R + W = 0
// This means: entries = reads - writes (net consumption)
```

### Debugging Imbalance

```rust
let (_, claimed_sum) = gen_interaction_trace(trace, relations);
if !claimed_sum.is_zero() {
    // Imbalance detected!
    // claimed_sum shows the net imbalance

    // Debug steps:
    // 1. Count emits and consumes per component
    // 2. Check conditional emits have matching consumes
    // 3. Verify multiplicity computation matches AIR
}
```

## Interaction Trace Generation

### Pattern 1: Simple Emit

```rust
// Unconditional emit (e.g., memory component)
let denom = combine!(relations.memory_access,
    [&cols.addr_space, &cols.addr, &cols.clk,
     &cols.l0, &cols.l1, &cols.l2, &cols.l3]);

// emit_col! adds +1/denom to the running sum
emit_col!(denom, logup_gen);
```

### Pattern 2: Conditional Emit

```rust
// Emit only when enabled
let denom = combine!(relations.memory_access,
    [&cols.addr_space, &cols.addr, &cols.clk, &cols.l0, ...]);

// Use write_col! for custom numerator
write_col!([&enabler], [denom], logup_gen);  // enabler/denom
```

### Pattern 3: Consume (Negative)

```rust
// Consume uses negative numerator
let denom = combine!(relations.register_access,
    [&cols.rd_addr, &cols.rd_clk, &cols.rd_l0, ...]);

// Negate enabler for consumption
let neg_enabler: Vec<PackedM31> = enabler.iter()
    .map(|e| -*e)
    .collect();

write_col!([&neg_enabler], [denom], logup_gen);
```

### Pattern 4: Multiple Relations

```rust
// Component uses multiple relations
pub fn gen_interaction_trace(trace, relations) -> (..., QM31) {
    let mut logup_gen = LogupTraceGenerator::new(log_size);

    // Relation 1: Program fetch
    let prog_denom = combine!(relations.program_access, [...]);
    emit_col!(prog_denom, logup_gen);

    // Relation 2: RS1 register read
    let rs1_denom = combine!(relations.register_access, [...]);
    consume_col!(rs1_denom, logup_gen);

    // Relation 3: RS2 register read
    let rs2_denom = combine!(relations.register_access, [...]);
    consume_col!(rs2_denom, logup_gen);

    // Relation 4: RD register write
    let rd_denom = combine!(relations.register_access, [...]);
    emit_col!(rd_denom, logup_gen);

    logup_gen.finalize()
}
```

## Preprocessed Table Multiplicities

For preprocessed (constant) tables, track how many times each entry is used:

```rust
// In multiplicities registration
pub fn register_multiplicities(
    counters: &mut Counters,
    trace: &ComponentTrace,
) {
    for i in 0..trace.len() {
        // Only count when row is active
        if trace.enabler[i] != PackedM31::zero() {
            // Increment counter for this lookup value
            counters.range_check_20.increment(
                trace.carry[i].to_array()
            );
        }
    }
}

// The preprocessed table generator uses these counts
// to emit the correct number of each entry
```

## Common LogUp Errors

### Error: Claimed sum not zero

**Cause:** Emit/consume imbalance **Debug:**

1. Add logging to count emits and consumes
2. Check conditional logic matches between AIR and witness
3. Verify all components using the relation

### Error: Wrong relation field order

**Cause:** Fields in `add_to_relation!` don't match `combine!` **Fix:** Ensure
identical field order everywhere

### Error: Missing relation in component

**Cause:** Forgot to add LogUp for a lookup **Fix:** Every table access needs
corresponding `add_to_relation!`

### Error: Double counting

**Cause:** Same lookup added twice **Fix:** Check for duplicate
`add_to_relation!` calls

---
title: Stwo Macros Reference
impact: HIGH
tags: macros, logup, relations, components
---

# Stwo Macros Reference

**Impact: HIGH**

The stwo-macros crate provides proc-macros that generate boilerplate code for
components, relations, and trace tables.

## LogUp Macros

### combine!

Combines columns into a `PackedQM31` denominator via relation's
`LookupElements`:

```rust
// Basic usage - combine columns for a relation
let denom = combine!(relations.memory_access,
    [&cols.addr_space, &cols.addr, &cols.clk, &cols.l0, &cols.l1, &cols.l2, &cols.l3]);

// The denominator is used for LogUp fractions: numerator / denom
```

**Field order MUST match** the relation definition in `relations.rs`:

```rust
// In relations.rs:
relations! {
    relations {
        memory_access: addr_space, addr, clk, limb_0, limb_1, limb_2, limb_3;
    }
}

// In witness.rs - SAME order:
let denom = combine!(relations.memory_access,
    [&cols.addr_space, &cols.addr, &cols.clk, &cols.l0, &cols.l1, &cols.l2, &cols.l3]);
```

### emit_col! / consume_col!

Write ±1/denom fractions to interaction trace:

```rust
// emit_col! adds +1/denom (component produces value)
emit_col!(&denom, interaction_trace);

// consume_col! adds -1/denom (component reads value)
consume_col!(&denom, interaction_trace);
```

### write_col!

Write arbitrary numerator/denom fraction:

```rust
// Custom numerator (e.g., conditional emit based on enabler)
let enabler: Vec<PackedM31> = /* ... */;
write_col!(&enabler, &denom, interaction_trace);

// Negative numerator for conditional consume
let neg_enabler: Vec<PackedM31> = enabler.iter().map(|e| -*e).collect();
write_col!(&neg_enabler, &denom, interaction_trace);
```

### write_pair!

**RECOMMENDED** - Combine two fractions into one column for efficiency:

```rust
// Combines (n0/d0 + n1/d1) into single column
// More efficient than two separate write_col! calls
write_pair!(&neg_enabler, &denom0, &pos_enabler, &denom1, interaction_trace);

// Use when you have two related lookups that can be combined
// Example: Read from rs1 (consume) and write to rd (emit)
write_pair!(
    &neg_rs1_enabler, &rs1_denom,  // consume rs1
    &pos_rd_enabler, &rd_denom,    // emit rd
    interaction_trace
);
```

### add_to_relation!

Add LogUp constraint in AIR evaluation:

```rust
fn evaluate<E: EvalAtRow>(&self, mut eval: E) -> E {
    // Positive multiplicity = emit (produce value)
    add_to_relation!(eval, self.relations.program_access,
        cols.enabler.clone(),  // positive
        cols.pc.clone(),
        opcode_id,
        cols.rd_addr.clone(),
        cols.rs1_addr.clone()
    );

    // Negative multiplicity = consume (read value)
    add_to_relation!(eval, self.relations.memory_access,
        -cols.enabler.clone(),  // negative
        cols.addr_space.clone(),
        cols.addr.clone(),
        cols.clk.clone(),
        cols.l0.clone(), cols.l1.clone(), cols.l2.clone(), cols.l3.clone()
    );

    eval.finalize_logup_in_pairs();
    eval
}
```

## relations! Macro

Defines lookup relations and generates associated types:

```rust
relations! {
    relations {
        // Dynamic relations (vary per execution)
        memory_access: addr_space, addr, clk, limb_0, limb_1, limb_2, limb_3;
        program_access: addr, value_0, value_1, value_2, value_3;
        registers_state: pc, clk;
        merkle: index, depth, value, root;
        poseidon2: state0, state1, /* ... */, state15;
    }
    preprocessed {
        // Static relations (constant tables)
        bitwise: a, b, result, op_id;
        range_check_20: value;
        range_check_8_8: limb_0, limb_1;
        range_check_m31: lsl, msl;
    }
}
```

**Generates:**

- `Relations` struct with one field per relation
- Wrapper types implementing `Relation<F, EF>` trait
- `Counter<T>` types for multiplicity tracking
- `Counters` struct aggregating all counters
- `PreProcessedTrace` struct for constant tables

## opcode_components! Macro

Generates boilerplate for opcode component families:

```rust
opcode_components! {
    base_alu_reg: add, sub, xor, or, and, sll, srl, sra, slt, sltu;
    base_alu_imm: addi, xori, ori, andi, slti, sltiu;
    // ... other families
}
```

**Generates per family:**

- `Traces` struct with trace columns
- `Claim` struct with log_size per component
- `ClaimedSum` struct with QM31 per component
- `Components` struct with FrameworkComponent instances
- `gen_trace()` function
- `gen_interaction_trace()` function

## define_trace_tables! Macro (Runner)

Generates trace table structures in the runner:

```rust
define_trace_tables! {
    base_alu_reg: {
        clk, pc, rd, rs1, rs2,
        rd_limb_0, rd_limb_1, rd_limb_2, rd_limb_3,
        rs1_limb_0, rs1_limb_1, rs1_limb_2, rs1_limb_3,
        rs2_limb_0, rs2_limb_1, rs2_limb_2, rs2_limb_3,
        opcode_add_flag, opcode_sub_flag, opcode_xor_flag,
        // ... other columns
    },
}
```

**Generates:**

- Per-opcode `Table` structs with typed columns
- `Tracer` struct containing all tables
- `trace_op!` macro for recording execution

**Usage in runner:**

```rust
trace_op!(base_alu_reg: tracer, {
    clk: step.clk,
    pc: step.pc,
    rd: result.rd,
    rs1: step.rs1,
    rs2: step.rs2,
    // ... other values
});
```

## Common Macro Errors

### Error: Field order mismatch

```rust
// relations.rs defines:
memory_access: addr_space, addr, clk, l0, l1, l2, l3;

// WRONG - different order in combine!
let denom = combine!(relations.memory_access,
    [&cols.addr, &cols.addr_space, &cols.clk, ...]);  // addr before addr_space!

// CORRECT - same order
let denom = combine!(relations.memory_access,
    [&cols.addr_space, &cols.addr, &cols.clk, ...]);
```

### Error: Missing field in add_to_relation!

```rust
// WRONG - missing limb_3
add_to_relation!(eval, self.relations.memory_access,
    -enabler,
    cols.addr_space, cols.addr, cols.clk,
    cols.l0, cols.l1, cols.l2  // Missing l3!
);

// CORRECT - all fields present
add_to_relation!(eval, self.relations.memory_access,
    -enabler,
    cols.addr_space, cols.addr, cols.clk,
    cols.l0, cols.l1, cols.l2, cols.l3
);
```

### Error: Forgetting finalize_logup_in_pairs()

```rust
// WRONG
fn evaluate<E: EvalAtRow>(&self, mut eval: E) -> E {
    add_to_relation!(eval, ...);
    eval  // Missing finalize!
}

// CORRECT
fn evaluate<E: EvalAtRow>(&self, mut eval: E) -> E {
    add_to_relation!(eval, ...);
    eval.finalize_logup_in_pairs();
    eval
}
```

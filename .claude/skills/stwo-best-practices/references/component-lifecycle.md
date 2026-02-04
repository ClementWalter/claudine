---
title: Component Lifecycle
impact: CRITICAL
tags: component, air, witness, trace
---

# Component Lifecycle

**Impact: CRITICAL**

Understanding the complete lifecycle of a Stwo component from trace generation
to proof verification.

## Lifecycle Phases

### Phase 1: Execution (Runner)

The runner executes the program and collects raw trace data:

```rust
// In runner/src/trace.rs
define_trace_tables! {
    base_alu_reg: {
        clk, pc, rd, rs1, rs2,
        opcode_add_flag, opcode_sub_flag, opcode_xor_flag,
        // ... other columns
    },
}

// During execution
trace_op!(base_alu_reg: tracer, {
    clk: step.clk,
    pc: step.pc,
    rd: step.rd,
    rs1: step.rs1,
    // ...
});
```

### Phase 2: Witness Generation (Main Trace)

Convert raw trace to columnar format:

```rust
// In prover/src/components/opcodes/base_alu_reg/columns.rs
impl ComponentColumns {
    pub fn from_table(table: &ComponentTable) -> Vec<CircleEvaluation<...>> {
        // Pad to power of 2
        // Convert to column format
        // Return circle evaluations
    }
}
```

### Phase 3: Interaction Trace (LogUp)

Generate LogUp fractions for lookups:

```rust
// In prover/src/components/opcodes/base_alu_reg/witness.rs
pub fn gen_interaction_trace(
    trace: &[CircleEvaluation<...>],
    relations: &Relations,
) -> (ColumnVec<CircleEvaluation<...>>, QM31) {
    let cols = ComponentColumns::from_iter(trace);
    let mut logup_gen = LogupTraceGenerator::new(log_size);

    // Compute denominators for each relation
    let program_denom = combine!(relations.program_access,
        [&cols.pc, &opcode_id, &cols.rd_addr, ...]);
    emit_col!(program_denom, logup_gen);

    logup_gen.finalize()
}
```

### Phase 4: Commitment

Commit to traces via Merkle tree:

```rust
// In prover/src/prover.rs
let commitment_scheme = CommitmentSchemeProver::new(config);

// Commit main trace
commitment_scheme.commit(main_trace_columns);

// Commit interaction trace
commitment_scheme.commit(interaction_trace_columns);
```

### Phase 5: AIR Evaluation

Evaluate constraints at random point:

```rust
// In prover/src/components/opcodes/base_alu_reg/air.rs
impl FrameworkEval for Eval {
    fn evaluate<E: EvalAtRow>(&self, mut eval: E) -> E {
        let cols = ComponentColumns::from_eval(&mut eval);

        // Add polynomial constraints
        eval.add_constraint(constraint_expr);

        // Add LogUp relations
        add_to_relation!(eval, self.relations.memory_access, ...);

        eval
    }
}
```

### Phase 6: Proof Generation

Generate FRI proof of constraint satisfaction:

```rust
// In prover/src/prover.rs
let proof = stwo::prover::prove(
    &components,
    &channel,
    &commitment_scheme,
)?;
```

### Phase 7: Verification

Verify proof without re-execution:

```rust
// In prover/src/verifier.rs
stwo::prover::verify(
    &components,
    &channel,
    &commitment_scheme_verifier,
    proof,
)?;
```

## Critical Synchronization Points

### 1. Column Order

Columns must appear in identical order everywhere:

```rust
// define_trace_tables! (runner)
base_alu_reg: { clk, pc, rd, rs1, rs2, ... }

// ComponentColumns::from_eval (prover AIR)
let clk = eval.next_trace_mask();
let pc = eval.next_trace_mask();
let rd = eval.next_trace_mask();
// Same order!

// ComponentColumns::from_iter (prover witness)
// Same order!
```

### 2. Derived Column Computation

Any computed value must be identical in AIR and witness:

```rust
// AIR (air.rs)
let rs1_value = cols.rs1_limb_0.clone()
    + cols.rs1_limb_1.clone() * shift_8
    + cols.rs1_limb_2.clone() * shift_16
    + cols.rs1_limb_3.clone() * shift_24;

// Witness (witness.rs)
let rs1_value: Vec<PackedM31> = (0..simd_size).map(|i| {
    cols.rs1_limb_0[i]
        + cols.rs1_limb_1[i] * PackedM31::broadcast(shift_8)
        + cols.rs1_limb_2[i] * PackedM31::broadcast(shift_16)
        + cols.rs1_limb_3[i] * PackedM31::broadcast(shift_24)
}).collect();
```

### 3. Relation Field Order

Fields in `add_to_relation!` must match `combine!`:

```rust
// relations.rs
relations! {
    relations {
        memory_access: addr_space, addr, clk, l0, l1, l2, l3;
    }
}

// air.rs - must match field order
add_to_relation!(eval, self.relations.memory_access,
    -enabler,
    cols.addr_space,  // 1st field
    cols.addr,        // 2nd field
    cols.clk,         // 3rd field
    cols.l0,          // 4th field
    cols.l1,          // 5th field
    cols.l2,          // 6th field
    cols.l3           // 7th field
);

// witness.rs - must match field order
let denom = combine!(relations.memory_access,
    [&cols.addr_space, &cols.addr, &cols.clk, &cols.l0, &cols.l1, &cols.l2, &cols.l3]
);
```

## Common Lifecycle Errors

### Error: "Constraint degree too high"

```
Cause: Polynomial degree exceeds log_size + 1
Fix: Simplify constraints or add intermediate columns
```

### Error: "Claimed sum is not zero"

```
Cause: LogUp lookups don't balance
Fix: Check every emit has corresponding consume
     Check multiplicities match between AIR and witness
```

### Error: "Column count mismatch"

```
Cause: Different number of columns in trace vs AIR
Fix: Ensure column extraction matches trace generation
```

### Error: "Invalid proof"

```
Cause: Many possible causes
Debug steps:
1. Check claimed_sum == 0 for all relations
2. Verify column order consistency
3. Check derived column computation matches
4. Ensure all constraints use proper field arithmetic
```

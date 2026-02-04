---
title: Debugging Stwo Proofs
impact: HIGH
tags: debugging, errors, troubleshooting
---

# Debugging Stwo Proofs

**Impact: HIGH**

Guide to diagnosing and fixing common Stwo proof failures.

## Error Categories

### 1. Constraint Violations

**Symptom:** Proof verification fails with constraint error

**Causes:**

- Polynomial constraint not satisfied
- Wrong column values in trace
- Incorrect derived variable computation

**Debug Steps:**

```rust
// Add trace logging in witness generation
#[cfg(debug_assertions)]
fn debug_trace_row(i: usize, cols: &ComponentColumns) {
    eprintln!("Row {}: clk={}, pc={}, enabler={}",
        i, cols.clk[i], cols.pc[i], cols.enabler[i]);
}

// Check specific constraint values
let constraint_val = cols.a[i] - cols.b[i];
if constraint_val != BaseField::zero() {
    eprintln!("Constraint violation at row {}: {} != 0", i, constraint_val);
}
```

### 2. LogUp Imbalance

**Symptom:** `claimed_sum` is not zero

**Causes:**

- Unbalanced emit/consume
- Missing relation in component
- Wrong multiplicity value
- Different logic between AIR and witness

**Debug Steps:**

```rust
// Track per-component contributions
let (interaction_trace, claimed_sum) = gen_interaction_trace(trace, relations);
eprintln!("Component {} claimed_sum: {:?}", name, claimed_sum);

// Count emits and consumes
let mut emit_count = 0;
let mut consume_count = 0;
for i in 0..trace_len {
    if enabler[i] != PackedM31::zero() {
        emit_count += 1;  // or consume_count
    }
}
eprintln!("Emits: {}, Consumes: {}", emit_count, consume_count);
```

### 3. Degree Bound Exceeded

**Symptom:** Runtime error about constraint degree

**Causes:**

- Too many multiplications in single constraint
- Forgot degree bound is `log_size + 1`

**Fix:**

```rust
// WRONG: Degree 4 constraint
eval.add_constraint(a * b * c * d);

// CORRECT: Split into intermediate constraints
// Add auxiliary column for a * b
eval.add_constraint(cols.ab.clone() - cols.a.clone() * cols.b.clone());
// Now use ab * c * d has degree 3
eval.add_constraint(cols.ab.clone() * cols.c.clone() * cols.d.clone());
```

### 4. Column Count Mismatch

**Symptom:** Panic about wrong number of columns

**Causes:**

- define_trace_tables doesn't match columns struct
- Missing column in from_eval
- Different column count between runner and prover

**Debug Steps:**

```rust
// Count columns
eprintln!("Main trace columns: {}", main_trace.len());
eprintln!("Expected columns: {}", ComponentColumns::NUM_COLUMNS);

// Check column indices
let cols = ComponentColumns::from_eval(&mut eval);
eprintln!("Column 0: {:?}", cols.clk);
```

## Systematic Debugging Process

### Step 1: Isolate the Component

```rust
// Test single component in isolation
#[test]
fn test_component_isolation() {
    let table = create_minimal_test_table();
    let trace = table.into_witness();

    // Check main trace is valid
    assert_eq!(trace.len(), EXPECTED_COLUMNS);

    // Check interaction trace
    let relations = Relations::dummy();
    let (_, claimed_sum) = gen_interaction_trace(&trace, &relations);
    assert!(claimed_sum.is_zero(), "LogUp imbalance: {:?}", claimed_sum);
}
```

### Step 2: Check Column Values

```rust
// Dump trace for inspection
fn dump_trace(trace: &[CircleEvaluation<...>]) {
    let cols = ComponentColumns::from_iter(trace.iter());
    for i in 0..min(10, cols.len()) {
        eprintln!("Row {}: clk={} pc={} rd={} rs1={} rs2={}",
            i, cols.clk[i], cols.pc[i],
            cols.rd[i], cols.rs1[i], cols.rs2[i]);
    }
}
```

### Step 3: Verify Constraints Manually

```rust
// Check each constraint at specific row
fn verify_constraints_manual(cols: &ComponentColumns, row: usize) {
    let enabler = cols.enabler[row];
    if enabler == M31::zero() {
        return;  // Constraint disabled
    }

    // Constraint 1: rd = rs1 + rs2
    let expected_rd = cols.rs1[row] + cols.rs2[row];
    assert_eq!(cols.rd[row], expected_rd,
        "Row {}: rd mismatch", row);

    // Continue for all constraints...
}
```

### Step 4: Compare AIR vs Witness

```rust
// Ensure derived columns match
fn compare_air_witness(
    air_cols: &AirColumns,
    witness_cols: &WitnessColumns,
) {
    for i in 0..air_cols.len() {
        // Check derived value computation matches
        let air_enabler = air_cols.flag1[i] + air_cols.flag2[i];
        let witness_enabler = witness_cols.enabler[i];
        assert_eq!(air_enabler, witness_enabler,
            "Row {}: enabler mismatch", i);
    }
}
```

## Common Fixes

### Fix: Missing Boolean Constraint

```rust
// Before (bug):
let selector = cols.flag;
eval.add_constraint(selector.clone() * constraint);

// After (fixed):
let selector = cols.flag.clone();
// Add boolean constraint!
eval.add_constraint(selector.clone() * (E::F::one() - selector.clone()));
eval.add_constraint(selector.clone() * constraint);
```

### Fix: Field Conversion

```rust
// Before (bug):
let constant = 256u32;  // Can't use in constraint!
eval.add_constraint(cols.value - constant);

// After (fixed):
let constant = E::F::from(BaseField::from_u32_unchecked(256));
eval.add_constraint(cols.value.clone() - constant);
```

### Fix: Clone Missing

```rust
// Before (bug):
eval.add_constraint(cols.a * cols.b);
eval.add_constraint(cols.a * cols.c);  // Error: a already moved!

// After (fixed):
eval.add_constraint(cols.a.clone() * cols.b.clone());
eval.add_constraint(cols.a.clone() * cols.c.clone());
```

### Fix: Relation Field Order

```rust
// Before (bug): Different field order
// air.rs:
add_to_relation!(eval, rel, mult, cols.a, cols.b, cols.c);
// witness.rs:
combine!(rel, [&cols.a, &cols.c, &cols.b]);  // Wrong order!

// After (fixed): Same field order
// air.rs:
add_to_relation!(eval, rel, mult, cols.a, cols.b, cols.c);
// witness.rs:
combine!(rel, [&cols.a, &cols.b, &cols.c]);  // Same order
```

## Test Helpers

```rust
// Create minimal valid trace for testing
fn create_test_trace() -> ComponentTable {
    let mut table = ComponentTable::new();

    // Add minimal valid row
    table.add_row(TestRow {
        clk: 0,
        pc: 0x1000,
        enabler: 1,
        // ... minimal valid values
    });

    table
}

// Assert claimed_sum is zero with helpful message
fn assert_logup_balanced(claimed_sum: QM31, component: &str) {
    assert!(
        claimed_sum.is_zero(),
        "LogUp imbalance in {}: {:?}\n\
         This usually means emit/consume don't match.\n\
         Check:\n\
         1. Every lookup has matching emit and consume\n\
         2. Multiplicity computation matches between AIR and witness\n\
         3. Conditional logic is identical in both places",
        component,
        claimed_sum
    );
}
```

## Logging Configuration

```rust
// Enable trace logging
RUST_LOG=stark_v_prover=debug cargo test

// Log specific component
RUST_LOG=stark_v_prover::components::opcodes::base_alu_reg=trace cargo test
```

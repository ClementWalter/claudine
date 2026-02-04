---
name: stwo-best-practices
description:
  Best practices for Stwo Circle STARK prover development. Use when writing AIR
  components, LogUp relations, witness generation, or constraint systems.
---

# Stwo Best Practices

Guidelines for developing with the Stwo Circle STARK framework - components,
constraints, LogUp relations, and witness generation.

## Quick Reference

| Category       | DO                                             | DON'T                                        |
| -------------- | ---------------------------------------------- | -------------------------------------------- |
| Components     | Sync AIR, witness, and columns exactly         | Mismatch column definitions between files    |
| Constraints    | `eval.add_constraint(expr)` with proper degree | Exceed `3` degree bound                      |
| Field Elements | `E::F::from(BaseField::from_u32_unchecked(v))` | Use raw `u32` in constraint expressions      |
| Enablers       | Constrain `enabler * (1 - enabler) = 0`        | Assume enabler is boolean without constraint |
| LogUp          | Balance emit/consume for every relation        | Emit without corresponding consume           |
| Derived Cols   | Compute identically in AIR and witness         | Different derivation logic between files     |
| Relations      | Use `add_to_relation!` macro                   | Manual relation arithmetic                   |
| Finalize       | Call `eval.finalize_logup_in_pairs()` at end   | Forget to finalize LogUp                     |
| Empty Trace    | Return `(vec![], QM31::zero())` for empty      | Access columns on empty trace                |
| Multiplicities | Same numerator sign in AIR and witness         | `-enabler` in AIR but `+enabler` in witness  |
| Testing        | E2E + component-level + interaction trace      | Only test happy path                         |

## When to Apply

- Writing new AIR components for opcodes or subsystems
- Implementing LogUp lookup relations
- Generating witness/interaction traces
- Defining constraint polynomials
- Working with preprocessed tables
- Debugging proof verification failures

## Core Principles

1. **Component Consistency** **(CRITICAL)** - AIR evaluation, witness
   generation, and column definitions must be perfectly synchronized
2. **LogUp Balance** **(CRITICAL)** - Every lookup emit must have a
   corresponding consume with matching weight
3. **Constraint Degree** **(HIGH)** - Never exceed polynomial degree `3`
4. **Field Arithmetic** **(HIGH)** - Always use proper `BaseField`/`QM31`
   conversions
5. **Documentation** **(MEDIUM)** - Reference `airs.md` sections and explain
   constraint purpose

---

## Component Structure

### File Organization

Every component follows this structure:

```
components/{component_name}/
├── mod.rs      # Module exports, type alias
├── columns.rs  # Column struct
├── air.rs      # FrameworkEval implementation
├── witness.rs  # Interaction trace generation
└── tests.rs    # Unit and E2E tests
```

### Type Alias Pattern

```rust
// CORRECT - Standard component type alias
pub type Component = FrameworkComponent<Eval>;

// Use in prover setup:
let component: Component = Component::new(
    tree_span_provider,
    Eval { log_size, relations },
    (interaction_claim.claimed_sum, None),
);
```

### Eval Struct Pattern

```rust
// CORRECT - Eval struct with required fields
#[derive(Clone)]
pub struct Eval {
    pub log_size: u32,
    pub relations: Relations,
}

impl FrameworkEval for Eval {
    fn log_size(&self) -> u32 {
        self.log_size
    }

    fn max_constraint_log_degree_bound(&self) -> u32 {
        self.log_size + 1  // Never exceed this!
    }

    fn evaluate<E: EvalAtRow>(&self, mut eval: E) -> E {
        // Constraint logic here
        eval
    }
}
```

---

## LogUp Macros

The codebase uses five core macros for LogUp operations:

### combine! - Create Denominators

```rust
// Combine columns into denominator via relation's lookup elements
let denom = combine!(relations.memory_access,
    [&cols.addr_space, &cols.addr, &cols.clk, &cols.l0, &cols.l1, &cols.l2, &cols.l3]);
```

### emit_col! / consume_col! - Simple Fractions

```rust
// Emit: +1/denom (component produces value)
emit_col!(&denom, interaction_trace);

// Consume: -1/denom (component reads value)
consume_col!(&denom, interaction_trace);
```

### write_col! - Custom Numerator

```rust
// Write arbitrary numerator/denom fraction
write_col!(&numerator, &denom, interaction_trace);
```

### write_pair! - Combine Two Fractions **(RECOMMENDED)**

```rust
// Combine two fractions into one column: (n0/d0 + n1/d1)
// More efficient than two separate write_col! calls
write_pair!(&neg_enabler, &denom0, &pos_enabler, &denom1, interaction_trace);
```

### add_to_relation! - AIR Constraint

```rust
// Add LogUp constraint in AIR evaluation
add_to_relation!(eval, self.relations.memory_access,
    -enabler.clone(),  // multiplicity (negative = consume)
    cols.addr.clone(),
    cols.clk.clone(),
    cols.l0.clone(), cols.l1.clone(), cols.l2.clone(), cols.l3.clone()
);
```

---

## Constraint Development

### Column Extraction

```rust
// CORRECT - Extract columns from evaluator
fn evaluate<E: EvalAtRow>(&self, mut eval: E) -> E {
    let cols = ComponentColumns::from_eval(&mut eval);
    // Use cols.field_name...
}

// WRONG - Manual column indexing
fn evaluate<E: EvalAtRow>(&self, mut eval: E) -> E {
    let col0 = eval.next_trace_mask();  // Error-prone
}
```

### Field Element Conversion

```rust
// CORRECT - Proper field conversion
let opcode_id = E::F::from(BaseField::from_u32_unchecked(OPCODE_ADD));
let one = E::F::one();
let zero = E::F::zero();

// WRONG - Raw integer in expression
let opcode_id = 0x33u32;  // Cannot use in constraints!
eval.add_constraint(cols.opcode - 0x33);  // Type error
```

### Boolean Enabler Pattern **(CRITICAL)**

```rust
// CORRECT - Always constrain enablers to be boolean
let enabler = cols.flag1.clone() + cols.flag2.clone();
eval.add_constraint(enabler.clone() * (E::F::one() - enabler.clone()));

// WRONG - Assuming enabler is boolean without constraint
let enabler = cols.flag1.clone() + cols.flag2.clone();
// Missing: boolean constraint!
// Prover could cheat with non-binary values
```

### Carry Propagation Pattern **(CRITICAL)**

For multi-limb arithmetic (32-bit values split into 4x8-bit limbs):

```rust
// CORRECT - Full carry chain for 4-limb addition
let inv_two_pow_8 = BaseField::from_u32_unchecked(1 << 8).inverse();
let inv_shift = E::F::from(inv_two_pow_8);

let mut carry: [E::F; 4] = std::array::from_fn(|_| E::F::zero());

// First limb carry
carry[0] = (rs1[0].clone() + rs2[0].clone() - rd[0].clone()) * inv_shift.clone();

// Propagate carry through remaining limbs
for i in 1..4 {
    carry[i] = (rs1[i].clone() + rs2[i].clone() + carry[i - 1].clone()
                - rd[i].clone()) * inv_shift.clone();
}

// Verify all carries are binary (0 or 1)
for c in carry {
    eval.add_constraint(opcode_flag.clone() * c.clone() * (E::F::one() - c));
}

// WRONG - Only checking first limb
let carry = (rs1[0].clone() + rs2[0].clone() - rd[0].clone()) * inv_shift;
eval.add_constraint(flag.clone() * carry * (E::F::one() - carry));
// Missing carry propagation to other limbs!
```

### Derived Variables

```rust
// CORRECT - Clear derivation with comments
// Section 3.2: Compute 32-bit value from 8-bit limbs
let value = cols.limb_0.clone()
    + cols.limb_1.clone() * E::F::from(BaseField::from_u32_unchecked(1 << 8))
    + cols.limb_2.clone() * E::F::from(BaseField::from_u32_unchecked(1 << 16))
    + cols.limb_3.clone() * E::F::from(BaseField::from_u32_unchecked(1 << 24));

// Document the constraint purpose
eval.add_constraint(enabler.clone() * (computed_value - expected_value));
```

---

## LogUp Relations

### Relation Definition

```rust
// In relations.rs using relations! macro
relations! {
    relations {
        // Main relations (dynamic lookups)
        program_access: addr, value_0, value_1, value_2, value_3;
        memory_access: addr_space, addr, clk, limb_0, limb_1, limb_2, limb_3;
        register_access: addr, clk, limb_0, limb_1, limb_2, limb_3;
    }
    preprocessed {
        // Preprocessed relations (constant tables)
        range_check_20: value;
        bitwise: a, b, result, op_id;
    }
}
```

### Adding to Relations in AIR **(CRITICAL)**

```rust
// CORRECT - Emit (positive multiplicity) - component produces values
add_to_relation!(eval, self.relations.program_access,
    cols.enabler.clone(),  // Positive = emit
    cols.pc.clone(),
    opcode_id,
    cols.rd_addr.clone(),
    cols.rs1_addr.clone()
);

// CORRECT - Consume (negative multiplicity) - component reads values
add_to_relation!(eval, self.relations.memory_access,
    -cols.enabler.clone(),  // Negative = consume
    cols.addr.clone(),
    cols.clk.clone(),
    cols.limb_0.clone(),
    cols.limb_1.clone()
);

// WRONG - Missing multiplicity
add_to_relation!(eval, self.relations.memory_access,
    cols.addr.clone(),  // No multiplicity - won't compile
    cols.clk.clone()
);
```

### LogUp Balance Rule **(CRITICAL)**

Every relation must balance: total emits = total consumes.

```rust
// Example: Memory component emits what opcodes consume
// In memory/air.rs:
add_to_relation!(eval, self.relations.memory_access,
    E::F::one(),  // Always emit (memory produces all accesses)
    ...);

// In base_alu_reg/air.rs:
add_to_relation!(eval, self.relations.memory_access,
    -cols.enabler.clone(),  // Consume when enabled
    ...);

// If claimed_sum != 0 at end of proof, lookups don't balance!
```

---

## Witness Generation

### Empty Trace Guard **(CRITICAL)**

Every `gen_interaction_trace` must handle empty traces:

```rust
pub fn gen_interaction_trace(
    trace: &[CircleEvaluation<SimdBackend, BaseField, BitReversedOrder>],
    relations: &Relations,
) -> (ColumnVec<CircleEvaluation<...>>, QM31) {
    // CRITICAL: Always check for empty trace first!
    if trace.is_empty() {
        return (vec![], QM31::zero());
    }

    // Safe to proceed with column extraction
    let cols = ComponentColumns::from_iter(trace.iter()...);
    // ...
}

// WRONG - Will panic on empty trace
pub fn gen_interaction_trace(trace: &[...], ...) -> ... {
    let cols = ComponentColumns::from_iter(trace.iter()...);  // PANIC!
    // ...
}
```

### Interaction Trace Pattern

```rust
pub fn gen_interaction_trace(
    trace: &[CircleEvaluation<SimdBackend, BaseField, BitReversedOrder>],
    relations: &Relations,
) -> (ColumnVec<CircleEvaluation<...>>, QM31) {
    // 1. Guard against empty trace
    if trace.is_empty() {
        return (vec![], QM31::zero());
    }

    // 2. Extract columns (MUST match AIR exactly)
    let cols = ComponentColumns::from_iter(trace.iter().map(|eval| &eval.values.data));
    let log_size = trace[0].domain.log_size();
    let simd_size = cols.clk.len();

    // 3. Create LogUp generator
    let mut interaction_trace = LogupTraceGenerator::new(log_size);

    // 4. Compute derived columns (MUST match AIR derivation)
    let enabler: Vec<PackedM31> = (0..simd_size)
        .map(|i| cols.flag1[i] + cols.flag2[i])
        .collect();

    // 5. Combine denominators and write fractions
    let denom = combine!(relations.memory_access,
        [&cols.addr, &cols.clk, &cols.limb_0, &cols.limb_1]);

    // Use write_pair! for efficiency when combining two fractions
    write_pair!(&neg_enabler, &denom0, &pos_enabler, &denom1, interaction_trace);

    // 6. Finalize and return
    interaction_trace.finalize_last()
}
```

### Column Synchronization **(CRITICAL)**

```rust
// CORRECT - Same derivation in both AIR and witness
// air.rs:
let enabler = cols.flag1.clone() + cols.flag2.clone();

// witness.rs:
let enabler: Vec<PackedM31> = (0..simd_size)
    .map(|i| cols.flag1[i] + cols.flag2[i])
    .collect();

// WRONG - Different derivation (will cause proof failure)
// air.rs:
let enabler = cols.flag1.clone() + cols.flag2.clone();

// witness.rs:
let enabler: Vec<PackedM31> = (0..simd_size)
    .map(|i| cols.flag1[i] * cols.flag2[i])  // WRONG: multiplication instead of addition!
    .collect();
```

---

## Preprocessed Tables

### Multiplicity Registration **(CRITICAL)**

Register multiplicities with the **same numerator sign** as used in
`gen_interaction_trace`:

```rust
// CORRECT - Numerator sign matches between functions
// In witness.rs gen_interaction_trace:
let neg_enabler: Vec<PackedM31> = (0..simd_size)
    .map(|i| -cols.enabler[i])
    .collect();
write_col!(&neg_enabler, &denom, interaction_trace);

// In witness.rs register_multiplicities:
pub fn register_multiplicities(
    trace: &[CircleEvaluation<...>],
    counters: &mut crate::relations::Counters,
) {
    if trace.is_empty() {
        return;
    }

    let cols = ComponentColumns::from_iter(trace.iter().map(|eval| &eval.values.data));
    let simd_size = cols.enabler.len();

    // MUST use same numerator sign as gen_interaction_trace!
    let neg_enabler: Vec<PackedM31> = (0..simd_size)
        .map(|i| -cols.enabler[i])
        .collect();

    counters.range_check_8_8.register_many(&neg_enabler, &[cols.value_0, cols.value_1]);
}

// WRONG - Different numerator sign causes LogUp imbalance
// In gen_interaction_trace:
let neg_enabler: Vec<PackedM31> = (0..simd_size).map(|i| -cols.enabler[i]).collect();

// In register_multiplicities:
let pos_enabler: Vec<PackedM31> = (0..simd_size).map(|i| cols.enabler[i]).collect();  // WRONG SIGN!
counters.range_check_8_8.register_many(&pos_enabler, ...);
```

### Preprocessed Relation Pattern

```rust
// For constant tables, use preprocessed relations
relations! {
    preprocessed {
        range_check_20: value;  // Checks value in [0, 2^20)
    }
}

// In AIR - consume from preprocessed table
add_to_relation!(eval, self.relations.range_check_20,
    -cols.enabler.clone(),
    cols.carry.clone()  // Must be in range [0, 2^20)
);
```

---

## Testing

### Component Test Pattern

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_table() {
        let table = runner::trace::ComponentTable::new();
        let trace = table.into_witness();
        assert!(!trace.is_empty());
        // Minimum size is 2^4 = 16 rows
        assert_eq!(trace.first().unwrap().domain.log_size(), 4);
    }

    #[test]
    fn test_interaction_trace() {
        let table = create_test_table();
        let trace = table.into_witness();
        let relations = Relations::dummy();

        let (interaction_trace, claimed_sum) =
            witness::gen_interaction_trace(trace.as_slice(), &relations);

        assert!(!interaction_trace.is_empty());
        // CRITICAL: claimed_sum must be zero for valid lookups
        assert!(claimed_sum.is_zero());
    }
}
```

### E2E Test Pattern

```rust
// Use test binary macro for full proving flow
crate::test_bin_e2e!(base_alu_reg, add);
crate::test_bin_e2e!(base_alu_reg, sub);
crate::test_bin_e2e!(base_alu_reg, xor);

// This compiles and runs guest binary, generates proof, verifies
```

### Test Debugging Tips

```rust
// Check claimed_sum when lookups fail
let (_, claimed_sum) = gen_interaction_trace(...);
if !claimed_sum.is_zero() {
    // Lookup imbalance! Check:
    // 1. All emits have corresponding consumes
    // 2. Multiplicities match between AIR and witness
    // 3. Derived columns computed identically
}
```

---

## AIR Finalization **(CRITICAL)**

### finalize_logup_in_pairs()

Always call `finalize_logup_in_pairs()` at the end of the `evaluate` function:

```rust
// CORRECT - Finalize after all add_to_relation! calls
fn evaluate<E: EvalAtRow>(&self, mut eval: E) -> E {
    let cols = ComponentColumns::from_eval(&mut eval);

    // Add polynomial constraints
    eval.add_constraint(enabler.clone() * (E::F::one() - enabler.clone()));

    // Add LogUp relations
    add_to_relation!(eval, self.relations.memory_access, -enabler.clone(), ...);
    add_to_relation!(eval, self.relations.program_access, enabler.clone(), ...);

    // CRITICAL: Must call after ALL add_to_relation! calls
    eval.finalize_logup_in_pairs();
    eval
}

// WRONG - Missing finalization
fn evaluate<E: EvalAtRow>(&self, mut eval: E) -> E {
    let cols = ComponentColumns::from_eval(&mut eval);
    add_to_relation!(eval, self.relations.memory_access, ...);
    eval  // Missing finalize_logup_in_pairs()!
}
```

---

## Anti-Patterns

### FORBIDDEN: Degree Violation

```rust
// FORBIDDEN - Degree too high
fn max_constraint_log_degree_bound(&self) -> u32 {
    self.log_size + 2  // WRONG: exceeds framework limit
}

// CORRECT
fn max_constraint_log_degree_bound(&self) -> u32 {
    self.log_size + 1
}
```

### FORBIDDEN: Unsynced Columns

```rust
// FORBIDDEN - Different column order in AIR vs witness
// air.rs:
add_to_relation!(eval, rel, mult, cols.a, cols.b, cols.c);

// witness.rs:
let denom = combine!(rel, [&cols.a, &cols.c, &cols.b]);  // WRONG ORDER!
```

### FORBIDDEN: Missing Boolean Constraint

```rust
// FORBIDDEN - Using unconstrained selector
let selector = cols.flag1.clone();
eval.add_constraint(selector.clone() * some_expr);  // selector could be anything!

// CORRECT - Constrain to boolean first
eval.add_constraint(selector.clone() * (E::F::one() - selector.clone()));
eval.add_constraint(selector.clone() * some_expr);
```

### FORBIDDEN: Raw Arithmetic in Constraints

```rust
// FORBIDDEN - Integer arithmetic in field expression
let shift = 1 << 8;  // u32
eval.add_constraint(cols.value - cols.limb * shift);  // Type error

// CORRECT - Field arithmetic
let shift = E::F::from(BaseField::from_u32_unchecked(1 << 8));
eval.add_constraint(cols.value.clone() - cols.limb.clone() * shift);
```

### FORBIDDEN: Forgetting Clone

```rust
// FORBIDDEN - Using expression after move
let x = cols.value.clone();
eval.add_constraint(x * something);
eval.add_constraint(x * other);  // ERROR: x already moved!

// CORRECT - Clone when reusing
let x = cols.value.clone();
eval.add_constraint(x.clone() * something);
eval.add_constraint(x.clone() * other);
```

### FORBIDDEN: Missing Empty Trace Check

```rust
// FORBIDDEN - Will panic on empty trace
pub fn gen_interaction_trace(trace: &[...]) -> (..., QM31) {
    let cols = ComponentColumns::from_iter(trace.iter()...);  // PANIC!
    ...
}

// CORRECT - Guard against empty trace
pub fn gen_interaction_trace(trace: &[...]) -> (..., QM31) {
    if trace.is_empty() {
        return (vec![], QM31::zero());
    }
    let cols = ComponentColumns::from_iter(trace.iter()...);
    ...
}
```

### FORBIDDEN: Multiplicity Sign Mismatch

```rust
// FORBIDDEN - Different signs between AIR and witness
// In air.rs:
add_to_relation!(eval, self.relations.bitwise, -enabler.clone(), ...);

// In witness.rs register_multiplicities:
let pos_enabler = vec![...];  // Should be neg_enabler!
counters.bitwise.register_many(&pos_enabler, ...);

// CORRECT - Same numerator sign in both places
// In air.rs:
add_to_relation!(eval, self.relations.bitwise, -enabler.clone(), ...);

// In witness.rs:
let neg_enabler: Vec<PackedM31> = (0..simd_size).map(|i| -cols.enabler[i]).collect();
counters.bitwise.register_many(&neg_enabler, ...);
```

### FORBIDDEN: Missing finalize_logup_in_pairs()

```rust
// FORBIDDEN - Missing finalization
fn evaluate<E: EvalAtRow>(&self, mut eval: E) -> E {
    add_to_relation!(eval, self.relations.table1, ...);
    add_to_relation!(eval, self.relations.table2, ...);
    eval  // Missing finalize_logup_in_pairs()!
}

// CORRECT - Always finalize at end
fn evaluate<E: EvalAtRow>(&self, mut eval: E) -> E {
    add_to_relation!(eval, self.relations.table1, ...);
    add_to_relation!(eval, self.relations.table2, ...);
    eval.finalize_logup_in_pairs();
    eval
}
```

### FORBIDDEN: Incomplete Carry Chain

```rust
// FORBIDDEN - Only first limb carry
let carry = (rs1[0] + rs2[0] - rd[0]) * inv_shift;
eval.add_constraint(flag * carry * (one - carry));
// Other limbs not verified!

// CORRECT - Full carry chain
let mut carry: [E::F; 4] = std::array::from_fn(|_| E::F::zero());
carry[0] = (rs1[0].clone() + rs2[0].clone() - rd[0].clone()) * inv_shift.clone();
for i in 1..4 {
    carry[i] = (rs1[i].clone() + rs2[i].clone() + carry[i-1].clone() - rd[i].clone()) * inv_shift.clone();
}
for c in carry {
    eval.add_constraint(flag.clone() * c.clone() * (E::F::one() - c));
}
```

---

## Reference Index

- `references/component-lifecycle.md` - Full component development workflow
- `references/logup-protocol.md` - LogUp lookup argument details
- `references/constraint-patterns.md` - Common constraint idioms
- `references/debugging.md` - Troubleshooting proof failures
- `references/macros.md` - LogUp macros (combine!, emit_col!, write_pair!, etc.)
- `references/preprocessed-tables.md` - Range checks, bitwise lookups,
  multiplicity tracking

## External Resources

- [Circle STARKs Paper](https://eprint.iacr.org/2024/278) - Mathematical
  foundation
- [Stwo Repository](https://github.com/starkware-libs/stwo) - Core prover
  implementation
- [LogUp Protocol](https://eprint.iacr.org/2022/1530) - Lookup argument theory
